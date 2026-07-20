from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from attackiq_cli import scenario_wizard_image as _scenario_wizard_image
from attackiq_cli.scenario_wizard_create import (
    CREATE_SCENARIO_SNIPPET as CREATE_SCENARIO_SNIPPET,
)
from attackiq_cli.scenario_wizard_create import (
    apply_scenario_wizard_create as _apply_scenario_wizard_create,
)
from attackiq_cli.scenario_wizard_create import (
    build_scenario_wizard_create_plan as build_scenario_wizard_create_plan,
)
from attackiq_cli.scenario_wizard_package import (
    COMPRESS_SCENARIO_SNIPPET as COMPRESS_SCENARIO_SNIPPET,
)
from attackiq_cli.scenario_wizard_package import (
    apply_scenario_wizard_package as _apply_scenario_wizard_package,
)
from attackiq_cli.scenario_wizard_package import (
    build_scenario_wizard_package_plan as build_scenario_wizard_package_plan,
)
from attackiq_cli.scenario_wizard_process import (
    run_subprocess_action as _run_subprocess_action,
)
from attackiq_cli.scenario_wizard_process import (
    venv_subprocess_env as _venv_subprocess_env,
)
from attackiq_cli.scenario_wizard_runtime import (
    ENV_SCENARIO_WIZARD_CACHE_DIR as ENV_SCENARIO_WIZARD_CACHE_DIR,
)
from attackiq_cli.scenario_wizard_runtime import (
    RUNTIME_SENTINELS as RUNTIME_SENTINELS,
)
from attackiq_cli.scenario_wizard_runtime import (
    _path_overlap_error as _path_overlap_error,
)
from attackiq_cli.scenario_wizard_runtime import (
    build_runtime_prepare_plan as build_runtime_prepare_plan,
)
from attackiq_cli.scenario_wizard_runtime import (
    inspect_runtime_bundle as inspect_runtime_bundle,
)
from attackiq_cli.scenario_wizard_runtime import (
    inspect_scenario_wizard_zip as inspect_scenario_wizard_zip,
)
from attackiq_cli.scenario_wizard_runtime import (
    prepare_runtime_bundle_from_bundle as prepare_runtime_bundle_from_bundle,
)
from attackiq_cli.scenario_wizard_runtime import (
    scenario_wizard_cache_dir as scenario_wizard_cache_dir,
)
from attackiq_cli.scenario_wizard_validation import (
    ScenarioWizardError as ScenarioWizardError,
)
from attackiq_cli.scenario_wizard_validation import (
    _is_python_312,
    _string_value,
)
from attackiq_cli.scenario_wizard_validation import (
    validate_generated_scenario as validate_generated_scenario,
)
from attackiq_cli.scenario_wizard_validation import (
    validate_runtime_bundle as validate_runtime_bundle,
)

MAX_IMAGE_LAYER_BYTES = _scenario_wizard_image.MAX_IMAGE_LAYER_BYTES
IMAGE_LAYER_SPOOL_MEMORY_BYTES = _scenario_wizard_image.IMAGE_LAYER_SPOOL_MEMORY_BYTES
IMAGE_LAYER_READ_CHUNK_BYTES = _scenario_wizard_image.IMAGE_LAYER_READ_CHUNK_BYTES
RUNTIME_SCRIPT_NAMES = _scenario_wizard_image.RUNTIME_SCRIPT_NAMES
RUNTIME_BIN_SCRIPT_NAMES = _scenario_wizard_image.RUNTIME_BIN_SCRIPT_NAMES
inspect_image_tar_runtime = _scenario_wizard_image.inspect_image_tar_runtime
_image_tar_inspection_error = _scenario_wizard_image._image_tar_inspection_error
_select_image_runtime_files = _scenario_wizard_image._select_image_runtime_files
_materialize_runtime_bundle_from_image_tar = (
    _scenario_wizard_image._materialize_runtime_bundle_from_image_tar
)
_write_image_tar_files = _scenario_wizard_image._write_image_tar_files
_write_stream_to_destination = _scenario_wizard_image._write_stream_to_destination
_get_tar_member = _scenario_wizard_image._get_tar_member
_spooled_image_layer_file = _scenario_wizard_image._spooled_image_layer_file
_write_sanitized_image_requirements_lock = (
    _scenario_wizard_image._write_sanitized_image_requirements_lock
)
_image_tar_index = _scenario_wizard_image._image_tar_index
_docker_save_layer_names = _scenario_wizard_image._docker_save_layer_names
_add_layer_tar_to_index = _scenario_wizard_image._add_layer_tar_to_index
_is_layer_whiteout = _scenario_wizard_image._is_layer_whiteout
_apply_layer_whiteout = _scenario_wizard_image._apply_layer_whiteout
_remove_index_path = _scenario_wizard_image._remove_index_path
_remove_index_children = _scenario_wizard_image._remove_index_children
_add_tar_member_to_index = _scenario_wizard_image._add_tar_member_to_index
_add_directory_parents = _scenario_wizard_image._add_directory_parents
_read_image_tar_file = _scenario_wizard_image._read_image_tar_file
_detect_runtime_entrypoint = _scenario_wizard_image._detect_runtime_entrypoint
_detect_bin_script_paths = _scenario_wizard_image._detect_bin_script_paths
_detect_tar_directory = _scenario_wizard_image._detect_tar_directory
_detect_tar_file = _scenario_wizard_image._detect_tar_file
_detect_image_tar_wizard_version = _scenario_wizard_image._detect_image_tar_wizard_version
_tar_directory_exists = _scenario_wizard_image._tar_directory_exists
_has_path_prefix = _scenario_wizard_image._has_path_prefix
_prefix_files = _scenario_wizard_image._prefix_files
_count_prefix_files = _scenario_wizard_image._count_prefix_files
_relative_to_tar_root = _scenario_wizard_image._relative_to_tar_root
_normalize_tar_member_name = _scenario_wizard_image._normalize_tar_member_name
_normalize_tar_path = _scenario_wizard_image._normalize_tar_path
_safe_relative_path = _scenario_wizard_image._safe_relative_path
_sanitize_requirements_lock = _scenario_wizard_image._sanitize_requirements_lock
_utc_now_iso = _scenario_wizard_image._utc_now_iso


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
    return _apply_scenario_wizard_create(
        config_path,
        output_dir,
        runtime_bundle,
        expected_wizard_version=expected_wizard_version,
        force=force,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        run_subprocess_action=_run_subprocess_action,
        venv_subprocess_env=_venv_subprocess_env,
    )


def apply_scenario_wizard_package(
    scenario_path: Path,
    *,
    force: bool = False,
    python_executable: str = "python3.12",
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    return _apply_scenario_wizard_package(
        scenario_path,
        force=force,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        run_subprocess_action=_run_subprocess_action,
        venv_subprocess_env=_venv_subprocess_env,
    )
