from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "reviews"

FINDING_PATTERN = re.compile(r"^###\s+\d+\)\s+(.+?)\s+-\s+(.+)$")


def _extract_findings(text: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = FINDING_PATTERN.match(line.strip())
        if not match:
            continue
        severity = match.group(1).strip()
        title = match.group(2).strip()
        findings.append((severity, title))
    return findings


def _normalize_slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "review"


def _render_tasks(review_path: Path, findings: list[tuple[str, str]]) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Commit Task Breakdown",
        f"Generated (UTC): {now}",
        f"Source review: `{review_path}`",
        "",
        "## Tasks",
    ]
    if not findings:
        lines.extend(
            [
                "1. Task: No parsed findings; add findings headings in the source review first.",
                "2. Task: Re-run `python3 scripts/review_findings_to_tasks.py --review <path>`.",
            ]
        )
        return "\n".join(lines) + "\n"

    task_index = 1
    for severity, title in findings:
        lines.extend(
            [
                f"{task_index}. Task: Address `{title}` ({severity}) in code.",
                f"{task_index + 1}. Task: Add or update regression tests for `{title}`.",
                f"{task_index + 2}. Task: Update docs/changelog/state notes for `{title}`.",
            ]
        )
        task_index += 3
    lines.extend(
        [
            "",
            "## Validation",
            "- `ruff check src tests`",
            "- `python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`",
            "- `pytest`",
        ]
    )
    return "\n".join(lines) + "\n"


def _default_output_path(review_path: Path) -> Path:
    stem = _normalize_slug(review_path.stem.replace("REVIEW_", ""))
    return DEFAULT_OUTPUT_DIR / f"TASKS_{stem}.md"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert review findings headings into a small commit-task checklist."
    )
    parser.add_argument(
        "--review",
        type=Path,
        required=True,
        help="Path to review markdown file with findings headings.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for task markdown.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print task breakdown to stdout instead of writing a file.",
    )
    args = parser.parse_args()

    review_path = args.review.resolve()
    text = review_path.read_text(encoding="utf-8")
    findings = _extract_findings(text)
    rendered = _render_tasks(review_path=review_path, findings=findings)

    if args.stdout:
        print(rendered, end="")
        return 0

    output = args.output.resolve() if args.output else _default_output_path(review_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote task breakdown to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
