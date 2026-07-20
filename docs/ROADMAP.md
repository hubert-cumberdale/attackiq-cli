# Roadmap

## Product Principles

- Prefer read-only wrappers before write workflows.
- Preserve dry-run defaults for mutation planning.
- Keep tenant data, generated artifacts, and raw browser captures out of git.
- Add abstractions only where they reduce operator friction and match existing service patterns.

## Near-Term Priorities

1. Use the 2026-07-08 project direction review as the current planning checkpoint for open issues
   #60 and #61 and as the closeout record for completed issues #55 and #59.
2. Keep `v0.1.26` release closeout records aligned with source tag, public mirror, CI, and
   enterprise package evidence while preserving generated artifacts outside git.
3. Keep the public release line and one-commit public mirror stable.
4. Keep GitHub Actions and `scripts/quality_gate.py` aligned so release checks have one practical
   source of truth.
5. Enforce the completed #55 architecture boundaries through the local and CI 800-line module
   check, and require a cohesive ownership need before further extraction.
6. Maintain redacted configuration backup coverage and endpoint-catalog validation.
7. Keep #60 in watch mode after the 2026-07-17 gate selected no new wrapper; reopen selection only
   for a named workflow with a safe projection and retention/redaction evidence.
8. Mature AIQ Assist MCP contracts before adding CLI or TUI consumption.
9. Keep the implemented new-assessment, assessment-from-template, assessment-default targets,
   assessment-run, new-test, test-scenario assignment, and test-status TUI previews read-only.
   Treat the current approved scope as complete; require a separate scope review before adding
   another operation.

## Project Direction Review Deltas

The 2026-05-27 enterprise maturity review is tracked in
`docs/REVIEW_2026-05-27_ENTERPRISE_MATURITY.md`. The post-#75 release-readiness audit is tracked
in `docs/REVIEW_2026-05-29_POST_75_RELEASE_READINESS.md`. The current project direction review is
tracked in `docs/REVIEW_2026-07-08_PROJECT_DIRECTION.md`.

Milestone tracks:

- Release closeout: issue #76 tracked version/changelog/metadata release prep, full gate evidence,
  and tag-time checks for `v0.1.26`; current production status is recorded in `docs/STATE.md`.
  Current `master` is past the `v0.1.26` tag and should use normal release-prep evidence before
  any future tag.
- Quality-gate parity: #75 added secret scanning, AIQ Assist MCP contract gates, and expanded
  release-script Ruff coverage to CI. Keep CI, release hygiene, and `scripts/quality_gate.py` in
  sync when new release scripts are added. Also keep deterministic review automation accurate
  enough that planning inputs do not conflict with direct git status evidence.
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
  imports. The final identified oversized-module slice moved DET pipeline GitLab/AttackIQ apply
  executors into `src/attackiq_cli/joiner/det_pipeline_apply.py`. The architecture check now fails
  locally and in CI if a Python module under `src/` exceeds 800 lines, completing #55 and keeping
  the decomposed boundaries from regrowing.
- Enterprise install simulation: preserve the public-tag package build, package verification,
  Artifactory evidence generation, signing evidence generation, evidence verification, and local
  wheelhouse install simulation as accepted no-Artifactory release evidence. The release-audit
  wrapper evaluation keeps the template plus individual validation scripts as the current standard
  and makes any future wrapper a separate, redaction-scoped issue.
- Backup-domain maturity: expand endpoint-catalog domains only after reviewed classification,
  fixtures, redaction coverage, and read-only validation.
- AIQ Assist MCP maturity: keep provider-source, fixture, auth-mode, timeout, and redaction
  contract work ahead of any user-facing CLI or TUI commands.
- TUI dry-run previews: the design, adapter guardrails, and all seven approved contextual previews
  are implemented: new-assessment, assessment-from-template, assessment-default targets,
  assessment-run, new-test, test-scenario assignment, and test-status. The modals reuse shared
  dry-run builders, render `No request sent`, and have no client/apply/export path. PR #133 closed
  #59 as completed; require a new reviewed scope before opening any additional preview work.
