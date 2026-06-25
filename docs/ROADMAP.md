# Roadmap

## Product Principles

- Prefer read-only wrappers before write workflows.
- Preserve dry-run defaults for mutation planning.
- Keep tenant data, generated artifacts, and raw browser captures out of git.
- Add abstractions only where they reduce operator friction and match existing service patterns.

## Near-Term Priorities

1. Complete `v0.1.26` tag approval, strict public mirror validation, and tag-time release hygiene;
   do not tag until release publication is explicitly requested.
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
  Subsequent slices extracted the `config`/`auth`, `assessment-schedules`, `source-types`,
  `blueprints`, `integrations`, `asset-groups`, `assets`, `tags`, `templates`, `results`, and
  `validation-results` command families, followed by the compact `spec` and `catalog` command
  families, then the experimental read-only `platform-api` parity command family and the
  no-network `build` payload-builder family and redacted read-only `backup configs` command
  family, the local `scenario-wizard` CLI family, and the remaining mixed CLI families (`call`,
  `export`, `scenarios`, `assessments`, `tests`, `join`, and `tui`). Keep
  `src/attackiq_cli/cli.py` focused on top-level app wiring, global options, and compatibility
  imports. Continue splitting
  `src/attackiq_cli/tui.py`, `src/attackiq_cli/services.py`,
  `src/attackiq_cli/scenario_wizard.py`, and `src/attackiq_cli/backup.py` incrementally along
  existing module boundaries.
- Enterprise install simulation: preserve the public-tag package build, package verification,
  Artifactory evidence generation, signing evidence generation, evidence verification, and local
  wheelhouse install simulation as accepted no-Artifactory release evidence. The release-audit
  wrapper evaluation keeps the template plus individual validation scripts as the current standard
  and makes any future wrapper a separate, redaction-scoped issue.
- Backup-domain maturity: expand endpoint-catalog domains only after reviewed classification,
  fixtures, redaction coverage, and read-only validation.
- AIQ Assist MCP maturity: keep provider-source, fixture, auth-mode, timeout, and redaction
  contract work ahead of any user-facing CLI or TUI commands.
- TUI dry-run previews: design read-only call-plan previews without apply-mode execution.
- Wrapper expansion: #75 added the first post-review wrapper family with `source-types`;
  subsequent slices added summary-only `assessment-schedules` and `edr-scan-schedules` wrappers
  and extracted the existing wrapper command families into focused modules. Add one future
  read-only wrapper family at a time, with service-boundary tests before CLI/TUI option forwarding
  tests.
- Supply-chain hardening: #75 added SBOM output, dependency integrity records, secret scanning,
  and least-privilege token plus trust-root guidance. The hash-pinned lock evaluation keeps
  `constraints.txt` plus `ENTERPRISE_DEPENDENCY_INTEGRITY.json` as the current standard while
  deferring additive hash-pinned runtime lock generation to a future prototype. Verifier-enforced
  external signing, attestation, and trust-root field groups plus the post-download package
  evidence checklist and pre-tag release-prep evidence checklist are the current release evidence
  standard.

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
- Use the observable-field-mappings intake note as the next `needs-redaction` candidate, with
  fixture and redaction tests required before enablement.
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
- Revisit remaining deferred candidates only after a separate redaction/output-retention review
  selects a safe summary projection and explicit out-of-scope write behavior.
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

- Keep the preview scope, required inputs, call-plan display shape, and redaction behavior aligned
  with `docs/TUI_DRY_RUN_PREVIEW_DESIGN.md`.
- Reuse `mutation_plans.py` and `tui_mutation_preview.py` for any future TUI preview controls.
- Update TUI help/status language only after preview controls are implemented.
- Keep apply-mode execution unavailable from the TUI unless a future apply-safe design is approved.

Acceptance:

- TUI previews show dry-run call-plan details without sending mutation requests.
- Tests prove no write path is reachable from preview flows.

## Recently Completed

- Prepared `v0.1.26` release-candidate metadata after rebaselining project state/roadmap docs and
  passing the full local quality gate on current `master` (2026-06-25).
- Aligned CLI architecture documentation so `src/attackiq_cli/cli.py` is documented as top-level
  app wiring, global option handling, and compatibility imports while focused `cli_*.py` modules
  own command-family parsing, validation, and orchestration (2026-06-23).
- Extracted the remaining mixed CLI command families into focused modules for `call`, `export`,
  `scenarios`, `assessments`, `tests`, `join`, and `tui` while preserving command behavior and
  the `src/attackiq_cli/cli.py` compatibility import surface (2026-06-23).
