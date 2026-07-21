from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

SENSITIVE_FILENAMES = {"pip.conf", ".pypirc", "pip.ini"}
REQUIRED_RUNTIME_MANIFEST_FIELDS = {
    "python_version",
    "runtime_version",
    "source_type",
    "wizard_version",
}
REQUIRED_SCENARIO_CONFIG_FIELDS = (
    "scenario_name",
    "scenario_description",
    "phase_description",
)
SECRET_KEY_MARKERS = (
    "api_key",
    "auth",
    "cookie",
    "credential",
    "jwt",
    "password",
    "secret",
    "token",
)
VALID_RUNTIME_SOURCE_TYPES = {"bundle", "fixture", "image", "image_tar", "manual"}


class ScenarioWizardError(ValueError):
    """Raised when Scenario Wizard metadata cannot be inspected safely."""


def validate_runtime_bundle(
    bundle_path: Path,
    *,
    expected_wizard_version: str | None = None,
) -> dict[str, Any]:
    path = bundle_path.expanduser()
    manifest_path = path / "manifest.json"
    runtime_entrypoint = path / "runtime" / "scenario_wizard.sh"
    runtime_create_module = path / "runtime" / "scenario_wizard" / "impl" / "make_scenario.py"
    templates_dir = path / "runtime" / "templates"
    nested_templates_dir = path / "runtime" / "scenario_wizard" / "templates"
    wheelhouse_dir = path / "wheelhouse"
    requirements_lock = path / "python" / "requirements.lock"
    site_packages_dir = path / "python" / "site-packages"
    runtime_bin_dir = path / "python" / "bin"
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        errors.append(f"Runtime bundle path does not exist: {path}")
    elif not path.is_dir():
        errors.append(f"Runtime bundle path must be a directory: {path}")

    manifest: dict[str, Any] | None = None
    manifest_valid_json = False
    if not manifest_path.exists():
        errors.append(f"Runtime bundle manifest not found: {manifest_path}")
    elif not manifest_path.is_file():
        errors.append(f"Runtime bundle manifest path must be a file: {manifest_path}")
    else:
        try:
            parsed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Runtime bundle manifest is not valid JSON: {exc}")
        else:
            if not isinstance(parsed_manifest, dict):
                errors.append("Runtime bundle manifest must contain a JSON object.")
            else:
                manifest = parsed_manifest
                manifest_valid_json = True

    if manifest is not None:
        _validate_runtime_manifest(
            manifest,
            errors=errors,
            warnings=warnings,
            expected_wizard_version=expected_wizard_version,
        )

    runtime_entrypoint_exists = runtime_entrypoint.is_file()
    runtime_create_module_exists = runtime_create_module.is_file()
    templates_dir_exists = templates_dir.is_dir() or nested_templates_dir.is_dir()
    wheelhouse_dir_exists = wheelhouse_dir.is_dir()
    requirements_lock_exists = requirements_lock.is_file()
    if path.exists() and path.is_dir():
        if not runtime_create_module_exists:
            errors.append(f"Runtime create module not found: {runtime_create_module}")
        if not templates_dir_exists:
            errors.append(f"Runtime templates directory not found: {templates_dir}")
        if not wheelhouse_dir_exists:
            errors.append(f"Runtime wheelhouse directory not found: {wheelhouse_dir}")
        if not requirements_lock_exists:
            errors.append(f"Runtime requirements lock not found: {requirements_lock}")
        elif _file_contains_credentialed_url(requirements_lock):
            errors.append("Runtime requirements lock contains credentialed URLs.")

    wheelhouse_files = _directory_files(wheelhouse_dir) if wheelhouse_dir_exists else []
    if wheelhouse_dir_exists and not wheelhouse_files:
        errors.append(f"Runtime wheelhouse contains no files: {wheelhouse_dir}")
    if site_packages_dir.is_dir() and not (runtime_bin_dir / "fullrelease").is_file():
        warnings.append(
            "Runtime site-packages are present without the fullrelease console script; "
            "image-backed package apply may fail."
        )
    actual_wheelhouse_sha256 = _sha256_directory(wheelhouse_dir) if wheelhouse_files else None
    if manifest is not None and actual_wheelhouse_sha256:
        expected_wheelhouse_sha256 = _string_value(manifest.get("wheelhouse_sha256"))
        if expected_wheelhouse_sha256:
            if expected_wheelhouse_sha256 != actual_wheelhouse_sha256:
                errors.append("Runtime wheelhouse checksum does not match manifest.")
        else:
            warnings.append("Runtime manifest does not declare wheelhouse_sha256.")

    sensitive_files = _sensitive_files_under(path) if path.exists() and path.is_dir() else []
    if sensitive_files:
        errors.append("Runtime bundle contains sensitive package configuration files.")
    symlinks = _symlinks_under(path) if path.exists() and path.is_dir() else []
    if symlinks:
        errors.append("Runtime bundle contains symbolic links.")

    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "manifest_valid_json": manifest_valid_json,
        "runtime_entrypoint": str(runtime_entrypoint),
        "runtime_entrypoint_exists": runtime_entrypoint_exists,
        "runtime_create_module": str(runtime_create_module),
        "runtime_create_module_exists": runtime_create_module_exists,
        "templates_dir": str(templates_dir if templates_dir.is_dir() else nested_templates_dir),
        "templates_dir_candidates": [str(templates_dir), str(nested_templates_dir)],
        "templates_dir_exists": templates_dir_exists,
        "wheelhouse_dir": str(wheelhouse_dir),
        "wheelhouse_dir_exists": wheelhouse_dir_exists,
        "wheelhouse_file_count": len(wheelhouse_files),
        "wheelhouse_sha256": actual_wheelhouse_sha256,
        "requirements_lock": str(requirements_lock),
        "requirements_lock_exists": requirements_lock_exists,
        "site_packages_dir": str(site_packages_dir),
        "site_packages_exists": site_packages_dir.is_dir(),
        "runtime_bin_dir": str(runtime_bin_dir),
        "runtime_bin_exists": runtime_bin_dir.is_dir(),
        "runtime_bin_script_files": [
            str(file_path)
            for file_path in _directory_files(runtime_bin_dir)
            if runtime_bin_dir.is_dir()
        ],
        "sensitive_files_present": sensitive_files,
        "symlinks_present": symlinks,
    }
    if manifest is not None:
        result["manifest"] = _safe_manifest_summary(manifest)
        result["secret_like_manifest_keys"] = _secret_like_keys(manifest)
    return result


