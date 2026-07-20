from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, cast

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(module_name: str, script_name: str) -> Any:
    script_path = _SCRIPTS_DIR / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


enterprise_evidence = _load_script("verify_enterprise_evidence", "verify_enterprise_evidence.py")
artifactory_builder = _load_script(
    "build_artifactory_promotion_evidence",
    "build_artifactory_promotion_evidence.py",
)
signing_builder = _load_script(
    "build_signing_attestation_evidence",
    "build_signing_attestation_evidence.py",
)


def write_package_dir(package_dir: Path) -> Path:
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

    verifier = enterprise_evidence.enterprise_verifier
    wheel_sha256 = verifier.sha256_file(wheel_path)
    constraints_path = package_dir / verifier.CONSTRAINTS_FILE_NAME
    constraints_path.write_text("httpx==0.27.2\n", encoding="utf-8")
    constraints_sha256 = verifier.sha256_file(constraints_path)
    manifest = {
        "schema_version": 1,
        "public_repo_url": "https://example.invalid/attackiq-cli.git",
        "source_ref": "v1.2.3",
        "source_commit": "abc123",
        "package_version": "1.2.3",
        "build_created_utc": "2026-05-27T00:00:00+00:00",
        "python_version": "3.12.3",
        "artifacts": [
            {
                "filename": wheel_path.name,
                "sha256": wheel_sha256,
                "type": "wheel",
            }
        ],
        "checksum_file": verifier.CHECKSUM_FILE_NAME,
        "constraints_file": {
            "filename": constraints_path.name,
            "sha256": constraints_sha256,
            "type": "install-constraints",
        },
        "provenance_file": verifier.PROVENANCE_NAME,
        "package_policy": "validated wheel for enterprise package repository promotion",
        "artifactory_policy": "upload is operator-owned; credentials are not accepted or stored",
        "sbom_policy": "offline package provenance and dependency inventory are generated",
        "validation_commands": [],
    }
    dependency_integrity = verifier.package_dependency_integrity.build_dependency_integrity(
        constraints_path=constraints_path,
        constraints_sha256=constraints_sha256,
        generated_utc="2026-05-27T00:00:00+00:00",
    )
    dependency_integrity_path = verifier.package_dependency_integrity.write_dependency_integrity(
        package_dir,
        dependency_integrity,
    )
    dependency_integrity_sha256 = verifier.sha256_file(dependency_integrity_path)
    manifest["dependency_integrity_file"] = {
        "filename": dependency_integrity_path.name,
        "sha256": dependency_integrity_sha256,
        "type": "dependency-integrity-json",
    }
    manifest_path = package_dir / verifier.MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    provenance = verifier.package_provenance.build_package_provenance(
        package_dir=package_dir,
        manifest=manifest,
        manifest_filename=verifier.MANIFEST_NAME,
        wheel_path=wheel_path,
        wheel_sha256=wheel_sha256,
        checksum_filename=verifier.CHECKSUM_FILE_NAME,
        generated_utc="2026-05-27T00:00:00+00:00",
    )
    provenance_path = verifier.package_provenance.write_package_provenance(package_dir, provenance)
    provenance_sha256 = verifier.sha256_file(provenance_path)

    (package_dir / verifier.CHECKSUM_FILE_NAME).write_text(
        f"{constraints_sha256}  {constraints_path.name}\n"
        f"{dependency_integrity_sha256}  {dependency_integrity_path.name}\n"
        f"{provenance_sha256}  {provenance_path.name}\n"
        f"{wheel_sha256}  {wheel_path.name}\n",
        encoding="utf-8",
    )
    return wheel_path


def write_artifactory_evidence(package_dir: Path) -> dict[str, Any]:
    evidence = artifactory_builder.build_artifactory_promotion_evidence(
        package_dir,
        artifactory_url="https://artifactory.example.invalid/artifactory",
        repository_path="api/pypi/attackiq-cli",
        generated_utc="2026-05-27T00:00:00+00:00",
    )
    artifactory_builder.write_evidence(
        evidence,
        package_dir / enterprise_evidence.ARTIFACTORY_EVIDENCE_NAME,
    )
    return cast(dict[str, Any], evidence)


def write_signing_evidence(package_dir: Path) -> dict[str, Any]:
    evidence = signing_builder.build_signing_attestation_evidence(
        package_dir,
        signing_profile="enterprise-release",
        generated_utc="2026-05-27T00:00:00+00:00",
    )
    signing_builder.write_evidence(
        evidence,
        package_dir / enterprise_evidence.SIGNING_EVIDENCE_NAME,
    )
    return cast(dict[str, Any], evidence)


def test_verify_enterprise_evidence_accepts_full_evidence_set(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)
    write_artifactory_evidence(package_dir)
    write_signing_evidence(package_dir)

    summary, errors = enterprise_evidence.verify_enterprise_evidence(
        package_dir,
        require_artifactory=True,
        require_signing=True,
    )

    assert errors == []
    assert summary is not None
    assert summary["artifactory_evidence"] is True
    assert summary["signing_evidence"] is True
    assert summary["promotion_file_count"] == 6
    assert summary["signing_subject_count"] == 7


