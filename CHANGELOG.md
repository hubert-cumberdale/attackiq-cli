# Changelog

All notable changes to this project are documented in this file.

## Unreleased

## v0.1.21 - 2026-05-26

### Added
- Added `constraints.txt` to enterprise package artifacts with manifest, checksum, provenance,
  Artifactory promotion evidence, and signing/attestation evidence coverage.

### Changed
- Updated offline package verification to validate declared install constraints when present.
- Updated enterprise delivery docs so Artifactory consumers use the constraints record promoted
  with the package.

### Validation
- `.venv/bin/python -m ruff check scripts/build_enterprise_package.py scripts/verify_enterprise_package.py scripts/package_provenance.py scripts/build_artifactory_promotion_evidence.py scripts/build_signing_attestation_evidence.py tests/test_enterprise_package.py tests/test_enterprise_package_verifier.py tests/test_artifactory_promotion_evidence.py tests/test_signing_attestation_evidence.py`
- `.venv/bin/python -m pytest tests/test_enterprise_package.py tests/test_enterprise_package_verifier.py tests/test_artifactory_promotion_evidence.py tests/test_signing_attestation_evidence.py -q`
- `.venv/bin/python -m mypy scripts/build_enterprise_package.py scripts/verify_enterprise_package.py scripts/package_provenance.py scripts/build_artifactory_promotion_evidence.py scripts/build_signing_attestation_evidence.py tests/test_enterprise_package.py tests/test_enterprise_package_verifier.py tests/test_artifactory_promotion_evidence.py tests/test_signing_attestation_evidence.py --cache-dir /tmp/aiq-cli-mypy-constraints`

## v0.1.20 - 2026-05-26

### Added
- Added credential-free signing and attestation evidence generation for verified enterprise package
  directories.
- Added a signing and attestation runbook covering subject coverage, expected detached signature
  files, expected attestation files, predicate requirements, and operator-owned trust controls.

### Changed
- Included the signing/attestation evidence helper in the local quality gate lint surface and
  enterprise delivery documentation.

### Validation
- `python3 scripts/check_release_governance.py`
- `python3 scripts/check_doc_links.py`
- `python3 scripts/check_public_safety.py`
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/pip-audit`
- `.venv/bin/pip-audit -r constraints.txt --no-deps`
- `git diff --check`

## v0.1.19 - 2026-05-25

### Added
- Added credential-free Artifactory promotion evidence generation for verified enterprise package
  directories.
- Added an Artifactory delivery runbook covering upload boundaries, post-download verification,
  install smoke checks, and operator-owned signing/attestation controls.

### Changed
- Included the Artifactory evidence helper in the local quality gate lint surface and enterprise
  delivery documentation.

### Validation
- `python3 scripts/check_release_governance.py`
- `python3 scripts/check_doc_links.py`
- `python3 scripts/check_public_safety.py`
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/pip-audit`
- `.venv/bin/pip-audit -r constraints.txt --no-deps`
- `git diff --check`

## v0.1.18 - 2026-05-25

### Changed
- Updated GitHub Actions workflow steps from `actions/checkout@v4` and
  `actions/setup-python@v5` to the Node 24-compatible `v6` action majors.
- Documented CI action runtime hygiene as part of production readiness and release stewardship.

### Validation
- `python3 scripts/check_release_governance.py`
- `python3 scripts/check_doc_links.py`
- `python3 scripts/check_public_safety.py`
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/pip-audit`
- `.venv/bin/pip-audit -r constraints.txt --no-deps`
- `git diff --check`

## v0.1.17 - 2026-05-25

### Added
- Added `ENTERPRISE_PACKAGE_PROVENANCE.json` to enterprise package output, capturing source tag,
  public commit, manifest digest, wheel digest, wheel size, and wheel dependency metadata without
  registry credentials or tenant data.
- Extended offline enterprise package verification to validate declared provenance files,
  provenance checksums, source/manifest agreement, and wheel metadata consistency.

### Validation
- `python3 scripts/build_enterprise_package.py --source-ref v0.1.17 --output-dir <dir>`
- `python3 scripts/verify_enterprise_package.py <package-dir>`
- `python3 scripts/check_public_mirror.py --ref v0.1.17`
- `python3 scripts/check_public_safety.py`
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/pip-audit`
- `.venv/bin/pip-audit -r constraints.txt --no-deps`
- `git diff --check`

## v0.1.16 - 2026-05-25

