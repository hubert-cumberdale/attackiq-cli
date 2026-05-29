# Roadmap

## Product Principles

- Prefer read-only wrappers before write workflows.
- Preserve dry-run defaults for mutation planning.
- Keep tenant data, generated artifacts, and raw browser captures out of git.
- Add abstractions only where they reduce operator friction and match existing service patterns.

## Near-Term Priorities

1. Prepare the post-#75 release candidate through issue #76 without tagging until release prep is
   explicitly requested.
2. Keep the public release line and one-commit public mirror stable.
3. Promote and verify enterprise packages from public release tags with constraints, checksum,
   manifest, SBOM, dependency-integrity, and provenance evidence.
4. Keep GitHub Actions and `scripts/quality_gate.py` aligned so release checks have one practical
   source of truth.
5. Maintain redacted configuration backup coverage and endpoint-catalog validation.
6. Continue adding high-value read-only wrappers for common AttackIQ workflows.
7. Refactor shared mutation dry-run helpers where it reduces duplication without changing
   operator-facing behavior.
8. Mature AIQ Assist MCP contracts before adding CLI or TUI consumption.
9. Explore read-only TUI mutation previews that display dry-run call plans without enabling writes.

## Post-#75 Review Deltas

The 2026-05-27 enterprise maturity review is tracked in
`docs/REVIEW_2026-05-27_ENTERPRISE_MATURITY.md`. The post-#75 release-readiness audit is tracked
in `docs/REVIEW_2026-05-29_POST_75_RELEASE_READINESS.md`.

Milestone tracks:

- Release-candidate preparation: issue #76 tracks version/changelog/metadata release prep, full
  gate evidence, and tag-time checks. It does not authorize tagging by itself.
- Quality-gate parity: #75 added secret scanning, AIQ Assist MCP contract gates, and expanded
  release-script Ruff coverage to CI. Keep CI, release hygiene, and `scripts/quality_gate.py` in
  sync when new release scripts are added.
- Architecture decomposition: #75 extracted shared mutation helpers, TUI provider/cache behavior,
  backup catalog validation, service core/tag/source-type modules, and Scenario Wizard validation.
  Continue splitting `src/attackiq_cli/cli.py`, `src/attackiq_cli/tui.py`,
  `src/attackiq_cli/services.py`, `src/attackiq_cli/scenario_wizard.py`, and
  `src/attackiq_cli/backup.py` incrementally along existing module boundaries.
- Enterprise install simulation: preserve the public-tag package build, package verification,
  Artifactory evidence generation, signing evidence generation, evidence verification, and local
  wheelhouse install simulation as accepted no-Artifactory release evidence.
- Backup-domain maturity: expand endpoint-catalog domains only after reviewed classification,
  fixtures, redaction coverage, and read-only validation.
- AIQ Assist MCP maturity: keep provider-source, fixture, auth-mode, timeout, and redaction
  contract work ahead of any user-facing CLI or TUI commands.
- TUI dry-run previews: design read-only call-plan previews without apply-mode execution.
- Wrapper expansion: #75 added the first post-review wrapper family with `source-types`. Add one
  future read-only wrapper family at a time, with service-boundary tests before CLI/TUI option
  forwarding tests.
- Supply-chain hardening: #75 added SBOM output, dependency integrity records, secret scanning,
  and least-privilege token plus trust-root guidance. Follow-up work should standardize external
  signing/trust-root evidence and evaluate hash-pinned lock generation.

## Release Stewardship

Tasks:

- Keep `docs/STATE.md`, `CHANGELOG.md`, release tags, and package metadata aligned.
- Run dependency constraints, release governance, public-safety, public-mirror, quality,
  enterprise-package, documentation, deep-dive, and dependency-audit gates before release.
- Keep generated packages, runtime caches, live-smoke output directories, backup artifacts, and raw
  tenant responses outside git.
- Keep public release guidance aligned with downstream enterprise package promotion needs.
- Keep GitHub Actions action majors aligned with current runner runtime support.
- Keep CI command coverage aligned with `scripts/quality_gate.py` when new release or evidence
  scripts are added.

Acceptance:

- Current production release status is unambiguous in `docs/STATE.md`.
- Public-safety and quality gates pass.
- Public mirror dry-runs pass and strict publication exports contain one commit.
- Enterprise package promotion artifacts build and verify from the public tag with
  constraints/checksum/manifest/SBOM/dependency-integrity/provenance evidence and no registry
  credentials.
- Artifactory promotion evidence can be generated without accepting registry credentials or
  performing uploads.
- Signing and attestation evidence can be generated without accepting signing keys, registry
  credentials, or performing signing.
- Generated enterprise evidence verifies offline against local package artifacts before promotion
  records are accepted.