- Wrapper expansion: #75 added the first post-review wrapper family with `source-types`;
  subsequent slices added summary-only `assessment-schedules` and `edr-scan-schedules` wrappers
  and extracted the existing wrapper command families into focused modules. The fresh 2026-07-17
  gate selected no further family, so #60 is in watch mode until one named workflow provides a safe
  summary projection, sanitized fixtures, and retention/redaction evidence.
- Supply-chain hardening: #75 added SBOM output, dependency integrity records, secret scanning,
  and least-privilege token plus trust-root guidance. The hash-pinned lock evaluation keeps
  `constraints.txt` plus `ENTERPRISE_DEPENDENCY_INTEGRITY.json` as the current standard while
  deferring additive hash-pinned runtime lock generation to a future prototype. Verifier-enforced
  external signing, attestation, and trust-root field groups plus the post-download package
  evidence checklist and pre-tag release-prep evidence checklist are the current release evidence
  standard. Keep #61 open for future policy changes, but do not treat it as an active blocker for
  routine architecture, wrapper, backup, or docs slices.

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
- Keep observable field mappings optional and endpoint-catalog only, with `needs-redaction`
  classification, fixture-backed redaction coverage, and no default-domain enablement.
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
- Keep consumer code blocked until provider-source documentation, explicit CLI/TUI consumption
  approval, and adapter mock-test evidence are all present.
- Keep synthetic fixture requests, expected outcomes, response envelopes, and redaction markers
  internally consistent without treating them as canonical provider evidence.
- Keep fixture redaction fail-closed: sensitive fields use exact placeholders, URLs use parsed
  HTTPS-only exact-host allowlisting, credential-bearing or invalid-port URLs fail, and raw
  transcript keys stay prohibited.
- Classify sensitive and raw-transcript fields from literal JSON object names so punctuation in
  provider extension keys cannot bypass redaction or retention checks.
- Require exact placeholders for every sensitive-key value; auth-mode marker words are not
  redaction placeholders outside the dedicated `auth_mode` field.
- Keep each committed synthetic fixture within the 16 KiB retention budget and reject oversized
  files before JSON parsing.
- Reject duplicate JSON object names at every nesting level before fixture contract validation so
  checked evidence cannot depend on parser-specific duplicate-name handling.
- Reject non-finite numeric constants before fixture contract validation so repository evidence
  remains interoperable JSON even inside provider-owned extension data.
- Reject floating-point exponent forms that overflow to infinity during decoding so the finite
  numeric invariant cannot be bypassed with otherwise standard JSON number syntax.
- Keep the fixture directory a closed inventory of expected regular JSON files with filename/case
  binding; reject ignored side artifacts, subdirectories, and symbolic links.
- Keep synthetic request headers minimal and fail-closed: exact redacted authorization plus JSON
  content type, with duplicate and cookie/session-style headers rejected.
- Keep synthetic request params aligned to their declared method: empty discovery params and a
  non-empty name plus arguments object for tool calls, without inferring provider tool schemas.
- Keep synthetic success containers method-specific and non-empty while leaving discovery/tool
  result item schemas unpinned until provider documentation exists.
- Keep synthetic auth/provider error envelopes actionable with integer codes and non-empty messages
  without inferring provider code values or coupling them to HTTP statuses.
- Keep repo-owned fixture wrappers closed to undeclared fields while leaving provider response
  bodies, result data, and provider error extensions unpinned.
- Keep stored synthetic HTTP statuses within valid numeric ranges without pinning provider-specific
  status values or coupling them to JSON-RPC error codes.

Acceptance:

- Contract and fixture gates pass.
- No CLI/TUI MCP command is introduced before the contract and fixture-backed test strategy are
  stable.
