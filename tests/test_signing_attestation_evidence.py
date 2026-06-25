from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "build_signing_attestation_evidence.py"
)
_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "build_signing_attestation_evidence",
    _SCRIPT_PATH,
)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
signing_evidence = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = signing_evidence
_SCRIPT_SPEC.loader.exec_module(signing_evidence)


def write_package_dir(
    package_dir: Path,
    *,
    include_artifactory: bool = False,
    include_constraints: bool = True,
) -> Path:
    package_dir.mkdir()
    wheel_path = package_dir / "attackiq_cli-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr("attackiq_cli/__init__.py", '__version__ = "1.2.3"\n')
        wheel.writestr(
            "attackiq_cli-1.2.3.dist-info/METADATA",
            "Metadata-Version: 2.1\n"
            "Name: attackiq-cli\n"
            "Version: 1.2.3\n"
            "Requires-Python: >=3.10\n"
            "Requires-Dist: httpx>=0.27,<0.28\n",
        )
    wheel_sha256 = signing_evidence.enterprise_verifier.sha256_file(wheel_path)
    constraints_path = package_dir / signing_evidence.enterprise_verifier.CONSTRAINTS_FILE_NAME
    constraints_sha256 = ""
    if include_constraints:
        constraints_path.write_text("httpx==0.27.2\n", encoding="utf-8")
        constraints_sha256 = signing_evidence.enterprise_verifier.sha256_file(constraints_path)

    manifest = {
        "schema_version": 1,
        "public_repo_url": "https://example.invalid/attackiq-cli.git",
        "source_ref": "v1.2.3",
        "source_commit": "abc123",
        "package_version": "1.2.3",
        "build_created_utc": "2026-05-26T00:00:00+00:00",
        "python_version": "3.12.3",
        "artifacts": [
            {
                "filename": wheel_path.name,
                "sha256": wheel_sha256,
                "type": "wheel",
            }
        ],
        "checksum_file": signing_evidence.enterprise_verifier.CHECKSUM_FILE_NAME,
        "provenance_file": signing_evidence.enterprise_verifier.PROVENANCE_NAME,
        "package_policy": "validated wheel for enterprise package repository promotion",
        "artifactory_policy": "upload is operator-owned; credentials are not accepted or stored",
        "sbom_policy": "offline package provenance and dependency inventory are generated",
        "validation_commands": [],
    }
    if include_constraints:
        manifest["constraints_file"] = {
            "filename": constraints_path.name,
            "sha256": constraints_sha256,
            "type": "install-constraints",
        }
        dependency_integrity = (
            signing_evidence.enterprise_verifier.package_dependency_integrity.build_dependency_integrity(
                constraints_path=constraints_path,
                constraints_sha256=constraints_sha256,
                generated_utc="2026-05-26T00:00:00+00:00",
            )
        )
        dependency_integrity_path = (
            signing_evidence.enterprise_verifier.package_dependency_integrity.write_dependency_integrity(
                package_dir,
                dependency_integrity,
            )
        )
        manifest["dependency_integrity_file"] = {
            "filename": dependency_integrity_path.name,
            "sha256": signing_evidence.enterprise_verifier.sha256_file(
                dependency_integrity_path
            ),
            "type": "dependency-integrity-json",
        }

    manifest_path = package_dir / signing_evidence.enterprise_verifier.MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    provenance = signing_evidence.enterprise_verifier.package_provenance.build_package_provenance(
        package_dir=package_dir,
        manifest=manifest,
        manifest_filename=signing_evidence.enterprise_verifier.MANIFEST_NAME,
        wheel_path=wheel_path,
        wheel_sha256=wheel_sha256,
        checksum_filename=signing_evidence.enterprise_verifier.CHECKSUM_FILE_NAME,
        generated_utc="2026-05-26T00:00:00+00:00",
    )
    write_provenance = (
        signing_evidence.enterprise_verifier.package_provenance.write_package_provenance
    )
    provenance_path = write_provenance(package_dir, provenance)
    provenance_sha256 = signing_evidence.enterprise_verifier.sha256_file(provenance_path)

    checksum_path = package_dir / signing_evidence.enterprise_verifier.CHECKSUM_FILE_NAME
    checksum_lines = [
        f"{provenance_sha256}  {provenance_path.name}\n",
        f"{wheel_sha256}  {wheel_path.name}\n",
    ]
    if include_constraints:
        checksum_lines.insert(0, f"{constraints_sha256}  {constraints_path.name}\n")
        checksum_lines.insert(
            1,
            f"{signing_evidence.enterprise_verifier.sha256_file(dependency_integrity_path)}  "
            f"{dependency_integrity_path.name}\n",
        )
    checksum_path.write_text(
        "".join(checksum_lines),
        encoding="utf-8",
    )

    if include_artifactory and not include_constraints:
        raise ValueError("artifactory test fixture requires constraints")

    if include_artifactory:
        promotion_manifest_sha256 = signing_evidence.enterprise_verifier.sha256_file(manifest_path)
        checksum_sha256 = signing_evidence.enterprise_verifier.sha256_file(checksum_path)
        artifactory_evidence = {
            "schema_version": 1,
            "promotion_files": [
                {
                    "filename": wheel_path.name,
                    "type": "wheel",
                    "sha256": wheel_sha256,
                    "size_bytes": wheel_path.stat().st_size,
                    "target": {"path": f"api/pypi/attackiq/{wheel_path.name}"},
                },
                {
                    "filename": checksum_path.name,
                    "type": "checksums",
                    "sha256": checksum_sha256,
                    "size_bytes": checksum_path.stat().st_size,
                    "target": {"path": f"api/pypi/attackiq/{checksum_path.name}"},
                },
                {
                    "filename": manifest_path.name,
                    "type": "promotion-manifest",
                    "sha256": promotion_manifest_sha256,
                    "size_bytes": manifest_path.stat().st_size,
                    "target": {"path": f"api/pypi/attackiq/{manifest_path.name}"},
                },
                {
                    "filename": constraints_path.name,
                    "type": "install-constraints",
                    "sha256": constraints_sha256,
                    "size_bytes": constraints_path.stat().st_size,
                    "target": {"path": f"api/pypi/attackiq/{constraints_path.name}"},
                },
                {
                    "filename": dependency_integrity_path.name,
                    "type": "dependency-integrity-json",
                    "sha256": signing_evidence.enterprise_verifier.sha256_file(
                        dependency_integrity_path
                    ),
                    "size_bytes": dependency_integrity_path.stat().st_size,
                    "target": {"path": f"api/pypi/attackiq/{dependency_integrity_path.name}"},
                },
                {
                    "filename": provenance_path.name,
                    "type": "package-provenance",
                    "sha256": provenance_sha256,
                    "size_bytes": provenance_path.stat().st_size,
                    "target": {"path": f"api/pypi/attackiq/{provenance_path.name}"},
                },
            ],
        }
        (package_dir / signing_evidence.ARTIFACTORY_EVIDENCE_NAME).write_text(
            json.dumps(artifactory_evidence, indent=2) + "\n",
            encoding="utf-8",
        )

    return wheel_path


