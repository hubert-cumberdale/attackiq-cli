#!/usr/bin/env python3
"""Check that tracked files and release wheels are safe for public publication."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIPPED_TRACKED_PATHS: set[str] = set()

SKIPPED_TRACKED_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".venv/",
    "build/",
    "dist/",
    "site/",
)

DISALLOWED_WHEEL_PREFIXES = (
    "docs/",
    "tests/",
    "custom-scenarios/",
    "scenario-wizard-configs/",
    "taskpacks/",
    "scripts/",
    ".github/",
)

DISALLOWED_WHEEL_NAMES = {
    "README.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "mkdocs.yml",
}


@dataclass(frozen=True)
class BlockedPattern:
    label: str
    regex: re.Pattern[str]


def _regex_pattern(*parts: str) -> re.Pattern[str]:
    return re.compile("".join(parts), re.IGNORECASE)


BLOCKED_PATTERNS = (
    BlockedPattern("private catalog repository", _regex_pattern(r"bas", r"[-_]", r"cloud")),
    BlockedPattern("private repository name", _regex_pattern(r"bas", r"_", r"rep")),
    BlockedPattern("private exposure platform name", _regex_pattern(r"\b", "ar", "gus", r"\b")),
    BlockedPattern("private exposure repository name", _regex_pattern(r"\b", "hy", "dra", r"\b")),
    BlockedPattern("lab-only scenario name", _regex_pattern(r"\b", "qi", "lin", r"\b")),
    BlockedPattern("private lab hostname", _regex_pattern("crow", "11d")),
    BlockedPattern("local workstation path", _regex_pattern("/", "home/", "noob")),
    BlockedPattern("local Windows user path", _regex_pattern("/", "mnt/c/", "Users")),
    BlockedPattern("local Windows username", _regex_pattern("Users/", "auner")),
)


def _git_tracked_files(root: Path = ROOT) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in completed.stdout.splitlines() if line.strip()]


def _should_scan_tracked_file(path: Path) -> bool:
    path_text = path.as_posix()
    if path_text in SKIPPED_TRACKED_PATHS:
        return False
    return not any(path_text.startswith(prefix) for prefix in SKIPPED_TRACKED_PREFIXES)


def _scan_text(path_label: str, text: str) -> list[str]:
    errors: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern in BLOCKED_PATTERNS:
            if pattern.regex.search(line):
                errors.append(f"{path_label}:{line_number}: blocked {pattern.label}")
    return errors


def scan_tracked_files(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative_path in _git_tracked_files(root):
        if not _should_scan_tracked_file(relative_path):
            continue
        absolute_path = root / relative_path
        if not absolute_path.is_file():
            continue
        try:
            text = absolute_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        errors.extend(_scan_text(relative_path.as_posix(), text))
    return errors


def validate_wheel_entries(entries: list[str]) -> list[str]:
    errors: list[str] = []
    for entry in entries:
        if entry in DISALLOWED_WHEEL_NAMES:
            errors.append(f"wheel contains disallowed top-level file: {entry}")
        for prefix in DISALLOWED_WHEEL_PREFIXES:
            if entry.startswith(prefix):
                errors.append(f"wheel contains disallowed path: {entry}")
                break
    return errors


def _wheel_text_entries(wheel: zipfile.ZipFile) -> list[tuple[str, str]]:
    text_entries: list[tuple[str, str]] = []
    for info in wheel.infolist():
        if info.is_dir():
            continue
        if info.file_size > 2_000_000:
            continue
        suffix = Path(info.filename).suffix.lower()
        name = Path(info.filename).name
        if suffix not in {".py", ".txt", ".toml", ".yaml", ".yml", ".json", ".md"} and name not in {
            "METADATA",
            "PKG-INFO",
        }:
            continue
        try:
            text = wheel.read(info).decode("utf-8")
        except UnicodeDecodeError:
            continue
        text_entries.append((info.filename, text))
    return text_entries


def build_wheel(output_dir: Path, *, root: Path = ROOT) -> Path:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "-c",
            "constraints.txt",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(output_dir),
            ".",
        ],
        cwd=root,
        check=True,
    )
    wheels = sorted(output_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one wheel, found {len(wheels)}")
    return wheels[0]


def scan_wheel(wheel_path: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(wheel_path) as wheel:
        entries = [info.filename for info in wheel.infolist()]
        errors.extend(validate_wheel_entries(entries))
        for entry_name, text in _wheel_text_entries(wheel):
            errors.extend(_scan_text(f"{wheel_path.name}!{entry_name}", text))
    return errors


def check_public_safety(*, root: Path = ROOT, scan_package: bool = True) -> list[str]:
    errors = scan_tracked_files(root)
    if scan_package:
        try:
            with tempfile.TemporaryDirectory(prefix="aiq-cli-public-wheel-") as tmpdir:
                wheel_path = build_wheel(Path(tmpdir), root=root)
                errors.extend(scan_wheel(wheel_path))
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            errors.append(f"wheel build failed: {exc}")
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-wheel",
        action="store_true",
        help="Only scan tracked source files; do not build and inspect a wheel.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    errors = check_public_safety(scan_package=not args.skip_wheel)
    if errors:
        print("Public safety check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Public safety check OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
