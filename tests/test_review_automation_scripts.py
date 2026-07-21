from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_deterministic_review() -> Any:
    script_path = _repo_root() / "scripts" / "deterministic_review.py"
    spec = importlib.util.spec_from_file_location("deterministic_review", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(Any, module)


deterministic_review = _load_deterministic_review()


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


def test_deterministic_review_worktree_status_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["git", "status", "--short"],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(deterministic_review.subprocess, "run", fake_run)

    assert deterministic_review._git_worktree_status(_repo_root()) == "clean"


def test_deterministic_review_worktree_status_dirty(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["git", "status", "--short"],
            returncode=0,
            stdout=" M docs/STATE.md\n",
            stderr="",
        )

    monkeypatch.setattr(deterministic_review.subprocess, "run", fake_run)

    assert deterministic_review._git_worktree_status(_repo_root()) == "dirty"


def test_deterministic_review_worktree_status_unknown_on_git_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=1, cmd=["git", "status", "--short"])

    monkeypatch.setattr(deterministic_review.subprocess, "run", fake_run)

    assert deterministic_review._git_worktree_status(_repo_root()) == "unknown"


def test_deterministic_review_architecture_check_enforces_800_line_boundary(
    tmp_path: Path,
) -> None:
    src_dir = tmp_path / "src" / "package"
    src_dir.mkdir(parents=True)
    (src_dir / "within_boundary.py").write_text("value = 1\n" * 800, encoding="utf-8")
    oversized_path = src_dir / "oversized.py"
    oversized_path.write_text("value = 1\n" * 801, encoding="utf-8")

    result = subprocess.run(
        [
            "python3",
            "scripts/deterministic_review.py",
            "--repo-root",
            str(tmp_path),
            "--check-architecture",
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Python modules must not exceed 800 lines" in result.stderr
    assert "src/package/oversized.py: 801 lines" in result.stderr
    assert "within_boundary.py" not in result.stderr

    oversized_path.write_text("value = 1\n" * 800, encoding="utf-8")
    result = subprocess.run(
        [
            "python3",
            "scripts/deterministic_review.py",
            "--repo-root",
            str(tmp_path),
            "--check-architecture",
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "no Python modules exceed 800 lines" in result.stdout


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
