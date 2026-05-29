#!/usr/bin/env python3
"""Build credential-free signing and attestation evidence for enterprise packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import verify_enterprise_package as enterprise_verifier
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback.
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import verify_enterprise_package as enterprise_verifier  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTORY_EVIDENCE_NAME = "ARTIFACTORY_PROMOTION_EVIDENCE.json"
EVIDENCE_NAME = "SIGNING_ATTESTATION_EVIDENCE.json"
SAFE_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+=/-]{0,127}$")
SAFE_SUFFIX_RE = re.compile(r"^\.[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
UNSAFE_PROFILE_RE = re.compile(
    r"(password|secret|token|credential|private[ _-]?key|BEGIN)",
    re.IGNORECASE,
)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def ensure_output_path(output_path: Path, *, root: Path = ROOT, overwrite: bool = False) -> Path:
    resolved = output_path.expanduser().resolve()
    repo_root = root.resolve()
    if resolved == repo_root or is_relative_to(resolved, repo_root):
        raise RuntimeError("signing evidence output path must be outside the source repo")
    if resolved.exists() and not overwrite:
        raise RuntimeError(f"signing evidence output already exists: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def validate_signing_profile(signing_profile: str | None) -> str | None:
    if signing_profile is None:
        return None
    value = signing_profile.strip()
    if not value:
        raise RuntimeError("signing profile must not be empty")
    if "://" in value:
        raise RuntimeError("signing profile must be a profile name, not a URL")
    if "\n" in value or "\r" in value:
        raise RuntimeError("signing profile must be a single line")
    if UNSAFE_PROFILE_RE.search(value):
        raise RuntimeError("signing profile must not contain secret-like material")
    if not SAFE_PROFILE_RE.fullmatch(value):
        raise RuntimeError("signing profile contains unsupported characters")
    return value


def validate_output_suffix(value: str, *, label: str) -> str:
    if "/" in value or "\\" in value:
        raise RuntimeError(f"{label} must be a filename suffix, not a path")
    if not SAFE_SUFFIX_RE.fullmatch(value):
        raise RuntimeError(f"{label} must start with '.' and contain only safe filename characters")
    return value


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{label}: expected JSON object")
    return data


def _load_manifest(package_dir: Path) -> dict[str, Any]:
    manifest_path = package_dir / enterprise_verifier.MANIFEST_NAME
    manifest, errors = enterprise_verifier.load_manifest(manifest_path)
    if errors:
        raise RuntimeError("package manifest could not be loaded:\n- " + "\n- ".join(errors))
    assert manifest is not None
    return manifest


def _base_subjects(package_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    subjects: list[dict[str, Any]] = []
    for artifact in manifest["artifacts"]:
        filename = artifact["filename"]
        subjects.append(
            _subject_from_file(
                package_dir,
                filename,
                subject_type=artifact["type"],
                sha256=artifact["sha256"],
                source="enterprise-promotion-manifest",
            )
        )

    subjects.append(
        _subject_from_file(
            package_dir,
            enterprise_verifier.CHECKSUM_FILE_NAME,
            subject_type="checksums",
            source="package-directory",
        )
    )
    subjects.append(
        _subject_from_file(
            package_dir,
            enterprise_verifier.MANIFEST_NAME,
            subject_type="promotion-manifest",
            source="package-directory",
        )
    )
    constraints_file = manifest.get("constraints_file")
    if isinstance(constraints_file, dict):
        constraints_filename = constraints_file.get("filename")
        constraints_sha256 = constraints_file.get("sha256")
        constraints_type = constraints_file.get("type")
        if isinstance(constraints_filename, str) and isinstance(constraints_sha256, str):
            subjects.append(
                _subject_from_file(
                    package_dir,
                    constraints_filename,
                    subject_type=(
                        constraints_type
                        if isinstance(constraints_type, str)
                        else "install-constraints"
                    ),
                    sha256=constraints_sha256,
                    source="package-directory",
                )
            )

    provenance_file = manifest.get("provenance_file")
    if isinstance(provenance_file, str):
        subjects.append(
            _subject_from_file(
                package_dir,
                provenance_file,
                subject_type="package-provenance",
                source="package-directory",
            )
        )
    sbom_file = manifest.get("sbom_file")
    if isinstance(sbom_file, dict):
        sbom_filename = sbom_file.get("filename")
        sbom_sha256 = sbom_file.get("sha256")
        sbom_type = sbom_file.get("type")
        if isinstance(sbom_filename, str) and isinstance(sbom_sha256, str):
            subjects.append(
                _subject_from_file(
                    package_dir,
                    sbom_filename,
                    subject_type=sbom_type if isinstance(sbom_type, str) else "spdx-json",
                    sha256=sbom_sha256,
                    source="package-directory",
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
            subjects.append(
                _subject_from_file(
                    package_dir,
                    dependency_integrity_filename,
                    subject_type=(
                        dependency_integrity_type
                        if isinstance(dependency_integrity_type, str)
                        else "dependency-integrity-json"
                    ),
                    sha256=dependency_integrity_sha256,
                    source="package-directory",
                )
            )
    return subjects


def _subject_from_file(
    package_dir: Path,
    filename: str,
    *,
    subject_type: str,
    source: str,
    sha256: str | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not enterprise_verifier.is_safe_artifact_name(filename):
        raise RuntimeError(f"unsafe signing subject filename: {filename}")
    path = package_dir / filename
    if not path.is_file():
        raise RuntimeError(f"signing subject file is missing: {filename}")
    digest = sha256 or enterprise_verifier.sha256_file(path)
    actual_digest = enterprise_verifier.sha256_file(path)
    if actual_digest != digest:
        raise RuntimeError(f"{filename}: subject SHA256 does not match local file")
    subject: dict[str, Any] = {
        "filename": filename,
        "type": subject_type,
        "sha256": digest,
        "size_bytes": path.stat().st_size,
        "source": source,
    }
    if target:
        subject["target"] = target
    return subject


def _load_artifactory_subjects(package_dir: Path) -> list[dict[str, Any]]:
    evidence_path = package_dir / ARTIFACTORY_EVIDENCE_NAME
    if not evidence_path.is_file():
        return []
    evidence = _load_json_object(evidence_path, label=ARTIFACTORY_EVIDENCE_NAME)
    promotion_files = evidence.get("promotion_files")
    if not isinstance(promotion_files, list):
        raise RuntimeError(f"{ARTIFACTORY_EVIDENCE_NAME}: promotion_files must be a list")

    subjects: list[dict[str, Any]] = []
    for index, promotion_file in enumerate(promotion_files):
        label = f"{ARTIFACTORY_EVIDENCE_NAME}: promotion_files[{index}]"
        if not isinstance(promotion_file, dict):
            raise RuntimeError(f"{label}: expected object")
        filename = promotion_file.get("filename")
        subject_type = promotion_file.get("type")
        sha256 = promotion_file.get("sha256")
        target = promotion_file.get("target")
        if not isinstance(filename, str):
            raise RuntimeError(f"{label}: filename must be a string")
        if not isinstance(subject_type, str):
            raise RuntimeError(f"{label}: type must be a string")
        if not isinstance(sha256, str):
            raise RuntimeError(f"{label}: sha256 must be a string")
        if target is not None and not isinstance(target, dict):
            raise RuntimeError(f"{label}: target must be an object")
        subjects.append(
            _subject_from_file(
                package_dir,
                filename,
                subject_type=subject_type,
                sha256=sha256,
                source=ARTIFACTORY_EVIDENCE_NAME,
                target=target,
            )
        )

    subjects.append(
        _subject_from_file(
            package_dir,
            ARTIFACTORY_EVIDENCE_NAME,
            subject_type="artifactory-promotion-evidence",
            source="package-directory",
        )
    )
    return subjects


def _dedupe_subjects(subjects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for subject in subjects:
        filename = subject["filename"]
        if filename in deduped and deduped[filename]["sha256"] != subject["sha256"]:
            raise RuntimeError(f"{filename}: conflicting signing subject SHA256 values")
        existing = deduped.get(filename)
        if existing is None or subject["source"] == ARTIFACTORY_EVIDENCE_NAME:
            deduped[filename] = subject
    return [deduped[filename] for filename in sorted(deduped)]


def _expected_outputs(
    subjects: list[dict[str, Any]],
    *,
    signature_suffix: str,
    attestation_suffix: str,
) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    for subject in subjects:
        filename = subject["filename"]
        outputs.append(
            {
                "subject": filename,
                "signature_file": f"{filename}{signature_suffix}",
                "attestation_file": f"{filename}{attestation_suffix}",
            }
        )
    return outputs


def build_signing_attestation_evidence(
    package_dir: Path,
    *,
    signing_profile: str | None = None,
    signature_suffix: str = ".sig",
    attestation_suffix: str = ".intoto.jsonl",
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

    safe_profile = validate_signing_profile(signing_profile)
    safe_signature_suffix = validate_output_suffix(signature_suffix, label="signature suffix")
    safe_attestation_suffix = validate_output_suffix(attestation_suffix, label="attestation suffix")
    manifest = _load_manifest(artifact_dir)
    subjects = _dedupe_subjects(
        _base_subjects(artifact_dir, manifest) + _load_artifactory_subjects(artifact_dir)
    )
    package_version = summary["package_version"]
    generated = generated_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": 1,
        "generated_utc": generated,
        "document_type": "attackiq-cli-signing-attestation-evidence",
        "package": {
            "source_ref": summary["source_ref"],
            "source_commit": summary["source_commit"],
            "package_version": package_version,
            "public_repo_url": manifest["public_repo_url"],
            "package_directory_name": artifact_dir.name,
        },
        "signing": {
            "profile": safe_profile,
            "credential_policy": (
                "private keys, signing tokens, certificates, passwords, and registry credentials "
                "must remain in enterprise signing infrastructure and must not be written here"
            ),
            "execution_policy": (
                "this repository records signing subjects and expected evidence only; signing, "
                "attestation, upload, and verification against enterprise trust roots are "
                "operator-owned"
            ),
        },
        "subjects": subjects,
        "expected_outputs": _expected_outputs(
            subjects,
            signature_suffix=safe_signature_suffix,
            attestation_suffix=safe_attestation_suffix,
        ),
        "predicate_requirements": [
            "source_ref",
            "source_commit",
            "package_version",
            "subject filename",
            "subject sha256",
            "build/provenance document reference",
            "Artifactory target path when available",
        ],
        "pre_signing_checks": [
            "python3 scripts/verify_enterprise_package.py <package-dir> --require-constraints",
            "python3 scripts/build_artifactory_promotion_evidence.py <package-dir> --output <file>",
            "compare each subject SHA256 with this evidence file before signing",
        ],
        "post_signing_checks": [
            "verify detached signatures with the enterprise trust root",
            "verify attestations bind each subject filename and SHA256",
            "download promoted artifacts into a clean directory and rerun package verification "
            "with --require-constraints",
        ],
        "retention_policy": [
            "do not commit this evidence file if it contains internal signing or registry details",
            "do not retain signing keys, bearer tokens, browser cookies, raw API responses, or "
            "tenant payloads",
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
        help="Verified enterprise package directory to prepare for signing and attestation.",
    )
    parser.add_argument(
        "--signing-profile",
        help="Public-safe enterprise signing profile name. Do not pass keys or credentials.",
    )
    parser.add_argument(
        "--signature-suffix",
        default=".sig",
        help="Detached signature filename suffix. Defaults to .sig.",
    )
    parser.add_argument(
        "--attestation-suffix",
        default=".intoto.jsonl",
        help="Attestation filename suffix. Defaults to .intoto.jsonl.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Evidence JSON output path outside the source repo. Defaults to "
            "<package-dir>/SIGNING_ATTESTATION_EVIDENCE.json."
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
        evidence = build_signing_attestation_evidence(
            artifact_dir,
            signing_profile=args.signing_profile,
            signature_suffix=args.signature_suffix,
            attestation_suffix=args.attestation_suffix,
        )
        output_path = ensure_output_path(
            args.output or artifact_dir / EVIDENCE_NAME,
            overwrite=args.overwrite,
        )
        write_evidence(evidence, output_path)
    except RuntimeError as exc:
        print("Signing and attestation evidence failed:", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        return 1

    print("Signing and attestation evidence OK.")
    print(f"Evidence: {output_path}")
    print(f"Package version: {evidence['package']['package_version']}")
    print(f"Subjects: {len(evidence['subjects'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