def validate_generated_scenario(scenario_path: Path, *, force: bool = False) -> dict[str, Any]:
    scenario = scenario_path.expanduser()
    requirements = scenario / "requirements.txt"
    wheelhouse_dir = scenario / ".pipdownload"
    descriptor = scenario / "descriptor.json"
    setup_cfg = scenario / "setup.cfg"
    main_py = scenario / "main.py"
    venv_path = scenario / "venv"
    venv_python = _venv_python_path(venv_path)
    target_dir = scenario / "target"
    target_zips = sorted(target_dir.glob("*.zip")) if target_dir.is_dir() else []
    errors: list[str] = []
    warnings: list[str] = []

    if not scenario.exists():
        errors.append(f"Generated scenario path does not exist: {scenario}")
    elif not scenario.is_dir():
        errors.append(f"Generated scenario path must be a directory: {scenario}")
    else:
        for required in (requirements, wheelhouse_dir, descriptor, setup_cfg, main_py):
            if not required.exists():
                errors.append(f"Required scenario package input not found: {required}")
        if wheelhouse_dir.exists() and not wheelhouse_dir.is_dir():
            errors.append(f"Scenario wheelhouse path must be a directory: {wheelhouse_dir}")
        if requirements.exists() and not requirements.is_file():
            errors.append(f"Scenario requirements path must be a file: {requirements}")
        if venv_path.exists() and not venv_python.is_file():
            errors.append(f"Scenario virtualenv exists but Python was not found: {venv_python}")
        if target_zips and not force:
            errors.append(
                "Scenario target directory already contains package zip files; use --force to "
                "package anyway."
            )
        if not (scenario / "version.txt").is_file():
            warnings.append("Generated scenario does not include version.txt.")

    return {
        "path": str(scenario),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "requirements": str(requirements),
        "requirements_exists": requirements.is_file(),
        "wheelhouse_dir": str(wheelhouse_dir),
        "wheelhouse_exists": wheelhouse_dir.is_dir(),
        "descriptor": str(descriptor),
        "descriptor_exists": descriptor.is_file(),
        "setup_cfg": str(setup_cfg),
        "setup_cfg_exists": setup_cfg.is_file(),
        "main_py": str(main_py),
        "main_py_exists": main_py.is_file(),
        "venv": str(venv_path),
        "venv_exists": venv_path.exists(),
        "venv_python": str(venv_python),
        "venv_python_exists": venv_python.is_file(),
        "target_dir": str(target_dir),
        "target_dir_exists": target_dir.is_dir(),
        "target_zip_files": [str(path) for path in target_zips],
        "force": force,
    }


