#!/usr/bin/env python3
"""Build and validate offline dependency integrity records for enterprise packages."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEPENDENCY_INTEGRITY_NAME = "ENTERPRISE_DEPENDENCY_INTEGRITY.json"
DOCUMENT_TYPE = "attackiq-cli-dependency-integrity"
CONSTRAINTS_FILE_NAME = "constraints.txt"
PIN_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)==([^\s#;]+)\s*$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def parse_constraints(constraints_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    dependencies: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: dict[str, int] = {}
    for line_number, raw_line in enumerate(
        constraints_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.fullmatch(line)
        if match is None:
            errors.append(
                f"{CONSTRAINTS_FILE_NAME}:{line_number}: expected exact '<name>==<version>' pin"
            )
            continue
        name = match.group(1)
        version = match.group(2)
        normalized_name = normalize_name(name)
        if normalized_name in seen:
            errors.append(
                f"{CONSTRAINTS_FILE_NAME}:{line_number}: duplicate pin for {normalized_name}"
            )
            continue
        seen[normalized_name] = line_number
        dependencies.append(
            {
                "line_number": line_number,
                "name": name,
                "normalized_name": normalized_name,
                "version": version,
                "constraint": line,
                "constraint_sha256": sha256_text(line),
            }
        )
    if not dependencies:
        errors.append(f"{CONSTRAINTS_FILE_NAME}: no dependency pins found")
    return dependencies, errors


def build_dependency_integrity(
    *,
    constraints_path: Path,
    constraints_sha256: str,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    dependencies, errors = parse_constraints(constraints_path)
    if errors:
        raise RuntimeError("constraints integrity parsing failed:\n- " + "\n- ".join(errors))
    generated = generated_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": 1,
        "document_type": DOCUMENT_TYPE,
        "generated_utc": generated,
        "constraints": {
            "filename": constraints_path.name,
            "sha256": constraints_sha256,
            "pinned_dependency_count": len(dependencies),
        },
        "pinned_dependencies": dependencies,
        "integrity_policy": (
            "offline exact-pin dependency integrity record; package artifact hash pinning, "
            "wheelhouse retention, and repository trust roots remain enterprise-owned controls"
        ),
    }


def write_dependency_integrity(package_dir: Path, integrity: dict[str, Any]) -> Path:
    integrity_path = package_dir / DEPENDENCY_INTEGRITY_NAME
    integrity_path.write_text(
        json.dumps(integrity, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return integrity_path


def load_dependency_integrity(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{DEPENDENCY_INTEGRITY_NAME}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{DEPENDENCY_INTEGRITY_NAME}: expected JSON object"]
    return data, []


def _manifest_constraints_entry(manifest: dict[str, Any]) -> dict[str, Any] | None:
    constraints_file = manifest.get("constraints_file")
    return constraints_file if isinstance(constraints_file, dict) else None


def validate_dependency_integrity(
    *,
    package_dir: Path,
    manifest: dict[str, Any],
    integrity: dict[str, Any],
    integrity_filename: str,
) -> list[str]:
    errors: list[str] = []
    if integrity_filename != DEPENDENCY_INTEGRITY_NAME:
        errors.append(f"{DEPENDENCY_INTEGRITY_NAME}: filename must be {DEPENDENCY_INTEGRITY_NAME}")
    if integrity.get("schema_version") != 1:
        errors.append(f"{DEPENDENCY_INTEGRITY_NAME}: schema_version must be 1")
    if integrity.get("document_type") != DOCUMENT_TYPE:
        errors.append(f"{DEPENDENCY_INTEGRITY_NAME}: document_type must be {DOCUMENT_TYPE}")

    constraints_entry = _manifest_constraints_entry(manifest)
    constraints = integrity.get("constraints")
    if constraints_entry is None:
        errors.append(f"{DEPENDENCY_INTEGRITY_NAME}: manifest constraints_file is required")
    elif not isinstance(constraints, dict):
        errors.append(f"{DEPENDENCY_INTEGRITY_NAME}: constraints must be an object")
    else:
        filename = constraints_entry.get("filename")
        digest = constraints_entry.get("sha256")
        if constraints.get("filename") != filename:
            errors.append(f"{DEPENDENCY_INTEGRITY_NAME}: constraints.filename must match manifest")
        if constraints.get("sha256") != digest:
            errors.append(f"{DEPENDENCY_INTEGRITY_NAME}: constraints.sha256 must match manifest")
        if isinstance(filename, str):
            constraints_path = package_dir / filename
            if constraints_path.is_file() and sha256_file(constraints_path) != digest:
                errors.append(
                    f"{DEPENDENCY_INTEGRITY_NAME}: constraints.sha256 must match local file"
                )

    pinned_dependencies = integrity.get("pinned_dependencies")
    if not isinstance(pinned_dependencies, list) or not pinned_dependencies:
        errors.append(f"{DEPENDENCY_INTEGRITY_NAME}: pinned_dependencies must be a non-empty list")
        return errors
    if constraints_entry is None:
        return errors
    filename = constraints_entry.get("filename")
    if not isinstance(filename, str):
        return errors
    expected_dependencies, parse_errors = parse_constraints(package_dir / filename)
    errors.extend(parse_errors)
    if parse_errors:
        return errors
    if pinned_dependencies != expected_dependencies:
        errors.append(
            f"{DEPENDENCY_INTEGRITY_NAME}: pinned_dependencies must match constraints.txt"
        )
    if isinstance(constraints, dict) and constraints.get("pinned_dependency_count") != len(
        expected_dependencies
    ):
        errors.append(
            f"{DEPENDENCY_INTEGRITY_NAME}: constraints.pinned_dependency_count must match "
            "constraints.txt"
        )
    return errors
