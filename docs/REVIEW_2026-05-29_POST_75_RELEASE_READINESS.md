# Post-75 Release Readiness Review
Date: 2026-05-29
Scope: merged PR #75, current `Unreleased` release-candidate readiness, local/GitHub quality
gates, documentation drift, issue housekeeping, and future roadmap readiness.

## Executive Summary

PR #75 is merged at commit `44b2e5f2e10c155572ae3fa77104ee22b9678ff3`. It completed the first
roadmap slices for architecture decomposition, the `source-types` read-only wrapper, enterprise
SBOM/dependency-integrity output, allowlisted source-secret scanning, and CI/local quality-gate
parity.

No blocking release-readiness defect was found. The current post-#75 state is ready for the
`v0.1.25` release-candidate metadata prepared after this audit. It is not yet a release tag:
publishing still needs release branch/PR validation, an explicit tag command, and tag-time
release-hygiene evidence.

## Review Inputs

- PR #75: `https://github.com/hubert-cumberdale/aiq-cli/pull/75`
- Merge commit: `44b2e5f2e10c155572ae3fa77104ee22b9678ff3`
- Prior review: `docs/REVIEW_2026-05-27_ENTERPRISE_MATURITY.md`
- Current docs: `README.md`, `CHANGELOG.md`, `docs/STATE.md`, `docs/ROADMAP.md`,
  `docs/ARCHITECTURE.md`, `docs/ARCHITECTURE_STANDARDS.md`,
  `docs/PRODUCTION_READINESS.md`, `docs/PUBLIC_RELEASE.md`,
  `docs/ARTIFACTORY_DELIVERY.md`, and `docs/PRODUCTION_OPERATOR_RUNBOOK.md`
- Quality definitions: `.github/workflows/ci.yml` and `scripts/quality_gate.py`
- GitHub issues: #54 through #61 and new release-prep tracker #76

## PR #75 Regression Surface

Architecture splits:

- Added `src/attackiq_cli/mutations.py` for shared mutation dry-run/apply output handling.
- Added `src/attackiq_cli/tui_provider.py` for TUI provider/cache behavior while preserving the
  read-only tab shell in `src/attackiq_cli/tui.py`.
- Added `src/attackiq_cli/backup_catalog.py` for endpoint-catalog model, loading, validation, and
  requested-domain safety checks.
- Added `src/attackiq_cli/service_core.py`, `src/attackiq_cli/services_tags.py`, and
  `src/attackiq_cli/services_source_types.py` while keeping the existing
  `src/attackiq_cli/services.py` import surface compatible.
- Added `src/attackiq_cli/scenario_wizard_validation.py` for Scenario Wizard runtime bundle and
  generated scenario validation helpers.

Read-only wrapper expansion:

- Added `attackiq source-types list` for `v1_source_types_list`.
- The wrapper requires `--company-id` and `--connector-id`, supports existing timeout/TLS/output
  patterns, and emits summary records without connector configuration.
- Coverage includes service-boundary tests and CLI forwarding/output tests.

Supply-chain and release hardening:

- Added `scripts/package_sbom.py` and `ENTERPRISE_PACKAGE_SBOM.spdx.json` generation for
  enterprise packages.
- Added `scripts/package_dependency_integrity.py` and `ENTERPRISE_DEPENDENCY_INTEGRITY.json`.
- Extended enterprise package, Artifactory evidence, signing evidence, and enterprise evidence
  verification to account for SBOM and dependency-integrity records.
- Added `scripts/check_secret_scan.py` with `security/secret-scan-allowlist.json`.
- Added CI steps for secret scanning, AIQ Assist MCP contract gates, and expanded Ruff coverage.

## CI And Local Gate Parity

The CI workflow and local quality gate now cover the same release-critical script families for
dependency constraints, release governance, public safety, secret scanning, public mirror dry run,
AIQ Assist MCP contract fixtures, Ruff, mypy, pytest, and doc links. CI additionally runs
deep-dive render and contract verification in the branch test matrix. The full local quality gate
can include MkDocs when docs dependencies are installed.

GitHub Actions success was confirmed for merge commit `44b2e5f2e10c155572ae3fa77104ee22b9678ff3`:

| Evidence | Result |
| --- | --- |
| Run | `26613853915` |
| Event/branch | `push` on `master` |
| Workflow | `CI` |
| Result | Success |
| Python jobs | `test (3.10)`, `test (3.11)`, and `test (3.12)` all succeeded |
| Tag-only job | `release-hygiene` skipped as expected for a branch push |

## Validation Results

