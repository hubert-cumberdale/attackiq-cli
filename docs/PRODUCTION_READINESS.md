# Production Readiness

This checklist defines the minimum bar before using `attackiq-cli` for production operator
workflows, promoting a production-ready Beta package, or graduating a release to General
Availability (GA).

Current release status: `v0.1.27` is the latest published and tagged production-ready Beta as of
2026-07-20; it is not GA. Release evidence records the source release commit
`6c26c502bfa16000fcb6bf8c4482b414f9bf8963`, public mirror snapshot
`0af7861abebd0d5ef9f3443b389b54d5f30da3eb`, tag-time CI run `29769671071`, strict public mirror
validation, public GitHub release publication, enterprise package verification, generated SBOM,
dependency-integrity and provenance records, Artifactory promotion evidence, signing and
attestation evidence, combined enterprise evidence verification, and the offline wheelhouse install
smoke. Continue to require workflow-specific approval for destructive, high-volume,
custom-scenario, restore/apply, or tenant-data-heavy activity.

Prepared candidate status: `v1.1.0` is the explicitly non-GA stable candidate for Gate 4. Its
package metadata is Production/Stable, while `v0.1.27` remains the production-ready Beta. The
private-source and public GitHub release records must remain prereleases with no attached artifacts
until a later GA promotion is separately authorized and completed.

Operators should use `docs/PRODUCTION_OPERATOR_RUNBOOK.md` for production install, configuration,
approved workflow, rollback, and evidence procedures.

## Readiness States

| State | Meaning | Allowed use |
| --- | --- | --- |
| Development | Feature work is still changing behavior or contracts. | Local development only. |
| Pilot | Local checks pass and workflows are documented, but release gates are incomplete. | Controlled internal use with dry-run defaults. |
| Production candidate | Local and CI gates pass, release metadata is aligned, and acceptance checks pass in a non-production tenant. | Candidate validation with named operators. |
| Production-ready Beta | Candidate has been tagged, audited, documented, and used successfully in a limited rollout, but has not passed the GA graduation gates. | Approved production work within documented workflow boundaries. |
| GA candidate | One immutable stable candidate has passed pre-rollout GA gates and is undergoing its approved production rollout. | The bounded GA roster on one approved production tenant only. |
| General Availability | The same immutable GA candidate has passed every graduation gate and has been explicitly promoted in `docs/STATE.md`. | Supported enterprise use within the certified stable contract. |

## Go/No-Go Gates

| Gate | Required evidence |
| --- | --- |
| Public safety | `python3 scripts/check_public_safety.py` passes for tracked files and wheel contents. |
| Secret scan | `python3 scripts/check_secret_scan.py` passes with only reviewed entries in `security/secret-scan-allowlist.json`. |
| Release-prep evidence | `docs/RELEASE_PREP_EVIDENCE_CHECKLIST.md` is completed before tag creation, including dependency constraints, public safety, secret scan, public mirror dry-run, `pip-audit`, constraints audit, and local quality-gate evidence. |
| Public mirror | `python3 scripts/check_public_mirror.py --ref vX.Y.Z` passes from a clean worktree and verifies a one-commit snapshot. |
| Enterprise package artifacts | Gate 4 entry criterion: after the immutable public candidate tag exists, `python3 scripts/build_enterprise_package.py --source-ref vX.Y.Z --output-dir <dir>` and `python3 scripts/verify_enterprise_package.py <dir> --require-constraints` pass for that tag and produced package directory, including declared install constraints, dependency integrity, SBOM, and package provenance. A pre-tag package is not Gate 3 evidence. |
| Artifactory promotion evidence | `python3 scripts/build_artifactory_promotion_evidence.py <dir> --output <file>` passes for a verified package directory when Artifactory promotion is in scope; output contains no credentials. |
| Signing and attestation evidence | `python3 scripts/build_signing_attestation_evidence.py <dir> --output <file>` passes for a verified package directory when signing or attestation is in scope; output contains no signing keys or credentials. |
| Enterprise evidence verification | `python3 scripts/verify_enterprise_evidence.py <dir> --require-artifactory --require-signing` passes when both evidence files are in scope. |
| Post-download package evidence | `docs/POST_DOWNLOAD_PACKAGE_EVIDENCE_CHECKLIST.md` is completed in the enterprise release record for the downloaded wheel, constraints, SBOM, dependency integrity, provenance, signatures, attestations, trust-root verification, and install smoke evidence. |
| No-Artifactory install simulation | Build a local wheelhouse from the verified package directory, then install `attackiq-cli==<version>` into a fresh venv with `--no-index --find-links`, the promoted `constraints.txt`, and no direct Artifactory access. |
| Quality gate | `.venv/bin/python scripts/quality_gate.py` passes without skips unless documented. |
| CI/local gate parity | GitHub Actions covers the same release-critical script linting and contract checks as `scripts/quality_gate.py`, or documented drift is tracked before release. |
| CI matrix | Gate 3 evidence: PR #166 and post-merge CI run `29856520468` passed the exact Python 3.10, 3.11, 3.12, and 3.13 matrix for merge commit `04f999d039d26684891cea40e04e2b8df20fc46f`. |
| CI action runtime | Workflow uses Node 24-compatible official action majors and has no Node 20 deprecation annotation. |
| Dependency audit | `pip-audit` against the installed constrained environment reports no unresolved known vulnerabilities. |
| Release metadata | `pyproject.toml`, `src/attackiq_cli/__init__.py`, `attackiq --version`, `CHANGELOG.md`, and the release tag all agree. |
| Documentation integrity | `python3 scripts/check_doc_links.py`, `python3 scripts/render_deep_dives.py --check`, `python3 scripts/verify_deep_dives.py`, and MkDocs build pass. |
| Security review | TLS defaults, explicit timeouts, dry-run/apply behavior, redaction, and config permission handling are reviewed for changed code paths. |
| Worktree hygiene | Release candidate branch has no unrelated or generated-file changes. |

