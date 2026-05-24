from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_QUALITY_GATE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quality_gate.py"
_QUALITY_GATE_SPEC = importlib.util.spec_from_file_location("quality_gate", _QUALITY_GATE_PATH)
assert _QUALITY_GATE_SPEC is not None
assert _QUALITY_GATE_SPEC.loader is not None
quality_gate = importlib.util.module_from_spec(_QUALITY_GATE_SPEC)
sys.modules[_QUALITY_GATE_SPEC.name] = quality_gate
_QUALITY_GATE_SPEC.loader.exec_module(quality_gate)


def test_quality_gate_build_commands_default():
    commands = quality_gate.build_commands()
    names = [command.name for command in commands]

    assert names == [
        "dependency constraints",
        "release governance",
        "public safety",
        "public mirror dry run",
        "AIQ Assist MCP provider contract",
        "AIQ Assist MCP fixtures",
        "ruff",
        "mypy",
        "pytest",
        "doc links",
        "mkdocs",
    ]
    assert commands[0].argv == [sys.executable, "scripts/check_dependency_constraints.py"]
    assert commands[1].argv == [sys.executable, "scripts/check_release_governance.py"]
    assert commands[2].argv == [sys.executable, "scripts/check_public_safety.py"]
    assert commands[3].argv == [
        sys.executable,
        "scripts/check_public_mirror.py",
        "--allow-dirty",
        "--skip-wheel",
    ]
    assert commands[4].argv == [sys.executable, "scripts/check_aiq_assist_mcp_contract.py"]
    assert commands[5].argv == [sys.executable, "scripts/check_aiq_assist_mcp_fixtures.py"]
    assert commands[6].argv == [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "src",
        "tests",
        "scripts/quality_gate.py",
        "scripts/build_enterprise_package.py",
        "scripts/check_public_mirror.py",
        "scripts/check_public_safety.py",
        "scripts/check_release_governance.py",
        "scripts/check_aiq_assist_mcp_contract.py",
        "scripts/check_aiq_assist_mcp_fixtures.py",
        "scripts/live_smoke.py",
    ]
    assert commands[-1].argv == [sys.executable, "-m", "mkdocs", "build"]


def test_quality_gate_build_commands_can_skip_mkdocs():
    commands = quality_gate.build_commands(include_mkdocs=False)

    assert [command.name for command in commands] == [
        "dependency constraints",
        "release governance",
        "public safety",
        "public mirror dry run",
        "AIQ Assist MCP provider contract",
        "AIQ Assist MCP fixtures",
        "ruff",
        "mypy",
        "pytest",
        "doc links",
    ]


def test_quality_gate_dry_run(capsys):
    result = quality_gate.main(["--dry-run", "--no-mkdocs"])

    assert result == 0
    output = capsys.readouterr().out
    assert "==> ruff:" in output
    assert "quality gate passed" in output