| Check | Result | Notes |
| --- | --- | --- |
| `python3 scripts/check_dependency_constraints.py` | Pass | Dependency metadata and constraints are aligned. |
| `python3 scripts/check_release_governance.py` | Pass | Release governance OK. |
| `python3 scripts/check_public_safety.py` | Pass | Built and scanned the current wheel successfully. |
| `python3 scripts/check_secret_scan.py` | Pass | Secret scan OK. |
| `python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass | Public mirror dry run OK for `HEAD`; source commit was `44b2e5f2e10c155572ae3fa77104ee22b9678ff3`. |
| `python3 scripts/check_aiq_assist_mcp_contract.py` | Pass | AIQ Assist MCP provider contract status OK. |
| `python3 scripts/check_aiq_assist_mcp_fixtures.py` | Pass | AIQ Assist MCP fixtures OK. |
| `python3 scripts/quality_gate.py --no-mkdocs` | Environment miss | The system `python3` lacks `ruff`, so the command failed at the Ruff step. |
| `.venv/bin/python scripts/quality_gate.py --no-mkdocs` | Pass | Equivalent project-dev-environment gate passed with Ruff, mypy, doc links, and `523 passed`. |
| `.venv/bin/python scripts/quality_gate.py` | Pass | Final `v0.1.25` release-candidate gate passed with public safety, secret scan, public mirror dry run, Ruff, mypy, `523 passed`, doc links, and MkDocs. |
| `python3 scripts/check_doc_links.py` | Pass | All referenced files exist. |
| `python3 scripts/render_deep_dives.py --check` | Pass | Deep-dive docs are up to date. |
| `python3 scripts/verify_deep_dives.py` | Pass | Deep-dive verification passed. |
| `python -m mkdocs build` | Environment miss | Bare `python` is not installed in this shell. |
| `.venv/bin/python -m mkdocs build` | Pass | MkDocs built the documentation successfully. |

The two environment misses are local interpreter/path issues, not product regressions. Release
operators should run the quality gate from an activated project development environment or by using
the project venv interpreter explicitly.

## Documentation Drift

Fixed by this housekeeping pass:

- `docs/STATE.md` now reflects the post-#75 date and `v0.1.25` release-candidate metadata.
- `docs/ROADMAP.md` now treats the #75 architecture, wrapper, and supply-chain work as completed
  slices and moves remaining work into follow-up milestone language.
- Historical maintenance notes that described SBOM/provenance/package artifacts as deferred now
  point readers to the current workflows instead of reading as present-tense guidance.
- The 2026-05-27 maturity review remains a historical review, with a pointer to this post-#75
  update for completed SBOM, dependency-integrity, secret-scan, and CI-parity work.

No tenant payloads, credentials, private package coordinates, raw browser artifacts, or generated
runtime artifacts were added.

## Known Limitations And Residual Risk

- `v0.1.25` metadata and changelog heading are prepared, but no GitHub release or tag has been
  created in this pass.
- Real Artifactory upload/download verification, signing, attestation publication, trust-root
  validation, repository permission evidence, and retention controls remain operator-owned
  enterprise evidence outside this repository.
- The architecture decomposition is started, not complete; `src/attackiq_cli/cli.py`,
  `src/attackiq_cli/services.py`, `src/attackiq_cli/tui.py`, `src/attackiq_cli/backup.py`, and
  `src/attackiq_cli/scenario_wizard.py` still have remaining extraction opportunities.
- `source-types` is the first post-review read-only wrapper family; future families should remain
  one-family-at-a-time with service tests before CLI/TUI forwarding tests.
- Hash-pinned dependency lock generation remains a follow-up beyond the current dependency
  integrity record.
- Local validation commands are sensitive to the selected interpreter. The repo venv has the
  required dev/docs tools; the system `python3` in this shell does not.

## Issue And Roadmap Status

- #54 was closed as completed because #75 implemented CI/local quality-gate parity and the
  merge-commit CI run succeeded on `master`.
- #55 remains open as the architecture-decomposition epic with completed #75 slices and new
  follow-up child candidates.
- #56 remains open for no-Artifactory evidence standardization.
- #57 remains open for backup-domain expansion through reviewed endpoint catalogs.
- #58 remains open for AIQ Assist MCP contract maturity before user-facing commands.
- #59 remains open for read-only TUI dry-run preview design.
- #60 remains open as the read-only wrapper expansion epic with the `source-types` slice completed.
- #61 remains open as the supply-chain provenance and release-evidence epic with #75 controls
  completed and follow-up integrity/signing evidence tasks still active.
- #76 tracks post-#75 release-candidate preparation and explicitly excludes tagging or publishing
  until requested.

## Recommendation

Current recommendation: proceed to a release-prep PR or equivalent review for the `v0.1.25`
candidate, but do not tag or publish from this housekeeping pass.

Required release-prep steps:

1. Confirm `v0.1.25` version/changelog/metadata review.
2. Run the full local gate from the project dev environment, including MkDocs and deep-dive checks.
3. Confirm GitHub Actions success on the release-prep PR and tag-time release-hygiene checks.
4. Keep enterprise package upload, signing, attestation, trust-root verification, and promotion
   evidence in the approved external enterprise workflow.