def test_build_signing_attestation_evidence_uses_artifactory_targets(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir, include_artifactory=True)

    evidence = signing_evidence.build_signing_attestation_evidence(
        package_dir,
        signing_profile="enterprise-release",
        generated_utc="2026-05-26T00:00:00+00:00",
    )

    assert evidence["package"]["source_ref"] == "v1.2.3"
    assert evidence["signing"]["profile"] == "enterprise-release"
    filenames = {subject["filename"] for subject in evidence["subjects"]}
    assert filenames == {
        wheel_path.name,
        signing_evidence.enterprise_verifier.CHECKSUM_FILE_NAME,
        signing_evidence.enterprise_verifier.MANIFEST_NAME,
        signing_evidence.enterprise_verifier.PROVENANCE_NAME,
        signing_evidence.enterprise_verifier.CONSTRAINTS_FILE_NAME,
        signing_evidence.enterprise_verifier.DEPENDENCY_INTEGRITY_NAME,
        signing_evidence.ARTIFACTORY_EVIDENCE_NAME,
    }
    wheel_subject = next(
        subject for subject in evidence["subjects"] if subject["filename"] == wheel_path.name
    )
    assert wheel_subject["source"] == signing_evidence.ARTIFACTORY_EVIDENCE_NAME
    assert wheel_subject["target"]["path"].endswith(wheel_path.name)

    assert (
        "python3 scripts/verify_enterprise_package.py <package-dir> --require-constraints"
        in evidence["pre_signing_checks"]
    )
    assert any("--require-constraints" in check for check in evidence["post_signing_checks"])

    outputs = {item["subject"]: item for item in evidence["expected_outputs"]}
    assert outputs[wheel_path.name]["signature_file"] == f"{wheel_path.name}.sig"
    assert outputs[wheel_path.name]["attestation_file"] == f"{wheel_path.name}.intoto.jsonl"

    external_fields = evidence["external_evidence_fields"]
    assert "signature_sha256" in external_fields["signature_verification"]
    assert "predicate_fields_verified" in external_fields["attestation_verification"]
    assert "trust_root_identifier" in external_fields["trust_root_verification"]
    assert "private trust-root paths" in external_fields["public_repository_excluded_values"]


