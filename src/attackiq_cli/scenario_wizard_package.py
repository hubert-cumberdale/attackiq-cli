from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from attackiq_cli.scenario_wizard_process import (
    run_subprocess_action as default_run_subprocess_action,
)
from attackiq_cli.scenario_wizard_process import (
    safe_process_output,
)
from attackiq_cli.scenario_wizard_process import (
    venv_subprocess_env as default_venv_subprocess_env,
)
from attackiq_cli.scenario_wizard_validation import (
    ScenarioWizardError,
    _sha256_file,
    _venv_python_path,
    validate_generated_scenario,
)

COMPRESS_SCENARIO_SNIPPET = (
    "from scenario_packaging.compress_scenario import CompressScenario; "
    "CompressScenario.FILES_TO_IGNORE.append('.aiq-runtime-site-packages'); "
    "raise SystemExit(0 if CompressScenario(None).compress_scenario() else 1)"
)

SubprocessRunner = Callable[..., dict[str, Any]]
VenvEnvBuilder = Callable[..., dict[str, str]]

__all__ = [
    "COMPRESS_SCENARIO_SNIPPET",
    "apply_scenario_wizard_package",
    "build_scenario_wizard_package_plan",
]


def build_scenario_wizard_package_plan(
    scenario_path: Path,
    *,
    force: bool = False,
    python_executable: str = "python3.12",
) -> dict[str, Any]:
    scenario = scenario_path.expanduser()
    validation = validate_generated_scenario(scenario, force=force)
    venv_path = scenario / "venv"
    venv_python = _venv_python_path(venv_path)
    wheelhouse_dir = scenario / ".pipdownload"
    requirements = scenario / "requirements.txt"
    site_packages_dir = _scenario_runtime_site_packages(scenario)
    target_dir = scenario / "target"
    runtime_bin_dir = _scenario_runtime_bin_dir(site_packages_dir) if site_packages_dir else None
    planned_actions: list[dict[str, Any]] = [
        {
            "name": "validate_generated_scenario",
            "path": str(scenario),
        },
    ]
    if not venv_path.exists():
        planned_actions.append(
            {
                "name": "create_virtualenv",
                "argv": [python_executable, "-m", "venv", str(venv_path)],
            }
        )
    else:
        planned_actions.append(
            {
                "name": "reuse_virtualenv",
                "path": str(venv_path),
            }
        )
    if site_packages_dir is not None:
        planned_actions.append(
            {
                "name": "link_runtime_site_packages",
                "path": str(site_packages_dir),
                "bin_dir": str(runtime_bin_dir or ""),
            }
        )
    planned_actions.append(
        {
            "name": "install_package_dependencies",
            "argv": [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse_dir),
                "-r",
                str(requirements),
            ],
        }
    )
    if site_packages_dir is None:
        planned_actions.append(
            {
                "name": "run_package",
                "cwd": str(scenario),
                "argv": ["package", "pdc", "--no-git", "-w", str(wheelhouse_dir)],
            }
        )
    else:
        planned_actions.extend(
            [
                {
                    "name": "create_descriptor_processed",
                    "cwd": str(scenario),
                    "argv": [
                        str(venv_python),
                        "-m",
                        "scenario_packaging.package",
                        "d",
                        "--no-git",
                    ],
                },
                {
                    "name": "copy_scenario_bin_dependencies",
                    "source": str(_venv_site_packages_dir(venv_path) or venv_path),
                    "destination": str(scenario / "bin"),
                },
                {
                    "name": "compress_scenario",
                    "cwd": str(scenario),
                    "argv": [str(venv_python), "-c", "<compress_scenario>"],
                },
            ]
        )
    planned_actions.append(
        {
            "name": "collect_target_packages",
            "path": str(target_dir),
        }
    )
    return {
        "command": "scenario-wizard package",
        "dry_run": True,
        "ready": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "scenario": validation,
        "planned_actions": planned_actions,
    }