## General Availability Readiness

`v1.1.0` is the prepared first governed stable candidate for enterprise operators. `v0.1.27`
remains the current production-ready Beta until all seven gates pass. Preparing or publishing the
candidate does not authorize production activity or declare GA, and both GitHub release records
remain prereleases until a later promotion is separately authorized.

Graduation gates, in order:

1. Freeze GA scope to the existing read-only workflows and mutation dry-run workflows. Apply mode,
   PyPI and broad public-package support, AIQ Assist MCP consumption, and new wrapper or TUI
   expansion remain outside this milestone.
2. Inventory the stable CLI and configuration contract, then add contract-test tasks for every
   documented command and option, configuration key, environment variable, exit behavior, and
   machine-readable output shape. Use `docs/GA_STABLE_CONTRACT.md` as the planning and task-status
   baseline. The command-tree fixture, documentation parity classifications,
   persisted-configuration, environment-variable, exit-behavior, and machine-output contract
   suites and the live-smoke scope and effective-TLS guards are implemented. Task 8 added the exact
   Python 3.10-3.13 CI matrix contract and is complete, closing the Gate 2 backlog.
3. Completed on 2026-07-21: PR #166 qualified Python 3.10, 3.11, 3.12, and 3.13 and squash-merged as
   commit `04f999d039d26684891cea40e04e2b8df20fc46f`. Post-merge CI run `29856520468` passed the
   exact four-version matrix. A fresh, constrained, uv-managed CPython 3.13.12 environment passed
   the full quality gate with 898 tests; the installed-environment and direct-constraints audits
   reported no known vulnerabilities. The source-level quality, security, documentation, and
   public-mirror gates passed without changing release behavior.
4. Authorized and in progress on 2026-07-21: prepare immutable `v1.1.0` candidate metadata, change
   the package classifier to Production/Stable, and publish verified private-source and public
   candidate tags and prereleases while keeping the release explicitly non-GA in `docs/STATE.md`.
   Tag-only enterprise-package and downstream evidence checks remain mandatory after the immutable
   public candidate tag exists; do not substitute or claim a pre-tag candidate package.
5. Run an approved 14-consecutive-day rollout against one production tenant with named operators
   and the bounded read-only and fake-ID dry-run roster. Require UTC checkpoints on days 0, 7, and
   14, TLS verification, redacted aggregate evidence, no apply operations, and a successful
   rollback rehearsal to `v0.1.27`.
6. Promote that same immutable `v1.1.0` candidate to GA only when no unresolved Critical or High
   incident, credential exposure, unintended write, rollback failure, or release-integrity failure
   remains.
7. If the rollout fails, leave the tag explicitly non-GA, suspend further use, fix forward in a new
   patch candidate, and restart the full 14-day clock. Never move or replace an existing tag.

### Required GA Outcomes

- Rollout: one approved production tenant completes 14 consecutive days with the bounded
  read-only and fake-ID dry-run roster, TLS verification, and checkpoints on days 0, 7, and 14.
- Rollback: the rollback owner successfully rehearses restoration to `v0.1.27`, and no rollback
  failure remains unresolved.
- Support: the release record assigns a release owner, production operator, security reviewer, and
  rollback owner, with a documented escalation path for the rollout. Assignments may live in the
  approved enterprise system; public docs must not expose private identities.
- Compatibility: the documented stable CLI and configuration contract follows the compatibility,
  deprecation, and removal policy in `docs/VERSIONING.md`.
- Evidence: the tracked record contains only version, public commit, UTC checkpoints, command
  categories, aggregate results, incidents, and rollback status. Credentials, tenant URLs, tenant
  or operator identifiers, raw responses, and local paths remain outside git.

Issues #60 and #61 remain non-blocking watch epics unless a rollout finding creates a concrete GA
blocker. AIQ Assist MCP consumption remains disabled. Apply-mode workflows require a separate
approval after GA and are not certified by this milestone.

