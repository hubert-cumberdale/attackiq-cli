from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_public_mirror.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("check_public_mirror", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
check_public_mirror = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = check_public_mirror
_SCRIPT_SPEC.loader.exec_module(check_public_mirror)


def test_ensure_output_dir_rejects_repo_local_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(RuntimeError, match="outside the source repository"):
        check_public_mirror.ensure_output_dir(repo_root / "public-export", root=repo_root)


def test_ensure_output_dir_rejects_file_path(tmp_path: Path) -> None:
    output_file = tmp_path / "export"
    output_file.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not a directory"):
        check_public_mirror.ensure_output_dir(output_file, root=tmp_path / "repo")


def test_prepare_public_mirror_rejects_dirty_non_head_ref(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="only supports the default --ref HEAD"):
        check_public_mirror.prepare_public_mirror(
            ref="v1.2.3",
            output_dir=tmp_path / "export",
            public_repo="owner/repo",
            manifest_name=check_public_mirror.DEFAULT_MANIFEST_NAME,
            scan_package=False,
            allow_dirty=True,
            root=tmp_path / "repo",
        )


def test_tree_digest_excludes_manifest_and_tracks_source_changes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    source_file = tmp_path / "src" / "module.py"
    source_file.write_text("VALUE = 1\n", encoding="utf-8")
    manifest = tmp_path / check_public_mirror.DEFAULT_MANIFEST_NAME
    manifest.write_text('{"generated": 1}\n', encoding="utf-8")

    first_digest = check_public_mirror.calculate_tree_sha256(tmp_path)
    manifest.write_text('{"generated": 2}\n', encoding="utf-8")
    second_digest = check_public_mirror.calculate_tree_sha256(tmp_path)
    source_file.write_text("VALUE = 2\n", encoding="utf-8")
    third_digest = check_public_mirror.calculate_tree_sha256(tmp_path)

    assert second_digest == first_digest
    assert third_digest != first_digest


def test_build_publication_manifest_records_public_boundary() -> None:
    manifest = check_public_mirror.build_publication_manifest(
        public_repo="owner/public-repo",
        source_ref="v1.2.3",
        source_commit="abc123",
        package_version="1.2.3",
        export_created_utc="2026-05-22T00:00:00+00:00",
        tree_sha256="digest",
        manifest_name=check_public_mirror.DEFAULT_MANIFEST_NAME,
        source_snapshot="git-archive",
        dirty_worktree_allowed=False,
    )

    assert manifest["public_repo"] == "owner/public-repo"
    assert manifest["source_ref"] == "v1.2.3"
    assert manifest["source_commit"] == "abc123"
    assert manifest["package_version"] == "1.2.3"
    assert manifest["dirty_worktree_allowed"] is False
    assert manifest["history_policy"] == "single sanitized source snapshot; no private git history"
    assert check_public_mirror.DEFAULT_MANIFEST_NAME in manifest["tree_sha256_excludes"]


def test_scan_snapshot_tree_rejects_blocked_private_reference(tmp_path: Path) -> None:
    blocked_hostname = "crow" + "11d"
    (tmp_path / "notes.md").write_text(
        f"remove {blocked_hostname} before release\n",
        encoding="utf-8",
    )

    errors = check_public_mirror.scan_snapshot_tree(tmp_path)

    assert errors == ["notes.md:1: blocked private lab hostname"]
