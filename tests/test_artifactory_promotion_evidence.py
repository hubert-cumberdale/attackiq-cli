from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "build_artifactory_promotion_evidence.py"
)
_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "build_artifactory_promotion_evidence",
    _SCRIPT_PATH,
)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
promotion_evidence = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = promotion_evidence
_SCRIPT_SPEC.loader.exec_module(promotion_evidence)


def write_package_dir(package_dir: Path, *, include_constraints: bool = True) -> Path:
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
    wheel_sha256 = promotion_evidence.enterprise_verifier.sha256_file(wheel_path)
    constraints_path = package_dir / promotion_evidence.enterprise_verifier.CONSTRAINTS_FILE_NAME
    constraints_sha256 = ""
    if include_constraints:
        constraints_path.write_text("httpx==0.27.2\n", encoding="utf-8")
        constraints_sha256 = promotion_evidence.enterprise_verifier.sha256_file(constraints_path)

    manifest = {
        "schema_version": 1,
        "public_repo_url": "https://example.invalid/attackiq-cli.git",
        "source_ref": "v1.2.3",
        "source_commit": "abc123",
        "package_version": "1.2.3",
        "build_created_utc": "2026-05-25T00:00:00+00:00",
        "python_version": "3.12.3",
        "artifacts": [
            {
                "filename": wheel_path.name,
                "sha256": wheel_sha256,
                "type": "wheel",
            }
        ],
        "checksum_file": promotion_evidence.enterprise_verifier.CHECKSUM_FILE_NAME,
        "provenance_file": promotion_evidence.enterprise_verifier.PROVENANCE_NAME,
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
            promotion_evidence.enterprise_verifier.package_dependency_integrity.build_dependency_integrity(
                constraints_path=constraints_path,
                constraints_sha256=constraints_sha256,
                generated_utc="2026-05-25T00:00:00+00:00",
            )
        )
        dependency_integrity_path = (
            promotion_evidence.enterprise_verifier.package_dependency_integrity.write_dependency_integrity(
                package_dir,
                dependency_integrity,
            )
        )
        manifest["dependency_integrity_file"] = {
            "filename": dependency_integrity_path.name,
            "sha256": promotion_evidence.enterprise_verifier.sha256_file(
                dependency_integrity_path
            ),
            "type": "dependency-integrity-json",
        }

    manifest_path = package_dir / promotion_evidence.enterprise_verifier.MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    provenance = promotion_evidence.enterprise_verifier.package_provenance.build_package_provenance(
        package_dir=package_dir,
        manifest=manifest,
        manifest_filename=promotion_evidence.enterprise_verifier.MANIFEST_NAME,
        wheel_path=wheel_path,
        wheel_sha256=wheel_sha256,
        checksum_filename=promotion_evidence.enterprise_verifier.CHECKSUM_FILE_NAME,
        generated_utc="2026-05-25T00:00:00+00:00",
    )
    write_provenance = (
        promotion_evidence.enterprise_verifier.package_provenance.write_package_provenance
    )
    provenance_path = write_provenance(package_dir, provenance)
    provenance_sha256 = promotion_evidence.enterprise_verifier.sha256_file(provenance_path)

    checksum_lines = [
        f"{provenance_sha256}  {provenance_path.name}\n",
        f"{wheel_sha256}  {wheel_path.name}\n",
    ]
    if include_constraints:
        checksum_lines.insert(0, f"{constraints_sha256}  {constraints_path.name}\n")
        checksum_lines.insert(
            1,
            f"{promotion_evidence.enterprise_verifier.sha256_file(dependency_integrity_path)}  "
            f"{dependency_integrity_path.name}\n",
        )
    (package_dir / promotion_evidence.enterprise_verifier.CHECKSUM_FILE_NAME).write_text(
        "".join(checksum_lines),
        encoding="utf-8",
    )
    return wheel_path


def test_build_artifactory_promotion_evidence_records_upload_plan(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir)

    evidence = promotion_evidence.build_artifactory_promotion_evidence(
        package_dir,
        artifactory_url="https://artifactory.example.invalid/artifactory",
        repository_path="api/pypi/attackiq-cli-local",
        generated_utc="2026-05-25T00:00:00+00:00",
    )

    assert evidence["package"]["source_ref"] == "v1.2.3"
    assert evidence["package"]["package_version"] == "1.2.3"
    assert evidence["artifactory"]["repository_url"] == (
        "https://artifactory.example.invalid/artifactory"
    )
    assert evidence["artifactory"]["repository_path"] == "api/pypi/attackiq-cli-local"

    filenames = {artifact["filename"] for artifact in evidence["promotion_files"]}
    assert filenames == {
        wheel_path.name,
        promotion_evidence.enterprise_verifier.CHECKSUM_FILE_NAME,
        promotion_evidence.enterprise_verifier.MANIFEST_NAME,
        promotion_evidence.enterprise_verifier.PROVENANCE_NAME,
        promotion_evidence.enterprise_verifier.CONSTRAINTS_FILE_NAME,
        promotion_evidence.enterprise_verifier.DEPENDENCY_INTEGRITY_NAME,
    }
    wheel_entry = next(
        artifact
        for artifact in evidence["promotion_files"]
        if artifact["filename"] == wheel_path.name
    )
    assert wheel_entry["target"]["url"].endswith(
        f"/api/pypi/attackiq-cli-local/{wheel_path.name}"
    )
    constraints_entry = next(
        artifact
        for artifact in evidence["promotion_files"]
        if artifact["filename"] == promotion_evidence.enterprise_verifier.CONSTRAINTS_FILE_NAME
    )
    assert constraints_entry["type"] == "install-constraints"
    assert (
        "python3 scripts/verify_enterprise_package.py <package-dir> --require-constraints"
        in evidence["pre_upload_checks"]
    )
    assert (
        "python3 scripts/verify_enterprise_package.py <downloaded-package-dir> "
        "--require-constraints"
        in evidence["post_upload_verification"]
    )
    assert "Artifactory upload credentials" in evidence["operator_owned_controls"]
    assert str(tmp_path) not in json.dumps(evidence)


def test_build_artifactory_promotion_evidence_rejects_invalid_package(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)
    (package_dir / promotion_evidence.enterprise_verifier.CHECKSUM_FILE_NAME).write_text(
        "",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="enterprise package verification failed"):
        promotion_evidence.build_artifactory_promotion_evidence(package_dir)


def test_build_artifactory_promotion_evidence_requires_constraints(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir, include_constraints=False)

    with pytest.raises(RuntimeError, match="constraints_file is required"):
        promotion_evidence.build_artifactory_promotion_evidence(package_dir)


def test_validate_artifactory_url_rejects_credentials() -> None:
    with pytest.raises(RuntimeError, match="embedded credentials"):
        promotion_evidence.validate_artifactory_url(
            "https://user@artifactory.example.invalid/artifactory"
        )


def test_validate_artifactory_url_requires_https() -> None:
    with pytest.raises(RuntimeError, match="https URL"):
        promotion_evidence.validate_artifactory_url("http://artifactory.example.invalid")


def test_validate_repository_path_rejects_url_and_parent_segments() -> None:
    with pytest.raises(RuntimeError, match="relative"):
        promotion_evidence.validate_repository_path("https://artifactory.example.invalid/repo")

    with pytest.raises(RuntimeError, match="parent"):
        promotion_evidence.validate_repository_path("api/pypi/../private")


def test_ensure_output_path_rejects_repo_local_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(RuntimeError, match="outside the source repo"):
        promotion_evidence.ensure_output_path(repo_root / "evidence.json", root=repo_root)
