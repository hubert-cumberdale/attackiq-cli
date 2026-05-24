# Maintenance

## Routine Tasks

- Run `python3 scripts/check_public_safety.py` before publication or package promotion.
- Run `python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel` during branch checks,
  then `python3 scripts/check_public_mirror.py --ref vX.Y.Z` from a clean worktree before public
  mirror publication.
- Run `python3 scripts/build_enterprise_package.py --source-ref vX.Y.Z --output-dir <dir>` after
  the public tag is available when enterprise package promotion is in scope.
- Run `.venv/bin/python scripts/quality_gate.py` before release.
- Run `python3 scripts/check_dependency_constraints.py` before release.
- Run `python3 scripts/check_release_governance.py` before release and after changing release
  status docs.
- Run `python3 scripts/check_doc_links.py`, `python3 scripts/render_deep_dives.py --check`, and
  `python3 scripts/verify_deep_dives.py` before release.
- Run `pip-audit` against the installed release environment, plus dependency files when needed.
- Verify the release tag, `pyproject.toml`, `src/attackiq_cli/__init__.py`, `attackiq --version`,
  and `CHANGELOG.md` version heading agree before tagging.
- Review `openapi.yaml` updates and re-test CLI against the latest schema.

## Branching And Release Scheme

- Stable branch: `master`.
- Release branches: `release/v<major>.<minor>.<patch>` when a dedicated release branch is needed.
- Feature branches: `feature/cli-<short-scope>` and `feature/tui-<short-scope>`.
- Release tags: `v<major>.<minor>.<patch>`.
- Practice: merge feature branches into `master`, cut the release tag on `master`, then branch the
  next version from `master`.

## Spec Update Checklist

- Update `src/attackiq_cli/openapi.yaml`.
- Validate `attackiq spec list` and `attackiq spec show`.
- Run targeted read-only commands to confirm pagination and output.

## Security Checklist

- Verify TLS verification defaults remain enabled.
- Confirm redaction paths cover new headers and fields.
- Ensure new network calls set explicit timeouts.
- Confirm no private repository names, workstation paths, tenant data, or raw browser captures are
  tracked.

## Documentation Checklist

- Update `README.md` for user-visible commands.
- Update `docs/STATE.md` for release status, capabilities, or limitations.
- Update `docs/ARCHITECTURE.md` if modules or flows change.
- Record significant choices in `docs/DECISIONS.md`.

## Public Mirror Workflow (2026-05-22)