- A provider-source status transition alone cannot disable the consumer-code guard.
- Fixture metadata cannot claim success, auth/provider failure, timeout, or malformed response when
  the stored synthetic response shape contradicts that outcome.
- Fixture content cannot hide raw sensitive text beside a redaction marker or behind a hostname
  that only begins with an allowed synthetic example name.
- Punctuation inside a literal JSON object name cannot hide a sensitive or raw-transcript-shaped
  provider extension key from the fixture gate.
- Sensitive provider-extension fields cannot use `oauth` or `token` as substitutes for exact
  redaction placeholders.
- Scheme-qualified fixture URLs cannot use non-HTTPS schemes, invalid ports, credentials, or hosts
  outside the exact synthetic allowlist.
- Committed synthetic fixture files cannot exceed 16 KiB or become transcript/response storage.
- Fixture JSON cannot contain duplicate object names, including inside provider-owned extension
  objects, while provider response field schemas remain otherwise unconstrained.
- Fixture JSON cannot contain `NaN`, `Infinity`, or `-Infinity`, including inside provider-owned
  extension data, while finite numeric values and provider response schemas remain unconstrained.
- Fixture JSON numeric literals cannot overflow the host float representation to infinity, while
  representable finite numeric values and provider response schemas remain unconstrained.
- The fixture gate rejects any directory entry outside the required case filenames and any fixture
  whose declared case drifts from its filename.
- Fixture requests cannot omit or duplicate required headers, change JSON content type, or add
  cookie/session-style authentication sources.
- Discovery fixtures cannot carry tool-call params, and tool-call fixtures cannot omit, blank, or
  extend the bounded synthetic name/arguments envelope.
- Successful discovery and tool-call fixtures require non-empty `tools` and `content` lists,
  respectively, without treating their item shapes as provider evidence.
- Auth/provider failure fixtures require integer error codes and non-empty messages without
  treating code values as provider evidence.
- Repo-owned fixture maps reject undeclared fields without treating provider response extensions as
  repo-owned schema.
- Stored response statuses remain within 100 through 599, and provider-error statuses remain within
  400 through 599, without requiring specific provider values inside those ranges.

## TUI Dry-Run Preview Design

Tasks:

- Keep the preview scope, required inputs, call-plan display shape, and redaction behavior aligned
  with `docs/TUI_DRY_RUN_PREVIEW_DESIGN.md`.
- Reuse `mutation_plans.py` and `tui_mutation_preview.py` for any future TUI preview controls.
- Keep TUI help/status language aligned with the implemented local-preview/no-request boundary.
- Keep apply-mode execution unavailable from the TUI unless a future apply-safe design is approved.

Acceptance:

- TUI previews show dry-run call-plan details without sending mutation requests.
- Tests prove no write path is reachable from preview flows.

## Recently Completed

- Rejected overflowing JSON exponent forms in AIQ Assist MCP synthetic fixtures so numeric values
  cannot decode as infinity and bypass the finite-number contract, without constraining provider
  schemas or adding adapter/network behavior (2026-07-20).
- Removed the AIQ Assist MCP sensitive-key exemption for `oauth` and `token` values so provider
  extensions cannot substitute auth-mode marker words for exact redaction placeholders, without
  changing provider schemas or adding adapter/network behavior (2026-07-20).
- Made AIQ Assist MCP fixture redaction inspect literal JSON object names, closing dotted-key
  bypasses for sensitive and raw-transcript-shaped provider extensions without closing provider
  response schemas or adding adapter/network behavior (2026-07-19).
- Rejected non-finite JSON numeric constants in AIQ Assist MCP synthetic fixtures before contract
  validation, preserving interoperable fixture syntax without constraining provider response
  schemas or adding adapter/network behavior (2026-07-19).
- Rejected duplicate JSON object names at every nesting level in AIQ Assist MCP synthetic fixtures
  before contract validation, preventing parser-dependent evidence without constraining provider
  response schemas or adding adapter/network behavior (2026-07-19).