### Added
- Added offline enterprise package verification for generated or Artifactory-downloaded package
  directories, including manifest/schema checks, checksum matching, safe artifact names, and wheel
  public-safety scanning.
- Documented the package verification step as part of enterprise promotion and install evidence.

### Validation
- `python3 scripts/verify_enterprise_package.py <package-dir>`
- `python3 scripts/build_enterprise_package.py --source-ref v0.1.16 --output-dir <dir>`
- `python3 scripts/check_public_mirror.py --ref v0.1.16`
- `python3 scripts/check_public_safety.py`
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/pip-audit`
- `.venv/bin/pip-audit -r constraints.txt --no-deps`
- `git diff --check`

## v0.1.15 - 2026-05-24

### Added
- Added enterprise package promotion tooling that builds a validated wheel from a public release
  tag, writes `SHA256SUMS`, and records an `ENTERPRISE_PROMOTION_MANIFEST.json` without accepting
  or storing registry credentials.
- Documented the Artifactory/internal package promotion workflow as an operator-owned upload from
  validated public-source artifacts.

### Validation
- `python3 scripts/build_enterprise_package.py --source-ref v0.1.15 --output-dir <dir>`
- `python3 scripts/check_public_mirror.py --ref v0.1.15`
- `python3 scripts/check_public_safety.py`
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/pip-audit`
- `.venv/bin/pip-audit -r constraints.txt --no-deps`
- `git diff --check`

## v0.1.14 - 2026-05-22

### Added
- Added a public mirror dry-run/export check that builds a no-history source snapshot, verifies it
  with public-safety rules, initializes a throwaway public-style repository, and writes a
  publication manifest.
- Documented the private-source/public-mirror workflow for publishing source snapshots without
  carrying private git history.

### Validation
- `python3 scripts/check_public_mirror.py --ref v0.1.14`
- `python3 scripts/check_public_safety.py`
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/pip-audit`
- `.venv/bin/pip-audit -r constraints.txt --no-deps`
- `git diff --check`

## v0.1.13 - 2026-05-22

### Added
- Added a public-safety guard that scans tracked files and built wheel contents for private
  repository, workstation, and lab-only references before release.
- Added public delivery guidance for GitHub publication and downstream enterprise package
  promotion.

### Changed
- Removed historical handoff, review, taskpack, lab scenario, and sibling-repository planning
  artifacts from the tracked tree.
- Replaced sibling-repository catalog defaults with a neutral local `catalog/` path and renamed the
  external exposure catalog source type to `external-easm`.
- Reworked public docs navigation around stable product, operator, backup, and release surfaces.

### Validation
- `python3 scripts/check_public_safety.py`
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/python scripts/check_doc_links.py`
- `.venv/bin/python scripts/check_release_governance.py`
- `.venv/bin/python scripts/render_deep_dives.py --check`
- `.venv/bin/python scripts/verify_deep_dives.py`
- `.venv/bin/pip-audit`
- `git diff --check`

## v0.1.12 - 2026-05-22

### Added
- Added `attackiq backup configs`, a read-only redacted configuration backup workflow for
  integrations, derived source types, and detection-rule candidates.
- Added configuration backup operator guidance, including safe preflight steps, retention rules,
  manifest requirements, and sanitized endpoint-catalog intake for browser-discovered endpoints.
- Added endpoint-catalog schema and example fixtures that reject write-like endpoints before they
  can be used by backup commands.

### Fixed
- Made the CSV output guard test ANSI-insensitive so GitHub Actions colorized option names do not
  break the assertion.

### Validation
- `.venv/bin/python scripts/quality_gate.py`
- `.venv/bin/python scripts/check_doc_links.py`
- `.venv/bin/python scripts/check_release_governance.py`
- `.venv/bin/python scripts/render_deep_dives.py --check`
- `.venv/bin/python scripts/verify_deep_dives.py`
- `.venv/bin/pip-audit`
- `.venv/bin/pip-audit -r constraints.txt --no-deps`
- `git diff --check`

## v0.1.11 - 2026-05-14

### Added
- Added `scripts/live_smoke.py`, a hard opt-in live smoke harness for the approved low-risk
  production roster. It runs bounded read-only checks and mutation dry-run call-plan generation
  only, redacts failure summaries, and excludes all `--apply` commands plus lab-only health gates.

### Docs
- Updated production operator, readiness, maintenance, state, and handoff docs so the released
  operator workflow includes the live smoke harness and raw-output retention guidance.

## v0.1.10 - 2026-05-12

