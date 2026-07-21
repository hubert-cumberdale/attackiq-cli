#!/usr/bin/env python3
"""Build public-safe Artifactory promotion evidence from enterprise package artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from scripts import verify_enterprise_package as enterprise_verifier
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback.
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import verify_enterprise_package as enterprise_verifier  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_NAME = "ARTIFACTORY_PROMOTION_EVIDENCE.json"
SAFE_REPOSITORY_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+@=-]*$")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_artifactory_url(url: str | None) -> str | None:
    if url is None:
        return None
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        raise RuntimeError("Artifactory URL must not include embedded credentials")
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("Artifactory URL must be an https URL")
    if parsed.query or parsed.fragment:
        raise RuntimeError("Artifactory URL must not include query strings or fragments")
    return url.rstrip("/")


def validate_repository_path(repository_path: str | None) -> str | None:
    if repository_path is None:
        return None
    if "://" in repository_path:
        raise RuntimeError("repository path must be relative, not a URL")
    if "\\" in repository_path or "?" in repository_path or "#" in repository_path:
        raise RuntimeError("repository path must not include URL syntax")
    normalized = repository_path.strip("/")
    if not normalized:
        raise RuntimeError("repository path must not be empty")
    for segment in normalized.split("/"):
        if segment in {"", ".", ".."}:
            raise RuntimeError(
                "repository path must not contain empty, current, or parent segments"
            )
        if not SAFE_REPOSITORY_SEGMENT_RE.fullmatch(segment):
            raise RuntimeError(f"repository path contains an unsafe segment: {segment}")
    return normalized


def ensure_output_path(output_path: Path, *, root: Path = ROOT, overwrite: bool = False) -> Path:
    resolved = output_path.expanduser().resolve()
    repo_root = root.resolve()
    if resolved == repo_root or is_relative_to(resolved, repo_root):
        raise RuntimeError("promotion evidence output path must be outside the source repo")
    if resolved.exists() and not overwrite:
        raise RuntimeError(f"promotion evidence output already exists: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _load_verified_manifest(package_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest_path = package_dir / enterprise_verifier.MANIFEST_NAME
    checksum_path = package_dir / enterprise_verifier.CHECKSUM_FILE_NAME
    manifest, manifest_errors = enterprise_verifier.load_manifest(manifest_path)
    checksums, checksum_errors = enterprise_verifier.parse_sha256s(checksum_path)
    errors = manifest_errors + checksum_errors
    if manifest is None:
        raise RuntimeError("package manifest could not be loaded")
    if errors:
        raise RuntimeError("package metadata could not be loaded:\n- " + "\n- ".join(errors))
    return manifest, checksums


def _target_for(
    filename: str,
    *,
    artifactory_url: str | None,
    repository_path: str | None,
) -> dict[str, str]:
    target_path = f"{repository_path}/{filename}" if repository_path else filename
    result = {"path": target_path}
    if artifactory_url:
        result["url"] = f"{artifactory_url}/{target_path}"
    return result


def _file_entry(
    package_dir: Path,
    filename: str,
    *,
    artifact_type: str,
    artifactory_url: str | None,
    repository_path: str | None,
    sha256: str | None = None,
) -> dict[str, Any]:
    if not enterprise_verifier.is_safe_artifact_name(filename):
        raise RuntimeError(f"unsafe promotion filename: {filename}")
    path = package_dir / filename
    if not path.is_file():
        raise RuntimeError(f"promotion file is missing: {filename}")
    digest = sha256 or enterprise_verifier.sha256_file(path)
    return {
        "filename": filename,
        "type": artifact_type,
        "sha256": digest,
        "size_bytes": path.stat().st_size,
        "target": _target_for(
            filename,
            artifactory_url=artifactory_url,
            repository_path=repository_path,
        ),
    }


def build_artifactory_promotion_evidence(
    package_dir: Path,
    *,
    artifactory_url: str | None = None,
    repository_path: str | None = None,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    artifact_dir = package_dir.expanduser().resolve()
    summary, errors = enterprise_verifier.verify_enterprise_package(
        artifact_dir,
        require_constraints=True,
    )
    if errors:
        raise RuntimeError("enterprise package verification failed:\n- " + "\n- ".join(errors))
    assert summary is not None

    safe_url = validate_artifactory_url(artifactory_url)
    safe_repository_path = validate_repository_path(repository_path)
    manifest, checksums = _load_verified_manifest(artifact_dir)

    promotion_files: list[dict[str, Any]] = []
    for artifact in manifest["artifacts"]:
        promotion_files.append(
            _file_entry(
                artifact_dir,
                artifact["filename"],
                artifact_type=artifact["type"],
                sha256=artifact["sha256"],
                artifactory_url=safe_url,
                repository_path=safe_repository_path,
            )
        )
    promotion_files.append(
        _file_entry(
            artifact_dir,
            enterprise_verifier.CHECKSUM_FILE_NAME,
            artifact_type="checksums",
            artifactory_url=safe_url,
            repository_path=safe_repository_path,
        )
    )
    promotion_files.append(
        _file_entry(
            artifact_dir,
            enterprise_verifier.MANIFEST_NAME,
            artifact_type="promotion-manifest",
            artifactory_url=safe_url,
            repository_path=safe_repository_path,
        )
    )
    constraints_file = manifest.get("constraints_file")
    if isinstance(constraints_file, dict):
        constraints_filename = constraints_file.get("filename")
        constraints_sha256 = constraints_file.get("sha256")
        constraints_type = constraints_file.get("type")
        if isinstance(constraints_filename, str) and isinstance(constraints_sha256, str):
            promotion_files.append(
                _file_entry(
                    artifact_dir,
                    constraints_filename,
                    artifact_type=(
                        constraints_type
                        if isinstance(constraints_type, str)
                        else "install-constraints"
                    ),
                    sha256=constraints_sha256,
                    artifactory_url=safe_url,
                    repository_path=safe_repository_path,
                )
            )
    provenance_file = manifest.get("provenance_file")
    if isinstance(provenance_file, str):
        promotion_files.append(
            _file_entry(
                artifact_dir,
                provenance_file,
                artifact_type="package-provenance",
                sha256=checksums.get(provenance_file),
                artifactory_url=safe_url,
                repository_path=safe_repository_path,
            )
        )
    sbom_file = manifest.get("sbom_file")
    if isinstance(sbom_file, dict):
        sbom_filename = sbom_file.get("filename")
        sbom_sha256 = sbom_file.get("sha256")
        sbom_type = sbom_file.get("type")
        if isinstance(sbom_filename, str) and isinstance(sbom_sha256, str):
            promotion_files.append(
                _file_entry(
                    artifact_dir,
                    sbom_filename,
                    artifact_type=sbom_type if isinstance(sbom_type, str) else "spdx-json",
                    sha256=sbom_sha256,
                    artifactory_url=safe_url,
                    repository_path=safe_repository_path,
                )
            )
    dependency_integrity_file = manifest.get("dependency_integrity_file")
    if isinstance(dependency_integrity_file, dict):
        dependency_integrity_filename = dependency_integrity_file.get("filename")
        dependency_integrity_sha256 = dependency_integrity_file.get("sha256")
        dependency_integrity_type = dependency_integrity_file.get("type")
        if isinstance(dependency_integrity_filename, str) and isinstance(
            dependency_integrity_sha256,
            str,
        ):
            promotion_files.append(
                _file_entry(
                    artifact_dir,
                    dependency_integrity_filename,
                    artifact_type=(
                        dependency_integrity_type
                        if isinstance(dependency_integrity_type, str)
                        else "dependency-integrity-json"
                    ),
                    sha256=dependency_integrity_sha256,
                    artifactory_url=safe_url,
                    repository_path=safe_repository_path,
                )
            )

    package_version = summary["package_version"]
    generated = generated_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": 1,
        "generated_utc": generated,
        "package": {
            "source_ref": summary["source_ref"],
            "source_commit": summary["source_commit"],
            "package_version": package_version,
            "public_repo_url": manifest["public_repo_url"],
            "build_created_utc": manifest.get("build_created_utc"),
            "package_directory_name": artifact_dir.name,
        },
        "artifactory": {
            "repository_url": safe_url,
            "repository_path": safe_repository_path,
            "credential_policy": (
                "registry credentials are operator-owned and must stay in enterprise secret "
                "storage, environment variables, or approved package-manager configuration"
            ),
            "tls_policy": "repository URLs must use https and must not include credentials",
        },
        "promotion_files": promotion_files,
        "pre_upload_checks": [
            "python3 scripts/verify_enterprise_package.py <package-dir> --require-constraints",
            "confirm the package directory is outside git and contains no tenant payloads",
            "confirm Artifactory credentials are not embedded in commands, URLs, files, or logs",
        ],
        "post_upload_verification": [
            "download the uploaded files into a clean directory outside git",
            "python3 scripts/verify_enterprise_package.py <downloaded-package-dir> "
            "--require-constraints",
            "compare the downloaded artifact SHA256 values with this evidence file",
        ],
        "consumer_install_validation": [
            "python -m pip install -c constraints.txt --index-url <artifactory-python-index-url> "
            f"attackiq-cli=={package_version}",
            "attackiq --version",
            "attackiq config validate",
        ],
        "operator_owned_controls": [
            "Artifactory upload credentials",
            "artifact signing",
            "registry attestation",
            "enterprise change-ticket approval",
        ],
        "retention_policy": [
            "do not commit this evidence file if it contains internal repository coordinates",
            "do not retain bearer tokens, browser cookies, raw API responses, or tenant payloads",
        ],
    }


def write_evidence(evidence: dict[str, Any], output_path: Path) -> Path:
    output_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package_dir",
        type=Path,
        help="Verified enterprise package directory produced from a public release tag.",
    )
    parser.add_argument(
        "--artifactory-url",
        help=(
            "HTTPS Artifactory base URL. Must not include credentials, query strings, "
            "or fragments."
        ),
    )
    parser.add_argument(
        "--repository-path",
        help="Relative Artifactory repository/path prefix for the promoted files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Evidence JSON output path outside the source repo. Defaults to "
            "<package-dir>/ARTIFACTORY_PROMOTION_EVIDENCE.json."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing evidence output file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        artifact_dir = args.package_dir.expanduser().resolve()
        evidence = build_artifactory_promotion_evidence(
            artifact_dir,
            artifactory_url=args.artifactory_url,
            repository_path=args.repository_path,
        )
        output_path = ensure_output_path(
            args.output or artifact_dir / EVIDENCE_NAME,
            overwrite=args.overwrite,
        )
        write_evidence(evidence, output_path)
    except RuntimeError as exc:
        print("Artifactory promotion evidence failed:", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        return 1

    print("Artifactory promotion evidence OK.")
    print(f"Evidence: {output_path}")
    print(f"Package version: {evidence['package']['package_version']}")
    print(f"Promotion files: {len(evidence['promotion_files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
