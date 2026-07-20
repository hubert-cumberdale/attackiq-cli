# Versioning

## Policy
- Use semantic versioning (`MAJOR.MINOR.PATCH`) for CLI and TUI releases.
- Increment MAJOR for breaking changes, MINOR for new features, PATCH for fixes.
- Release tags must be created from `master`.

## Branching
- Stable branch: `master`.
- Release branches: `release/v<major>.<minor>.<patch>` when a dedicated release branch is needed.
- Feature branches: `feature/cli-<short-scope>` and `feature/tui-<short-scope>`.

## Workflow
- Merge feature branches into `master`.
- Tag releases on `master`:
  - Release tags: `v<major>.<minor>.<patch>`
- Cut release branches from the tagged commit as needed.

## Current Release Line
- The current production-ready release is the latest published/tagged version declared in
  `docs/STATE.md`.
- During pre-tag release prep, `docs/STATE.md` may also declare a prepared release candidate. The
  prepared candidate must match `pyproject.toml`, `src/attackiq_cli/__init__.py`,
  `attackiq --version`, and `CHANGELOG.md`; after tagging and publication, promote that version to
  the current production-ready release line.
- Do not derive the current production release by sorting all tags. Historical tags may exist that
  predate current release hygiene.
- Historical exception: `v1.0.0` points to an older commit whose package metadata reports `0.1.0`.
  Keep it as historical/non-production context unless maintainers explicitly approve tag deletion
  or replacement after downstream-impact review.
- `scripts/check_release_governance.py` enforces that either the documented production-ready
  release line or the explicit prepared release candidate follows package metadata, and that the
  historical `v1.0.0` exception remains documented.

## Notes
- Keep `docs/STATE.md` updated with current capabilities and limitations at each release.
- Keep `pyproject.toml`, `src/attackiq_cli/__init__.py`, and `attackiq --version` aligned with
  the release tag.
- Keep `constraints.txt` refreshed whenever dependency ranges or release tooling changes.
- Record notable decisions in `docs/DECISIONS.md`.
- CI release hygiene currently triggers on `v*` tags and validates that the tag matches
  `pyproject.toml` plus a matching `CHANGELOG.md` heading.
