from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from typing import Any

from attackiq_cli.scenario_wizard_package import (
    apply_scenario_wizard_package,
    build_scenario_wizard_package_plan,
)


def _write_generated_scenario(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".pipdownload").mkdir()
    (path / "requirements.txt").write_text("", encoding="utf-8")
    (path / "descriptor.json").write_text("{}", encoding="utf-8")
    (path / "setup.cfg").write_text("[metadata]\nname = fixture\n", encoding="utf-8")
    (path / "main.py").write_text("print('fixture')\n", encoding="utf-8")
    (path / "version.txt").write_text("1.0.0\n", encoding="utf-8")
    return path


def test_build_scenario_wizard_package_plan_ready(tmp_path: Path) -> None:
    scenario = _write_generated_scenario(tmp_path / "scenario")

    payload = build_scenario_wizard_package_plan(scenario, python_executable=sys.executable)

    assert payload["ready"] is True
    assert payload["scenario"]["requirements_exists"] is True
    assert [action["name"] for action in payload["planned_actions"]] == [
        "validate_generated_scenario",
        "create_virtualenv",
        "install_package_dependencies",
        "run_package",
        "collect_target_packages",
    ]


def test_apply_scenario_wizard_package_uses_injected_subprocess_runner(tmp_path: Path) -> None:
    scenario = _write_generated_scenario(tmp_path / "scenario")
    calls: list[str] = []

    def _fake_run_subprocess_action(
        name: str,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: float,
        display_argv: list[str] | None = None,
    ) -> dict[str, Any]:
        del argv, env, timeout_seconds, display_argv
        calls.append(name)
        if name == "run_package":
            target = cwd / "target"
            target.mkdir(exist_ok=True)
            with zipfile.ZipFile(target / "folder-1.0.0.zip", "w") as archive:
                archive.writestr("descriptor.json", "{}")
        return {
            "name": name,
            "argv": [name],
            "cwd": str(cwd),
            "return_code": 0,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    payload = apply_scenario_wizard_package(
        scenario,
        python_executable=sys.executable,
        timeout_seconds=30.0,
        run_subprocess_action=_fake_run_subprocess_action,
    )

    assert payload["packaged"] is True
    assert calls == ["create_virtualenv", "install_package_dependencies", "run_package"]
    assert payload["packages"][0]["filename"] == "folder-1.0.0.zip"
