from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reviews"
DEFAULT_OUTPUT_PREFIX = "REVIEW_"
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}


@dataclass(frozen=True)
class Check:
    section: str
    title: str
    pattern: re.Pattern[str]
    file_globs: tuple[str, ...]
    max_matches: int = 25


CHECKS: tuple[Check, ...] = (
    Check(
        section="Architecture Signals",
        title="Oversized Modules (line count > 800)",
        pattern=re.compile(r".*"),
        file_globs=("src/**/*.py",),
        max_matches=25,
    ),
    Check(
        section="Architecture Signals",
        title="Broad Exception Catching",
        pattern=re.compile(r"except\s+Exception(?:\s+as\s+\w+)?\s*:"),
        file_globs=("src/**/*.py",),
    ),
    Check(
        section="Security Signals",
        title="TLS Insecure Toggles / Overrides",
        pattern=re.compile(r"\binsecure\b|\bverify_tls\b", re.IGNORECASE),
        file_globs=("src/**/*.py",),
    ),
    Check(
        section="Security Signals",
        title="Header Redaction Logic References",
        pattern=re.compile(r"redact|authorization|cookie|token|jwt", re.IGNORECASE),
        file_globs=("src/**/*.py",),
    ),
    Check(
        section="Security Signals",
        title="Network Calls (httpx usage)",
        pattern=re.compile(r"\bhttpx\.(Client|AsyncClient|get|post|put|patch|delete|request)\b"),
        file_globs=("src/**/*.py",),
    ),
    Check(
        section="Test Signals",
        title="Redaction-Related Tests",
        pattern=re.compile(r"redact|cookie|authorization|token|jwt", re.IGNORECASE),
        file_globs=("tests/test_*.py",),
    ),
    Check(
        section="Test Signals",
        title="Header / Call Validation Tests",
        pattern=re.compile(r"test_.*(header|cookie|call|validate)", re.IGNORECASE),
        file_globs=("tests/test_*.py",),
    ),
)


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def _iter_files(repo_root: Path, globs: tuple[str, ...]) -> list[Path]:
    found: set[Path] = set()
    for pattern in globs:
        for path in repo_root.glob(pattern):
            if not path.is_file():
                continue
            if _is_excluded(path):
                continue
            found.add(path)
    return sorted(found)


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").splitlines()


def _find_matches(repo_root: Path, check: Check) -> list[tuple[str, int, str]]:
    matches: list[tuple[str, int, str]] = []
    for path in _iter_files(repo_root, check.file_globs):
        rel = path.relative_to(repo_root).as_posix()
        lines = _read_lines(path)
        if check.title == "Oversized Modules (line count > 800)":
            if len(lines) > 800:
                matches.append((rel, len(lines), f"line_count={len(lines)}"))
            continue
        for i, line in enumerate(lines, start=1):
            if check.pattern.search(line):
                matches.append((rel, i, line.rstrip()))
    return matches[: check.max_matches]


def _count_tests(repo_root: Path) -> tuple[int, list[tuple[str, int]]]:
    per_file: list[tuple[str, int]] = []
    total = 0
    for path in _iter_files(repo_root, ("tests/test_*.py",)):
        lines = _read_lines(path)
        count = sum(1 for line in lines if line.lstrip().startswith("def test_"))
        if count:
            rel = path.relative_to(repo_root).as_posix()
            per_file.append((rel, count))
            total += count
    per_file.sort(key=lambda item: (-item[1], item[0]))
    return total, per_file


def _git_value(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _render_report(repo_root: Path, checks: tuple[Check, ...], generated_at: dt.datetime) -> str:
    branch = _git_value(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    commit = _git_value(repo_root, ["rev-parse", "HEAD"])
    status = _git_value(repo_root, ["status", "--short"])
    short_status = "clean" if not status else "dirty"

    by_section: dict[str, list[str]] = {
        "Architecture Signals": [],
        "Security Signals": [],
        "Test Signals": [],
    }
    for check in checks:
        matches = _find_matches(repo_root, check)
        lines = [f"### {check.title}", f"- Matches shown: {len(matches)}"]
        if matches:
            lines.append("```text")
            for rel, line_no, line in matches:
                lines.append(f"{rel}:{line_no}: {line}")
            lines.append("```")
        by_section[check.section].append("\n".join(lines))

    test_total, per_file = _count_tests(repo_root)
    top_files = per_file[:20]
    test_lines = ["### Test Inventory", f"- Total discovered `def test_` functions: {test_total}"]
    if top_files:
        test_lines.append("```text")
        for rel, count in top_files:
            test_lines.append(f"{rel}: {count}")
        test_lines.append("```")
    by_section["Test Signals"].append("\n".join(test_lines))

    header = [
        "# Deterministic Review Report",
        f"Date (UTC): {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Repository: `{repo_root}`",
        "",
        "## Snapshot",
        f"- Branch: `{branch}`",
        f"- Commit: `{commit}`",
        f"- Worktree: `{short_status}`",
        "",
        "## Architecture Signals",
        by_section["Architecture Signals"][0],
        "",
        by_section["Architecture Signals"][1],
        "",
        "## Security Signals",
        by_section["Security Signals"][0],
        "",
        by_section["Security Signals"][1],
        "",
        by_section["Security Signals"][2],
        "",
        "## Test Signals",
        by_section["Test Signals"][0],
        "",
        by_section["Test Signals"][1],
        "",
        by_section["Test Signals"][2],
        "",
        "## Findings (Fill After Analysis)",
        "### 1) <Severity> - <Finding Title>",
        "- File references:",
        "  - `path:line`",
        "- Detail:",
        "  - ...",
        "- Risk:",
        "  - ...",
        "",
        "## Commit Tasks (Small, Sequential)",
        "1. Task: <one logical change>",
        "2. Task: <tests for change>",
        "3. Task: <docs/update state>",
        "",
        "## Validation Commands",
        "- `ruff check src tests`",
        "- `python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`",
        "- `pytest`",
    ]
    return "\n".join(header) + "\n"


def _default_output_path(now: dt.datetime) -> Path:
    stamp = now.strftime("%Y-%m-%d")
    return DEFAULT_OUTPUT_DIR / f"{DEFAULT_OUTPUT_PREFIX}{stamp}.md"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic architecture/security/test review scaffold."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to scan.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report to a path. Default: docs/reviews/REVIEW_<YYYY-MM-DD>.md",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print report to stdout instead of writing a file.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    now = dt.datetime.now(dt.timezone.utc)
    report = _render_report(repo_root=repo_root, checks=CHECKS, generated_at=now)
    if args.stdout:
        print(report, end="")
        return 0

    output = args.output.resolve() if args.output else _default_output_path(now)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote deterministic review scaffold to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