def _scenario_config_summary(config_path: Path) -> tuple[dict[str, Any], list[str]]:
    path = config_path.expanduser()
    errors: list[str] = []
    data: dict[str, Any] | None = None
    if not path.exists():
        errors.append(f"Scenario configuration not found: {path}")
    elif not path.is_file():
        errors.append(f"Scenario configuration path must be a file: {path}")
    else:
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Scenario configuration is not valid JSON: {exc}")
        else:
            if not isinstance(parsed, dict):
                errors.append("Scenario configuration must contain a JSON object.")
            else:
                data = parsed

    required_fields = {
        field: bool(_string_value(data.get(field))) if data is not None else False
        for field in REQUIRED_SCENARIO_CONFIG_FIELDS
    }
    missing = [field for field, present in required_fields.items() if not present]
    if missing:
        errors.append(f"Scenario configuration is missing required fields: {', '.join(missing)}")

    secret_keys = _secret_like_keys(data or {})
    if secret_keys:
        errors.append("Scenario configuration contains secret-like keys.")

    scenario_name = _string_value((data or {}).get("scenario_name"))
    extra_fields = sorted(key for key in (data or {}) if key not in REQUIRED_SCENARIO_CONFIG_FIELDS)
    summary: dict[str, Any] = {
        "path": str(path),
        "valid": not errors,
        "required_fields": required_fields,
        "scenario_name": scenario_name or None,
        "scenario_slug": _slugify_scenario_name(scenario_name) if scenario_name else None,
        "extra_fields": extra_fields,
        "secret_like_keys": secret_keys,
    }
    return summary, errors


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ScenarioWizardError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ScenarioWizardError(f"{label} must contain a JSON object.")
    return data


def _safe_manifest_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "created_at",
        "python_version",
        "runtime_version",
        "source_type",
        "wheelhouse_sha256",
        "wizard_version",
    }
    return {key: manifest[key] for key in sorted(allowed_keys) if key in manifest}


def _validate_runtime_manifest(
    manifest: dict[str, Any],
    *,
    errors: list[str],
    warnings: list[str],
    expected_wizard_version: str | None,
) -> None:
    missing = [
        field
        for field in sorted(REQUIRED_RUNTIME_MANIFEST_FIELDS)
        if not _string_value(manifest.get(field))
    ]
    if missing:
        errors.append(f"Runtime manifest is missing required fields: {', '.join(missing)}")

    source_type = _string_value(manifest.get("source_type"))
    if source_type and source_type not in VALID_RUNTIME_SOURCE_TYPES:
        errors.append(
            "Runtime manifest source_type must be one of: "
            f"{', '.join(sorted(VALID_RUNTIME_SOURCE_TYPES))}."
        )

    python_version = _string_value(manifest.get("python_version"))
    if python_version and not _is_python_312(python_version):
        errors.append("Runtime manifest python_version must target Python 3.12.")

    wizard_version = _string_value(manifest.get("wizard_version"))
    if expected_wizard_version and wizard_version and wizard_version != expected_wizard_version:
        errors.append(
            "Runtime manifest wizard_version does not match expected version "
            f"{expected_wizard_version}."
        )

    secret_keys = _secret_like_keys(manifest)
    if secret_keys:
        errors.append("Runtime manifest contains secret-like keys.")

    if "created_at" not in manifest:
        warnings.append("Runtime manifest does not declare created_at.")


def _slugify_scenario_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "scenario"


def _is_python_312(version: str) -> bool:
    return bool(re.match(r"^3\.12(?:\.|$)", version.strip()))


def _directory_files(path: Path) -> list[Path]:
    return sorted(file for file in path.rglob("*") if file.is_file() and not file.is_symlink())


def _sensitive_files_under(path: Path) -> list[str]:
    sensitive: list[str] = []
    for file in _directory_files(path):
        if file.name.lower() in SENSITIVE_FILENAMES:
            sensitive.append(file.relative_to(path).as_posix())
    return sensitive


def _symlinks_under(path: Path) -> list[str]:
    symlinks: list[str] = []
    for item in path.rglob("*"):
        if item.is_symlink():
            symlinks.append(item.relative_to(path).as_posix())
    return symlinks


def _secret_like_keys(value: Any, *, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for raw_key, nested_value in value.items():
            key = str(raw_key)
            key_path = f"{prefix}.{key}" if prefix else key
            lowered = key.lower()
            if any(marker in lowered for marker in SECRET_KEY_MARKERS):
                keys.append(key_path)
            keys.extend(_secret_like_keys(nested_value, prefix=key_path))
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            keys.extend(_secret_like_keys(nested_value, prefix=f"{prefix}[{index}]"))
    return sorted(set(keys))


def _sha256_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for file in _directory_files(path):
        relative = file.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_file(file).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _file_contains_credentialed_url(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return _contains_credentialed_url(text)


def _contains_credentialed_url(text: str) -> bool:
    return bool(re.search(r"://[^/\s:@]+:[^/\s@]+@", text))


def _venv_python_path(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