def test_build_signing_attestation_evidence_accepts_package_without_artifactory(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir)

    evidence = signing_evidence.build_signing_attestation_evidence(package_dir)

    filenames = {subject["filename"] for subject in evidence["subjects"]}
    assert wheel_path.name in filenames
    assert signing_evidence.enterprise_verifier.CONSTRAINTS_FILE_NAME in filenames
    assert signing_evidence.ARTIFACTORY_EVIDENCE_NAME not in filenames


def test_build_signing_attestation_evidence_rejects_invalid_package(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)
    (package_dir / signing_evidence.enterprise_verifier.CHECKSUM_FILE_NAME).write_text(
        "",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="enterprise package verification failed"):
        signing_evidence.build_signing_attestation_evidence(package_dir)


def test_build_signing_attestation_evidence_requires_constraints(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir, include_constraints=False)

    with pytest.raises(RuntimeError, match="constraints_file is required"):
        signing_evidence.build_signing_attestation_evidence(package_dir)


def test_build_signing_attestation_evidence_rejects_tampered_artifactory_record(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir, include_artifactory=True)
    artifactory_path = package_dir / signing_evidence.ARTIFACTORY_EVIDENCE_NAME
    artifactory = json.loads(artifactory_path.read_text(encoding="utf-8"))
    artifactory["promotion_files"][0]["sha256"] = "0" * 64
    artifactory_path.write_text(json.dumps(artifactory, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=f"{wheel_path.name}: subject SHA256"):
        signing_evidence.build_signing_attestation_evidence(package_dir)


def test_validate_signing_profile_rejects_url_and_secret_like_values() -> None:
    with pytest.raises(RuntimeError, match="not a URL"):
        signing_evidence.validate_signing_profile("https://signing.example.invalid/profile")

    with pytest.raises(RuntimeError, match="secret-like"):
        signing_evidence.validate_signing_profile("release-private-key")


def test_validate_output_suffix_rejects_paths() -> None:
    with pytest.raises(RuntimeError, match="not a path"):
        signing_evidence.validate_output_suffix("../artifact.sig", label="signature suffix")


def test_ensure_output_path_rejects_repo_local_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(RuntimeError, match="outside the source repo"):
        signing_evidence.ensure_output_path(repo_root / "evidence.json", root=repo_root)