- Extracted the local `scenario-wizard` Typer command family into `cli_scenario_wizard.py` while
  preserving runtime inspect/validate/prepare behavior, local create/package dry-run/apply gating,
  timeout/source validation, JSON/file output, Scenario Wizard error rendering, and the
  `src/attackiq_cli/cli.py` compatibility import surface (2026-06-05).
- Extracted the redacted read-only `backup configs` Typer command family into `cli_backup.py`
  while preserving domain/page/company/catalog/tenant option validation, auth/TLS/timeout
  handling, redaction-safe backup execution, manifest/artifact status output, and focused CLI
  backup coverage (2026-06-05).
- Extracted the no-network `build` Typer command family into `cli_build.py` while preserving
  assessment/test payload generation, UUID/list validation, optional spec validation, suggested
  `attackiq call` rendering, JSON/file output, and the `src/attackiq_cli/cli.py` compatibility
  import surface (2026-06-05).
- Extracted the experimental read-only `platform-api` parity Typer command family into
  `cli_platform_api.py` while preserving scenario/assets parity behavior, backend comparison
  output, fail-on-mismatch exit behavior, auth/TLS/timeout handling, file/stdout JSON output, and
  the `src/attackiq_cli/cli.py` compatibility import surface (2026-06-04).
- Extracted the local read-only `catalog` Typer command family into `cli_catalog.py` while
  preserving validate/list/coverage behavior, provider/status/surface/limit/output-format
  validation, normalized JSON/CSV output, coverage technique toggling, file output messages, and
  the `src/attackiq_cli/cli.py` compatibility import surface (2026-06-04).
- Extracted the read-only `spec` Typer command family into `cli_spec.py` while preserving
  list/search/find/show behavior, field validation, limit/offset validation, no-match warnings,
  parameter display, security formatting, and the `src/attackiq_cli/cli.py` compatibility import
  surface (2026-06-04).
- Extracted the `validation-results` Typer command family into `cli_validation_results.py` while
  preserving list/by-asset/execution behavior, filter and path validation, JSON/CSV output,
  auth/TLS/timeout handling, malformed-response handling, and HTTP error reporting (2026-06-03).
- Extracted the `results` Typer command family into `cli_results.py` while preserving
  list/phases/logs behavior, mode and join-key validation, JSON/CSV output, auth/TLS/timeout
  handling, and HTTP error reporting (2026-06-03).
- Extracted the `templates` Typer command family into `cli_templates.py` while preserving
  list/show/tests behavior, summary CSV output, auth/TLS/timeout handling, and JSON behavior
  (2026-06-03).
- Extracted the `tags` Typer command family into `cli_tags.py` while preserving list/show/search
  behavior, table output, summary JSON/CSV output, auth/TLS/timeout handling, and error reporting
  (2026-06-03).
- Extracted the `assets` Typer command family into `cli_assets.py` while preserving list/show
  behavior, Platform API backend selection, summary CSV output, auth/TLS/timeout handling, and
  JSON behavior (2026-06-03).
- Extracted the `asset-groups` Typer command family into `cli_asset_groups.py` while preserving
  list/show behavior, summary CSV output, auth/TLS/timeout handling, and JSON behavior
  (2026-06-03).
- Extracted the `integrations` Typer command family into `cli_integrations.py` while preserving
  schema-backed filters, summary output, auth/TLS/timeout handling, and JSON/CSV behavior
  (2026-06-03).
- Added `attackiq edr-scan-schedules list` for summary-only read-only
  `v1_emm_edr_scan_schedules_list` output that omits raw target asset IDs and excludes
  retrieve/runs/create/update/delete behavior (2026-06-02).
- Reviewed remaining read-only wrapper redaction/output-retention risk and selected
  summary-only EDR scan schedules as the next wrapper family (2026-06-02).
- Evaluated hash-pinned lock generation and kept exact pins plus
  `ENTERPRISE_DEPENDENCY_INTEGRITY.json` as the current release standard while deferring additive
  hash-pinned runtime-lock generation to a future prototype (2026-06-02).
- Added `attackiq assessment-schedules list` for read-only `get_project_schedule_list` summaries
  with service response-shape tests, CLI forwarding tests, JSON/CSV output, and no schedule
  mutation path (2026-06-02).
- Classified assessment project schedules as the next read-only wrapper family, limited the future
  scope to `get_project_schedule_list`, and kept schedule mutation/CRUD endpoints out of scope
  (2026-06-02).
- Added TUI command-surface and preview-adapter tests proving the current preview path exposes no
  `--apply`, client, apply callback, mutation, or write-like command path (2026-06-02).