Gates 1-3 are complete and Gate 4 candidate preparation is in progress. Gate 3 evidence is
anchored to PR #166, merge commit
`04f999d039d26684891cea40e04e2b8df20fc46f`, post-merge CI run `29856520468`, the 898-test
CPython 3.13.12 quality gate, and clean installed-environment and direct-constraints dependency
audits. Prepared version `1.1.0` and the Production/Stable classifier do not change Python
`>=3.10`, the Python 3.10 Ruff/mypy baselines, dependencies, API behavior, or apply restrictions.
Gate 5 remains separately authorized.

## Live Acceptance Checks

Run these against a non-production AttackIQ tenant with redacted outputs. Do not store raw tokens,
cookies, signed URLs, or private host data in the repo.

```bash
.venv/bin/python scripts/live_smoke.py --dry-run
ATTACKIQ_LIVE_SMOKE=1 .venv/bin/python scripts/live_smoke.py \
  --output-dir /tmp/aiq-cli-live-smoke-acceptance
```

The harness omits all `--apply` commands. Preserve only redacted summaries in repo-tracked
evidence. Live execution refuses page sizes above 5 and exits before launching any command unless
the effective base URL uses `https://` and persisted configuration has TLS verification enabled.
The plan-only `--dry-run` does not load tenant configuration or make network requests.

## No-Artifactory Enterprise Validation

When direct Artifactory access is unavailable, validate the repository-owned delivery boundary with
offline package and local install checks:

Use `docs/NO_ARTIFACTORY_RELEASE_EVIDENCE_TEMPLATE.md` to record public-safe command status,
artifact digests, generated evidence checks, and the local wheelhouse install simulation without
capturing registry credentials, private coordinates, trust-root material, or workstation paths.
`docs/RELEASE_AUDIT_WRAPPER_EVALUATION.md` records the current decision to keep this template and
the individual validation scripts as the evidence standard instead of adding an executing wrapper
for the current release line.

```bash
python3 scripts/build_enterprise_package.py \
  --source-ref vX.Y.Z \
  --output-dir /tmp/attackiq-cli-enterprise-package-vX.Y.Z
python3 scripts/verify_enterprise_package.py /tmp/attackiq-cli-enterprise-package-vX.Y.Z --require-constraints
python3 scripts/build_artifactory_promotion_evidence.py \
  /tmp/attackiq-cli-enterprise-package-vX.Y.Z \
  --artifactory-url https://artifactory.example.com/artifactory \
  --repository-path api/pypi/attackiq-cli-local \
  --output /tmp/attackiq-cli-enterprise-package-vX.Y.Z/ARTIFACTORY_PROMOTION_EVIDENCE.json
python3 scripts/build_signing_attestation_evidence.py \
  /tmp/attackiq-cli-enterprise-package-vX.Y.Z \
  --signing-profile enterprise-release \
  --output /tmp/attackiq-cli-enterprise-package-vX.Y.Z/SIGNING_ATTESTATION_EVIDENCE.json
python3 scripts/verify_enterprise_evidence.py \
  /tmp/attackiq-cli-enterprise-package-vX.Y.Z \
  --require-artifactory \
  --require-signing
```

Then populate a local wheelhouse and install from it without contacting Artifactory:

```bash
mkdir -p /tmp/attackiq-cli-enterprise-package-vX.Y.Z/local-wheelhouse
python -m pip download \
  --dest /tmp/attackiq-cli-enterprise-package-vX.Y.Z/local-wheelhouse \
  -c /tmp/attackiq-cli-enterprise-package-vX.Y.Z/constraints.txt \
  /tmp/attackiq-cli-enterprise-package-vX.Y.Z/attackiq_cli-X.Y.Z-py3-none-any.whl
python -m venv /tmp/attackiq-cli-enterprise-package-vX.Y.Z/install-venv
/tmp/attackiq-cli-enterprise-package-vX.Y.Z/install-venv/bin/python -m pip install \
  --no-index \
  --find-links /tmp/attackiq-cli-enterprise-package-vX.Y.Z/local-wheelhouse \
  -c /tmp/attackiq-cli-enterprise-package-vX.Y.Z/constraints.txt \
  attackiq-cli==X.Y.Z
/tmp/attackiq-cli-enterprise-package-vX.Y.Z/install-venv/bin/attackiq --version
/tmp/attackiq-cli-enterprise-package-vX.Y.Z/install-venv/bin/attackiq config validate
```

This path validates package reproducibility, evidence consistency, dependency availability, and
installability without registry credentials. It does not replace operator-run upload/download,
repository permission, artifact signing, attestation publication, trust-root verification, or the
post-download package evidence checklist.

## Production-Ready Beta Rollout Plan

1. Stabilize: fix all quality-gate failures and remove stale/untracked artifacts.
2. Audit: run dependency audit, security/redaction review, public-safety, public-mirror,
   enterprise-package build/verification, no-Artifactory install simulation when direct registry
   access is unavailable, and docs integrity checks.
3. Cut candidate: update changelog/version metadata and tag only after local and CI gates pass.
4. Pilot: run live acceptance checks in a non-production tenant with named operators.
5. Promote: mark the release production-ready Beta only after pilot notes and any follow-up fixes
   are recorded. This promotion does not imply GA.

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
