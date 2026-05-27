#!/usr/bin/env python3
"""Verify enterprise Artifactory and signing evidence offline."""

from __future__ import annotations

import argparse
import json
import sys
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


ARTIFACTORY_EVIDENCE_NAME = "ARTIFACTORY_PROMOTION_EVIDENCE.json"
SIGNING_EVIDENCE_NAME = "SIGNING_ATTESTATION_EVIDENCE.json"
SIGNING_DOCUMENT_TYPE = "attackiq-cli-signing-attestation-evidence"
REQUIRED_PREDICATES = {
    "source_ref",
    "source_commit",
    "package_version",
    "subject filename",
    "subject sha256",
    "build/provenance document reference",
    "Artifactory target path when available",
}


def load_json_object(path: Path, *, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{label}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{label}: expected JSON object"]
    return data, []


def _as_dict(value: object, *, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{label}: expected object")
        return None
    return value


def _as_list(value: object, *, label: str, errors: list[str]) -> list[Any] | None:
    if not isinstance(value, list):
        errors.append(f"{label}: expected list")
        return None
    return value


def _validate_package_identity(
    evidence: dict[str, Any],
    *,
    manifest: dict[str, Any],
    package_dir: Path,
    label: str,
) -> list[str]:
    errors: list[str] = []
    package = _as_dict(evidence.get("package"), label=f"{label}: package", errors=errors)
    if package is None:
        return errors

    expected = {
        "source_ref": manifest.get("source_ref"),
        "source_commit": manifest.get("source_commit"),
        "package_version": manifest.get("package_version"),
        "public_repo_url": manifest.get("public_repo_url"),
        "package_directory_name": package_dir.name,
    }
    for key, expected_value in expected.items():
        if package.get(key) != expected_value:
            errors.append(f"{label}: package.{key} must match package manifest")
    return errors


def _target_errors(target: object, *, filename: str, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(target, dict):
        return [f"{label}: target must be an object"]
    path = target.get("path")
    if not isinstance(path, str) or not path:
        errors.append(f"{label}: target.path must be a non-empty string")
    elif (
        path.startswith("/")
        or "\\" in path
        or "?" in path
        or "#" in path
        or any(segment in {"", ".", ".."} for segment in path.split("/"))
        or (not path.endswith(f"/{filename}") and path != filename)
    ):
        errors.append(f"{label}: target.path is not a safe relative artifact path")

    url = target.get("url")
    if url is not None:
        if not isinstance(url, str) or not url:
            errors.append(f"{label}: target.url must be a non-empty string")
        else:
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"{label}: target.url must be an https URL")
            if parsed.username or parsed.password:
                errors.append(f"{label}: target.url must not include credentials")
            if parsed.query or parsed.fragment:
                errors.append(f"{label}: target.url must not include query strings or fragments")
            if isinstance(path, str) and path and not url.rstrip("/").endswith(path):
                errors.append(f"{label}: target.url must end with target.path")
    return errors


def _file_entry(
    package_dir: Path,
    filename: str,
    *,
    artifact_type: str,
    sha256: str | None = None,
    source: str | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = package_dir / filename
    digest = sha256 or enterprise_verifier.sha256_file(path)
    entry: dict[str, Any] = {
        "filename": filename,
        "type": artifact_type,
        "sha256": digest,
        "size_bytes": path.stat().st_size,
    }
    if source is not None:
        entry["source"] = source
    if target is not None:
        entry["target"] = target
    return entry


def expected_promotion_files(
    package_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        filename = artifact.get("filename")
        digest = artifact.get("sha256")
        artifact_type = artifact.get("type")
        if isinstance(filename, str) and isinstance(digest, str) and isinstance(artifact_type, str):
            entries[filename] = _file_entry(
                package_dir,
                filename,
                artifact_type=artifact_type,
                sha256=digest,
            )

    entries[enterprise_verifier.CHECKSUM_FILE_NAME] = _file_entry(
        package_dir,
        enterprise_verifier.CHECKSUM_FILE_NAME,
        artifact_type="checksums",
    )
    entries[enterprise_verifier.MANIFEST_NAME] = _file_entry(
        package_dir,
        enterprise_verifier.MANIFEST_NAME,
        artifact_type="promotion-manifest",
    )

    constraints_file = manifest.get("constraints_file")
    if isinstance(constraints_file, dict):
        filename = constraints_file.get("filename")
        digest = constraints_file.get("sha256")
        artifact_type = constraints_file.get("type")
        if isinstance(filename, str) and isinstance(digest, str):
            entries[filename] = _file_entry(
                package_dir,
                filename,
                artifact_type=(
                    artifact_type if isinstance(artifact_type, str) else "install-constraints"
                ),
                sha256=digest,
            )

    provenance_file = manifest.get("provenance_file")
    if isinstance(provenance_file, str):
        entries[provenance_file] = _file_entry(
            package_dir,
            provenance_file,
            artifact_type="package-provenance",
        )
    return entries


def _validate_named_entries(
    entries: list[Any],
    *,
    expected: dict[str, dict[str, Any]],
    label: str,
    require_target: bool = False,
) -> list[str]:
    errors: list[str] = []
    seen: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(entries):
        item_label = f"{label}[{index}]"
        entry = _as_dict(item, label=item_label, errors=errors)
        if entry is None:
            continue
        filename = entry.get("filename")
        if not isinstance(filename, str) or not enterprise_verifier.is_safe_artifact_name(filename):
            errors.append(f"{item_label}: filename must be a safe local filename")
            continue
        if filename in seen:
            errors.append(f"{item_label}: duplicate filename")
        seen[filename] = entry

    for filename, expected_entry in expected.items():
        entry = seen.get(filename)
        if entry is None:
            errors.append(f"{label}: missing entry for {filename}")
            continue
        for key in ("type", "sha256", "size_bytes"):
            if entry.get(key) != expected_entry.get(key):
                errors.append(f"{label}: {filename}.{key} must match local package artifact")
        target = entry.get("target")
        if target is not None:
            errors.extend(_target_errors(target, filename=filename, label=f"{label}: {filename}"))
        elif require_target:
            errors.append(f"{label}: {filename}.target is required")
        expected_target = expected_entry.get("target")
        if expected_target is not None and target != expected_target:
            errors.append(f"{label}: {filename}.target must match Artifactory evidence")

    for filename in sorted(set(seen) - set(expected)):
        errors.append(f"{label}: unexpected entry for {filename}")
    return errors


def _contains_required_check(checks: object, required_text: str, *, label: str) -> list[str]:
    if not isinstance(checks, list):
        return [f"{label}: expected list"]
    if not any(isinstance(item, str) and required_text in item for item in checks):
        return [f"{label}: missing {required_text}"]
    return []


def validate_artifactory_evidence(
    package_dir: Path,
    manifest: dict[str, Any],
    evidence: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    label = ARTIFACTORY_EVIDENCE_NAME
    if evidence.get("schema_version") != 1:
        errors.append(f"{label}: schema_version must be 1")
    errors.extend(
        _validate_package_identity(
            evidence,
            manifest=manifest,
            package_dir=package_dir,
            label=label,
        )
    )

    artifactory = _as_dict(
        evidence.get("artifactory"),
        label=f"{label}: artifactory",
        errors=errors,
    )
    if artifactory is not None:
        repository_url = artifactory.get("repository_url")
        if repository_url is not None:
            parsed = urlparse(repository_url) if isinstance(repository_url, str) else None
            if parsed is None or parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"{label}: artifactory.repository_url must be an https URL")
            elif parsed.username or parsed.password:
                errors.append(f"{label}: artifactory.repository_url must not include credentials")
        repository_path = artifactory.get("repository_path")
        if repository_path is not None and (
            not isinstance(repository_path, str)
            or repository_path.startswith("/")
            or "\\" in repository_path
            or any(segment in {"", ".", ".."} for segment in repository_path.split("/"))
        ):
            errors.append(f"{label}: artifactory.repository_path must be a safe relative path")

    expected = expected_promotion_files(package_dir, manifest)
    promotion_files = _as_list(
        evidence.get("promotion_files"),
        label=f"{label}: promotion_files",
        errors=errors,
    )
    if promotion_files is not None:
        errors.extend(
            _validate_named_entries(
                promotion_files,
                expected=expected,
                label=f"{label}: promotion_files",
            )
        )

    errors.extend(
        _contains_required_check(
            evidence.get("pre_upload_checks"),
            "--require-constraints",
            label=f"{label}: pre_upload_checks",
        )
    )
    errors.extend(
        _contains_required_check(
            evidence.get("post_upload_verification"),
            "--require-constraints",
            label=f"{label}: post_upload_verification",
        )
    )
    errors.extend(
        _contains_required_check(
            evidence.get("consumer_install_validation"),
            f"attackiq-cli=={manifest.get('package_version')}",
            label=f"{label}: consumer_install_validation",
        )
    )
    errors.extend(
        _contains_required_check(
            evidence.get("consumer_install_validation"),
            "constraints.txt",
            label=f"{label}: consumer_install_validation",
        )
    )
    return expected, errors


def expected_signing_subjects(
    package_dir: Path,
    manifest: dict[str, Any],
    artifactory_evidence: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if artifactory_evidence is None:
        return {
            filename: {
                **entry,
                "source": (
                    "enterprise-promotion-manifest"
                    if entry["type"] == "wheel"
                    else "package-directory"
                ),
            }
            for filename, entry in expected_promotion_files(package_dir, manifest).items()
        }

    subjects: dict[str, dict[str, Any]] = {}
    promotion_files = artifactory_evidence.get("promotion_files")
    if isinstance(promotion_files, list):
        for item in promotion_files:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename")
            artifact_type = item.get("type")
            digest = item.get("sha256")
            target = item.get("target")
            if (
                isinstance(filename, str)
                and isinstance(artifact_type, str)
                and isinstance(digest, str)
            ):
                subjects[filename] = _file_entry(
                    package_dir,
                    filename,
                    artifact_type=artifact_type,
                    sha256=digest,
                    source=ARTIFACTORY_EVIDENCE_NAME,
                    target=target if isinstance(target, dict) else None,
                )
    subjects[ARTIFACTORY_EVIDENCE_NAME] = _file_entry(
        package_dir,
        ARTIFACTORY_EVIDENCE_NAME,
        artifact_type="artifactory-promotion-evidence",
        source="package-directory",
    )
    return dict(sorted(subjects.items()))


def _expected_output_errors(outputs: object, *, subjects: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    output_items = _as_list(
        outputs,
        label=f"{SIGNING_EVIDENCE_NAME}: expected_outputs",
        errors=errors,
    )
    if output_items is None:
        return errors
    by_subject: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(output_items):
        label = f"{SIGNING_EVIDENCE_NAME}: expected_outputs[{index}]"
        output = _as_dict(item, label=label, errors=errors)
        if output is None:
            continue
        subject = output.get("subject")
        if not isinstance(subject, str):
            errors.append(f"{label}: subject must be a string")
            continue
        if subject in by_subject:
            errors.append(f"{label}: duplicate subject")
        by_subject[subject] = output

    for subject in subjects:
        output = by_subject.get(subject)
        if output is None:
            errors.append(f"{SIGNING_EVIDENCE_NAME}: expected_outputs missing {subject}")
            continue
        for key in ("signature_file", "attestation_file"):
            value = output.get(key)
            if (
                not isinstance(value, str)
                or not enterprise_verifier.is_safe_artifact_name(value)
                or not value.startswith(f"{subject}.")
            ):
                errors.append(
                    f"{SIGNING_EVIDENCE_NAME}: expected_outputs {subject}.{key} "
                    "must be a safe filename derived from the subject"
                )

    for subject in sorted(set(by_subject) - set(subjects)):
        errors.append(f"{SIGNING_EVIDENCE_NAME}: unexpected expected_outputs subject {subject}")
    return errors


def validate_signing_evidence(
    package_dir: Path,
    manifest: dict[str, Any],
    evidence: dict[str, Any],
    *,
    artifactory_evidence: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    label = SIGNING_EVIDENCE_NAME
    if evidence.get("schema_version") != 1:
        errors.append(f"{label}: schema_version must be 1")
    if evidence.get("document_type") != SIGNING_DOCUMENT_TYPE:
        errors.append(f"{label}: document_type must be {SIGNING_DOCUMENT_TYPE}")
    errors.extend(
        _validate_package_identity(
            evidence,
            manifest=manifest,
            package_dir=package_dir,
            label=label,
        )
    )

    signing = _as_dict(evidence.get("signing"), label=f"{label}: signing", errors=errors)
    if signing is not None:
        profile = signing.get("profile")
        if profile is not None and (not isinstance(profile, str) or "://" in profile):
            errors.append(f"{label}: signing.profile must be a public-safe profile name")

    subjects = _as_list(evidence.get("subjects"), label=f"{label}: subjects", errors=errors)
    expected_subjects = expected_signing_subjects(package_dir, manifest, artifactory_evidence)
    if subjects is not None:
        errors.extend(
            _validate_named_entries(
                subjects,
                expected=expected_subjects,
                label=f"{label}: subjects",
            )
        )
    errors.extend(
        _expected_output_errors(
            evidence.get("expected_outputs"),
            subjects=expected_subjects,
        )
    )

    predicates = evidence.get("predicate_requirements")
    if not isinstance(predicates, list) or not REQUIRED_PREDICATES.issubset(
        {item for item in predicates if isinstance(item, str)}
    ):
        errors.append(f"{label}: predicate_requirements must include required predicate fields")
    errors.extend(
        _contains_required_check(
            evidence.get("pre_signing_checks"),
            "--require-constraints",
            label=f"{label}: pre_signing_checks",
        )
    )
    errors.extend(
        _contains_required_check(
            evidence.get("post_signing_checks"),
            "--require-constraints",
            label=f"{label}: post_signing_checks",
        )
    )
    return errors


def verify_enterprise_evidence(
    package_dir: Path,
    *,
    require_artifactory: bool = False,
    require_signing: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    artifact_dir = package_dir.expanduser().resolve()
    summary, errors = enterprise_verifier.verify_enterprise_package(
        artifact_dir,
        require_constraints=True,
    )
    if errors:
        return None, errors
    assert summary is not None

    manifest, manifest_errors = enterprise_verifier.load_manifest(
        artifact_dir / enterprise_verifier.MANIFEST_NAME
    )
    if manifest is None:
        return None, manifest_errors

    artifactory_evidence: dict[str, Any] | None = None
    artifactory_path = artifact_dir / ARTIFACTORY_EVIDENCE_NAME
    artifactory_present = artifactory_path.is_file()
    promotion_count = 0
    if artifactory_present:
        artifactory_evidence, load_errors = load_json_object(
            artifactory_path,
            label=ARTIFACTORY_EVIDENCE_NAME,
        )
        errors.extend(load_errors)
        if artifactory_evidence is not None:
            expected_promotions, artifactory_errors = validate_artifactory_evidence(
                artifact_dir,
                manifest,
                artifactory_evidence,
            )
            promotion_count = len(expected_promotions)
            errors.extend(artifactory_errors)
    elif require_artifactory:
        errors.append(f"missing {ARTIFACTORY_EVIDENCE_NAME}")

    signing_path = artifact_dir / SIGNING_EVIDENCE_NAME
    signing_present = signing_path.is_file()
    signing_subject_count = 0
    if signing_present:
        signing_evidence, load_errors = load_json_object(signing_path, label=SIGNING_EVIDENCE_NAME)
        errors.extend(load_errors)
        if signing_evidence is not None:
            expected_subjects = expected_signing_subjects(
                artifact_dir,
                manifest,
                artifactory_evidence,
            )
            signing_subject_count = len(expected_subjects)
            errors.extend(
                validate_signing_evidence(
                    artifact_dir,
                    manifest,
                    signing_evidence,
                    artifactory_evidence=artifactory_evidence,
                )
            )
    elif require_signing:
        errors.append(f"missing {SIGNING_EVIDENCE_NAME}")

    if errors:
        return None, errors
    return {
        **summary,
        "artifactory_evidence": artifactory_present,
        "signing_evidence": signing_present,
        "promotion_file_count": promotion_count,
        "signing_subject_count": signing_subject_count,
    }, []


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package_dir",
        type=Path,
        help="Enterprise package artifact directory to verify.",
    )
    parser.add_argument(
        "--require-artifactory",
        action="store_true",
        help=f"Fail when {ARTIFACTORY_EVIDENCE_NAME} is missing.",
    )
    parser.add_argument(
        "--require-signing",
        action="store_true",
        help=f"Fail when {SIGNING_EVIDENCE_NAME} is missing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    summary, errors = verify_enterprise_evidence(
        args.package_dir,
        require_artifactory=args.require_artifactory,
        require_signing=args.require_signing,
    )
    if errors:
        print("Enterprise evidence verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    assert summary is not None
    print("Enterprise evidence verification OK.")
    print(f"Package directory: {summary['package_dir']}")
    print(f"Source ref: {summary['source_ref']}")
    print(f"Source commit: {summary['source_commit']}")
    print(f"Package version: {summary['package_version']}")
    print(f"Artifactory evidence: {summary['artifactory_evidence']}")
    print(f"Promotion files: {summary['promotion_file_count']}")
    print(f"Signing evidence: {summary['signing_evidence']}")
    print(f"Signing subjects: {summary['signing_subject_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