- A local wheelhouse install simulation from the verified enterprise package succeeds without
  requiring direct Artifactory access.
- Release notes identify validation commands without including tenant payloads.

## Configuration Backup Maturity

Tasks:

- Keep `attackiq backup configs` read-only and redacted.
- Expand backup domains only after endpoint discovery is sanitized, reviewed, fixture-backed, and
  classified as backup-safe or needs-redaction.
- Continue rejecting write-like and unsupported endpoint-catalog entries.
- Maintain manifest requirements and retention guidance.

Acceptance:

- Backup artifacts contain no raw secret-like values.
- Endpoint-catalog tests prove write-like methods cannot be enabled.
- Operator docs keep restore/apply flows out of the first backup workflow.

## Read-Only Wrapper Expansion

Inventory and family selection are tracked in
`docs/READ_ONLY_WRAPPER_INVENTORY.md`.

Tasks:

- Add one wrapper family at a time from existing TUI/export usage or common operator workflows.
- Reuse existing service, pagination, timeout, TLS, auth, JSON, and CSV output patterns.
- Document new command surfaces in `README.md` and `docs/STATE.md`.

Acceptance:

- New commands have focused tests for options, output formatting, redaction/error behavior, and
  bounded pagination where applicable.
- No write behavior is introduced in this track.

## AIQ Assist MCP Integration Maturity

Tasks:

- Maintain `docs/AIQ_ASSIST_MCP_CONTRACT.md` as the repo-local consumer contract.
- Capture supported auth paths, endpoint ownership, timeout behavior, fixture strategy, and
  failure modes before user-facing commands are added.
- Keep provider-source status validated by `scripts/check_aiq_assist_mcp_contract.py`.

Acceptance:

- Contract and fixture gates pass.
- No CLI/TUI MCP command is introduced before the contract and fixture-backed test strategy are
  stable.

## TUI Dry-Run Preview Design

Tasks:

- Define preview scope, required inputs, call-plan display shape, and redaction behavior before
  implementation.
- Reuse shared dry-run helpers.
- Keep apply-mode execution unavailable from the TUI unless a future apply-safe design is approved.

Acceptance:

- TUI previews show dry-run call-plan details without sending mutation requests.
- Tests prove no write path is reachable from preview flows.

## Recently Completed

- Completed post-#75 release-readiness validation and issue cleanup plan (2026-05-29).
- Merged first architecture decomposition slices for mutation output helpers, TUI provider/cache,
  backup catalog validation, service submodules, and Scenario Wizard validation (2026-05-29).
- Added `attackiq source-types list` as the first selected read-only wrapper expansion slice
  (2026-05-29).
- Added offline SPDX JSON SBOM records to enterprise package artifacts (2026-05-29).
- Added allowlisted CI/local secret scanning for source files (2026-05-28).
- Added offline dependency integrity records to enterprise package artifacts (2026-05-28).
- Expanded least-privilege release-token and enterprise trust-root verification guidance
  (2026-05-28).
- Added offline verification for generated enterprise Artifactory and signing evidence (2026-05-27).
- Aligned generated Artifactory and signing evidence checklists with required install-constraints verification (2026-05-27).
- Added fail-closed required install-constraints verification for current enterprise package promotion and signing evidence (2026-05-26).
- Added `constraints.txt` to enterprise package artifacts, package provenance, Artifactory evidence, and signing evidence (2026-05-26).
- Added credential-free signing and attestation evidence generation for verified enterprise package directories (2026-05-26).
- Added credential-free Artifactory promotion evidence generation and delivery runbook for verified enterprise package directories (2026-05-25).
- Updated GitHub Actions workflow actions to Node 24-compatible official action majors before the June 2, 2026 default runtime switch (2026-05-25).
- Added offline enterprise package provenance/dependency inventory for package directories, including source/manifest agreement and wheel metadata verification (2026-05-25).
- Added offline enterprise package verification for generated or Artifactory-downloaded package
  directories, covering manifest/schema checks, checksums, safe artifact names, and wheel
  public-safety scanning (2026-05-25).
- Added credential-free enterprise package promotion tooling for public release tags, generating a
  validated wheel, `SHA256SUMS`, and `ENTERPRISE_PROMOTION_MANIFEST.json` without Artifactory
  credentials (2026-05-24).
- Added `attackiq backup configs` for redacted configuration capture across integrations, derived
  source types, and read-only detection-rule candidates (2026-05-22).
- Added endpoint-catalog validation for discovered backup endpoints, including rejection of
  write-like and unsupported domains (2026-05-22).
- Prepared the repository for public GitHub publication and enterprise package promotion with
  public-safety scans and wheel-content checks (2026-05-22).
- Added a no-history public mirror dry-run/export check for the fresh public GitHub repository
  workflow (2026-05-22).
