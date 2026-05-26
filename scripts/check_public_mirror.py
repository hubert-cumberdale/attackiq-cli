#!/usr/bin/env python3
"""Prepare and validate a no-history public source mirror snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback.
    import tomli as tomllib  # type: ignore[no-redef]

try:
    from scripts import check_public_safety as public_safety
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback.
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import check_public_safety as public_safety  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_REPO = "hubert-cumberdale/attackiq-cli"
DEFAULT_MANIFEST_NAME = "PUBLICATION_MANIFEST.json"


def _run(
    argv: list[str],
    *,
    cwd: Path,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def _git_output(argv: list[str], *, root: Path = ROOT) -> str:
    completed = _run(argv, cwd=root)
    return completed.stdout.strip()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_output_dir() -> Path:
    return Path("/tmp") / f"attackiq-cli-public-export-{utc_timestamp()}"


def ensure_output_dir(path: Path, *, root: Path = ROOT) -> Path:
    output_dir = path.expanduser().resolve()
    repo_root = root.resolve()
    if output_dir == repo_root or is_relative_to(output_dir, repo_root):
        raise RuntimeError("public mirror export directory must be outside the source repository")
    if output_dir.exists() and not output_dir.is_dir():
        raise RuntimeError(f"public mirror export path is not a directory: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"public mirror export directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def ensure_clean_worktree(*, root: Path = ROOT) -> None:
    status = _git_output(["git", "status", "--porcelain"], root=root)
    if status:
        raise RuntimeError(
            "source worktree is dirty; commit changes before a strict mirror export "
            "or use --allow-dirty for a local dry run"
        )


def resolve_commit(ref: str, *, root: Path = ROOT) -> str:
    return _git_output(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], root=root)


def export_ref_archive(ref: str, output_dir: Path, *, root: Path = ROOT) -> None:
    with tempfile.TemporaryDirectory(prefix="attackiq-cli-public-archive-") as tmpdir:
        archive_path = Path(tmpdir) / "source.tar"
        _run(["git", "archive", "--format=tar", "--output", str(archive_path), ref], cwd=root)
        safe_extract_tar(archive_path, output_dir)


def safe_extract_tar(archive_path: Path, output_dir: Path) -> None:
    output_root = output_dir.resolve()
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            target = (output_root / member.name).resolve()
            if target != output_root and not is_relative_to(target, output_root):
                raise RuntimeError(f"archive member escapes export directory: {member.name}")
        archive.extractall(output_root)


def export_working_tree(output_dir: Path, *, root: Path = ROOT) -> None:
    tracked_and_untracked = _git_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        root=root,
    ).splitlines()
    for relative_text in tracked_and_untracked:
        relative_path = Path(relative_text)
        source_path = root / relative_path
        if not source_path.exists() or not (source_path.is_file() or source_path.is_symlink()):
            continue
        target_path = output_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path, follow_symlinks=False)


def load_package_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def iter_snapshot_files(root: Path, *, manifest_name: str | None = None) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        relative_path = path.relative_to(root)
        if relative_path.parts and relative_path.parts[0] == ".git":
            continue
        if manifest_name is not None and relative_path.as_posix() == manifest_name:
            continue
        if path.is_file():
            files.append(relative_path)
    return sorted(files, key=lambda item: item.as_posix())


def calculate_tree_sha256(root: Path, *, manifest_name: str = DEFAULT_MANIFEST_NAME) -> str:
    digest = hashlib.sha256()
    for relative_path in iter_snapshot_files(root, manifest_name=manifest_name):
        file_digest = hashlib.sha256((root / relative_path).read_bytes()).hexdigest()
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def scan_snapshot_tree(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path in iter_snapshot_files(root):
        if not public_safety._should_scan_tracked_file(relative_path):
            continue
        absolute_path = root / relative_path
        try:
            text = absolute_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        errors.extend(public_safety._scan_text(relative_path.as_posix(), text))
    return errors


def build_publication_manifest(
    *,
    public_repo: str,
    source_ref: str,
    source_commit: str,
    package_version: str,
    export_created_utc: str,
    tree_sha256: str,
    manifest_name: str,
    source_snapshot: str,
    dirty_worktree_allowed: bool,
) -> dict[str, Any]:
    release_ref = f"v{package_version}"
    return {
        "schema_version": 1,
        "public_repo": public_repo,
        "source_ref": source_ref,
        "source_commit": source_commit,
        "source_snapshot": source_snapshot,
        "dirty_worktree_allowed": dirty_worktree_allowed,
        "package_version": package_version,
        "export_created_utc": export_created_utc,
        "history_policy": "single sanitized source snapshot; no private git history",
        "package_policy": "source mirror only; no package artifacts are committed",
        "tree_sha256": tree_sha256,
        "tree_sha256_excludes": [manifest_name, ".git/"],
        "validation_commands": [
            "python3 scripts/check_public_safety.py",
            "python3 scripts/check_public_mirror.py --ref " + release_ref,
            ".venv/bin/python scripts/quality_gate.py",
            "git rev-list --count HEAD",
        ],
    }


def write_manifest(export_dir: Path, manifest_name: str, manifest: dict[str, Any]) -> Path:
    manifest_path = export_dir / manifest_name
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    return manifest_path


def initialize_public_repo(export_dir: Path, *, package_version: str) -> None:
    if (export_dir / ".git").exists():
        raise RuntimeError(f"export directory already contains a git repository: {export_dir}")
    _run(["git", "init"], cwd=export_dir)
    _run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=export_dir)
    _run(["git", "add", "-A"], cwd=export_dir)
    _run(
        [
            "git",
            "-c",
            "user.name=AttackIQ CLI Release Bot",
            "-c",
            "user.email=release@example.invalid",
            "commit",
            "-m",
            f"Initial public release v{package_version}",
        ],
        cwd=export_dir,
    )
    commit_count = _git_output(["git", "rev-list", "--count", "HEAD"], root=export_dir)
    if commit_count != "1":
        raise RuntimeError(
            f"public mirror repository must contain one commit, found {commit_count}"
        )
    status = _git_output(["git", "status", "--porcelain"], root=export_dir)
    if status:
        raise RuntimeError("public mirror repository has uncommitted files after initialization")


def prepare_public_mirror(
    *,
    ref: str,
    output_dir: Path,
    public_repo: str,
    manifest_name: str,
    scan_package: bool,
    allow_dirty: bool,
    root: Path = ROOT,
) -> dict[str, Any]:
    if allow_dirty and ref != "HEAD":
        raise RuntimeError("--allow-dirty only supports the default --ref HEAD working-tree export")
    if not allow_dirty:
        ensure_clean_worktree(root=root)

    source_commit = resolve_commit(ref, root=root)
    export_dir = ensure_output_dir(output_dir, root=root)
    source_snapshot = "working-tree" if allow_dirty else "git-archive"
    if allow_dirty:
        export_working_tree(export_dir, root=root)
    else:
        export_ref_archive(ref, export_dir, root=root)

    package_version = load_package_version(export_dir)
    export_created_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    tree_sha256 = calculate_tree_sha256(export_dir, manifest_name=manifest_name)
    manifest = build_publication_manifest(
        public_repo=public_repo,
        source_ref=ref,
        source_commit=source_commit,
        package_version=package_version,
        export_created_utc=export_created_utc,
        tree_sha256=tree_sha256,
        manifest_name=manifest_name,
        source_snapshot=source_snapshot,
        dirty_worktree_allowed=allow_dirty,
    )
    manifest_path = write_manifest(export_dir, manifest_name, manifest)

    errors = scan_snapshot_tree(export_dir)
    if scan_package:
        with tempfile.TemporaryDirectory(prefix="attackiq-cli-public-wheel-") as tmpdir:
            wheel_path = public_safety.build_wheel(Path(tmpdir), root=export_dir)
            errors.extend(public_safety.scan_wheel(wheel_path))
    if errors:
        raise RuntimeError("public mirror safety scan failed:\n- " + "\n- ".join(errors))

    initialize_public_repo(export_dir, package_version=package_version)
    return {
        "export_dir": export_dir,
        "manifest_path": manifest_path,
        "public_repo": public_repo,
        "source_ref": ref,
        "source_commit": source_commit,
        "package_version": package_version,
        "source_snapshot": source_snapshot,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref",
        default="HEAD",
        help="Git ref to export in strict mode. Defaults to HEAD.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Empty directory for the generated public snapshot. Defaults to /tmp with UTC suffix.",
    )
    parser.add_argument(
        "--public-repo",
        default=DEFAULT_PUBLIC_REPO,
        help=f"Expected public repository name. Defaults to {DEFAULT_PUBLIC_REPO}.",
    )
    parser.add_argument(
        "--manifest-name",
        default=DEFAULT_MANIFEST_NAME,
        help=f"Publication manifest filename. Defaults to {DEFAULT_MANIFEST_NAME}.",
    )
    parser.add_argument(
        "--skip-wheel",
        action="store_true",
        help="Skip the wheel build/inspection step; source snapshot checks still run.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Use the current working tree for local dry runs instead of requiring a clean ref.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_dir = args.output_dir or default_output_dir()
    try:
        summary = prepare_public_mirror(
            ref=args.ref,
            output_dir=output_dir,
            public_repo=args.public_repo,
            manifest_name=args.manifest_name,
            scan_package=not args.skip_wheel,
            allow_dirty=args.allow_dirty,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print("Public mirror check failed:", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            if exc.stdout:
                print(exc.stdout, file=sys.stderr)
            if exc.stderr:
                print(exc.stderr, file=sys.stderr)
        return 1

    print("Public mirror check OK.")
    print(f"Export directory: {summary['export_dir']}")
    print(f"Publication manifest: {summary['manifest_path']}")
    print(f"Public repository: {summary['public_repo']}")
    print(f"Source ref: {summary['source_ref']}")
    print(f"Source commit: {summary['source_commit']}")
    print(f"Source snapshot: {summary['source_snapshot']}")
    print(f"Package version: {summary['package_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
