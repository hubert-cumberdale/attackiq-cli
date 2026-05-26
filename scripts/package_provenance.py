#!/usr/bin/env python3
"""Build and validate offline package provenance for enterprise package directories."""

from __future__ import annotations

import email
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROVENANCE_NAME = "ENTERPRISE_PACKAGE_PROVENANCE.json"
PROVENANCE_DOCUMENT_TYPE = "attackiq-cli-enterprise-package-provenance"
CONSTRAINTS_FILE_NAME = "constraints.txt"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_wheel_metadata(wheel_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(wheel_path) as wheel:
        metadata_names = [
            name
            for name in wheel.namelist()
            if name.endswith(".dist-info/METADATA") and not name.startswith("/")
        ]
        if len(metadata_names) != 1:
            raise RuntimeError(
                f"expected exactly one wheel METADATA file in {wheel_path.name}, "
                f"found {len(metadata_names)}"
            )
        metadata_text = wheel.read(metadata_names[0]).decode("utf-8")

    message = email.message_from_string(metadata_text)
    dependencies = sorted(message.get_all("Requires-Dist") or [])
    return {
        "metadata_file": metadata_names[0],
        "metadata_version": message.get("Metadata-Version", ""),
        "name": message.get("Name", ""),
        "version": message.get("Version", ""),
        "summary": message.get("Summary", ""),
        "requires_python": message.get("Requires-Python", ""),
        "dependencies": dependencies,
    }


def _constraints_file_entry(
    *,
    package_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any] | None:
    constraints_file = manifest.get("constraints_file")
    if not isinstance(constraints_file, dict):
        return None
    filename = constraints_file.get("filename")
    sha256 = constraints_file.get("sha256")
    if not isinstance(filename, str) or not isinstance(sha256, str):
        return None
    constraints_path = package_dir / filename
    return {
        "filename": filename,
        "type": constraints_file.get("type"),
        "sha256": sha256,
        "size_bytes": constraints_path.stat().st_size if constraints_path.is_file() else None,
    }


def build_package_provenance(
    *,
    package_dir: Path,
    manifest: dict[str, Any],
    manifest_filename: str,
    wheel_path: Path,
    wheel_sha256: str,
    checksum_filename: str,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Create a public-safe provenance document for a built enterprise package."""

    generated = generated_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    wheel_metadata = _read_wheel_metadata(wheel_path)
    return {
        "schema_version": 1,
        "document_type": PROVENANCE_DOCUMENT_TYPE,
        "generated_utc": generated,
        "source": {
            "public_repo_url": manifest.get("public_repo_url"),
            "source_ref": manifest.get("source_ref"),
            "source_commit": manifest.get("source_commit"),
            "package_version": manifest.get("package_version"),
        },
        "promotion_manifest": {
            "filename": manifest_filename,
            "sha256": sha256_file(package_dir / manifest_filename),
        },
        "checksum_file": checksum_filename,
        "artifacts": [
            {
                "filename": wheel_path.name,
                "type": "wheel",
                "sha256": wheel_sha256,
                "size_bytes": wheel_path.stat().st_size,
            }
        ],
        "install_constraints": _constraints_file_entry(
            package_dir=package_dir,
            manifest=manifest,
        ),
        "wheel_metadata": wheel_metadata,
        "provenance_policy": (
            "offline package provenance and dependency inventory; registry upload, "
            "signing, and attestation remain operator-owned"
        ),
    }


def write_package_provenance(package_dir: Path, provenance: dict[str, Any]) -> Path:
    provenance_path = package_dir / PROVENANCE_NAME
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return provenance_path


def load_package_provenance(provenance_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(provenance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{PROVENANCE_NAME}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{PROVENANCE_NAME}: expected JSON object"]
    return data, []


def _validate_source(manifest: dict[str, Any], provenance: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source = provenance.get("source")
    if not isinstance(source, dict):
        return [f"{PROVENANCE_NAME}: source must be an object"]
    for key in ("public_repo_url", "source_ref", "source_commit", "package_version"):
        if source.get(key) != manifest.get(key):
            errors.append(f"{PROVENANCE_NAME}: source.{key} must match promotion manifest")
    return errors


def _validate_artifacts(
    manifest: dict[str, Any],
    provenance: dict[str, Any],
    package_dir: Path,
) -> list[str]:
    errors: list[str] = []
    artifacts = provenance.get("artifacts")
    manifest_artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return [f"{PROVENANCE_NAME}: artifacts must be a non-empty list"]
    if not isinstance(manifest_artifacts, list):
        return errors

    manifest_by_name = {
        artifact.get("filename"): artifact
        for artifact in manifest_artifacts
        if isinstance(artifact, dict) and isinstance(artifact.get("filename"), str)
    }
    for index, artifact in enumerate(artifacts):
        label = f"{PROVENANCE_NAME}: artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{label}: expected object")
            continue
        filename = artifact.get("filename")
        if not isinstance(filename, str) or filename not in manifest_by_name:
            errors.append(f"{label}: filename must match a manifest artifact")
            continue
        manifest_artifact = manifest_by_name[filename]
        if artifact.get("type") != manifest_artifact.get("type"):
            errors.append(f"{label}: type must match promotion manifest")
        if artifact.get("sha256") != manifest_artifact.get("sha256"):
            errors.append(f"{label}: sha256 must match promotion manifest")
        artifact_path = package_dir / filename
        if artifact_path.is_file() and artifact.get("size_bytes") != artifact_path.stat().st_size:
            errors.append(f"{label}: size_bytes must match artifact file size")
    return errors


def _validate_install_constraints(
    manifest: dict[str, Any],
    provenance: dict[str, Any],
    package_dir: Path,
) -> list[str]:
    errors: list[str] = []
    manifest_constraints = manifest.get("constraints_file")
    provenance_constraints = provenance.get("install_constraints")
    if manifest_constraints is None:
        if provenance_constraints is not None:
            errors.append(f"{PROVENANCE_NAME}: install_constraints must be omitted")
        return errors
    if not isinstance(manifest_constraints, dict):
        return errors
    if not isinstance(provenance_constraints, dict):
        return [f"{PROVENANCE_NAME}: install_constraints must be an object"]

    filename = manifest_constraints.get("filename")
    if provenance_constraints.get("filename") != filename:
        errors.append(f"{PROVENANCE_NAME}: install_constraints.filename must match manifest")
    if provenance_constraints.get("type") != manifest_constraints.get("type"):
        errors.append(f"{PROVENANCE_NAME}: install_constraints.type must match manifest")
    if provenance_constraints.get("sha256") != manifest_constraints.get("sha256"):
        errors.append(f"{PROVENANCE_NAME}: install_constraints.sha256 must match manifest")
    if isinstance(filename, str):
        constraints_path = package_dir / filename
        if constraints_path.is_file() and (
            provenance_constraints.get("size_bytes") != constraints_path.stat().st_size
        ):
            errors.append(
                f"{PROVENANCE_NAME}: install_constraints.size_bytes must match file size"
            )
    return errors


def _validate_wheel_metadata(manifest: dict[str, Any], provenance: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    wheel_metadata = provenance.get("wheel_metadata")
    if not isinstance(wheel_metadata, dict):
        return [f"{PROVENANCE_NAME}: wheel_metadata must be an object"]
    if wheel_metadata.get("name") != "attackiq-cli":
        errors.append(f"{PROVENANCE_NAME}: wheel_metadata.name must be attackiq-cli")
    if wheel_metadata.get("version") != manifest.get("package_version"):
        errors.append(f"{PROVENANCE_NAME}: wheel_metadata.version must match package_version")
    dependencies = wheel_metadata.get("dependencies")
    dependencies_valid = isinstance(dependencies, list) and all(
        isinstance(item, str) for item in dependencies
    )
    if not dependencies_valid:
        errors.append(
            f"{PROVENANCE_NAME}: wheel_metadata.dependencies must be a list of strings"
        )
    return errors


def validate_package_provenance(
    *,
    package_dir: Path,
    manifest: dict[str, Any],
    provenance: dict[str, Any],
    provenance_filename: str,
) -> list[str]:
    errors: list[str] = []
    if provenance.get("schema_version") != 1:
        errors.append(f"{PROVENANCE_NAME}: schema_version must be 1")
    if provenance.get("document_type") != PROVENANCE_DOCUMENT_TYPE:
        errors.append(f"{PROVENANCE_NAME}: document_type is invalid")
    if not isinstance(provenance.get("generated_utc"), str) or not provenance["generated_utc"]:
        errors.append(f"{PROVENANCE_NAME}: generated_utc must be a non-empty string")

    promotion_manifest = provenance.get("promotion_manifest")
    if not isinstance(promotion_manifest, dict):
        errors.append(f"{PROVENANCE_NAME}: promotion_manifest must be an object")
    else:
        manifest_filename = promotion_manifest.get("filename")
        if manifest_filename != "ENTERPRISE_PROMOTION_MANIFEST.json":
            errors.append(f"{PROVENANCE_NAME}: promotion_manifest.filename is invalid")
        elif not (package_dir / manifest_filename).is_file():
            errors.append(f"{PROVENANCE_NAME}: promotion manifest file is missing")
        else:
            expected_manifest_sha = sha256_file(package_dir / manifest_filename)
            if promotion_manifest.get("sha256") != expected_manifest_sha:
                errors.append(
                    f"{PROVENANCE_NAME}: promotion_manifest.sha256 does not match "
                    "manifest file"
                )

    if provenance.get("checksum_file") != manifest.get("checksum_file"):
        errors.append(f"{PROVENANCE_NAME}: checksum_file must match promotion manifest")
    if provenance_filename != PROVENANCE_NAME:
        errors.append(f"{PROVENANCE_NAME}: unexpected provenance filename")

    errors.extend(_validate_source(manifest, provenance))
    errors.extend(_validate_artifacts(manifest, provenance, package_dir))
    errors.extend(_validate_install_constraints(manifest, provenance, package_dir))
    errors.extend(_validate_wheel_metadata(manifest, provenance))
    return errors