def apply_scenario_wizard_package(
    scenario_path: Path,
    *,
    force: bool = False,
    python_executable: str = "python3.12",
    timeout_seconds: float = 300.0,
    run_subprocess_action: SubprocessRunner = default_run_subprocess_action,
    venv_subprocess_env: VenvEnvBuilder = default_venv_subprocess_env,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ScenarioWizardError("Scenario Wizard package timeout must be greater than zero.")
    plan = build_scenario_wizard_package_plan(
        scenario_path,
        force=force,
        python_executable=python_executable,
    )
    if not plan["ready"]:
        raise ScenarioWizardError("; ".join(plan["errors"]))

    scenario = scenario_path.expanduser()
    venv_path = scenario / "venv"
    venv_python = _venv_python_path(venv_path)
    wheelhouse_dir = scenario / ".pipdownload"
    requirements = scenario / "requirements.txt"
    site_packages_dir = _scenario_runtime_site_packages(scenario)
    runtime_bin_dir = _scenario_runtime_bin_dir(site_packages_dir) if site_packages_dir else None
    target_dir = scenario / "target"
    command_specs: list[dict[str, Any]] = []
    if not venv_path.exists():
        command_specs.append(
            {
                "name": "create_virtualenv",
                "argv": [python_executable, "-m", "venv", str(venv_path)],
                "cwd": str(scenario),
            }
        )
    if site_packages_dir is not None:
        command_specs.append(
            {
                "name": "link_runtime_site_packages",
                "runtime_site_packages": str(site_packages_dir),
                "cwd": str(scenario),
            }
        )
    env = venv_subprocess_env(
        venv_path,
        prepend_path=runtime_bin_dir,
        home_dir=scenario.parent / f".{scenario.name}-aiq-scenario-wizard-package-home",
        use_setuptools_distutils=site_packages_dir is not None,
    )
    command_specs.append(
        {
            "name": "install_package_dependencies",
            "argv": [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse_dir),
                "-r",
                str(requirements),
            ],
            "cwd": str(scenario),
        }
    )
    if site_packages_dir is None:
        package_argv = ["package", "pdc", "--no-git", "-w", str(wheelhouse_dir)]
        command_specs.append(
            {
                "name": "run_package",
                "argv": package_argv,
                "cwd": str(scenario),
            },
        )
    else:
        command_specs.extend(
            [
                {
                    "name": "create_descriptor_processed",
                    "argv": [
                        str(venv_python),
                        "-m",
                        "scenario_packaging.package",
                        "d",
                        "--no-git",
                    ],
                    "cwd": str(scenario),
                },
                {
                    "name": "copy_scenario_bin_dependencies",
                    "cwd": str(scenario),
                },
                {
                    "name": "compress_scenario",
                    "argv": [str(venv_python), "-c", COMPRESS_SCENARIO_SNIPPET],
                    "display_argv": [str(venv_python), "-c", "<compress_scenario>"],
                    "cwd": str(scenario),
                },
            ]
        )

    action_results: list[dict[str, Any]] = []
    for command in command_specs:
        if command["name"] == "link_runtime_site_packages":
            result = _link_runtime_site_packages_action(
                venv_path,
                Path(command["runtime_site_packages"]),
                cwd=Path(command["cwd"]),
            )
            action_results.append(result)
            if result["return_code"] != 0:
                break
            continue
        if command["name"] == "copy_scenario_bin_dependencies":
            result = _copy_scenario_bin_dependencies_action(
                venv_path,
                scenario,
                cwd=Path(command["cwd"]),
            )
            action_results.append(result)
            if result["return_code"] != 0:
                break
            continue
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

    errors: list[str] = []
    for result in action_results:
        if result["timed_out"]:
            errors.append(f"{result['name']} timed out after {timeout_seconds:g} seconds.")
        elif result["return_code"] != 0:
            errors.append(f"{result['name']} failed with exit code {result['return_code']}.")

    package_files = _package_file_entries(target_dir)
    if not errors and not package_files:
        errors.append(f"No package zip files were produced under: {target_dir}")

    return {
        "command": "scenario-wizard package",
        "dry_run": False,
        "packaged": not errors,
        "errors": errors,
        "warnings": plan["warnings"],
        "scenario": validate_generated_scenario(scenario, force=True),
        "actions": action_results,
        "packages": package_files,
    }


