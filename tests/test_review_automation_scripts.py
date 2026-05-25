from __future__ import annotations

import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_deterministic_review_script_stdout_contains_core_sections() -> None:
    repo = _repo_root()
    result = subprocess.run(
        ["python3", "scripts/deterministic_review.py", "--stdout"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    out = result.stdout
    assert "# Deterministic Review Report" in out
    assert "## Architecture Signals" in out
    assert "## Security Signals" in out
    assert "## Test Signals" in out
    assert "## Findings (Fill After Analysis)" in out
    assert "## Commit Tasks (Small, Sequential)" in out


def test_findings_to_tasks_parses_hyphenated_severity(tmp_path: Path) -> None:
    review = tmp_path / "review.md"
    review.write_text(
        "\n".join(
            [
                "# Review",
                "### 1) High - Cookie redaction gap",
                "### 2) Low-Medium - Header control character validation",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python3",
            "scripts/review_findings_to_tasks.py",
            "--review",
            str(review),
            "--stdout",
        ],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    out = result.stdout
    assert "Cookie redaction gap" in out
    assert "Header control character validation" in out
    assert "(Low-Medium)" in out
