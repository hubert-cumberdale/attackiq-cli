# Roadmap

## Product Principles

- Prefer read-only wrappers before write workflows.
- Preserve dry-run defaults for mutation planning.
- Keep tenant data, generated artifacts, and raw browser captures out of git.
- Add abstractions only where they reduce operator friction and match existing service patterns.

## Near-Term Priorities

1. Keep the public release line and one-commit public mirror stable.
2. Promote and verify enterprise packages from public release tags with checksum, manifest, and provenance evidence.
3. Maintain redacted configuration backup coverage and endpoint-catalog validation.
4. Continue adding high-value read-only wrappers for common AttackIQ workflows.
5. Refactor shared mutation dry-run helpers where it reduces duplication without changing
   operator-facing behavior.
6. Mature AIQ Assist MCP contracts before adding CLI or TUI consumption.
7. Explore read-only TUI mutation previews that display dry-run call plans without enabling writes.

## Release Stewardship

Tasks:

- Keep `docs/STATE.md`, `CHANGELOG.md`, release tags, and package metadata aligned.
- Run dependency constraints, release governance, public-safety, public-mirror, quality,
  enterprise-package, documentation, deep-dive, and dependency-audit gates before release.
- Keep generated packages, runtime caches, live-smoke output directories, backup artifacts, and raw
  tenant responses outside git.
- Keep public release guidance aligned with downstream enterprise package promotion needs.
- Keep GitHub Actions action majors aligned with current runner runtime support.

Acceptance:

- Current production release status is unambiguous in `docs/STATE.md`.
- Public-safety and quality gates pass.
- Public mirror dry-runs pass and strict publication exports contain one commit.
- Enterprise package promotion artifacts build and verify from the public tag with
  checksum/manifest evidence and no registry credentials.
- Artifactory promotion evidence can be generated without accepting registry credentials or
  performing uploads.
- Signing and attestation evidence can be generated without accepting signing keys, registry
  credentials, or performing signing.
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