def _scenario_runtime_site_packages(scenario: Path) -> Path | None:
    marker = scenario / ".aiq-runtime-site-packages"
    if not marker.is_file():
        return None
    try:
        path = Path(marker.read_text(encoding="utf-8").strip()).expanduser()
    except OSError:
        return None
    return path if path.is_dir() else None


def _scenario_runtime_bin_dir(site_packages_dir: Path) -> Path | None:
    bin_dir = site_packages_dir.parent / "bin"
    return bin_dir if bin_dir.is_dir() else None


def _venv_site_packages_dir(venv_path: Path) -> Path | None:
    if os.name == "nt":
        candidate = venv_path / "Lib" / "site-packages"
        return candidate if candidate.is_dir() else None
    for candidate in sorted((venv_path / "lib").glob("python*/site-packages")):
        if candidate.is_dir():
            return candidate
    return None


def _link_runtime_site_packages_action(
    venv_path: Path,
    site_packages_dir: Path,
    *,
    cwd: Path,
) -> dict[str, Any]:
    venv_site_packages = _venv_site_packages_dir(venv_path)
    if venv_site_packages is None:
        return {
            "name": "link_runtime_site_packages",
            "argv": [],
            "cwd": str(cwd),
            "return_code": 1,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": f"Virtualenv site-packages directory not found: {venv_path}",
        }
    pth_file = venv_site_packages / "attackiq_scenario_wizard_runtime.pth"
    try:
        pth_file.write_text(
            f"import site; site.addsitedir({str(site_packages_dir)!r})\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return {
            "name": "link_runtime_site_packages",
            "argv": [],
            "cwd": str(cwd),
            "return_code": 1,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": safe_process_output(str(exc)),
        }
    return {
        "name": "link_runtime_site_packages",
        "argv": [],
        "cwd": str(cwd),
        "return_code": 0,
        "timed_out": False,
        "stdout_tail": str(pth_file),
        "stderr_tail": "",
    }


def _copy_scenario_bin_dependencies_action(
    venv_path: Path,
    scenario_path: Path,
    *,
    cwd: Path,
) -> dict[str, Any]:
    source = _venv_site_packages_dir(venv_path)
    if source is None:
        return {
            "name": "copy_scenario_bin_dependencies",
            "argv": [],
            "cwd": str(cwd),
            "return_code": 1,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": f"Virtualenv site-packages directory not found: {venv_path}",
        }
    destination = scenario_path / "bin"
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    try:
        for item in source.iterdir():
            if _skip_venv_site_package_copy(item.name):
                continue
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True, symlinks=False)
            elif item.is_file() and not item.is_symlink():
                shutil.copy2(item, target)
            copied += 1
    except OSError as exc:
        return {
            "name": "copy_scenario_bin_dependencies",
            "argv": [],
            "cwd": str(cwd),
            "return_code": 1,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": safe_process_output(str(exc)),
        }
    return {
        "name": "copy_scenario_bin_dependencies",
        "argv": [],
        "cwd": str(cwd),
        "return_code": 0,
        "timed_out": False,
        "stdout_tail": f"Copied {copied} venv site-package entries to {destination}",
        "stderr_tail": "",
    }


def _skip_venv_site_package_copy(name: str) -> bool:
    normalized = name.lower()
    if normalized in {
        "__pycache__",
        "_distutils_hack",
        "attackiq_scenario_wizard_runtime.pth",
        "distutils-precedence.pth",
        "pip",
        "pkg_resources",
        "setuptools",
        "wheel",
    }:
        return True
    return normalized.startswith(("pip-", "setuptools-", "wheel-"))


def _package_file_entries(target_dir: Path) -> list[dict[str, Any]]:
    if not target_dir.exists() or not target_dir.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(target_dir.glob("*.zip")):
        if not path.is_file():
            continue
        entries.append(
            {
                "path": str(path),
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return entries
