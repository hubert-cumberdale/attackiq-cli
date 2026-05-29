#!/usr/bin/env python3
"""Scan source files for likely committed secrets with an explicit allowlist."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALLOWLIST = ROOT / "security" / "secret-scan-allowlist.json"
MAX_SCAN_BYTES = 2_000_000

SKIPPED_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".venv/",
    "build/",
    "dist/",
    "site/",
)

TEXT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

TEXT_NAMES = {
    ".gitignore",
    "Dockerfile",
    "LICENSE",
}

SAFE_VALUE_MARKERS = (
    "changeme",
    "dummy",
    "example",
    "placeholder",
    "redacted",
    "sample",
)

SAFE_EXAMPLE_VALUES = {
    "account-token",
    "acct-token-value",
    "do-not-leak",
    "header.payload.signature",
    "jwt-value",
    "secret-token",
    "secret-value",
    "tenant-token-value",
}

SAFE_VARIABLE_VALUES = {
    "account_token",
    "api_token",
    "auth_token",
    "effective_account_token",
    "effective_jwt",
    "jwt",
    "password",
    "secret",
    "token",
}

SECRET_ASSIGNMENT_RE = re.compile(
    r"""
    \b
    (?P<key>
        api[_-]?key
        | api[_-]?token
        | access[_-]?token
        | account[_-]?token
        | auth[_-]?token
        | bearer[_-]?token
        | client[_-]?secret
        | jwt
        | password
        | passwd
        | private[_-]?key
        | refresh[_-]?token
        | secret
        | token
    )
    \b
    \s*(?::|=)\s*
    (?P<quote>['"]?)
    (?P<value>[A-Za-z0-9_./+~:@%=-]{8,})
    (?P=quote)
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class SecretPattern:
    label: str
    regex: re.Pattern[str]


PATTERN_RULES = (
    SecretPattern(
        "private key block",
        re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----"),
    ),
    SecretPattern("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b")),
    SecretPattern("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    SecretPattern("AWS access key", re.compile(r"\bA(?:KIA|SIA)[0-9A-Z]{16}\b")),
    SecretPattern(
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
)


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line_number: int
    label: str

    def message(self) -> str:
        return f"{self.path}:{self.line_number}: possible {self.label}"


@dataclass(frozen=True)
class AllowlistEntry:
    path: str
    labels: frozenset[str]
    line_contains: str | None
    note: str | None

    def allows(self, finding: SecretFinding, line: str) -> bool:
        if finding.path != self.path:
            return False
        if self.labels and finding.label not in self.labels:
            return False
        return self.line_contains is None or self.line_contains in line


def _safe_value(value: str, *, quoted: bool) -> bool:
    normalized = value.strip().strip("'\"").lower()
    if not normalized:
        return True
    if normalized.startswith("<") and normalized.endswith(">"):
        return True
    if normalized.startswith("${") and normalized.endswith("}"):
        return True
    if normalized.startswith("$"):
        return True
    if normalized in SAFE_EXAMPLE_VALUES:
        return True
    if any(marker in normalized for marker in SAFE_VALUE_MARKERS):
        return True
    if quoted:
        return False
    if normalized in SAFE_VARIABLE_VALUES:
        return True
    return "." in value and bool(
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", value)
    )


def _findings_for_line(path_label: str, line_number: int, line: str) -> list[SecretFinding]:
    findings = [
        SecretFinding(path_label, line_number, pattern.label)
        for pattern in PATTERN_RULES
        if pattern.regex.search(line)
    ]
    for match in SECRET_ASSIGNMENT_RE.finditer(line):
        quote = match.group("quote")
        value = match.group("value")
        if _safe_value(value, quoted=bool(quote)):
            continue
        findings.append(SecretFinding(path_label, line_number, "secret assignment"))
    return findings


def _allowed(finding: SecretFinding, line: str, allowlist: tuple[AllowlistEntry, ...]) -> bool:
    return any(entry.allows(finding, line) for entry in allowlist)


def scan_text(
    path_label: str,
    text: str,
    *,
    allowlist: tuple[AllowlistEntry, ...] = (),
) -> list[str]:
    errors: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for finding in _findings_for_line(path_label, line_number, line):
            if not _allowed(finding, line, allowlist):
                errors.append(finding.message())
    return errors


def _coerce_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"allowlist entry {field} must be a non-empty string")
    return value


def load_allowlist(path: Path = DEFAULT_ALLOWLIST) -> tuple[AllowlistEntry, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"{path}: version must be 1")
    raw_entries = data.get("allowlist")
    if not isinstance(raw_entries, list):
        raise ValueError(f"{path}: allowlist must be a list")

    entries: list[AllowlistEntry] = []
    for index, raw_entry in enumerate(raw_entries, start=1):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"{path}: allowlist entry {index} must be an object")
        labels_value = raw_entry.get("labels", [])
        if not isinstance(labels_value, list) or not all(
            isinstance(label, str) for label in labels_value
        ):
            raise ValueError(f"{path}: allowlist entry {index} labels must be a string list")
        line_contains_value = raw_entry.get("line_contains")
        if line_contains_value is not None and not isinstance(line_contains_value, str):
            raise ValueError(f"{path}: allowlist entry {index} line_contains must be a string")
        note_value = raw_entry.get("note")
        if note_value is not None and not isinstance(note_value, str):
            raise ValueError(f"{path}: allowlist entry {index} note must be a string")
        entries.append(
            AllowlistEntry(
                path=_coerce_str(raw_entry.get("path"), field="path"),
                labels=frozenset(labels_value),
                line_contains=line_contains_value,
                note=note_value,
            )
        )
    return tuple(entries)


def _git_scan_files(root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(path) for path in completed.stdout.split("\0") if path]


def _should_scan(relative_path: Path, absolute_path: Path) -> bool:
    path_text = relative_path.as_posix()
    if any(path_text.startswith(prefix) for prefix in SKIPPED_PREFIXES):
        return False
    if not absolute_path.is_file():
        return False
    if absolute_path.stat().st_size > MAX_SCAN_BYTES:
        return False
    suffix = relative_path.suffix.lower()
    return suffix in TEXT_SUFFIXES or relative_path.name in TEXT_NAMES


def scan_files(
    *,
    root: Path = ROOT,
    allowlist: tuple[AllowlistEntry, ...] = (),
) -> list[str]:
    errors: list[str] = []
    for relative_path in _git_scan_files(root):
        absolute_path = root / relative_path
        if not _should_scan(relative_path, absolute_path):
            continue
        try:
            text = absolute_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        errors.extend(scan_text(relative_path.as_posix(), text, allowlist=allowlist))
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allowlist",
        default=str(DEFAULT_ALLOWLIST),
        help="Path to the JSON secret-scan allowlist.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        allowlist = load_allowlist(Path(args.allowlist))
        errors = scan_files(allowlist=allowlist)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Secret scan setup failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("Secret scan failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Secret scan OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
