"""Validate release-line docs do not rely on highest-version tag sorting."""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback.
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
CURRENT_RELEASE_RE = re.compile(
    r"Current production-ready release:\s*`(?P<release>v\d+\.\d+\.\d+)`"
)
VERSION_HEADING_RE = re.compile(r"^## (?P<release>v\d+\.\d+\.\d+) ", re.MULTILINE)


def load_pyproject_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def extract_current_release(state_text: str) -> str | None:
    match = CURRENT_RELEASE_RE.search(state_text)
    if not match:
        return None
    return match.group("release")


def changelog_releases(changelog_text: str) -> set[str]:
    return {match.group("release") for match in VERSION_HEADING_RE.finditer(changelog_text)}


def check_release_governance(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected_release = f"v{load_pyproject_version(root)}"

    state = (root / "docs" / "STATE.md").read_text(encoding="utf-8")
    current_release = extract_current_release(state)
    if current_release is None:
        errors.append("docs/STATE.md must declare `Current production-ready release: `vX.Y.Z``.")
    elif current_release != expected_release:
        errors.append(
            "docs/STATE.md current production-ready release does not match pyproject version: "
            f"state={current_release}, pyproject={expected_release}."
        )

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if expected_release not in changelog_releases(changelog):
        errors.append(f"CHANGELOG.md must include a heading for {expected_release}.")

    versioning = (root / "docs" / "VERSIONING.md").read_text(encoding="utf-8")
    if "Do not derive the current production release by sorting all tags" not in versioning:
        errors.append("docs/VERSIONING.md must forbid current-release selection by tag sorting.")
    if "v1.0.0" not in versioning or "historical" not in versioning.lower():
        errors.append("docs/VERSIONING.md must document the historical `v1.0.0` exception.")

    maintenance = (root / "docs" / "MAINTENANCE.md").read_text(encoding="utf-8")
    if "GitHub issue #34" not in maintenance or "v1.0.0" not in maintenance:
        errors.append("docs/MAINTENANCE.md must reference issue #34 for stale `v1.0.0` governance.")

    return errors


def main() -> int:
    errors = check_release_governance()
    if errors:
        print("Release governance check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Release governance OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
