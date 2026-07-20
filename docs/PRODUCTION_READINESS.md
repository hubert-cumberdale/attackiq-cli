# Production Readiness

This checklist defines the minimum bar before using `attackiq-cli` for production operator
workflows or promoting a release package.

Current release status: `v0.1.26` is the latest published/tagged production release as of
2026-06-25. Release evidence records the source release commit
`bc85fc96dd663b3f230db5a077313469c3e6987b`, public mirror snapshot
`ad46849452f5d63e5b84caf6df555d8120a095ae`, tag-time CI run `28193339998`, strict public mirror
validation, public GitHub release publication, enterprise package verification, generated SBOM,
dependency-integrity and provenance records, Artifactory promotion evidence, signing and
attestation evidence, combined enterprise evidence verification, and the offline wheelhouse install
smoke. Continue to require workflow-specific approval for destructive, high-volume,
custom-scenario, restore/apply, or tenant-data-heavy activity.

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
| Secret scan | `python3 scripts/check_secret_scan.py` passes with only reviewed entries in `security/secret-scan-allowlist.json`. |
| Release-prep evidence | `docs/RELEASE_PREP_EVIDENCE_CHECKLIST.md` is completed before tag creation, including dependency constraints, public safety, secret scan, public mirror dry-run, `pip-audit`, constraints audit, and local quality-gate evidence. |
| Public mirror | `python3 scripts/check_public_mirror.py --ref vX.Y.Z` passes from a clean worktree and verifies a one-commit snapshot. |
| Enterprise package artifacts | `python3 scripts/build_enterprise_package.py --source-ref vX.Y.Z --output-dir <dir>` and `python3 scripts/verify_enterprise_package.py <dir> --require-constraints` pass for the public tag and produced package directory, including declared install constraints, dependency integrity, SBOM, and package provenance. |
| Artifactory promotion evidence | `python3 scripts/build_artifactory_promotion_evidence.py <dir> --output <file>` passes for a verified package directory when Artifactory promotion is in scope; output contains no credentials. |
| Signing and attestation evidence | `python3 scripts/build_signing_attestation_evidence.py <dir> --output <file>` passes for a verified package directory when signing or attestation is in scope; output contains no signing keys or credentials. |
| Enterprise evidence verification | `python3 scripts/verify_enterprise_evidence.py <dir> --require-artifactory --require-signing` passes when both evidence files are in scope. |
| Post-download package evidence | `docs/POST_DOWNLOAD_PACKAGE_EVIDENCE_CHECKLIST.md` is completed in the enterprise release record for the downloaded wheel, constraints, SBOM, dependency integrity, provenance, signatures, attestations, trust-root verification, and install smoke evidence. |
| No-Artifactory install simulation | Build a local wheelhouse from the verified package directory, then install `attackiq-cli==<version>` into a fresh venv with `--no-index --find-links`, the promoted `constraints.txt`, and no direct Artifactory access. |
| Quality gate | `.venv/bin/python scripts/quality_gate.py` passes without skips unless documented. |
| CI/local gate parity | GitHub Actions covers the same release-critical script linting and contract checks as `scripts/quality_gate.py`, or documented drift is tracked before release. |
| CI matrix | GitHub Actions passes on Python 3.10, 3.11, and 3.12 for the candidate commit. |
| CI action runtime | Workflow uses Node 24-compatible official action majors and has no Node 20 deprecation annotation. |
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

## Rollout Plan

1. Stabilize: fix all quality-gate failures and remove stale/untracked artifacts.
2. Audit: run dependency audit, security/redaction review, public-safety, public-mirror,
   enterprise-package build/verification, no-Artifactory install simulation when direct registry
   access is unavailable, and docs integrity checks.
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
