from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from attackiq_cli.scenario_wizard_validation import (
    SENSITIVE_FILENAMES,
    ScenarioWizardError,
    _sha256_file,
    _string_value,
    validate_runtime_bundle,
)

ENV_SCENARIO_WIZARD_CACHE_DIR = "ATTACKIQ_SCENARIO_WIZARD_CACHE_DIR"
RUNTIME_SENTINELS = {
    "scenario_wizard.sh",
    "create_docker_venv.sh",
    "setup_scenario.sh",
    "templates/",
}

__all__ = [
    "ENV_SCENARIO_WIZARD_CACHE_DIR",
    "RUNTIME_SENTINELS",
    "build_runtime_prepare_plan",
    "inspect_runtime_bundle",
    "inspect_scenario_wizard_zip",
    "prepare_runtime_bundle_from_bundle",
    "scenario_wizard_cache_dir",
]


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
