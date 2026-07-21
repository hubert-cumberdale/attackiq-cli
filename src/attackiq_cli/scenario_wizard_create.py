from __future__ import annotations

import contextlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from attackiq_cli.scenario_wizard_process import (
    run_subprocess_action as default_run_subprocess_action,
)
from attackiq_cli.scenario_wizard_process import (
    venv_subprocess_env as default_venv_subprocess_env,
)
from attackiq_cli.scenario_wizard_validation import (
    ScenarioWizardError,
    _directory_files,
    _load_json_object,
    _scenario_config_summary,
    _string_value,
    _venv_python_path,
    validate_runtime_bundle,
)

CREATE_SCENARIO_SNIPPET = r"""
import json
import os
import pathlib
import sys

if len(sys.argv) != 2:
    print("Usage: python -c <scenario_wizard_create> <configuration_file>", file=sys.stderr)
    raise SystemExit(2)

config_path = pathlib.Path(sys.argv[1])
output_root = pathlib.Path(os.environ["AIQ_SCENARIO_WIZARD_OUTPUT_DIR"])
with config_path.open("r", encoding="utf-8") as handle:
    configuration = json.load(handle)

from scenario_wizard.impl import make_scenario, scenario_params


def _get_scenario_dir_input(self):
    return str(output_root)


scenario_params.ScenarioParamsClass._GetScenarioDirInput = _get_scenario_dir_input
if hasattr(make_scenario, "ScenarioParamsClass"):
    make_scenario.ScenarioParamsClass._GetScenarioDirInput = _get_scenario_dir_input

raise SystemExit(0 if make_scenario.ScenarioTemplateClass(configuration).Run() else 1)
"""

SubprocessRunner = Callable[..., dict[str, Any]]
VenvEnvBuilder = Callable[..., dict[str, str]]

__all__ = [
    "CREATE_SCENARIO_SNIPPET",
    "apply_scenario_wizard_create",
    "build_scenario_wizard_create_plan",
]


def build_scenario_wizard_create_plan(
    config_path: Path,
    output_dir: Path,
    runtime_bundle: Path,
    *,
    expected_wizard_version: str | None = None,
    force: bool = False,
    python_executable: str = "python3.12",
) -> dict[str, Any]:
    config_summary, config_errors = _scenario_config_summary(config_path)
    output_root = output_dir.expanduser()
    scenario_slug = _string_value(config_summary.get("scenario_slug")) or "scenario"
    scenario_path = output_root / scenario_slug
    runtime_validation = validate_runtime_bundle(
        runtime_bundle,
        expected_wizard_version=expected_wizard_version,
    )

    errors = list(config_errors)
    warnings: list[str] = []
    if not runtime_validation["valid"]:
        errors.append("Runtime bundle is not valid for local Scenario Wizard create.")
    if scenario_path.exists() and not force:
        errors.append(f"Generated scenario path already exists: {scenario_path}")
    if force:
        warnings.append("Force mode would allow overwriting an existing generated scenario path.")

    venv_path = output_root / ".aiq-scenario-wizard-venv"
    venv_python = _venv_python_path(venv_path)
    runtime_dir = runtime_bundle.expanduser() / "runtime"
    wheelhouse_dir = runtime_bundle.expanduser() / "wheelhouse"
    requirements_lock = runtime_bundle.expanduser() / "python" / "requirements.lock"
    site_packages_dir = runtime_bundle.expanduser() / "python" / "site-packages"
    dependency_action: dict[str, Any]
    if site_packages_dir.is_dir():
        dependency_action = {
            "name": "use_runtime_site_packages",
            "path": str(site_packages_dir),
        }
    else:
        dependency_action = {
            "name": "install_runtime_dependencies",
            "argv": [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse_dir),
                "-r",
                str(requirements_lock),
            ],
        }
    return {
        "command": "scenario-wizard create",
        "dry_run": True,
        "ready": not errors,
        "errors": errors,
        "warnings": warnings,
        "configuration": config_summary,
        "output": {
            "directory": str(output_root),
            "expected_scenario_path": str(scenario_path),
            "expected_scenario_path_exists": scenario_path.exists(),
            "force": force,
        },
        "runtime_bundle": runtime_validation,
        "planned_actions": [
            {
                "name": "validate_configuration",
                "path": str(config_path.expanduser()),
            },
            {
                "name": "validate_runtime_bundle",
                "path": str(runtime_bundle.expanduser()),
            },
            {
                "name": "create_output_directory",
                "path": str(output_root),
            },
            {
                "name": "create_virtualenv",
                "argv": [python_executable, "-m", "venv", str(venv_path)],
            },
            {
                "name": "use_runtime_python_directory",
                "runtime_path": str(runtime_dir),
                "site_packages_path": (
                    str(site_packages_dir) if site_packages_dir.is_dir() else None
                ),
            },
            dependency_action,
            {
                "name": "run_scenario_wizard",
                "cwd": str(output_root),
                "argv": [
                    str(venv_python),
                    "-c",
                    "<scenario_wizard_create>",
                    "<scenario_configuration_file>",
                ],
                "argument_source": str(config_path.expanduser()),
            },
        ],
    }