- Added a 16 KiB per-file retention limit to AIQ Assist MCP synthetic fixtures, rejecting oversized
  files before JSON parsing without constraining provider response schemas or adding
  adapter/network behavior (2026-07-19).
- Required valid HTTPS for scheme-qualified AIQ Assist MCP synthetic fixture URLs, rejecting other
  schemes and invalid ports while preserving the exact example-host and no-credentials rules, with
  no adapter/network behavior (2026-07-19).
- Bounded AIQ Assist MCP synthetic HTTP response statuses while allowing unassigned in-range values
  and keeping provider-specific status choices and JSON-RPC error codes unconstrained, with no
  adapter/network behavior (2026-07-19).
- Closed repo-owned AIQ Assist MCP synthetic fixture maps to undeclared fields while leaving
  provider response bodies, result data, and provider error extensions unconstrained and adding no
  adapter/network behavior (2026-07-19).
- Required bounded AIQ Assist MCP synthetic failure details for auth/provider errors while leaving
  error-code values and HTTP-status relationships unconstrained until provider documentation
  exists and adding no adapter/network behavior (2026-07-19).
- Required method-specific non-empty success lists in AIQ Assist MCP synthetic fixtures while
  leaving discovery and tool-result item schemas unconstrained until provider documentation exists
  and adding no adapter/network behavior (2026-07-19).
- Bound AIQ Assist MCP synthetic request params to their declared method, requiring empty
  discovery params and an exact non-empty name/arguments envelope for tool calls without asserting
  a provider tool catalog or adding adapter/network behavior (2026-07-19).
- Bound AIQ Assist MCP synthetic requests to a minimal case-insensitive header envelope with exact
  redacted authorization and JSON content type, rejecting omissions, duplicates, and cookie-style
  sources without changing provider status or adding adapter/network behavior (2026-07-18).
- Closed the AIQ Assist MCP fixture directory to the expected regular JSON case files, rejecting
  side artifacts, subdirectories, symbolic links, invalid roots, and filename/case drift without
  changing provider status or adding adapter/network behavior (2026-07-18).
- Hardened the AIQ Assist MCP synthetic-fixture redaction gate so sensitive fields require exact
  placeholders, URL validation parses and exactly allowlists synthetic example hosts, embedded URL
  credentials fail, and raw transcript keys remain prohibited, without changing provider status or
  adding adapter/network behavior (2026-07-18).
- Made the AIQ Assist MCP synthetic-fixture gate reject outcome drift across success, auth/provider
  errors, timeout, and malformed-response cases while preserving the fixtures as non-canonical,
  offline consumer-contract evidence (2026-07-18).
- Hardened the AIQ Assist MCP provider-source transition so documented source status alone cannot
  unlock consumer code; the gate now requires boolean consumption approval and adapter mock-test
  evidence while leaving the current provider status pending and all consumption/live checks
  blocked (2026-07-18).
- Added a fail-closed 800-line Python module boundary to deterministic review automation, wired it
  into the standard local quality gate and GitHub Actions with parity coverage, and completed the
  #55 architecture-decomposition epic after all identified oversized modules were split
  (2026-07-18).
- Merged PR #133 as `8ecb6ba6ee05c4ed2563a35defad2e5bba04648b`, closing #59 after all
  seven approved previews, explicit help/status read-only language, the 702-test local quality
  gate, and the Python 3.10/3.11/3.12 PR and post-merge CI matrices passed (2026-07-18).
- Added the seventh #59 read-only TUI preview UX for assessment-from-template call plans, including
  required template UUID and assessment-name validation, optional blueprint UUID validation,
  Assessments-tab-only command-palette routing, bounded local rendering, `No request sent` status,
  explicit read-only/no-request help and Status language, and tests proving no client/apply/export
  path. This completes every operation and acceptance criterion in the approved preview design
  scope (2026-07-18).
