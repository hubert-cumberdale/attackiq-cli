from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from attackiq_cli.scenario_wizard_validation import (
    SENSITIVE_FILENAMES,
    _contains_credentialed_url,
    _directory_files,
    _is_python_312,
    _load_json_object,
    _scenario_config_summary,
    _sha256_directory,
    _sha256_file,
    _string_value,
    _venv_python_path,
)
from attackiq_cli.scenario_wizard_validation import (
    ScenarioWizardError as ScenarioWizardError,
)
from attackiq_cli.scenario_wizard_validation import (
    validate_generated_scenario as validate_generated_scenario,
)
from attackiq_cli.scenario_wizard_validation import (
    validate_runtime_bundle as validate_runtime_bundle,
)

ENV_SCENARIO_WIZARD_CACHE_DIR = "ATTACKIQ_SCENARIO_WIZARD_CACHE_DIR"
PROCESS_OUTPUT_LIMIT = 4000
MAX_IMAGE_LAYER_BYTES = 512 * 1024 * 1024
IMAGE_LAYER_SPOOL_MEMORY_BYTES = 16 * 1024 * 1024
IMAGE_LAYER_READ_CHUNK_BYTES = 1024 * 1024
RUNTIME_SCRIPT_NAMES = {
    "check_versions.sh",
    "create_docker_venv.sh",
    "run_scenario.sh",
    "scenario_wizard.sh",
    "setup_scenario.sh",
    "test_scenario.sh",
}
RUNTIME_BIN_SCRIPT_NAMES = {
    "fullrelease",
    "package",
    "postrelease",
    "prerelease",
    "release",
    "setup_scenario_bin",
}
COMPRESS_SCENARIO_SNIPPET = (
    "from scenario_packaging.compress_scenario import CompressScenario; "
    "CompressScenario.FILES_TO_IGNORE.append('.aiq-runtime-site-packages'); "
    "raise SystemExit(0 if CompressScenario(None).compress_scenario() else 1)"
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
RUNTIME_SENTINELS = {
    "scenario_wizard.sh",
    "create_docker_venv.sh",
    "setup_scenario.sh",
    "templates/",
}
SUBPROCESS_ENV_ALLOWLIST = (
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
)


def scenario_wizard_cache_dir() -> Path:
    override = os.getenv(ENV_SCENARIO_WIZARD_CACHE_DIR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "attackiq-cli" / "scenario-wizard"


def inspect_scenario_wizard_zip(zip_path: Path, *, cache_dir: Path | None = None) -> dict[str, Any]:
    path = zip_path.expanduser()
    if not path.exists():
        raise ScenarioWizardError(f"Scenario Wizard zip not found: {path}")
    if not path.is_file():
        raise ScenarioWizardError(f"Scenario Wizard zip path must be a file: {path}")
    try:
        with ZipFile(path) as archive:
            names = sorted(archive.namelist())
            version = _read_version(archive)
            file_entries = [_file_entry(archive, name) for name in names]
    except BadZipFile as exc:
        raise ScenarioWizardError(f"Scenario Wizard zip is not a valid zip file: {path}") from exc

    wrapper_version = _string_value(version.get("self"))
    bundle_root = (cache_dir or scenario_wizard_cache_dir()).expanduser()
    expected_bundle = bundle_root / wrapper_version if wrapper_version else bundle_root / "unknown"
    runtime_bundle = inspect_runtime_bundle(expected_bundle)
    contains_local_runtime = _contains_local_runtime(names)

    return {
        "zip_path": str(path),
        "zip_sha256": _sha256_file(path),
        "wrapper_version": wrapper_version or None,
        "minimal_docker_image_version": _string_value(version.get("minimal_docker_image_version"))
        or None,
        "file_count": len(names),
        "files": file_entries,
        "sensitive_files_present": [
            entry["name"] for entry in file_entries if entry.get("sensitive") is True
        ],
        "contains_local_runtime": contains_local_runtime,
        "wrapper_only": not contains_local_runtime,
        "expected_bundle_path": str(expected_bundle),
        "runtime_bundle": runtime_bundle,
    }


def inspect_runtime_bundle(path: Path) -> dict[str, Any]:
    validation = validate_runtime_bundle(path)
    manifest_path = path / "manifest.json"
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "manifest_valid": validation["valid"],
        "runtime_entrypoint_exists": (path / "runtime" / "scenario_wizard.sh").exists(),
        "validation": {
            "valid": validation["valid"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        },
    }
    if "manifest" in validation:
        result["manifest"] = validation["manifest"]
    return result


def build_runtime_prepare_plan(
    source_bundle: Path,
    *,
    cache_dir: Path | None = None,
    wizard_version: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    source = source_bundle.expanduser()
    source_validation = validate_runtime_bundle(source, expected_wizard_version=wizard_version)
    manifest = source_validation.get("manifest")
    manifest_version = (
        _string_value(manifest.get("wizard_version")) if isinstance(manifest, dict) else ""
    )
    target_version = _string_value(wizard_version) or manifest_version
    cache_root = (cache_dir or scenario_wizard_cache_dir()).expanduser()
    destination = cache_root / target_version if target_version else cache_root / "unknown"

    errors: list[str] = []
    warnings: list[str] = []
    if not source_validation["valid"]:
        errors.append("Source runtime bundle is not valid.")
    if not target_version:
        errors.append("Scenario Wizard version could not be determined for destination path.")
    if destination.exists() and not force:
        errors.append(f"Destination runtime bundle already exists: {destination}")
    overlap_error = _path_overlap_error(source, destination)
    if overlap_error:
        errors.append(overlap_error)
    if force:
        warnings.append("Force mode would replace an existing destination runtime bundle.")

    return {
        "command": "scenario-wizard runtime prepare",
        "dry_run": True,
        "ready": not errors,
        "errors": errors,
        "warnings": warnings,
        "source": {
            "type": "bundle",
            "path": str(source),
            "validation": source_validation,
        },
        "cache_dir": str(cache_root),
        "destination": {
            "path": str(destination),
            "exists": destination.exists(),
            "force": force,
            "wizard_version": target_version or None,
        },
        "planned_actions": [
            {
                "name": "validate_source_bundle",
                "path": str(source),
            },
            {
                "name": "create_cache_directory",
                "path": str(cache_root),
            },
            {
                "name": "copy_runtime_bundle",
                "source": str(source),
                "destination": str(destination),
                "replace_existing": force,
            },
            {
                "name": "validate_destination_bundle",
                "path": str(destination),
            },
        ],
    }


def prepare_runtime_bundle_from_bundle(
    source_bundle: Path,
    *,
    cache_dir: Path | None = None,
    wizard_version: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    plan = build_runtime_prepare_plan(
        source_bundle,
        cache_dir=cache_dir,
        wizard_version=wizard_version,
        force=force,
    )
    if not plan["ready"]:
        raise ScenarioWizardError("; ".join(plan["errors"]))

    source = Path(plan["source"]["path"])
    destination = Path(plan["destination"]["path"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    shutil.copytree(source, destination, symlinks=False)
    validation = validate_runtime_bundle(destination, expected_wizard_version=wizard_version)
    return {
        "command": "scenario-wizard runtime prepare",
        "dry_run": False,
        "prepared": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "source": plan["source"],
        "destination": {
            **plan["destination"],
            "exists": destination.exists(),
            "validation": validation,
        },
    }


def build_runtime_prepare_from_image_tar_plan(
    image_tar: Path,
    *,
    cache_dir: Path | None = None,
    wizard_version: str | None = None,
    force: bool = False,
    runtime_root: str | None = None,
    wheelhouse_path: str | None = None,
    requirements_path: str | None = None,
    python_version: str = "3.12",
) -> dict[str, Any]:
    source = image_tar.expanduser()
    inspection = inspect_image_tar_runtime(
        source,
        runtime_root=runtime_root,
        wheelhouse_path=wheelhouse_path,
        requirements_path=requirements_path,
    )
    target_version = _string_value(wizard_version) or _string_value(
        inspection.get("wizard_version")
    )
    cache_root = (cache_dir or scenario_wizard_cache_dir()).expanduser()
    destination = cache_root / target_version if target_version else cache_root / "unknown"

    errors = list(inspection["errors"])
    warnings = list(inspection["warnings"])
    if not target_version:
        errors.append("Scenario Wizard version could not be determined for destination path.")
    if not _is_python_312(python_version):
        errors.append("Runtime bundle python_version must target Python 3.12.")
    if destination.exists() and not force:
        errors.append(f"Destination runtime bundle already exists: {destination}")
    overlap_error = _path_overlap_error(source, destination)
    if overlap_error:
        errors.append(overlap_error)
    if force:
        warnings.append("Force mode would replace an existing destination runtime bundle.")

    return {
        "command": "scenario-wizard runtime prepare",
        "dry_run": True,
        "ready": not errors,
        "errors": errors,
        "warnings": warnings,
        "source": {
            "type": "image_tar",
            "path": str(source),
            "inspection": inspection,
        },
        "cache_dir": str(cache_root),
        "destination": {
            "path": str(destination),
            "exists": destination.exists(),
            "force": force,
            "wizard_version": target_version or None,
            "python_version": python_version,
        },
        "planned_actions": [
            {
                "name": "inspect_image_tar",
                "path": str(source),
            },
            {
                "name": "create_cache_directory",
                "path": str(cache_root),
            },
            {
                "name": "extract_selected_runtime_files",
                "runtime_root": inspection.get("runtime_root"),
                "wheelhouse_path": inspection.get("wheelhouse_path"),
                "requirements_path": inspection.get("requirements_path"),
                "destination": str(destination),
                "replace_existing": force,
            },
            {
                "name": "validate_destination_bundle",
                "path": str(destination),
            },
        ],
    }


def prepare_runtime_bundle_from_image_tar(
    image_tar: Path,
    *,
    cache_dir: Path | None = None,
    wizard_version: str | None = None,
    force: bool = False,
    runtime_root: str | None = None,
    wheelhouse_path: str | None = None,
    requirements_path: str | None = None,
    python_version: str = "3.12",
) -> dict[str, Any]:
    plan = build_runtime_prepare_from_image_tar_plan(
        image_tar,
        cache_dir=cache_dir,
        wizard_version=wizard_version,
        force=force,
        runtime_root=runtime_root,
        wheelhouse_path=wheelhouse_path,
        requirements_path=requirements_path,
        python_version=python_version,
    )
    if not plan["ready"]:
        raise ScenarioWizardError("; ".join(plan["errors"]))

    destination = Path(plan["destination"]["path"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-",
        dir=destination.parent,
    ) as tmp_dir:
        staging = Path(tmp_dir) / "bundle"
        _materialize_runtime_bundle_from_image_tar(
            Path(plan["source"]["path"]),
            staging,
            inspection=plan["source"]["inspection"],
            wizard_version=str(plan["destination"]["wizard_version"]),
            python_version=python_version,
        )
        validation = validate_runtime_bundle(
            staging,
            expected_wizard_version=str(plan["destination"]["wizard_version"]),
        )
        if not validation["valid"]:
            raise ScenarioWizardError("; ".join(validation["errors"]))
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        shutil.move(str(staging), destination)

    validation = validate_runtime_bundle(
        destination,
        expected_wizard_version=str(plan["destination"]["wizard_version"]),
    )
    return {
        "command": "scenario-wizard runtime prepare",
        "dry_run": False,
        "prepared": validation["valid"],
        "errors": validation["errors"],
        "warnings": plan["warnings"] + validation["warnings"],
        "source": plan["source"],
        "destination": {
            **plan["destination"],
            "exists": destination.exists(),
            "validation": validation,
        },
    }


def inspect_image_tar_runtime(
    image_tar: Path,
    *,
    runtime_root: str | None = None,
    wheelhouse_path: str | None = None,
    requirements_path: str | None = None,
) -> dict[str, Any]:
    source = image_tar.expanduser()
    errors: list[str] = []
    warnings: list[str] = []
    if not source.exists():
        return _image_tar_inspection_error(source, f"Image tar not found: {source}")
    if not source.is_file():
        return _image_tar_inspection_error(source, f"Image tar path must be a file: {source}")
    try:
        index = _image_tar_index(source)
    except (ScenarioWizardError, tarfile.TarError, OSError) as exc:
        return _image_tar_inspection_error(source, f"Image tar could not be read: {exc}")

    try:
        normalized_runtime_root = _normalize_tar_path(runtime_root) if runtime_root else ""
    except ScenarioWizardError as exc:
        errors.append(str(exc))
        normalized_runtime_root = ""
    if normalized_runtime_root:
        runtime_entrypoint = f"{normalized_runtime_root}/scenario_wizard.sh"
        if runtime_entrypoint not in index["files"]:
            errors.append(f"Runtime entrypoint not found in image tar: {runtime_entrypoint}")
    else:
        runtime_entrypoint = _detect_runtime_entrypoint(index)
        if runtime_entrypoint:
            normalized_runtime_root = str(Path(runtime_entrypoint).parent).replace(".", "")
            normalized_runtime_root = normalized_runtime_root.strip("/")
        else:
            errors.append("Could not detect scenario_wizard.sh in image tar.")

    templates_dir = _detect_tar_directory(
        index,
        explicit_path=None,
        candidates=[
            f"{normalized_runtime_root}/templates",
            f"{normalized_runtime_root}/scenario_wizard/templates",
        ],
    )
    if not templates_dir:
        errors.append(
            "Runtime templates directory not found in image tar; checked "
            f"{normalized_runtime_root}/templates and "
            f"{normalized_runtime_root}/scenario_wizard/templates."
        )

    detected_wheelhouse = _detect_tar_directory(
        index,
        explicit_path=wheelhouse_path,
        candidates=[
            f"{normalized_runtime_root}/wheelhouse",
            f"{normalized_runtime_root}/.pipdownload",
            f"{normalized_runtime_root}/pipdownload",
            "wheelhouse",
            ".pipdownload",
        ],
    )
    if not detected_wheelhouse:
        errors.append("Could not detect a runtime wheelhouse directory in image tar.")
    wheelhouse_file_count = _count_prefix_files(index["files"], detected_wheelhouse)
    if detected_wheelhouse and wheelhouse_file_count < 1:
        errors.append(f"Runtime wheelhouse contains no files in image tar: {detected_wheelhouse}")

    detected_requirements = _detect_tar_file(
        index,
        explicit_path=requirements_path,
        candidates=[
            f"{normalized_runtime_root}/requirements.lock",
            f"{normalized_runtime_root}/requirements.txt",
            f"{normalized_runtime_root}/python/requirements.lock",
            "requirements.lock",
            "requirements.txt",
        ],
    )
    if not detected_requirements:
        errors.append("Could not detect runtime requirements in image tar.")

    detected_site_packages = _detect_tar_directory(
        index,
        explicit_path=None,
        candidates=[
            f"{normalized_runtime_root}/.venv/lib/python3.12/site-packages",
            "usr/local/lib/python3.12/site-packages",
            "usr/lib/python3.12/site-packages",
        ],
    )

    detected_version = _detect_image_tar_wizard_version(index, source, normalized_runtime_root)
    script_paths = [
        f"{normalized_runtime_root}/{name}".strip("/")
        for name in sorted(RUNTIME_SCRIPT_NAMES)
        if f"{normalized_runtime_root}/{name}".strip("/") in index["files"]
    ]
    bin_script_paths = _detect_bin_script_paths(index, normalized_runtime_root)
    sensitive_files = [
        path for path in sorted(index["files"]) if Path(path).name.lower() in SENSITIVE_FILENAMES
    ]
    if sensitive_files:
        warnings.append(
            "Image tar contains sensitive package configuration files; they are excluded."
        )

    return {
        "path": str(source),
        "exists": True,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "format": index["format"],
        "file_count": len(index["files"]),
        "directory_count": len(index["dirs"]),
        "runtime_root": normalized_runtime_root or None,
        "runtime_entrypoint": runtime_entrypoint or None,
        "templates_dir": templates_dir or None,
        "runtime_script_paths": script_paths,
        "bin_script_paths": bin_script_paths,
        "wheelhouse_path": detected_wheelhouse,
        "wheelhouse_file_count": wheelhouse_file_count,
        "requirements_path": detected_requirements,
        "site_packages_path": detected_site_packages,
        "site_packages_file_count": _count_prefix_files(index["files"], detected_site_packages),
        "wizard_version": detected_version,
        "sha256": _sha256_file(source),
        "sensitive_files_present": sensitive_files,
    }


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
    plan = {
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
    return plan


def apply_scenario_wizard_create(
    config_path: Path,
    output_dir: Path,
    runtime_bundle: Path,
    *,
    expected_wizard_version: str | None = None,
    force: bool = False,
    python_executable: str = "python3.12",
    timeout_seconds: float = 300.0,
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
    env = _venv_subprocess_env(
        venv_path,
        extra_pythonpath=_create_pythonpath_entries(runtime_dir, site_packages_dir),
        home_dir=create_home_dir,
    )
    env["AIQ_SCENARIO_WIZARD_OUTPUT_DIR"] = str(output_root)
    try:
        for command in command_specs:
            result = _run_subprocess_action(
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
            "stderr_tail": _safe_process_output(str(exc)),
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
            "stderr_tail": _safe_process_output(str(exc)),
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
    env = _venv_subprocess_env(
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
        result = _run_subprocess_action(
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


def _image_tar_inspection_error(path: Path, error: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "valid": False,
        "errors": [error],
        "warnings": [],
        "format": None,
        "file_count": 0,
        "directory_count": 0,
        "runtime_root": None,
        "runtime_entrypoint": None,
        "templates_dir": None,
        "runtime_script_paths": [],
        "bin_script_paths": [],
        "wheelhouse_path": None,
        "wheelhouse_file_count": 0,
        "requirements_path": None,
        "site_packages_path": None,
        "site_packages_file_count": 0,
        "wizard_version": None,
        "sha256": _sha256_file(path) if path.exists() and path.is_file() else None,
        "sensitive_files_present": [],
    }


def _select_image_runtime_files(
    files: dict[str, Any],
    *,
    runtime_root: str,
    templates_dir: str,
    wheelhouse_path: str,
) -> list[str]:
    selected: set[str] = set()
    selected.update(_prefix_files(files, templates_dir))
    selected.update(_prefix_files(files, f"{runtime_root}/scenario_wizard"))
    selected.update(_prefix_files(files, f"{runtime_root}/template_test_config"))
    wheelhouse_prefix = wheelhouse_path.rstrip("/") + "/"
    runtime_prefix = runtime_root.rstrip("/") + "/"
    for path in _prefix_files(files, runtime_root):
        if wheelhouse_path and path.startswith(wheelhouse_prefix):
            continue
        relative = path[len(runtime_prefix) :] if path.startswith(runtime_prefix) else path
        if "/" not in relative and Path(relative).suffix in {".py", ".sh", ".txt"}:
            selected.add(path)
    return sorted(selected)


def _materialize_runtime_bundle_from_image_tar(
    image_tar: Path,
    destination: Path,
    *,
    inspection: dict[str, Any],
    wizard_version: str,
    python_version: str,
) -> None:
    index = _image_tar_index(image_tar)
    destination.mkdir(parents=True, exist_ok=True)
    runtime_root = _string_value(inspection.get("runtime_root"))
    templates_dir = _string_value(inspection.get("templates_dir"))
    wheelhouse_path = _string_value(inspection.get("wheelhouse_path"))
    requirements_path = _string_value(inspection.get("requirements_path"))
    site_packages_path = _string_value(inspection.get("site_packages_path"))
    runtime_files = set(inspection.get("runtime_script_paths") or [])
    runtime_files.update(
        _select_image_runtime_files(
            index["files"],
            runtime_root=runtime_root,
            templates_dir=templates_dir,
            wheelhouse_path=wheelhouse_path,
        )
    )
    selected_files: list[tuple[dict[str, str], Path, str]] = []

    for path in sorted(runtime_files):
        if Path(path).name.lower() in SENSITIVE_FILENAMES:
            continue
        relative = _relative_to_tar_root(path, runtime_root)
        selected_files.append((index["files"][path], destination / "runtime", relative))

    for path in sorted(inspection.get("bin_script_paths") or []):
        if path not in index["files"]:
            continue
        selected_files.append(
            (index["files"][path], destination / "python" / "bin", Path(path).name)
        )

    for path in _prefix_files(index["files"], wheelhouse_path):
        if Path(path).name.lower() in SENSITIVE_FILENAMES:
            continue
        relative = _relative_to_tar_root(path, wheelhouse_path)
        selected_files.append((index["files"][path], destination / "wheelhouse", relative))
    if site_packages_path:
        for path in _prefix_files(index["files"], site_packages_path):
            if Path(path).name.lower() in SENSITIVE_FILENAMES:
                continue
            relative = _relative_to_tar_root(path, site_packages_path)
            selected_files.append(
                (index["files"][path], destination / "python" / "site-packages", relative)
            )

    _write_image_tar_files(image_tar, selected_files)
    for script in _directory_files(destination / "python" / "bin"):
        script.chmod(0o755)
    _write_sanitized_image_requirements_lock(
        image_tar,
        index["files"][requirements_path],
        destination / "python" / "requirements.lock",
    )
    manifest = {
        "created_at": _utc_now_iso(),
        "python_version": python_version,
        "runtime_version": f"image-tar:{_sha256_file(image_tar)[:12]}",
        "source_type": "image_tar",
        "wheelhouse_sha256": _sha256_directory(destination / "wheelhouse"),
        "wizard_version": wizard_version,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_image_tar_files(
    image_tar: Path,
    selected_files: list[tuple[dict[str, str], Path, str]],
) -> None:
    layer_groups: dict[str, list[tuple[dict[str, str], Path, str]]] = {}
    with tarfile.open(image_tar) as archive:
        for source, destination_root, relative_path in selected_files:
            if source["type"] == "outer":
                extracted = archive.extractfile(source["member"])
                if extracted is None:
                    raise ScenarioWizardError(f"Could not read tar member: {source['member']}")
                _write_stream_to_destination(destination_root, relative_path, extracted)
                continue
            layer_groups.setdefault(source["layer"], []).append(
                (source, destination_root, relative_path)
            )
        for layer_name, layer_files in layer_groups.items():
            layer_member = _get_tar_member(archive, layer_name)
            with _spooled_image_layer_file(
                archive,
                layer_member,
                label=layer_name,
            ) as layer_file:
                layer_archive = tarfile.open(fileobj=layer_file, mode="r:*")
                with layer_archive:
                    layer_members = {member.name: member for member in layer_archive.getmembers()}
                    for source, destination_root, relative_path in layer_files:
                        member = layer_members.get(source["member"])
                        if member is None:
                            raise ScenarioWizardError(
                                f"Could not find layer member: {source['member']}"
                            )
                        extracted = layer_archive.extractfile(member)
                        if extracted is None:
                            raise ScenarioWizardError(
                                f"Could not read layer member: {source['member']}"
                            )
                        _write_stream_to_destination(
                            destination_root,
                            relative_path,
                            extracted,
                        )


def _write_stream_to_destination(destination_root: Path, relative_path: str, stream: Any) -> None:
    relative = _safe_relative_path(relative_path)
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        shutil.copyfileobj(stream, handle)


def _get_tar_member(archive: tarfile.TarFile, name: str) -> tarfile.TarInfo:
    try:
        return archive.getmember(name)
    except KeyError as exc:
        raise ScenarioWizardError(f"Could not find tar member: {name}") from exc


@contextlib.contextmanager
def _spooled_image_layer_file(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    *,
    label: str,
) -> Any:
    if member.size > MAX_IMAGE_LAYER_BYTES:
        raise ScenarioWizardError(
            f"Image layer {label} is {member.size} bytes, exceeding the "
            f"{MAX_IMAGE_LAYER_BYTES} byte limit."
        )
    extracted = archive.extractfile(member)
    if extracted is None:
        raise ScenarioWizardError(f"Could not read image layer: {label}")
    spool = tempfile.SpooledTemporaryFile(max_size=IMAGE_LAYER_SPOOL_MEMORY_BYTES)
    try:
        total = 0
        while True:
            chunk = extracted.read(IMAGE_LAYER_READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_IMAGE_LAYER_BYTES:
                raise ScenarioWizardError(
                    f"Image layer {label} exceeded the {MAX_IMAGE_LAYER_BYTES} byte limit."
                )
            spool.write(chunk)
        spool.seek(0)
        yield spool
    finally:
        with contextlib.suppress(OSError):
            extracted.close()
        spool.close()


def _write_sanitized_image_requirements_lock(
    image_tar: Path,
    source: dict[str, str],
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        _sanitize_requirements_lock(_read_image_tar_file(image_tar, source)),
        encoding="utf-8",
    )


def _image_tar_index(path: Path) -> dict[str, Any]:
    index: dict[str, Any] = {
        "files": {},
        "dirs": set(),
        "format": "filesystem",
    }
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        members_by_name: dict[str, tarfile.TarInfo] = {}
        for member in members:
            normalized = _normalize_tar_member_name(member.name)
            if not normalized:
                continue
            members_by_name[normalized] = member
        layer_names = _docker_save_layer_names(archive, members_by_name)
        if layer_names:
            index["format"] = "docker-save"
            for layer_name in layer_names:
                layer_member = members_by_name.get(layer_name)
                if layer_member is None or not layer_member.isfile():
                    continue
                with _spooled_image_layer_file(
                    archive,
                    layer_member,
                    label=layer_member.name,
                ) as layer_file:
                    _add_layer_tar_to_index(index, layer_member.name, layer_file)
            return index

        for member in members:
            normalized = _normalize_tar_member_name(member.name)
            if not normalized:
                continue
            if member.isfile() and normalized.endswith("layer.tar"):
                index["format"] = "docker-save"
                with _spooled_image_layer_file(archive, member, label=member.name) as layer_file:
                    _add_layer_tar_to_index(index, member.name, layer_file)
                continue
            _add_tar_member_to_index(
                index,
                normalized,
                source={"type": "outer", "member": member.name},
                is_dir=member.isdir(),
                is_file=member.isfile(),
                is_link=member.issym() or member.islnk(),
            )
    return index


def _docker_save_layer_names(
    archive: tarfile.TarFile,
    members_by_name: dict[str, tarfile.TarInfo],
) -> list[str]:
    manifest_member = members_by_name.get("manifest.json")
    if manifest_member is None or not manifest_member.isfile():
        return []
    extracted = archive.extractfile(manifest_member)
    if extracted is None:
        return []
    try:
        parsed = json.loads(extracted.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    layer_names: list[str] = []
    for image in parsed:
        if not isinstance(image, dict):
            continue
        layers = image.get("Layers")
        if not isinstance(layers, list):
            continue
        for layer in layers:
            normalized = _normalize_tar_member_name(str(layer))
            if normalized:
                layer_names.append(normalized)
    return layer_names


def _add_layer_tar_to_index(index: dict[str, Any], layer_name: str, layer_file: Any) -> None:
    with tarfile.open(fileobj=layer_file, mode="r:*") as layer:
        normalized_members: list[tuple[tarfile.TarInfo, str]] = []
        whiteouts: list[str] = []
        for member in layer.getmembers():
            normalized = _normalize_tar_member_name(member.name)
            if not normalized:
                continue
            if member.isfile() and _is_layer_whiteout(normalized):
                whiteouts.append(normalized)
                continue
            normalized_members.append((member, normalized))

        for whiteout in whiteouts:
            _apply_layer_whiteout(index, whiteout)

        for member, normalized in normalized_members:
            _add_tar_member_to_index(
                index,
                normalized,
                source={"type": "layer", "layer": layer_name, "member": member.name},
                is_dir=member.isdir(),
                is_file=member.isfile(),
                is_link=member.issym() or member.islnk(),
            )


def _is_layer_whiteout(path: str) -> bool:
    return Path(path).name.startswith(".wh.")


def _apply_layer_whiteout(index: dict[str, Any], whiteout_path: str) -> None:
    name = Path(whiteout_path).name
    parent = Path(whiteout_path).parent.as_posix()
    parent = "" if parent == "." else parent
    if name == ".wh..wh..opq":
        _remove_index_children(index, parent)
        return
    target_name = name.removeprefix(".wh.")
    if not target_name:
        return
    target = f"{parent}/{target_name}" if parent else target_name
    _remove_index_path(index, target)


def _remove_index_path(index: dict[str, Any], target: str) -> None:
    normalized = target.rstrip("/")
    if not normalized:
        return
    prefix = normalized + "/"
    for path in list(index["files"]):
        if path == normalized or path.startswith(prefix):
            del index["files"][path]
    for path in list(index["dirs"]):
        if path == normalized or path.startswith(prefix):
            index["dirs"].discard(path)


def _remove_index_children(index: dict[str, Any], parent: str) -> None:
    normalized = parent.rstrip("/")
    if not normalized:
        index["files"].clear()
        index["dirs"].clear()
        return
    prefix = normalized + "/"
    for path in list(index["files"]):
        if path.startswith(prefix):
            del index["files"][path]
    for path in list(index["dirs"]):
        if path.startswith(prefix):
            index["dirs"].discard(path)


def _add_tar_member_to_index(
    index: dict[str, Any],
    normalized: str,
    *,
    source: dict[str, str],
    is_dir: bool,
    is_file: bool,
    is_link: bool,
) -> None:
    if is_link:
        return
    if is_dir:
        _add_directory_parents(index["dirs"], normalized)
        return
    if is_file:
        if Path(normalized).name.startswith(".wh."):
            return
        _add_directory_parents(index["dirs"], str(Path(normalized).parent))
        index["files"][normalized] = source


def _add_directory_parents(dirs: set[str], path: str) -> None:
    normalized = path.strip("/")
    if not normalized or normalized == ".":
        return
    current = Path(normalized)
    dirs.add(current.as_posix())
    for parent in current.parents:
        parent_text = parent.as_posix()
        if parent_text == ".":
            break
        dirs.add(parent_text)


def _read_image_tar_file(image_tar: Path, source: dict[str, str]) -> bytes:
    with tarfile.open(image_tar) as archive:
        if source["type"] == "outer":
            extracted = archive.extractfile(source["member"])
            if extracted is None:
                raise ScenarioWizardError(f"Could not read tar member: {source['member']}")
            return extracted.read()
        layer_member = _get_tar_member(archive, source["layer"])
        with _spooled_image_layer_file(
            archive,
            layer_member,
            label=source["layer"],
        ) as layer_file, tarfile.open(fileobj=layer_file, mode="r:*") as layer_archive:
            extracted = layer_archive.extractfile(source["member"])
            if extracted is None:
                raise ScenarioWizardError(f"Could not read layer member: {source['member']}")
            return extracted.read()


def _detect_runtime_entrypoint(index: dict[str, Any]) -> str:
    files: dict[str, Any] = index["files"]
    candidates = sorted(path for path in files if path.endswith("/scenario_wizard.sh"))
    if "scenario_wizard.sh" in files:
        return "scenario_wizard.sh"
    preferred = [path for path in candidates if path.endswith("usr/src/folder/scenario_wizard.sh")]
    if preferred:
        return preferred[0]
    return candidates[0] if candidates else ""


def _detect_bin_script_paths(index: dict[str, Any], runtime_root: str) -> list[str]:
    files: dict[str, Any] = index["files"]
    candidates: list[str] = []
    for name in sorted(RUNTIME_BIN_SCRIPT_NAMES):
        for path in (
            f"usr/local/bin/{name}",
            f"{runtime_root}/.venv/bin/{name}".strip("/"),
            f"{runtime_root}/venv/bin/{name}".strip("/"),
            f"{runtime_root}/bin/{name}".strip("/"),
        ):
            if path in files:
                candidates.append(path)
                break
    return candidates


def _detect_tar_directory(
    index: dict[str, Any],
    *,
    explicit_path: str | None,
    candidates: list[str],
) -> str:
    if explicit_path:
        try:
            normalized = _normalize_tar_path(explicit_path)
        except ScenarioWizardError:
            return ""
        return normalized if _tar_directory_exists(index, normalized) else ""
    for candidate in candidates:
        normalized = _normalize_tar_member_name(candidate)
        if normalized and _tar_directory_exists(index, normalized):
            return normalized
    return ""


def _detect_tar_file(
    index: dict[str, Any],
    *,
    explicit_path: str | None,
    candidates: list[str],
) -> str:
    if explicit_path:
        try:
            normalized = _normalize_tar_path(explicit_path)
        except ScenarioWizardError:
            return ""
        return normalized if normalized in index["files"] else ""
    for candidate in candidates:
        normalized = _normalize_tar_member_name(candidate)
        if normalized in index["files"]:
            return normalized
    return ""


def _detect_image_tar_wizard_version(
    index: dict[str, Any],
    image_tar: Path,
    runtime_root: str,
) -> str | None:
    for candidate in (f"{runtime_root}/version.txt".strip("/"), "version.txt"):
        if candidate not in index["files"]:
            continue
        try:
            data = json.loads(_read_image_tar_file(image_tar, index["files"][candidate]))
        except (json.JSONDecodeError, UnicodeDecodeError, ScenarioWizardError):
            continue
        version = _string_value(data.get("self")) if isinstance(data, dict) else ""
        if version:
            return version
    return None


def _tar_directory_exists(index: dict[str, Any], path: str) -> bool:
    return path in index["dirs"] or _has_path_prefix(index["files"], path)


def _has_path_prefix(paths: dict[str, Any] | set[str], prefix: str) -> bool:
    if not prefix:
        return False
    normalized = prefix.rstrip("/") + "/"
    return any(path.startswith(normalized) for path in paths)


def _prefix_files(files: dict[str, Any], prefix: str) -> list[str]:
    if not prefix:
        return []
    normalized = prefix.rstrip("/") + "/"
    return sorted(path for path in files if path.startswith(normalized))


def _count_prefix_files(files: dict[str, Any], prefix: str) -> int:
    return len(_prefix_files(files, prefix))


def _relative_to_tar_root(path: str, root: str) -> str:
    root_prefix = root.rstrip("/") + "/"
    if root and path.startswith(root_prefix):
        return path[len(root_prefix) :]
    if path == root:
        return Path(path).name
    return Path(path).name


def _normalize_tar_member_name(path: str) -> str:
    try:
        return _normalize_tar_path(path)
    except ScenarioWizardError:
        return ""


def _normalize_tar_path(path: str | None) -> str:
    text = (path or "").replace("\\", "/").strip()
    text = re.sub(r"^/+", "", text)
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ScenarioWizardError(f"Unsafe tar path: {path}")
        parts.append(part)
    return "/".join(parts)


def _safe_relative_path(path: str) -> Path:
    normalized = _normalize_tar_path(path)
    if not normalized:
        raise ScenarioWizardError("Refusing to write empty relative path.")
    return Path(normalized)


def _read_version(archive: ZipFile) -> dict[str, Any]:
    if "version.txt" not in archive.namelist():
        return {}
    try:
        data = json.loads(archive.read("version.txt").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ScenarioWizardError("Scenario Wizard version.txt is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise ScenarioWizardError("Scenario Wizard version.txt must contain a JSON object.")
    return data


def _file_entry(archive: ZipFile, name: str) -> dict[str, Any]:
    info = archive.getinfo(name)
    sensitive = Path(name).name.lower() in SENSITIVE_FILENAMES
    entry: dict[str, Any] = {
        "name": name,
        "size_bytes": info.file_size,
        "sensitive": sensitive,
    }
    if sensitive:
        entry["sha256"] = None
        entry["redaction"] = "content and checksum suppressed"
        return entry
    entry["sha256"] = hashlib.sha256(archive.read(name)).hexdigest()
    return entry


def _contains_local_runtime(names: list[str]) -> bool:
    normalized = {name.rstrip("/") for name in names}
    for sentinel in RUNTIME_SENTINELS:
        if sentinel.endswith("/"):
            prefix = sentinel.rstrip("/") + "/"
            if any(name.startswith(prefix) for name in names):
                return True
            continue
        if sentinel in normalized:
            return True
    return False


def _relative_files(path: Path) -> list[str]:
    if not path.exists() or not path.is_dir():
        return []
    return [file.relative_to(path).as_posix() for file in _directory_files(path)]


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


def _path_overlap_error(source: Path, destination: Path) -> str | None:
    try:
        source_resolved = source.resolve(strict=False)
        destination_resolved = destination.resolve(strict=False)
    except OSError as exc:
        return f"Could not resolve runtime bundle paths: {exc}"
    if source_resolved == destination_resolved:
        return "Source and destination runtime bundle paths must be different."
    if source_resolved in destination_resolved.parents:
        return "Destination runtime bundle path must not be inside the source bundle."
    if destination_resolved in source_resolved.parents:
        return "Source runtime bundle path must not be inside the destination bundle."
    return None


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


def _venv_bin_dir(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts"
    return venv_path / "bin"


def _subprocess_env(
    *,
    extra_pythonpath: Path | Iterable[Path] | None = None,
    prepend_path: Path | None = None,
    home_dir: Path | None = None,
    use_setuptools_distutils: bool = False,
) -> dict[str, str]:
    env = {
        key: value
        for key in SUBPROCESS_ENV_ALLOWLIST
        if (value := os.environ.get(key))
    }
    env.setdefault("PATH", os.defpath)
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    if prepend_path is not None:
        existing_path = env.get("PATH", "")
        env["PATH"] = str(prepend_path) + os.pathsep + existing_path
    if extra_pythonpath is not None:
        env["PYTHONPATH"] = _pythonpath_value(extra_pythonpath)
    if extra_pythonpath is not None or use_setuptools_distutils:
        env["SETUPTOOLS_USE_DISTUTILS"] = "local"
    if home_dir is not None:
        home_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = home_dir / ".cache"
        tmp_dir = home_dir / "tmp"
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home_dir)
        env["USERPROFILE"] = str(home_dir)
        env["XDG_CACHE_HOME"] = str(cache_dir)
        env["PIP_CACHE_DIR"] = str(cache_dir / "pip")
        env["TMPDIR"] = str(tmp_dir)
        env["TEMP"] = str(tmp_dir)
        env["TMP"] = str(tmp_dir)
    return env


def _venv_subprocess_env(
    venv_path: Path,
    *,
    extra_pythonpath: Path | Iterable[Path] | None = None,
    prepend_path: Path | None = None,
    home_dir: Path | None = None,
    use_setuptools_distutils: bool = False,
) -> dict[str, str]:
    env = _subprocess_env(
        extra_pythonpath=extra_pythonpath,
        prepend_path=prepend_path,
        home_dir=home_dir,
        use_setuptools_distutils=use_setuptools_distutils,
    )
    env["VIRTUAL_ENV"] = str(venv_path)
    existing_path = env.get("PATH", "")
    env["PATH"] = str(_venv_bin_dir(venv_path)) + os.pathsep + existing_path
    return env


def _pythonpath_value(value: Path | Iterable[Path]) -> str:
    if isinstance(value, Path):
        return str(value)
    return os.pathsep.join(str(path) for path in value)


def _run_subprocess_action(
    name: str,
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float,
    display_argv: list[str] | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "argv": display_argv or argv,
            "cwd": str(cwd),
            "return_code": None,
            "timed_out": True,
            "stdout_tail": _safe_process_output(exc.stdout or ""),
            "stderr_tail": _safe_process_output(exc.stderr or ""),
        }
    except OSError as exc:
        return {
            "name": name,
            "argv": display_argv or argv,
            "cwd": str(cwd),
            "return_code": 127,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": _safe_process_output(str(exc)),
        }
    return {
        "name": name,
        "argv": display_argv or argv,
        "cwd": str(cwd),
        "return_code": completed.returncode,
        "timed_out": False,
        "stdout_tail": _safe_process_output(completed.stdout),
        "stderr_tail": _safe_process_output(completed.stderr),
    }


def _safe_process_output(value: str | bytes) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    text = re.sub(
        r"(?i)(authorization|api[_-]?key|jwt|password|secret|token)(\s*[:=]\s*)(\S+)",
        r"\1\2***",
        text,
    )
    text = re.sub(r"://([^/\s:@]+):([^/\s@]+)@", r"://***:***@", text)
    if len(text) > PROCESS_OUTPUT_LIMIT:
        return text[-PROCESS_OUTPUT_LIMIT:]
    return text


def _sanitize_requirements_lock(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace")
    sanitized: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith(("--index-url", "--extra-index-url")) or lowered.startswith("-i "):
            continue
        if _contains_credentialed_url(stripped):
            continue
        sanitized.append(line)
    return "\n".join(sanitized).rstrip() + "\n"


def _utc_now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
