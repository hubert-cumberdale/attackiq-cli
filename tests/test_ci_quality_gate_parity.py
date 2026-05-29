from __future__ import annotations

import importlib.util
import shlex
import sys
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
_QUALITY_GATE_PATH = ROOT / "scripts" / "quality_gate.py"
_QUALITY_GATE_SPEC = importlib.util.spec_from_file_location("quality_gate", _QUALITY_GATE_PATH)
assert _QUALITY_GATE_SPEC is not None
assert _QUALITY_GATE_SPEC.loader is not None
quality_gate = importlib.util.module_from_spec(_QUALITY_GATE_SPEC)
sys.modules[_QUALITY_GATE_SPEC.name] = quality_gate
_QUALITY_GATE_SPEC.loader.exec_module(quality_gate)


def _ci_run_commands(job_name: str = "test") -> list[str]:
    workflow = cast(
        dict[str, Any],
        yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")),
    )
    jobs = cast(dict[str, Any], workflow["jobs"])
    job = cast(dict[str, Any], jobs[job_name])
    steps = cast(list[dict[str, Any]], job["steps"])
    commands: list[str] = []
    for step in steps:
        run = step.get("run")
        if isinstance(run, str):
            commands.append(run.strip())
    return commands


def _normalize_python(tokens: list[str]) -> tuple[str, ...]:
    if tokens and Path(tokens[0]).name in {"python", "python3"}:
        tokens[0] = "python"
    return tuple(tokens)


def _quality_gate_script_commands() -> set[tuple[str, ...]]:
    commands = set()
    for command in quality_gate.build_commands(include_mkdocs=False):
        if len(command.argv) > 1 and command.argv[1].startswith("scripts/"):
            commands.add(_normalize_python(list(command.argv)))
    return commands


def _ci_single_line_commands() -> set[tuple[str, ...]]:
    commands = set()
    for command in _ci_run_commands():
        if "\n" not in command:
            commands.add(_normalize_python(shlex.split(command)))
    return commands


def _quality_gate_ruff_targets() -> set[str]:
    command = next(command for command in quality_gate.build_commands() if command.name == "ruff")
    check_index = command.argv.index("check")
    return set(command.argv[check_index + 1 :])


def _ci_ruff_targets() -> set[str]:
    command = next(command for command in _ci_run_commands() if "ruff check" in command)
    tokens = shlex.split(command)
    check_index = tokens.index("check")
    return set(tokens[check_index + 1 :])


def test_ci_runs_quality_gate_script_checks() -> None:
    assert _quality_gate_script_commands() <= _ci_single_line_commands()


def test_ci_ruff_targets_match_quality_gate() -> None:
    assert _ci_ruff_targets() == _quality_gate_ruff_targets()
