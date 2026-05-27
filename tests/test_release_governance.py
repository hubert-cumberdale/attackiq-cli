from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_release_governance.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("check_release_governance", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
release_governance = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = release_governance
_SCRIPT_SPEC.loader.exec_module(release_governance)


def _write_minimal_repo(root: Path, *, state_release: str = "v0.1.10") -> None:
    (root / "docs").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "attackiq-cli"\nversion = "0.1.10"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## v0.1.10 - 2026-05-12\n",
        encoding="utf-8",
    )
    (root / "docs" / "STATE.md").write_text(
        f"# State\n\n- Current production-ready release: `{state_release}`.\n",
        encoding="utf-8",
    )
    (root / "docs" / "VERSIONING.md").write_text(
        "\n".join(
            [
                "# Versioning",
                "",
                "Do not derive the current production release by sorting all tags.",
                "The historical `v1.0.0` tag is retained as historical context only.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs" / "MAINTENANCE.md").write_text(
        "Stale historical tag `v1.0.0` is tracked in GitHub issue #34.\n",
        encoding="utf-8",
    )


def test_release_governance_passes_when_current_release_matches_metadata(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)

    assert release_governance.check_release_governance(tmp_path) == []


def test_release_governance_rejects_highest_tag_style_mismatch(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path, state_release="v1.0.0")

    errors = release_governance.check_release_governance(tmp_path)

    assert any("does not match pyproject version" in error for error in errors)
