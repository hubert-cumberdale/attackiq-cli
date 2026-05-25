from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_enterprise_package.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("verify_enterprise_package", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
enterprise_verifier = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = enterprise_verifier
_SCRIPT_SPEC.loader.exec_module(enterprise_verifier)


def write_package_dir(
    package_dir: Path,
    *,
    public_repo_url: str = "https://example.invalid/attackiq-cli.git",
    wheel_entry: str = "attackiq_cli/__init__.py",
) -> Path:
    package_dir.mkdir()
    wheel_path = package_dir / "attackiq_cli-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr(wheel_entry, '__version__ = "1.2.3"\n')
    wheel_sha256 = enterprise_verifier.sha256_file(wheel_path)

    manifest = {
        "schema_version": 1,
        "public_repo_url": public_repo_url,
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
        "checksum_file": enterprise_verifier.CHECKSUM_FILE_NAME,
        "package_policy": "validated wheel for enterprise package repository promotion",
        "artifactory_policy": "upload is operator-owned; credentials are not accepted or stored",
        "sbom_policy": "SBOM/provenance generation is deferred to a later milestone",
        "validation_commands": [],
    }
    (package_dir / enterprise_verifier.MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    (package_dir / enterprise_verifier.CHECKSUM_FILE_NAME).write_text(
        f"{wheel_sha256}  {wheel_path.name}\n",
        encoding="utf-8",
    )
    return wheel_path


def test_verify_enterprise_package_accepts_valid_package(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)

    summary, errors = enterprise_verifier.verify_enterprise_package(package_dir)

    assert errors == []
    assert summary is not None
    assert summary["source_ref"] == "v1.2.3"
    assert summary["package_version"] == "1.2.3"
    assert summary["artifact_count"] == 1


def test_verify_enterprise_package_rejects_checksum_mismatch(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir)
    (package_dir / enterprise_verifier.CHECKSUM_FILE_NAME).write_text(
        f"{'0' * 64}  {wheel_path.name}\n",
        encoding="utf-8",
    )

    summary, errors = enterprise_verifier.verify_enterprise_package(package_dir)

    assert summary is None
    assert f"{wheel_path.name}: manifest SHA256 does not match SHA256SUMS" in errors


def test_verify_enterprise_package_rejects_tampered_artifact(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir)
    wheel_path.write_bytes(b"tampered\n")

    summary, errors = enterprise_verifier.verify_enterprise_package(package_dir)

    assert summary is None
    assert f"{wheel_path.name}: file SHA256 does not match manifest" in errors


def test_verify_enterprise_package_rejects_repo_url_credentials(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir, public_repo_url="https://token@example.invalid/repo.git")

    summary, errors = enterprise_verifier.verify_enterprise_package(package_dir)

    assert summary is None
    assert (
        f"{enterprise_verifier.MANIFEST_NAME}: public_repo_url must not include credentials"
        in errors
    )


def test_verify_enterprise_package_rejects_unsafe_checksum_filename(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    write_package_dir(package_dir)
    checksum_path = package_dir / enterprise_verifier.CHECKSUM_FILE_NAME
    checksum_path.write_text(
        checksum_path.read_text(encoding="utf-8") + f"{'0' * 64}  ../evil.whl\n",
        encoding="utf-8",
    )

    summary, errors = enterprise_verifier.verify_enterprise_package(package_dir)

    assert summary is None
    assert f"{enterprise_verifier.CHECKSUM_FILE_NAME}:2: unsafe artifact filename" in errors


def test_verify_enterprise_package_runs_wheel_safety_scan(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    wheel_path = write_package_dir(package_dir, wheel_entry="docs/internal.md")

    summary, errors = enterprise_verifier.verify_enterprise_package(package_dir)

    assert summary is None
    assert f"{wheel_path.name}: wheel contains disallowed path: docs/internal.md" in errors