- Added the sixth #59 read-only TUI preview UX for new-assessment call plans, including selected-
  scenario UUID prefill, assessment-name and scenario-list validation, stable UUID deduplication,
  Scenarios-tab-only command-palette routing, bounded local rendering, `No request sent` status,
  and tests proving no client/apply/export path (2026-07-18).
- Added the fifth #59 read-only TUI preview UX for assessment-default-target call plans, including
  selected-assessment UUID prefill, optional asset/asset-group lists with at-least-one validation,
  stable UUID deduplication, Assessments-tab-only command-palette routing, bounded local rendering,
  `No request sent` status, and tests proving no client/apply/export path (2026-07-18).
- Added the fourth #59 read-only TUI preview UX for test-scenario assignment call plans, including
  selected-test UUID prefill, explicit test/scenario UUID validation, stable list deduplication,
  Tests-tab-only command-palette routing, bounded JSON-body rendering, `No request sent` status,
  and tests proving no client/apply/export path (2026-07-18).
- Added the third #59 read-only TUI preview UX for new-test call plans, including selected-
  assessment UUID prefill, explicit UUID and name validation, Assessments-tab-only command-palette
  routing, bounded JSON-body rendering, `No request sent` status, and tests proving no
  client/apply/export path (2026-07-18).
- Added the second #59 read-only TUI preview UX for test-status call plans, including selected-row
  UUID prefill, explicit UUID validation, Tests-tab-only command-palette routing, shared bounded
  local modal behavior, `No request sent` status, and tests proving no client/apply/export path
  (2026-07-17).
- Added the first #59 read-only TUI preview UX for assessment-run call plans, including selected-row
  UUID prefill, explicit UUID validation, contextual command-palette routing, bounded local modal
  rendering, `No request sent` status, and tests proving no client/apply/export path (2026-07-17).
- Completed a fresh #60 redaction/output-retention selection gate and explicitly selected no new
  wrapper family; deferred all remaining candidates until a concrete operator workflow satisfies
  the field-projection, fixture, retention, redaction, and service-boundary criteria (2026-07-17).
- Split GitLab retry/client behavior and apply-gated GitLab issue updates plus AttackIQ assessment
  creation into `joiner/det_pipeline_apply.py` while preserving the `det_pipeline.py`
  compatibility exports, deterministic stages, artifacts, CLI behavior, explicit timeout, and
  apply gate (2026-07-17).
- Split Scenario Wizard image-tar runtime inspection, bounded layer spooling, Docker whiteout/index
  handling, selected-file materialization, safe path normalization, sensitive-file exclusion, and
  requirements credential filtering into `scenario_wizard_image.py` while preserving high-level
  prepare planning/apply behavior and the `scenario_wizard.py` compatibility surface (2026-07-17).
- Split Scenario Wizard cache resolution, wrapper ZIP inspection with sensitive-file suppression,
  runtime-bundle validation summaries, bundle-copy dry-run planning, and bundle-copy apply behavior
  into `scenario_wizard_runtime.py` while preserving the `scenario_wizard.py` compatibility
  surface, validation, and CLI behavior (2026-07-17).
- Split Scenario Wizard create dry-run planning, isolated apply execution, temporary configuration
  transport, runtime dependency setup, and generated-file result collection into
  `scenario_wizard_create.py` while preserving the `scenario_wizard.py` compatibility surface,
  subprocess injection, environment isolation, redaction, and CLI behavior (2026-07-17).
- Split the TUI runtime state model and pure auth, base URL, spec cache, environment-label, and
  workspace-display derivation into `tui_provider_state.py` while preserving `tui_provider.py`
  compatibility imports, workspace resolution, service calls, cache behavior, and read-only
  behavior (2026-07-17).
- Split the Textual app shell, tab orchestration, command-palette dispatch, cache/status actions,
  paging/export routing, help, and focus controls into `tui_app.py` while preserving the `tui.py`
  compatibility facade, command IDs, key bindings, tab state, and read-only behavior
  (2026-07-17).
