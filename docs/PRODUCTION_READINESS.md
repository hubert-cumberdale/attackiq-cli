# Production Readiness

This checklist defines the minimum bar before using `attackiq-cli` for production operator
workflows or promoting a release package.

Current release status: `v0.1.16` is production-ready for standard documented CLI work and
credential-free enterprise package promotion as of 2026-05-25 after public-safety cleanup, public
mirror validation, package promotion artifact validation, offline package verification, local
quality gates, release governance checks, and package guard updates. Continue to require
workflow-specific approval for destructive, high-volume, custom-scenario, restore/apply, or
tenant-data-heavy activity.

Operators should use `docs/PRODUCTION_OPERATOR_RUNBOOK.md` for production install, configuration,
approved workflow, rollback, and evidence procedures.

## Readiness States

| State | Meaning | Allowed use |
| --- | --- | --- |
| Development | Feature work is still changing behavior or contracts. | Local development only. |
| Pilot | Local checks pass and workflows are documented, but release gates are incomplete. | Controlled internal use with dry-run defaults. |
| Production candidate | Local and CI gates pass, release metadata is aligned, and acceptance checks pass in a non-production tenant. | Limited production rollout with named operators. |
| Production | Candidate has been tagged, audited, documented, and used successfully in limited rollout. | Standard work use. |

## Go/No-Go Gates

| Gate | Required evidence |
| --- | --- |
| Public safety | `python3 scripts/check_public_safety.py` passes for tracked files and wheel contents. |
| Public mirror | `python3 scripts/check_public_mirror.py --ref vX.Y.Z` passes from a clean worktree and verifies a one-commit snapshot. |
| Enterprise package artifacts | `python3 scripts/build_enterprise_package.py --source-ref vX.Y.Z --output-dir <dir>` and `python3 scripts/verify_enterprise_package.py <dir>` pass for the public tag and produced package directory. |
| Quality gate | `.venv/bin/python scripts/quality_gate.py` passes without skips unless documented. |
| CI matrix | GitHub Actions passes on Python 3.10, 3.11, and 3.12 for the candidate commit. |
| Dependency audit | `pip-audit` against the installed constrained environment reports no unresolved known vulnerabilities. |
| Release metadata | `pyproject.toml`, `src/attackiq_cli/__init__.py`, `attackiq --version`, `CHANGELOG.md`, and the release tag all agree. |
| Documentation integrity | `python3 scripts/check_doc_links.py`, `python3 scripts/render_deep_dives.py --check`, `python3 scripts/verify_deep_dives.py`, and MkDocs build pass. |
| Security review | TLS defaults, explicit timeouts, dry-run/apply behavior, redaction, and config permission handling are reviewed for changed code paths. |
| Worktree hygiene | Release candidate branch has no unrelated or generated-file changes. |

## Live Acceptance Checks

Run these against a non-production AttackIQ tenant with redacted outputs. Do not store raw tokens,
cookies, signed URLs, or private host data in the repo.

```bash
.venv/bin/python scripts/live_smoke.py --dry-run
ATTACKIQ_LIVE_SMOKE=1 .venv/bin/python scripts/live_smoke.py \
  --output-dir /tmp/aiq-cli-live-smoke-acceptance
```

The harness omits all `--apply` commands. Preserve only redacted summaries in repo-tracked
evidence.

## Rollout Plan

1. Stabilize: fix all quality-gate failures and remove stale/untracked artifacts.
2. Audit: run dependency audit, security/redaction review, public-safety, public-mirror,
   enterprise-package build/verification, and docs integrity checks.
3. Cut candidate: update changelog/version metadata and tag only after local and CI gates pass.
4. Pilot: run live acceptance checks in a non-production tenant with named operators.
5. Promote: mark the release production-ready only after pilot notes and any follow-up fixes are
   recorded.

The historical `v1.0.0` tag is stale release-governance debt tracked in GitHub issue #34 and
should not be used to identify the current production release line.

## Operational Requirements

- Keep generated scenario packages, runtime caches, API responses, backup artifacts, and MkDocs
  `site/` output outside git.
- Keep TLS verification enabled unless a documented lab exception requires `--insecure`.
- Prefer environment variables for tokens in automation.
- Preserve dry-run defaults for writes.
- Use `constraints.txt` for reproducible operator installs:

```bash
python -m pip install -c constraints.txt --upgrade pip
python -m pip install -c constraints.txt .
```