def apply_scenario_wizard_create(
    config_path: Path,
    output_dir: Path,
    runtime_bundle: Path,
    *,
    expected_wizard_version: str | None = None,
    force: bool = False,
    python_executable: str = "python3.12",
    timeout_seconds: float = 300.0,
    run_subprocess_action: SubprocessRunner = default_run_subprocess_action,
    venv_subprocess_env: VenvEnvBuilder = default_venv_subprocess_env,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ScenarioWizardError("Scenario Wizard create timeout must be greater than zero.")
    plan = build_scenario_wizard_create_plan(
        config_path,
        output_dir,
        runtime_bundle,
        expected_wizard_version=expected_wizard_version,
        force=force,
        python_executable=python_executable,
    )
    if not plan["ready"]:
        raise ScenarioWizardError("; ".join(plan["errors"]))

    config_data = _load_json_object(config_path, label="Scenario configuration")
    config_json = json.dumps(config_data, sort_keys=True)
    output_root = output_dir.expanduser()
    output_root.mkdir(parents=True, exist_ok=True)
    create_home_dir = output_root / ".aiq-scenario-wizard-home"
    config_transport_path = _write_restrictive_temp_text(create_home_dir, config_json)

    venv_path = output_root / ".aiq-scenario-wizard-venv"
    venv_python = _venv_python_path(venv_path)
    runtime_root = runtime_bundle.expanduser()
    runtime_dir = runtime_root / "runtime"
    wheelhouse_dir = runtime_root / "wheelhouse"
    requirements_lock = runtime_root / "python" / "requirements.lock"
    site_packages_dir = runtime_root / "python" / "site-packages"
    command_specs: list[dict[str, Any]] = [
        {
            "name": "create_virtualenv",
            "argv": [python_executable, "-m", "venv", str(venv_path)],
            "cwd": str(output_root),
        }
    ]
    if not site_packages_dir.is_dir():
        command_specs.append(
            {
                "name": "install_runtime_dependencies",
                "argv": [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--find-links",
                    str(wheelhouse_dir),
                    "-r",
                    str(requirements_lock),
                ],
                "cwd": str(output_root),
            }
        )
    command_specs.append(
        {
            "name": "run_scenario_wizard",
            "argv": [str(venv_python), "-c", CREATE_SCENARIO_SNIPPET, str(config_transport_path)],
            "display_argv": [
                str(venv_python),
                "-c",
                "<scenario_wizard_create>",
                "<scenario_configuration_file>",
            ],
            "cwd": str(output_root),
        }
    )

    action_results: list[dict[str, Any]] = []
    env = venv_subprocess_env(
        venv_path,
        extra_pythonpath=_create_pythonpath_entries(runtime_dir, site_packages_dir),
        home_dir=create_home_dir,
    )
    env["AIQ_SCENARIO_WIZARD_OUTPUT_DIR"] = str(output_root)
    try:
        for command in command_specs:
            result = run_subprocess_action(
                command["name"],
                command["argv"],
                cwd=Path(command["cwd"]),
                env=env,
                timeout_seconds=timeout_seconds,
                display_argv=command.get("display_argv"),
            )
            action_results.append(result)
            if result["timed_out"] or result["return_code"] != 0:
                break
    finally:
        _unlink_if_exists(config_transport_path)

    errors: list[str] = []
    for result in action_results:
        if result["timed_out"]:
            errors.append(f"{result['name']} timed out after {timeout_seconds:g} seconds.")
        elif result["return_code"] != 0:
            errors.append(f"{result['name']} failed with exit code {result['return_code']}.")

    scenario_path = Path(plan["output"]["expected_scenario_path"])
    wheelhouse_copied = False
    site_packages_marker_written = False
    if not errors and not scenario_path.exists():
        errors.append(f"Expected generated scenario path was not created: {scenario_path}")
    if not errors and (scenario_path / "requirements.txt").is_file():
        scenario_wheelhouse = scenario_path / ".pipdownload"
        if not scenario_wheelhouse.exists():
            shutil.copytree(wheelhouse_dir, scenario_wheelhouse, symlinks=False)
            wheelhouse_copied = True
        if site_packages_dir.is_dir():
            (scenario_path / ".aiq-runtime-site-packages").write_text(
                str(site_packages_dir) + "\n",
                encoding="utf-8",
            )
            site_packages_marker_written = True

    return {
        "command": "scenario-wizard create",
        "dry_run": False,
        "created": not errors,
        "errors": errors,
        "warnings": plan["warnings"],
        "configuration": plan["configuration"],
        "output": {
            **plan["output"],
            "expected_scenario_path_exists": scenario_path.exists(),
            "generated_files": _relative_files(scenario_path) if scenario_path.exists() else [],
            "wheelhouse_copied": wheelhouse_copied,
            "site_packages_marker_written": site_packages_marker_written,
        },
        "runtime_bundle": plan["runtime_bundle"],
        "actions": action_results,
    }


def _create_pythonpath_entries(runtime_dir: Path, site_packages_dir: Path) -> list[Path]:
    entries = [runtime_dir]
    if site_packages_dir.is_dir():
        entries.append(site_packages_dir)
    return entries


def _relative_files(path: Path) -> list[str]:
    if not path.exists() or not path.is_dir():
        return []
    return [file.relative_to(path).as_posix() for file in _directory_files(path)]


def _write_restrictive_temp_text(directory: Path, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(
        prefix="scenario-configuration-",
        suffix=".json",
        dir=directory,
        text=True,
    )
    path = Path(raw_path)
    try:
        os.chmod(path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
    except Exception:
        with contextlib.suppress(OSError):
            os.close(fd)
        _unlink_if_exists(path)
        raise
    return path


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