- Release: `v0.1.14`.
- Private-source GitHub release: published from tag `v0.1.14`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release: published from public tag `v0.1.14`.
- Merge commit: `38af81a`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #43
  (run `26300374202`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `38af81a`
  (run `26300543652`).
- Tag-time CI: passed on Python 3.10, 3.11, and 3.12 for tag `v0.1.14`, including
  release-hygiene checks for dependency constraints, release governance, public safety, strict
  public mirror dry run, changelog heading, tag/package version alignment, and dependency audit
  (run `26300567465`).
- Strict public mirror export: generated from tag `v0.1.14` into
  `/tmp/attackiq-cli-public-export-v0.1.14-20260522`; `PUBLICATION_MANIFEST.json` records source
  commit `38af81a96e1b3716bab66f1a7984960e85f9ad93`, source snapshot `git-archive`, package
  version `0.1.14`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.14` into
  `/tmp/attackiq-cli-public-verify-v0.1.14-20260522`; `git rev-list --count HEAD` returned `1`,
  `python3 scripts/check_public_safety.py --skip-wheel` passed, and a blocked-reference scan found
  no private repository names, workstation paths, or lab-only references.
- Purpose: add the no-history public mirror workflow for `hubert-cumberdale/attackiq-cli`.
- Added guardrail: `scripts/check_public_mirror.py` exports a sanitized source snapshot, writes
  `PUBLICATION_MANIFEST.json`, runs public-safety validation, initializes a one-commit public-style
  repository, and rejects repo-local export directories.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`451 passed`),
  `.venv/bin/python scripts/check_public_mirror.py --allow-dirty` passed with wheel inspection,
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.14`, both dependency-audit
  commands passed, release governance passed, doc-link and deep-dive checks passed, and
  `git diff --check` passed.
- Scope boundary: first public enterprise delivery is GitHub source only. Package registry
  promotion, Artifactory publishing, and package artifacts remain deferred until a separate
  delivery workflow is approved.

## Public Release (2026-05-22)

- Release: `v0.1.13`.
- GitHub release: published from tag `v0.1.13`.
- Merge commit: `529f41d`.
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `529f41d`
  (run `26297870834`).
- Tag-time CI: passed on Python 3.10, 3.11, and 3.12 for tag `v0.1.13`, including
  release-hygiene checks for dependency constraints, release governance, public safety, changelog
  heading, tag/package version alignment, and dependency audit (run `26297913026`).
- Clean install smoke: cloned tag `v0.1.13` into
  `/tmp/aiq-cli-release-checkout-v0.1.13-20260522`, installed into
  `/tmp/aiq-cli-install-smoke-v0.1.13-20260522` with the tagged `constraints.txt`; `attackiq
  --version` reported `attackiq-cli version 0.1.13`, `pip check` passed, and
  `attackiq backup configs --help` rendered.
- Purpose: prepare the repository for public GitHub publication and downstream enterprise package
  promotion.
- Added guardrail: `scripts/check_public_safety.py` scans tracked files and built wheels for
  blocked private references and disallowed artifact paths.
- Removed tracked historical handoffs, review notes, taskpacks, lab scenario payloads, and
  sibling-repository planning docs.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`445 passed`),
  `python3 scripts/check_public_safety.py`, both dependency-audit commands, `attackiq --version`,
  release governance, `git diff --check`, and clean wheel inspection passed.
- Scope boundary: Artifactory or other enterprise package promotion is downstream of the validated
  wheel; this repo does not store enterprise registry credentials or publish automation. The
  current tree is scrubbed, but existing git history still contains removed private/lab files; do
  not make this repository public in place until history handling is explicitly approved.

## Production Promotion (2026-05-22)

- Release: `v0.1.12`
- GitHub release: published from tag `v0.1.12`.
- Purpose: release the first redacted configuration-backup workflow:
  `attackiq backup configs`.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed, doc links, release
  governance, deep-dive render/verification, both dependency-audit commands, `attackiq --version`,
  editable package metadata refresh, and `git diff --check` passed.
- Scope boundary: standard documented CLI work remains approved; configuration-backup artifacts
  must remain redacted and outside git; destructive, high-volume, custom-scenario, restore/apply,
  customer-mode, or raw connector-configuration workflows still require separate approval.

## Previous Production Promotions

- `v0.1.11` added the opt-in live smoke harness for the approved low-risk production roster and
  kept lab-only health gates outside the production roster.
- `v0.1.10` aligned the production operator runbook with release hygiene, clean install smoke, and
  dependency-audit expectations.

## Dependency Constraints

- `constraints.txt` pins the validated CI/release tooling environment.
- CI installs branch/PR and tag-release jobs with `python -m pip install -c constraints.txt ...`.
- `scripts/check_dependency_constraints.py` verifies runtime, dev, and release-audit direct
  dependencies are covered by exact pins in `constraints.txt`.
- `scripts/check_release_governance.py` verifies:
  - `docs/STATE.md` declares the current production-ready release.
  - The declared release matches `pyproject.toml` and `CHANGELOG.md`.
  - `docs/VERSIONING.md` documents that current-release selection must not use highest-version tag
    sorting and records the historical `v1.0.0` exception.
- Stale historical tag governance remains tracked in GitHub issue #34 for the `v1.0.0` exception.