- Split Results tab models, state, async loading, view-mode grouping, rendering, filtering,
  paging, detail, exports, and view-state restoration into `tui_results.py` while preserving
  `tui.py` compatibility imports, command IDs, provider calls, filter semantics, and read-only
  behavior (2026-07-17).
- Split Assets tab state, async loading, rendering, filtering, paging, detail, exports, and
  view-state restoration into `tui_assets.py` while preserving `tui.py` compatibility imports,
  command IDs, provider calls, filter semantics, and read-only behavior (2026-07-17).
- Split Tests tab state, async loading, rendering, filtering, paging, detail, exports, and
  view-state restoration into `tui_tests.py` while preserving `tui.py` compatibility imports,
  command IDs, provider calls, filter semantics, and read-only behavior (2026-07-17).
- Split Assessments tab state, async loading, rendering, filtering, paging, detail, exports, and
  view-state restoration into `tui_assessments.py` while preserving `tui.py` compatibility
  imports, command IDs, provider calls, typed filter validation, and read-only behavior
  (2026-07-17).
- Split Scenarios tab state, async loading, rendering, filtering, paging, detail, exports, and
  view-state restoration into `tui_scenarios.py` while preserving `tui.py` compatibility imports,
  command IDs, provider calls, and read-only behavior (2026-07-17).
- Split Settings tab runtime/config/cache record builders and detail text formatting into
  `tui_settings.py`, then moved the Settings tab state, rendering, filtering, and export actions
  into the same module while preserving `tui.py` compatibility imports and read-only behavior
  (2026-07-16 through 2026-07-17).
- Split shared TUI export path construction and JSON/CSV file-writing helpers into
  `tui_exports.py` while preserving per-tab export status messages and output filenames
  (2026-07-16).
- Split the shared TUI Textual stylesheet into `tui_styles.py` while preserving
  `AttackIQTuiApp.CSS` and existing TUI selectors (2026-07-16).
- Split shared TUI header/banner/filter/list/detail/status widgets and the placeholder workflow
  tab shell into `tui_widgets.py` while preserving existing `tui.py` class imports and read-only
  behavior (2026-07-16).
- Split pure TUI shortcut text, command-palette matching/group hints, and runtime-error formatting
  into `tui_display.py` while preserving existing `tui.py` helper imports and read-only tab
  behavior (2026-07-16).
- Split pure TUI result grouping, list filtering, and scenario/assessment/test/asset/settings/results
  sort helpers into `tui_record_lists.py` while preserving existing `tui.py` helper imports and
  read-only tab behavior (2026-07-16).
- Split pure TUI record ID extraction, fallback labels, and scenario/assessment/test/asset detail
  text builders into `tui_record_text.py` while preserving existing `tui.py` helper imports and
  read-only tab behavior (2026-07-16).
- Split pure TUI structured-filter parsing, typed filter coercion, schema-drift aliases, and
  sort-field resolution into `tui_filters.py` while preserving existing `tui.py` helper imports
  and read-only tab behavior (2026-07-16).
- Split TUI task lifecycle and blocking executor handoff helpers for cancellation, task
  replacement, debounced reloads, and tab background work into `tui_tasks.py` without changing TUI
  behavior, command IDs, or network paths (2026-07-16).
- Fixed deterministic review worktree status reporting so empty `git status --short` output
  renders as clean while command failures render as unknown, with focused review automation tests
  (2026-07-16).
- Published and promoted `v0.1.26` as the current production release after strict public mirror,
  tag-time CI, enterprise package, combined evidence verification, and offline wheelhouse install
  evidence were recorded (2026-06-25).
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
- Documented observable field mappings as an optional endpoint-catalog backup domain while keeping
  it out of default coverage and without adding a first-class wrapper (2026-06-29).
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