- Added shared assessment/test mutation plan builders and a read-only TUI mutation preview adapter
  that renders redacted call-plan summaries with `No request sent` status and no client/apply hooks
  (2026-06-02).
- Drafted the TUI dry-run preview design with assessment/test scope, required inputs, call-plan
  display shape, redaction behavior, adapter boundaries, and cancellation/error states
  (2026-06-02).
- Drafted the AIQ Assist MCP fail-closed adapter design with default-skipped live tests and explicit
  rejection of browser, cookie, transcript, and local session-file auth sources (2026-06-02).
- Made AIQ Assist MCP malformed-response, timeout, provider-error, and redaction fixture coverage
  explicit in the contract docs and fixture regression tests (2026-06-02).
- Expanded AIQ Assist MCP synthetic fixtures so both OAuth and regular-token auth paths have
  fixture-backed success coverage for discovery and tool invocation plus existing auth-failure
  coverage (2026-06-02).
- Finalized AIQ Assist MCP provider-source ownership status so the repo-local gate is owned by
  `aiq-cli` maintainers while the canonical provider wire contract remains blocked on a named AIQ
  Assist MCP service owner (2026-06-02).
- Reviewed detection/alert-rule candidates and kept them backup-only until a safe read-only wrapper
  projection, redaction contract, and service boundary are specified (2026-06-02).
- Added a public-safe no-Artifactory release evidence template covering enterprise package build,
  package verification, credential-free evidence generation, enterprise evidence verification, and
  local wheelhouse install simulation (2026-06-02).
- Evaluated a release-audit wrapper and retained the no-Artifactory evidence template plus
  individual validation scripts as the current repository-owned evidence standard (2026-06-02).
- Selected observable field mappings as the next configuration-backup endpoint-catalog candidate
  through a sanitized `needs-redaction` intake note (2026-06-02).
- Added fixture-backed redaction coverage for the observable-field-mappings endpoint-catalog
  backup candidate without enabling it in default backup coverage (2026-06-02).
- Added retention and manifest guidance for the observable-field-mappings backup candidate while
  keeping it out of production operator examples and default coverage (2026-06-02).
- Split read-only TUI domain-controller metadata for command palette availability, focus
  prefixes, and filter-help text into `tui_domains.py` without adding TUI write behavior
  (2026-06-02).
- Split assessment/test mutation service helpers and synthetic operation builders into
  `services_mutations.py` while preserving the `services.py` compatibility surface (2026-06-02).
- Split scenario filter normalization, summary records, read-only native and Platform API list
  behavior, detail fetches, and health checks into `services_scenarios.py` while preserving the
  `services.py` compatibility surface (2026-06-02).
- Split results mode query selection, validation-result filters, read-only result/validation-result
  fetches, and phase result/log join helpers into `services_results.py` while preserving the
  `services.py` compatibility surface (2026-06-02).
- Split assessment and test service filters, summaries, read-only list/detail helpers, and TUI page
  fetch helpers into `services_assessment_tests.py` while preserving the `services.py`
  compatibility surface (2026-06-02).
- Split asset service filters, summaries, native and Platform API read-only list helpers, and TUI
  page/detail fetch helpers into `services_assets.py` while preserving the `services.py`
  compatibility surface (2026-06-02).
- Split assessment-template and template-test service filters, summaries, TUI page/detail helpers,
  and read-only list behavior into `services_templates.py` while preserving the `services.py`
  compatibility surface (2026-06-02).
- Split asset-group service filters, summaries, read-only list pagination, and detail fetch
  behavior into `services_asset_groups.py` while preserving the `services.py` compatibility
  surface (2026-06-02).
- Split integration connector service filters, configuration-safe summaries, and read-only list
  behavior into `services_integrations.py` while preserving the `services.py` compatibility surface
  (2026-06-02).
- Split blueprint service filter, summary, and read-only list behavior into `services_blueprints.py`
  while preserving the `services.py` compatibility surface (2026-06-02).
- Extracted the `config` and `auth` Typer command family into `cli_config.py` while preserving
  top-level command registration and CLI help/output behavior (2026-06-02).
- Split Scenario Wizard package planning/apply behavior and shared subprocess helpers into focused
  modules while preserving `scenario_wizard.py` compatibility exports (2026-06-02).
- Split backup domain fetchers, pagination validation, and source-type request derivation into
  `backup_fetchers.py` while preserving the `backup.py` compatibility surface (2026-06-01).
- Split backup redaction and artifact-writing helpers into `backup_artifacts.py` while preserving
  the `backup.py` compatibility surface (2026-05-29).
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
