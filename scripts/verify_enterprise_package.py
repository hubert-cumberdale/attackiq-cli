#!/usr/bin/env python3
"""Verify enterprise package promotion artifacts offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from scripts import check_public_safety as public_safety
    from scripts import package_provenance
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback.
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import check_public_safety as public_safety  # type: ignore[no-redef]
    import package_provenance  # type: ignore[no-redef]


CHECKSUM_FILE_NAME = "SHA256SUMS"
MANIFEST_NAME = "ENTERPRISE_PROMOTION_MANIFEST.json"
PROVENANCE_NAME = package_provenance.PROVENANCE_NAME
CONSTRAINTS_FILE_NAME = "constraints.txt"
RELEASE_REF_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_safe_artifact_name(filename: str) -> bool:
    artifact_path = Path(filename)
    return (
        filename == artifact_path.name
        and not artifact_path.is_absolute()
        and filename not in {"", ".", ".."}
    )


def parse_sha256s(checksum_path: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    hashes: dict[str, str] = {}
    for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2:
            errors.append(f"{CHECKSUM_FILE_NAME}:{line_number}: expected '<sha256>  <filename>'")
            continue
        digest, filename = parts
        if not SHA256_RE.fullmatch(digest):
            errors.append(f"{CHECKSUM_FILE_NAME}:{line_number}: invalid SHA256 digest")
        if not is_safe_artifact_name(filename):
            errors.append(f"{CHECKSUM_FILE_NAME}:{line_number}: unsafe artifact filename")
        if filename in hashes:
            errors.append(f"{CHECKSUM_FILE_NAME}:{line_number}: duplicate artifact filename")
        hashes[filename] = digest
    if not hashes:
        errors.append(f"{CHECKSUM_FILE_NAME}: no artifact checksums found")
    return hashes, errors


def load_manifest(manifest_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{MANIFEST_NAME}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{MANIFEST_NAME}: expected JSON object"]
    return data, []


def validate_public_repo_url(public_repo_url: object) -> list[str]:
    if not isinstance(public_repo_url, str) or not public_repo_url:
        return [f"{MANIFEST_NAME}: public_repo_url must be a non-empty string"]
    parsed = urlparse(public_repo_url)
    if parsed.username or parsed.password:
        return [f"{MANIFEST_NAME}: public_repo_url must not include credentials"]
    return []


def _constraints_file_entry(manifest: dict[str, Any]) -> dict[str, Any] | None:
    constraints_file = manifest.get("constraints_file")
    return constraints_file if isinstance(constraints_file, dict) else None


def validate_manifest_shape(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append(f"{MANIFEST_NAME}: schema_version must be 1")

    source_ref = manifest.get("source_ref")
    package_version = manifest.get("package_version")
    source_ref_match = RELEASE_REF_RE.fullmatch(source_ref) if isinstance(source_ref, str) else None
    if source_ref_match is None:
        errors.append(f"{MANIFEST_NAME}: source_ref must be a vX.Y.Z release tag")
    elif package_version != source_ref_match.group("version"):
        errors.append(f"{MANIFEST_NAME}: package_version must match source_ref")

    if not isinstance(package_version, str) or not package_version:
        errors.append(f"{MANIFEST_NAME}: package_version must be a non-empty string")
    if not isinstance(manifest.get("source_commit"), str) or not manifest["source_commit"]:
        errors.append(f"{MANIFEST_NAME}: source_commit must be a non-empty string")
    if manifest.get("checksum_file") != CHECKSUM_FILE_NAME:
        errors.append(f"{MANIFEST_NAME}: checksum_file must be {CHECKSUM_FILE_NAME}")

    constraints_file = manifest.get("constraints_file")
    if constraints_file is not None:
        if not isinstance(constraints_file, dict):
            errors.append(f"{MANIFEST_NAME}: constraints_file must be an object")
        else:
            filename = constraints_file.get("filename")
            digest = constraints_file.get("sha256")
            if filename != CONSTRAINTS_FILE_NAME:
                errors.append(
                    f"{MANIFEST_NAME}: constraints_file.filename must be "
                    f"{CONSTRAINTS_FILE_NAME}"
                )
            if constraints_file.get("type") != "install-constraints":
                errors.append(f"{MANIFEST_NAME}: constraints_file.type must be install-constraints")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(
                    f"{MANIFEST_NAME}: constraints_file.sha256 must be a 64-character "
                    "lowercase hex digest"
                )

    provenance_file = manifest.get("provenance_file")
    if provenance_file is not None and provenance_file != PROVENANCE_NAME:
        errors.append(f"{MANIFEST_NAME}: provenance_file must be {PROVENANCE_NAME}")
    errors.extend(validate_public_repo_url(manifest.get("public_repo_url")))

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"{MANIFEST_NAME}: artifacts must be a non-empty list")
        return errors

    wheel_count = 0
    for index, artifact in enumerate(artifacts):
        label = f"{MANIFEST_NAME}: artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{label}: expected object")
            continue
        filename = artifact.get("filename")
        digest = artifact.get("sha256")
        artifact_type = artifact.get("type")
        if not isinstance(filename, str) or not is_safe_artifact_name(filename):
            errors.append(f"{label}: filename must be a safe local filename")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"{label}: sha256 must be a 64-character lowercase hex digest")
        if artifact_type != "wheel":
            errors.append(f"{label}: type must be wheel")
        else:
            wheel_count += 1
        if isinstance(filename, str) and isinstance(package_version, str):
            expected_prefix = f"attackiq_cli-{package_version}-"
            if not filename.startswith(expected_prefix) or not filename.endswith(".whl"):
                errors.append(f"{label}: wheel filename must match package_version")

    if wheel_count != 1:
        errors.append(f"{MANIFEST_NAME}: exactly one wheel artifact is required")
    return errors


def verify_artifacts(
    package_dir: Path,
    manifest: dict[str, Any],
    checksums: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    allowed_checksum_only = set()
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return errors

    manifest_hashes: dict[str, str] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        filename = artifact.get("filename")
        expected_digest = artifact.get("sha256")
        artifact_type = artifact.get("type")
        if not isinstance(filename, str) or not isinstance(expected_digest, str):
            continue
        manifest_hashes[filename] = expected_digest
        if checksums.get(filename) != expected_digest:
            errors.append(f"{filename}: manifest SHA256 does not match {CHECKSUM_FILE_NAME}")
            continue
        artifact_path = package_dir / filename
        if not artifact_path.is_file():
            errors.append(f"{filename}: artifact file is missing")
            continue
        actual_digest = sha256_file(artifact_path)
        if actual_digest != expected_digest:
            errors.append(f"{filename}: file SHA256 does not match manifest")
            continue
        if artifact_type == "wheel":
            wheel_errors = public_safety.scan_wheel(artifact_path)
            errors.extend(f"{filename}: {error}" for error in wheel_errors)

    constraints_file = _constraints_file_entry(manifest)
    if constraints_file is not None:
        filename = constraints_file.get("filename")
        expected_digest = constraints_file.get("sha256")
        if isinstance(filename, str) and isinstance(expected_digest, str):
            allowed_checksum_only.add(filename)
            if checksums.get(filename) != expected_digest:
                errors.append(f"{filename}: manifest SHA256 does not match {CHECKSUM_FILE_NAME}")
            constraints_path = package_dir / filename
            if not constraints_path.is_file():
                errors.append(f"{filename}: constraints file is missing")
            else:
                actual_digest = sha256_file(constraints_path)
                if actual_digest != expected_digest:
                    errors.append(f"{filename}: file SHA256 does not match manifest")

    provenance_file = manifest.get("provenance_file")
    if isinstance(provenance_file, str):
        allowed_checksum_only.add(provenance_file)
    extra_checksums = set(checksums) - set(manifest_hashes) - allowed_checksum_only
    for filename in sorted(extra_checksums):
        errors.append(f"{filename}: checksum entry is not listed in manifest artifacts")
    missing_checksums = set(manifest_hashes) - set(checksums)
    for filename in sorted(missing_checksums):
        errors.append(f"{filename}: manifest artifact is missing from {CHECKSUM_FILE_NAME}")
    return errors


def verify_provenance(
    package_dir: Path,
    manifest: dict[str, Any],
    checksums: dict[str, str],
) -> list[str]:
    provenance_file = manifest.get("provenance_file")
    if provenance_file is None:
        return []
    if not isinstance(provenance_file, str) or not is_safe_artifact_name(provenance_file):
        return [f"{MANIFEST_NAME}: provenance_file must be a safe local filename"]

    errors: list[str] = []
    provenance_path = package_dir / provenance_file
    expected_digest = checksums.get(provenance_file)
    if expected_digest is None:
        errors.append(f"{provenance_file}: provenance file is missing from {CHECKSUM_FILE_NAME}")
    if not provenance_path.is_file():
        errors.append(f"{provenance_file}: provenance file is missing")
        return errors
    actual_digest = sha256_file(provenance_path)
    if expected_digest is not None and actual_digest != expected_digest:
        errors.append(f"{provenance_file}: file SHA256 does not match {CHECKSUM_FILE_NAME}")

    provenance, provenance_errors = package_provenance.load_package_provenance(provenance_path)
    errors.extend(provenance_errors)
    if provenance is not None:
        errors.extend(
            package_provenance.validate_package_provenance(
                package_dir=package_dir,
                manifest=manifest,
                provenance=provenance,
                provenance_filename=provenance_file,
            )
        )
    return errors


def verify_enterprise_package(
    package_dir: Path,
    *,
    require_constraints: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    artifact_dir = package_dir.expanduser().resolve()
    errors: list[str] = []
    if not artifact_dir.is_dir():
        return None, [f"enterprise package directory does not exist: {artifact_dir}"]

    manifest_path = artifact_dir / MANIFEST_NAME
    checksum_path = artifact_dir / CHECKSUM_FILE_NAME
    if not manifest_path.is_file():
        errors.append(f"missing {MANIFEST_NAME}")
    if not checksum_path.is_file():
        errors.append(f"missing {CHECKSUM_FILE_NAME}")
    if errors:
        return None, errors

    manifest, manifest_errors = load_manifest(manifest_path)
    checksums, checksum_errors = parse_sha256s(checksum_path)
    errors.extend(manifest_errors)
    errors.extend(checksum_errors)
    if manifest is None:
        return None, errors

    errors.extend(validate_manifest_shape(manifest))
    if require_constraints and _constraints_file_entry(manifest) is None:
        errors.append(f"{MANIFEST_NAME}: constraints_file is required")
    errors.extend(verify_artifacts(artifact_dir, manifest, checksums))
    errors.extend(verify_provenance(artifact_dir, manifest, checksums))
    if errors:
        return None, errors

    return {
        "package_dir": artifact_dir,
        "source_ref": manifest["source_ref"],
        "source_commit": manifest["source_commit"],
        "package_version": manifest["package_version"],
        "artifact_count": len(manifest["artifacts"]),
        "provenance_present": bool(manifest.get("provenance_file")),
        "constraints_present": bool(_constraints_file_entry(manifest)),
    }, []


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package_dir",
        type=Path,
        help="Enterprise package artifact directory to verify.",
    )
    parser.add_argument(
        "--require-constraints",
        action="store_true",
        help=(
            "Fail when the package manifest does not declare the checked "
            "constraints.txt artifact."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    summary, errors = verify_enterprise_package(
        args.package_dir,
        require_constraints=args.require_constraints,
    )
    if errors:
        print("Enterprise package verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    assert summary is not None
    print("Enterprise package verification OK.")
    print(f"Package directory: {summary['package_dir']}")
    print(f"Source ref: {summary['source_ref']}")
    print(f"Source commit: {summary['source_commit']}")
    print(f"Package version: {summary['package_version']}")
    print(f"Artifact count: {summary['artifact_count']}")
    print(f"Package provenance: {summary['provenance_present']}")
    print(f"Install constraints: {summary['constraints_present']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