### Fixed
- Made shell-completion script generation deterministic in non-interactive environments by honoring
  `ATTACKIQ_COMPLETION_SHELL` or `SHELL` before falling back to process-based shell detection.

### Security
- Refreshed the constrained development/release-audit environment to patched versions of `pip`,
  `pytest`, `pygments`, `requests`, and `urllib3`.
- Constrained CI's pip bootstrap so branch and release jobs use the validated pip pin.

### Docs
- Added a production-readiness checklist covering quality gates, release metadata, dependency
  audit, security review, live acceptance checks, and rollout stages.

## v0.1.9 - 2026-03-20

### Fixed
- Fixed `scripts/verify_deep_dives.py` help-surface verification to inspect the AttackIQ CLI
  command tree directly for `attackiq ... --help` checks, avoiding Rich/Typer help truncation in
  CI output capture.

### Validation
- `python3 scripts/check_doc_links.py`
- `python3 scripts/verify_deep_dives.py`
- `.venv/bin/python -m ruff check src tests scripts/verify_deep_dives.py`
- `.venv/bin/python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`
- `.venv/bin/python -m pytest -q`

## v0.1.8 - 2026-03-20

### Fixed
- Fixed `scripts/verify_deep_dives.py` fallback imports so deep-dive verification works when the
  script is loaded outside package-style import contexts, including CI pytest collection.

### Validation
- `.venv/bin/python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m ruff check scripts/verify_deep_dives.py`
- `.venv/bin/python -m pytest -q tests/test_deep_dive_contracts.py`
- `.venv/bin/python -m pytest -q`
- `python3 scripts/check_doc_links.py`
- `python3 scripts/verify_deep_dives.py`

## v0.1.7 - 2026-03-20

### Fixed
- Fixed CI pytest collection for `tests/test_deep_dive_contracts.py` by loading deep-dive helper
  scripts from file paths instead of relying on `scripts` package-style imports during test
  collection.

### Validation
- `.venv/bin/python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`
- `.venv/bin/python -m pytest -q tests/test_deep_dive_contracts.py`
- `.venv/bin/python -m pytest -q`
- `python3 scripts/check_doc_links.py`
- `python3 scripts/verify_deep_dives.py`

## v0.1.6 - 2026-03-20

### Fixed
- Fixed CI mypy regressions in CLI output handling and test helper annotations after the
  `v0.1.5` release cut.

### Validation
- `.venv/bin/python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m pytest -q`

## v0.1.5 - 2026-03-20

### Added
- Added a first-class `attackiq assessments create-from-template` command backed by the bundled
  `v1_assessments_project_from_template_create` operation.

### Changed
- Moved `attackiq tags search` request/pagination logic into `attackiq_cli.services` to keep the
  CLI entrypoint thin and consistent with other service-backed commands.
- Standardized dry-run output across mutation commands on a shared call-plan JSON shape
  (`operation_id`, `path_params`, `query_params`, optional `json_body`).
- Aligned release-process docs with the actual CI/tagging workflow (`v<version>` tags and
  generic `release/v<version>` branch naming).

### Validation
- `python3 scripts/check_doc_links.py`
- `python3 scripts/render_deep_dives.py --check`
- `python3 scripts/verify_deep_dives.py`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m pytest -q`

## v0.1.4 - 2026-02-12

### Fixed
- Aligned runtime package version metadata so CLI/runtime version (`attackiq --version`) matches
  package release versioning.

### Changed
- Updated architecture/UX/state/current-work docs to reflect that all workflow tabs are active
  read-only workflows in the TUI.
- Recorded docs-alignment completion in roadmap references.

### Validation
- `python3 scripts/check_doc_links.py`
- `.venv/bin/attackiq --help`
- `.venv/bin/attackiq tui --help`
- `.venv/bin/python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m pytest -q`

## v0.1.1 - 2026-02-12

### Fixed
- `attackiq tags list --page N` now fetches a single explicit page instead of auto-paginating.
- Pagination helper now treats `page` as a starting page instead of overriding every request.

### Changed
- `attackiq export templates --scenario-concurrency` now enforces `>= 1`.
- `attackiq export templates`, `attackiq export scenarios`, and `attackiq export tests` now enforce
  `--page-size >= 1`.

### Tests
- Added regression coverage for pagination semantics and export option validation guards.

### Docs
- Updated export assessments docs to include `--name`.
- Synced state/handoff/current-work notes with pagination and validation behavior.