def test_verify_enterprise_evidence_allows_optional_evidence(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)

    summary, errors = enterprise_evidence.verify_enterprise_evidence(package_dir)

    assert errors == []
    assert summary is not None
    assert summary["artifactory_evidence"] is False
    assert summary["signing_evidence"] is False
    assert summary["promotion_file_count"] == 0
    assert summary["signing_subject_count"] == 0


def test_verify_enterprise_evidence_requires_requested_files(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)

    summary, errors = enterprise_evidence.verify_enterprise_evidence(
        package_dir,
        require_artifactory=True,
        require_signing=True,
    )

    assert summary is None
    assert f"missing {enterprise_evidence.ARTIFACTORY_EVIDENCE_NAME}" in errors
    assert f"missing {enterprise_evidence.SIGNING_EVIDENCE_NAME}" in errors


def test_verify_enterprise_evidence_rejects_tampered_artifactory_sha(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir)
    evidence = write_artifactory_evidence(package_dir)
    evidence["promotion_files"][0]["sha256"] = "0" * 64
    (package_dir / enterprise_evidence.ARTIFACTORY_EVIDENCE_NAME).write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )

    summary, errors = enterprise_evidence.verify_enterprise_evidence(
        package_dir,
        require_artifactory=True,
    )

    assert summary is None
    assert any(
        wheel_path.name in error and "sha256 must match local package artifact" in error
        for error in errors
    )


def test_verify_enterprise_evidence_requires_constraints_checks(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)
    evidence = write_artifactory_evidence(package_dir)
    evidence["pre_upload_checks"] = ["confirm package directory is outside git"]
    evidence["post_upload_verification"] = ["download the uploaded files"]
    (package_dir / enterprise_evidence.ARTIFACTORY_EVIDENCE_NAME).write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )

    summary, errors = enterprise_evidence.verify_enterprise_evidence(
        package_dir,
        require_artifactory=True,
    )

    assert summary is None
    assert (
        f"{enterprise_evidence.ARTIFACTORY_EVIDENCE_NAME}: "
        "pre_upload_checks: missing --require-constraints"
    ) in errors
    assert (
        f"{enterprise_evidence.ARTIFACTORY_EVIDENCE_NAME}: "
        "post_upload_verification: missing --require-constraints"
    ) in errors


def test_verify_enterprise_evidence_rejects_tampered_signing_subject(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir)
    write_artifactory_evidence(package_dir)
    evidence = write_signing_evidence(package_dir)
    wheel_subject = next(
        subject for subject in evidence["subjects"] if subject["filename"] == wheel_path.name
    )
    wheel_subject["sha256"] = "0" * 64
    (package_dir / enterprise_evidence.SIGNING_EVIDENCE_NAME).write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )

    summary, errors = enterprise_evidence.verify_enterprise_evidence(
        package_dir,
        require_artifactory=True,
        require_signing=True,
    )

    assert summary is None
    assert any(
        wheel_path.name in error and "sha256 must match local package artifact" in error
        for error in errors
    )


def test_verify_enterprise_evidence_requires_signing_expected_outputs(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)
    write_artifactory_evidence(package_dir)
    evidence = write_signing_evidence(package_dir)
    missing_subject = evidence["expected_outputs"].pop(0)["subject"]
    (package_dir / enterprise_evidence.SIGNING_EVIDENCE_NAME).write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )

    summary, errors = enterprise_evidence.verify_enterprise_evidence(
        package_dir,
        require_artifactory=True,
        require_signing=True,
    )

    assert summary is None
    assert (
        f"{enterprise_evidence.SIGNING_EVIDENCE_NAME}: expected_outputs "
        f"missing {missing_subject}"
    ) in errors


def test_verify_enterprise_evidence_requires_external_evidence_fields(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)
    write_artifactory_evidence(package_dir)
    evidence = write_signing_evidence(package_dir)
    evidence["external_evidence_fields"]["trust_root_verification"].remove(
        "trust_root_identifier"
    )
    (package_dir / enterprise_evidence.SIGNING_EVIDENCE_NAME).write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )

    summary, errors = enterprise_evidence.verify_enterprise_evidence(
        package_dir,
        require_artifactory=True,
        require_signing=True,
    )

    assert summary is None
    assert (
        f"{enterprise_evidence.SIGNING_EVIDENCE_NAME}: external_evidence_fields."
        "trust_root_verification missing trust_root_identifier"
    ) in errors


def test_verify_enterprise_evidence_cli_reports_missing_evidence(
    tmp_path: Path,
    capsys: Any,
) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)

    result = enterprise_evidence.main([str(package_dir), "--require-artifactory"])

    captured = capsys.readouterr()
    assert result == 1
    assert "Enterprise evidence verification failed:" in captured.err
    assert f"missing {enterprise_evidence.ARTIFACTORY_EVIDENCE_NAME}" in captured.err
