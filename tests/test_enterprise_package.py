from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_enterprise_package.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("build_enterprise_package", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
enterprise_package = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = enterprise_package
_SCRIPT_SPEC.loader.exec_module(enterprise_package)


def write_fake_wheel(wheel_path: Path, *, version: str = "1.2.3") -> None:
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: attackiq-cli\n"
        f"Version: {version}\n"
        "Summary: Test wheel\n"
        "Requires-Python: >=3.10\n"
        "Requires-Dist: httpx>=0.27,<0.28\n"
    )
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr("attackiq_cli/__init__.py", f"__version__ = '{version}'\n")
        wheel.writestr(f"attackiq_cli-{version}.dist-info/METADATA", metadata)


def test_ensure_output_dir_rejects_repo_local_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(RuntimeError, match="outside the source repo"):
        enterprise_package.ensure_output_dir(repo_root / "dist", root=repo_root)


def test_validate_source_ref_requires_release_tag() -> None:
    assert enterprise_package.validate_source_ref("v1.2.3") == "1.2.3"

    with pytest.raises(RuntimeError, match="vX.Y.Z release tag"):
        enterprise_package.validate_source_ref("main")


def test_validate_package_version_rejects_mismatch() -> None:
    with pytest.raises(RuntimeError, match="package version mismatch"):
        enterprise_package.validate_package_version("v1.2.3", "1.2.4")


def test_validate_public_repo_url_rejects_credentials() -> None:
    with pytest.raises(RuntimeError, match="embedded credentials"):
        enterprise_package.validate_public_repo_url("https://token@example.invalid/repo.git")


def test_sha256_file_and_checksum_writer(tmp_path: Path) -> None:
    wheel = tmp_path / "attackiq_cli-1.2.3-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes\n")

    digest = enterprise_package.sha256_file(wheel)
    checksum_path = enterprise_package.write_sha256s(tmp_path, {wheel.name: digest})

    assert digest == "d0995fbab28019f357bfaa8021396aa90224dafc0b6bda07afeeb2a83097fdd6"
    assert checksum_path.read_text(encoding="utf-8") == f"{digest}  {wheel.name}\n"


def test_build_promotion_manifest_records_enterprise_boundary() -> None:
    manifest = enterprise_package.build_promotion_manifest(
        public_repo_url="https://example.invalid/repo.git",
        source_ref="v1.2.3",
        source_commit="abc123",
        package_version="1.2.3",
        wheel_filename="attackiq_cli-1.2.3-py3-none-any.whl",
        wheel_sha256="digest",
        build_created_utc="2026-05-24T00:00:00+00:00",
    )

    assert manifest["public_repo_url"] == "https://example.invalid/repo.git"
    assert manifest["source_ref"] == "v1.2.3"
    assert manifest["source_commit"] == "abc123"
    assert manifest["package_version"] == "1.2.3"
    assert manifest["artifacts"] == [
        {
            "filename": "attackiq_cli-1.2.3-py3-none-any.whl",
            "sha256": "digest",
            "type": "wheel",
        }
    ]
    assert "credentials are not accepted or stored" in manifest["artifactory_policy"]
    assert manifest["provenance_file"] == enterprise_package.PROVENANCE_NAME
    assert manifest["sbom_policy"].startswith("offline package provenance")


def test_build_enterprise_package_fails_on_wheel_safety_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_clone(_repo_url: str, _source_ref: str, destination: Path) -> None:
        destination.mkdir()
        (destination / "pyproject.toml").write_text(
            '[project]\nname = "attackiq-cli"\nversion = "1.2.3"\n',
            encoding="utf-8",
        )

    def fake_build_wheel(output_dir: Path, *, root: Path) -> Path:
        assert (root / "pyproject.toml").exists()
        wheel_path = output_dir / "attackiq_cli-1.2.3-py3-none-any.whl"
        write_fake_wheel(wheel_path)
        return wheel_path

    monkeypatch.setattr(enterprise_package, "clone_source", fake_clone)
    monkeypatch.setattr(enterprise_package, "resolve_source_commit", lambda _source_dir: "abc123")
    monkeypatch.setattr(enterprise_package.public_safety, "scan_tracked_files", lambda _root: [])
    monkeypatch.setattr(enterprise_package.public_safety, "build_wheel", fake_build_wheel)
    monkeypatch.setattr(
        enterprise_package.public_safety,
        "scan_wheel",
        lambda _wheel_path: ["wheel contains disallowed path: docs/internal.md"],
    )

    with pytest.raises(RuntimeError, match="enterprise wheel safety scan failed"):
        enterprise_package.build_enterprise_package(
            source_ref="v1.2.3",
            output_dir=tmp_path / "out",
            public_repo_url="https://example.invalid/repo.git",
            root=tmp_path / "repo",
        )


def test_build_enterprise_package_writes_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_clone(_repo_url: str, _source_ref: str, destination: Path) -> None:
        destination.mkdir()
        (destination / "pyproject.toml").write_text(
            '[project]\nname = "attackiq-cli"\nversion = "1.2.3"\n',
            encoding="utf-8",
        )

    def fake_build_wheel(output_dir: Path, *, root: Path) -> Path:
        assert (root / "pyproject.toml").exists()
        wheel_path = output_dir / "attackiq_cli-1.2.3-py3-none-any.whl"
        write_fake_wheel(wheel_path)
        return wheel_path

    monkeypatch.setattr(enterprise_package, "clone_source", fake_clone)
    monkeypatch.setattr(enterprise_package, "resolve_source_commit", lambda _source_dir: "abc123")
    monkeypatch.setattr(enterprise_package.public_safety, "scan_tracked_files", lambda _root: [])
    monkeypatch.setattr(enterprise_package.public_safety, "build_wheel", fake_build_wheel)
    monkeypatch.setattr(enterprise_package.public_safety, "scan_wheel", lambda _wheel_path: [])

    summary = enterprise_package.build_enterprise_package(
        source_ref="v1.2.3",
        output_dir=tmp_path / "out",
        public_repo_url="https://example.invalid/repo.git",
        root=tmp_path / "repo",
    )

    wheel_path = summary["wheel_path"]
    checksum_path = summary["checksum_path"]
    manifest_path = summary["manifest_path"]
    provenance_path = summary["provenance_path"]
    assert wheel_path.exists()
    assert checksum_path.exists()
    assert manifest_path.exists()
    assert provenance_path.exists()

    checksum_text = checksum_path.read_text(encoding="utf-8")
    assert wheel_path.name in checksum_text
    assert provenance_path.name in checksum_text

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert manifest["source_commit"] == "abc123"
    assert manifest["provenance_file"] == enterprise_package.PROVENANCE_NAME
    assert provenance["source"]["source_commit"] == "abc123"
    assert provenance["wheel_metadata"]["dependencies"] == ["httpx>=0.27,<0.28"]
