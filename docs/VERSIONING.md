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

## First Governed Stable Line

- `v1.1.0` is the prepared first governed stable candidate for enterprise operators. Its
  Production/Stable package classifier records the intended compatibility line; it becomes GA
  only after every gate in `docs/ROADMAP.md` and `docs/PRODUCTION_READINESS.md` passes for the same
  immutable candidate.
- Until that promotion, `v0.1.27` remains the current production-ready Beta. Both private-source
  and public `v1.1.0` GitHub releases remain prereleases, and the candidate is not the current
  production-ready release or an authorization for tenant activity.
- The stale historical `v1.0.0` tag remains immutable, non-production history. Do not delete,
  replace, move, or treat it as the first governed stable release.
- Within a stable major version, documented commands, options, configuration keys, environment
  variables, exit behavior, and machine-readable output classified as stable in
  `docs/GA_STABLE_CONTRACT.md` remain compatible.
- A deprecation must warn for at least one subsequent minor release. A deprecated stable surface
  is removed no earlier than the next major release.

## Notes
- Keep `docs/STATE.md` updated with current capabilities and limitations at each release.
- Keep `pyproject.toml`, `src/attackiq_cli/__init__.py`, and `attackiq --version` aligned with
  the release tag.
- Keep `constraints.txt` refreshed whenever dependency ranges or release tooling changes.
- Record notable decisions in `docs/DECISIONS.md`.
- CI release hygiene currently triggers on `v*` tags and validates that the tag matches
  `pyproject.toml` plus a matching `CHANGELOG.md` heading.
