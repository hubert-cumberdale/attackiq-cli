# Decisions (Lightweight ADR)

Use this log to capture key decisions and the rationale behind them.

## Template
- Date:
- Decision:
- Context:
- Rationale:
- Consequences:

## Log
- 2026-01-23: Avoid external README badges; keep docs self-contained.
  - Context: documentation should not introduce external dependencies.
  - Rationale: minimize outbound calls and keep README stable offline.
  - Consequences: use local text links instead of badge images.
- 2026-01-24: Adopt Textual for the initial TUI implementation.
  - Context: new TUI needed for status/config visibility and scenario browsing.
  - Rationale: modern Python TUI framework with maintained ecosystem and Python 3.10 support.
  - Consequences: add `textual` dependency and keep TUI scope minimal/read-only initially.
- 2026-05-13: Keep historical `v1.0.0` tag but exclude it from current-release selection.
  - Context: `v1.0.0` points to an older commit whose package metadata reports `0.1.0`, while
    the `v0.1.x` line is the current production-ready release line with passing release hygiene.
  - Rationale: deleting or moving a published tag is a destructive governance action; explicit
    release status docs and validation avoid accidental highest-version tag selection.
  - Consequences: current-release automation must use the documented release line and package
    metadata, not semantic tag sorting; `scripts/check_release_governance.py` enforces this rule.
- 2026-07-21: Target `v1.1.0` as the first governed GA release for enterprise operators.
  - Context: `v0.1.27` is a production-ready Beta, while the stale `v1.0.0` tag is immutable
    non-production history and cannot establish a stable release contract.
  - Rationale: a 14-consecutive-day rollout on one approved production tenant, with Python
    3.10-3.13 qualification and explicit rollout, security, and rollback ownership, provides a
    reviewable graduation boundary.
  - Consequences: stable major-version surfaces remain compatible; deprecations warn for at least
    one subsequent minor and removals wait until the next major. GA covers existing read-only and
    fake-ID dry-run workflows only; apply mode, PyPI and broad public-package support, AIQ Assist
    MCP consumption, and new wrapper or TUI expansion remain outside scope.
