# Architecture Standards

These standards define how new capabilities should be added to `aiq-cli`.

## Module Boundaries

| Layer | Owns | Must avoid |
| --- | --- | --- |
| `src/attackiq_cli/cli.py` | Top-level Typer app assembly, global callback/version/completion behavior, command registration, and compatibility imports. | Command-family implementation, domain business rules, and output shaping. |
| `src/attackiq_cli/cli_*.py` | Typer command-family parsing, validation, user-facing orchestration, dry-run/apply gates, and terminal output handling. | Business rules that need reuse by TUI, tests, or adapters. |
| `client.py` | HTTP transport, auth selection, retries, redaction, response status handling. | Domain-specific payload building. |
| `service_core.py` | Shared service context, auth/client setup, and small normalization helpers. | Domain-specific operation selection and output shaping. |
| `services.py` | Backwards-compatible import facade for service helpers split into focused modules. | New domain behavior, command-specific rendering, and terminal UX. |
| `services_tags.py` | Tag query builders, tag resolution, summaries, and tag fetch helpers. | Non-tag service workflows and write behavior. |
| `services_source_types.py` | Source-type query builders, summaries, and read-only list fetch helpers. | Connector configuration output and write behavior. |
| `services_edr_scan_schedules.py` | EDR scan schedule query builders, summaries, and read-only list fetch helpers. | Schedule writes, schedule detail/run history, and raw target asset IDs. |
| `exporter.py` | CSV/JSON output normalization and file writing helpers. | Network calls. |
| `tui.py` | TUI launch orchestration and compatibility imports. | Textual app-shell behavior, focused tab behavior, endpoint-specific logic, or apply/write behavior. |
| `tui_app.py` | Textual app shell, tab orchestration, command-palette dispatch, cache/status actions, paging/export routing, help, and focus controls. | Focused tab implementation, service query logic, transport behavior, and any apply/write behavior. |
| `tui_provider.py` | Read-only service fetching, bounded in-session caches, cache diagnostics, workspace resolution, and compatibility imports for runtime state symbols. | Widget rendering, service implementation, transport changes, and any apply/write behavior. |
| `tui_provider_state.py` | TUI runtime state model and pure auth, base URL, spec cache, environment-label, and workspace-display derivation. | Network calls, cache mutation, widget rendering, and any apply/write behavior. |
| `tui_assessments.py` | Assessments tab state, async loading, rendering, filtering, paging, detail, exports, and view-state restoration. | Assessment service implementation, app-level command registration, mutations, and any apply/write behavior. |
| `tui_assets.py` | Assets tab state, async loading, rendering, filtering, paging, detail, exports, and view-state restoration. | Asset service implementation, app-level command registration, mutations, and any apply/write behavior. |
| `tui_domains.py` | Read-only TUI domain-controller metadata, command palette availability, focus prefixes, and filter-help text. | Widget rendering, network calls, apply/write behavior, and service fetch logic. |
| `tui_preview.py` | Local scenario/assessment/test preview input validation, bounded call-plan rendering, and Textual modal controls over approved pure mutation-plan builders. | Client construction, service mutation calls, apply flags, preview persistence, and generic API browsing. |
| `tui_exports.py` | Timestamped export path construction and JSON/CSV file writing helpers for TUI list tabs. | Tab rendering, service/provider calls, command registration, and any apply/write behavior. |
| `tui_results.py` | Results tab models, state, async loading, view-mode grouping, rendering, filtering, paging, detail, exports, and view-state restoration. | Results service implementation, app-level command registration, and any apply/write behavior. |
| `tui_scenarios.py` | Scenarios tab state, async loading, rendering, filtering, paging, detail, exports, and view-state restoration. | Scenario service implementation, app-level command registration, and any apply/write behavior. |
| `tui_styles.py` | Shared Textual stylesheet for the TUI app shell, overlays, panes, filters, footer, and results status display. | Widget rendering, service/provider calls, command registration, and any apply/write behavior. |
| `tui_tests.py` | Tests tab state, async loading, rendering, filtering, paging, detail, exports, and view-state restoration. | Test service implementation, app-level command registration, mutations, and any apply/write behavior. |
| `scenario_wizard_validation.py` | Scenario Wizard runtime bundle and generated scenario validation, checksum helpers, and secret-key screening. | Runtime preparation, subprocess execution, or package apply behavior. |
| Future `adapters/` | Out-of-spec endpoints, sibling repo imports, external file/API contracts. | Direct coupling to Typer or TUI rendering. |

## Command Pattern

New commands should follow this sequence:

1. Parse and validate CLI inputs.
2. Load config and resolve base URL.
3. Build auth context and validate required auth.
4. Build a request plan or service call.
5. Return a dry-run preview unless the command is read-only or `--apply` is present.
6. Execute through shared client/services.
7. Write structured output through a common helper.

Mutation commands must be dry-run by default unless there is a documented exception.

## Wrapper Expansion Pattern

New first-class OpenAPI wrappers should use the smallest shared boundary that fits the operation
family:

1. Keep Typer-only parsing, `--output` handling, and command help in the focused
   `src/attackiq_cli/cli_*.py` module for that command family.
2. Put query/filter normalization, operation selection, response-shape validation, and reusable
   fetch helpers in `services.py` or a focused service submodule when a family grows past one or
   two helpers.
3. Make TUI filters call the same service-layer query builders as CLI wrappers instead of
   forwarding endpoint-specific strings directly.
4. Add focused tests at the service boundary first, then CLI/TUI tests for option forwarding and
   user-facing errors.
5. Do not add a new write-like wrapper until the corresponding dry-run/apply gate and redaction
   behavior are covered.

## Decomposition Thresholds

Python modules under `src/` must not exceed 800 lines. The boundary is enforced by
`python3 scripts/deterministic_review.py --check-architecture` in both the standard local quality
gate and GitHub Actions. A cohesive ownership need can justify another focused module, but not an
exception to the checked line-count boundary.

The oversized modules identified by the 2026-05-27 enterprise maturity review have been
decomposed. The table below records the resulting ownership boundaries and preferred direction for
future changes:

| Module | Current role | Preferred extraction direction |
| --- | --- | --- |
| `src/attackiq_cli/cli.py` | Top-level Typer app assembly, global options, completion fallback, command registration, and compatibility imports. | Keep command-family behavior in focused `cli_*.py` modules. |
| `src/attackiq_cli/cli_call.py` | Generic `call` command parsing, OpenAPI request validation, dry-run previews, response formatting, and ad hoc request execution. | Shared schema coercion helpers, transport-level retry/redaction logic, and unrelated command families. |
| `src/attackiq_cli/cli_export.py` | `export` Typer command family, pagination orchestration, export option validation, optional scenario enrichment, and JSON/CSV output handling. | Export row normalization internals, generic pagination helpers, and unrelated command families. |
| `src/attackiq_cli/cli_scenarios.py` | `scenarios` Typer command family, list/show/upload option validation, backend selection, package upload redaction, and JSON/CSV output handling. | Scenario service response parsing, assessment/test mutations, and unrelated command families. |
| `src/attackiq_cli/cli_assessments.py` | `assessments` Typer command family, read-only list/detail output handling, dry-run/apply assessment mutations, and assessment defaults orchestration. | Assessment/test shared service parsing, mutation plan construction, and unrelated command families. |
| `src/attackiq_cli/cli_tests.py` | `tests` Typer command family, read-only list/detail output handling, dry-run/apply test mutations, and test status orchestration. | Assessment/test shared service parsing, mutation plan construction, and unrelated command families. |
| `src/attackiq_cli/cli_join.py` | Top-level `join` command option validation and dispatch into dataset and DET pipeline joiner workflows. | Join algorithm internals, GitLab update application, and AttackIQ assessment creation services. |
| `src/attackiq_cli/cli_tui.py` | Top-level `tui` command option validation and launch handoff to the Textual app. | TUI widget rendering, cache/provider behavior, and service fetch logic. |
| `src/attackiq_cli/cli_assessment_schedules.py` | `assessment-schedules` Typer command family, read-only output validation, auth/TLS/timeout orchestration, and JSON/CSV output handling. | Assessment schedule service response parsing, schedule mutation behavior, and unrelated command families. |
| `src/attackiq_cli/cli_asset_groups.py` | `asset-groups` Typer command family, list/show option validation, auth/TLS/timeout orchestration, and JSON/CSV output handling. | Asset-group service response parsing, asset-group mutation behavior, and unrelated command families. |
| `src/attackiq_cli/cli_assets.py` | `assets` Typer command family, list/show option validation, Platform API backend selection, auth/TLS/timeout orchestration, and JSON/CSV output handling. | Asset service response parsing, asset mutation behavior, and unrelated command families. |
| `src/attackiq_cli/cli_backup.py` | `backup configs` Typer command family, redacted configuration-backup option validation, auth/TLS/timeout orchestration, domain selection, manifest/artifact status output, and backup error rendering. | Backup fetcher/redaction internals, endpoint-catalog model changes, write-like backup domains, restore/apply behavior, and unrelated command families. |
| `src/attackiq_cli/cli_blueprints.py` | `blueprints` Typer command family, search filter validation, auth/TLS/timeout orchestration, and JSON/CSV output handling. | Blueprint service response parsing, blueprint mutation behavior, and unrelated command families. |
| `src/attackiq_cli/cli_build.py` | No-network `build` Typer command family, assessment/test payload construction, UUID/list validation, optional spec validation, suggested `attackiq call` rendering, and JSON/file output handling. | Network execution, apply-mode mutation behavior, assessment/test service calls, and unrelated command families. |
| `src/attackiq_cli/cli_catalog.py` | `catalog` Typer command family, local BAS catalog validation, filter validation, normalized JSON/CSV output, coverage summaries, and file-output handling. | Network calls, AttackIQ API orchestration, catalog record normalization rules, and unrelated command families. |
| `src/attackiq_cli/cli_config.py` | `config` and `auth` Typer command family, local config load/save UX, validation display, and credential masking. | Networked command orchestration, service calls, and global CLI callback behavior. |
| `src/attackiq_cli/cli_edr_scan_schedules.py` | `edr-scan-schedules` Typer command family, filter validation, auth/TLS/timeout orchestration, and JSON/CSV summary output handling. | Schedule writes, schedule detail/run history, raw target asset IDs, and unrelated command families. |
| `src/attackiq_cli/cli_integrations.py` | `integrations` Typer command family, schema-backed filter validation, auth/TLS/timeout orchestration, and JSON/CSV summary output handling. | Connector configuration output, integration writes, service response parsing, and unrelated command families. |
| `src/attackiq_cli/cli_platform_api.py` | Experimental read-only `platform-api` parity command family, scenario/asset option validation, backend comparison payload shaping, fail-on-mismatch handling, auth/TLS/timeout orchestration, and JSON/file output handling. | Broader Platform API adapter/client behavior, service response parsing, write behavior, and unrelated command families. |
| `src/attackiq_cli/cli_results.py` | `results` Typer command family, mode/join-key/output validation, auth/TLS/timeout orchestration, and JSON/CSV output handling. | Result service response parsing, validation-result CLI rendering, TUI tab layout, and unrelated command families. |
| `src/attackiq_cli/cli_scenario_wizard.py` | `scenario-wizard` Typer command family, runtime inspect/validate/prepare option validation, local create/package dry-run/apply gating, JSON/file output, and Scenario Wizard error rendering. | Runtime bundle validation internals, subprocess execution, package planning internals, network/API behavior, and unrelated command families. |
| `src/attackiq_cli/cli_source_types.py` | `source-types` Typer command family, UUID filter validation, auth/TLS/timeout orchestration, and JSON/CSV output handling. | Source-type service response parsing, connector configuration output, write behavior, and unrelated command families. |
| `src/attackiq_cli/cli_spec.py` | `spec` Typer command family, OpenAPI operation table rendering, field/limit/offset validation, parameter display, and security formatting. | Generic `call` execution, schema parsing, network orchestration, and unrelated command families. |
| `src/attackiq_cli/cli_tags.py` | `tags` Typer command family, list/show/search option validation, auth/TLS/timeout orchestration, table output, and JSON/CSV summary output handling. | Tag service response parsing, tag mutation behavior, and unrelated command families. |
| `src/attackiq_cli/cli_templates.py` | `templates` Typer command family, list/show/tests option validation, auth/TLS/timeout orchestration, and JSON/CSV output handling. | Template service response parsing, template mutation behavior, export enrichment behavior, and unrelated command families. |
| `src/attackiq_cli/cli_validation_results.py` | `validation-results` Typer command family, filter/path/output validation, auth/TLS/timeout orchestration, and JSON/CSV output handling. | Validation-result service response parsing, result CLI rendering, TUI tab layout, and unrelated command families. |
| `src/attackiq_cli/tui.py` | TUI launch orchestration and compatibility imports. | Textual app-shell behavior, focused tab behavior, service-backed query contracts, and any apply/write behavior. |
| `src/attackiq_cli/tui_app.py` | Textual app shell, tab orchestration, command-palette dispatch, cache/status actions, paging/export routing, help, and focus controls. | Focused tab implementation, service query logic, transport behavior, and any apply/write behavior. |
| `src/attackiq_cli/tui_assessments.py` | Assessments tab state, async loading, rendering, filtering, paging, detail, exports, and view-state restoration. | Assessment service implementation, app-level command registration, mutations, and any apply/write behavior. |
| `src/attackiq_cli/tui_assets.py` | Assets tab state, async loading, rendering, filtering, paging, detail, exports, and view-state restoration. | Asset service implementation, app-level command registration, mutations, and any apply/write behavior. |
| `src/attackiq_cli/tui_display.py` | Shortcut text, command-palette matching/group hints, and runtime error formatting for TUI display paths. | Widget rendering, service/provider calls, command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_domains.py` | Read-only tab/domain controller metadata, command palette entries, per-tab command availability, focus prefixes, and filter-help text. | Widget rendering, service/provider calls, cache mutation, and any apply/write behavior. |
| `src/attackiq_cli/tui_exports.py` | Timestamped export path construction and JSON/CSV file writing helpers for TUI list tabs. | Tab rendering, service/provider calls, command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_filters.py` | Structured-filter parsing, typed filter coercion, schema-drift aliases, and sort-field resolution for TUI tabs. | Widget rendering, service/provider calls, command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_record_lists.py` | Result grouping, list filtering, and scenario/assessment/test/asset/settings/results sort helpers for TUI tabs. | Widget rendering, service/provider calls, command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_record_text.py` | Record ID extraction, fallback labels, and scenario/assessment/test/asset detail text builders for TUI panes. | Widget rendering, service/provider calls, command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_results.py` | Results tab models, state, async loading, view-mode grouping, rendering, filtering, paging, detail, exports, and view-state restoration. | Results service implementation, app-level command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_scenarios.py` | Scenarios tab state, async loading, rendering, filtering, paging, detail, exports, and view-state restoration. | Scenario service implementation, app-level command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_settings.py` | Settings tab state, rendering, filtering, export actions, and record/detail builders for runtime/config/cache diagnostics. | Service/provider calls beyond cache diagnostics, app-level command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_tasks.py` | TUI task cancellation, replacement, result consumption, debounced reload scheduling, and blocking executor handoff helpers. | Widget rendering, service/provider calls, command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_styles.py` | Shared Textual stylesheet for the TUI app shell, overlays, panes, filters, footer, and results status display. | Widget rendering, service/provider calls, command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_tests.py` | Tests tab state, async loading, rendering, filtering, paging, detail, exports, and view-state restoration. | Test service implementation, app-level command registration, mutations, and any apply/write behavior. |
| `src/attackiq_cli/tui_widgets.py` | Shared header/banner/filter/list/detail/status widgets and placeholder workflow tab shell. | Domain-specific list/detail loading, provider calls outside status cache diagnostics, command registration, and any apply/write behavior. |
| `src/attackiq_cli/tui_provider.py` | Read-only TUI service fetching, bounded in-session caches, cache diagnostics, workspace resolution, and runtime-state compatibility imports. | Keep provider/cache contracts reusable by tabs without adding write behavior; keep runtime state derivation in `tui_provider_state.py`. |
| `src/attackiq_cli/tui_provider_state.py` | TUI runtime state model and auth/base-URL/spec-cache/environment/workspace display derivation. | Keep the boundary pure; avoid network calls, cache mutation, widget rendering, and write behavior. |
| `src/attackiq_cli/tui_mutation_preview.py` | Read-only mutation preview model, supported-operation allowlist, and bounded redaction helpers. | Textual controls, client construction, service mutation calls, apply flags, and preview persistence. |
| `src/attackiq_cli/tui_preview.py` | New-assessment, assessment-from-template, assessment-default targets, assessment-run, new-test, test-scenario assignment, and test-status input validation, bounded call-plan rendering, and local Textual modal controls. | Client construction, service mutation calls, apply flags, preview persistence, and unsupported operation fallback. |
| `src/attackiq_cli/service_core.py` | Shared service context, auth/client construction, and low-level normalization helpers. | Keep domain operation logic in focused service modules. |
| `src/attackiq_cli/services.py` | Backwards-compatible import facade for focused service modules and shared core helpers. | New domain behavior; keep additions in focused service submodules. |
| `src/attackiq_cli/services_assessment_tests.py` | Assessment and test filter normalization, summary records, read-only list/detail helpers, and TUI page fetch helpers. | Assessment/test mutations, CLI rendering, and non-assessment/test wrapper families. |
| `src/attackiq_cli/services_mutations.py` | Assessment/test mutation helpers, synthetic operation builders, apply-mode service calls, and mutation response normalization. | CLI rendering, read-only wrapper families, TUI write behavior, and transport-level retry/redaction logic. |
| `src/attackiq_cli/services_assets.py` | Asset filter normalization, summary records, native and Platform API read-only list helpers, and TUI page/detail fetch helpers. | Asset mutations, CLI rendering, and non-asset wrapper families. |
| `src/attackiq_cli/services_asset_groups.py` | Asset-group filter normalization, summary records, read-only list pagination, and detail fetch helpers. | Asset mutation behavior, CLI rendering, and non-asset-group wrapper families. |
| `src/attackiq_cli/services_blueprints.py` | Blueprint filter normalization, summary records, and read-only list fetch helper for `v1_blueprints_list`. | Blueprint mutation behavior, CLI rendering, and non-blueprint wrapper families. |
| `src/attackiq_cli/services_edr_scan_schedules.py` | EDR scan schedule filter normalization, summary records, read-only pagination, and target-scope derivation for `v1_emm_edr_scan_schedules_list`. | EDR schedule mutation behavior, retrieve/run history, raw target asset IDs, CLI rendering, and non-EDR schedule wrapper families. |
| `src/attackiq_cli/services_integrations.py` | Integration connector filter normalization, configuration-safe summary records, and read-only list fetch helper for `v1_company_connectors_list`. | Connector configuration output, integration mutations, CLI rendering, and non-integration wrapper families. |
| `src/attackiq_cli/services_results.py` | Results mode query selection, validation-result filters, read-only result list fetches, validation-result fetches, and phase result/log join helpers. | Result/validation CLI rendering, TUI tab layout, and non-result wrapper families. |
| `src/attackiq_cli/services_scenarios.py` | Scenario filter normalization, summary records, read-only native and Platform API list behavior, detail fetches, and health checks. | Scenario package upload, assessment/test mutation helpers, CLI rendering, and non-scenario wrapper families. |
| `src/attackiq_cli/services_tags.py` | Tag filter normalization, tag name resolution, tag summaries, and tag list/detail/search fetch helpers. | Keep read-only tag behavior isolated without adding write behavior. |
| `src/attackiq_cli/services_templates.py` | Assessment-template and template-test filter normalization, summary records, TUI page/detail helpers, and read-only list fetch helpers. | Template mutation behavior, CLI rendering, and non-template wrapper families. |
| `src/attackiq_cli/services_source_types.py` | Source-type filter normalization, summary records, and list fetch helper for `v1_source_types_list`. | Keep connector configuration output out of this read-only wrapper family. |
| `src/attackiq_cli/joiner/det_pipeline.py` | Deterministic DET stages A-E, artifact writing, dry-run/apply report orchestration, and compatibility exports for apply executors. | GitLab/AttackIQ network mutation implementation, CLI parsing, and unrelated dataset-join behavior. |
| `src/attackiq_cli/joiner/det_pipeline_apply.py` | GitLab retry/client behavior and apply-gated GitLab issue updates plus AttackIQ assessment creation. | Deterministic normalization/reconciliation/recommendation/plan stages, CLI rendering, and dry-run artifact generation. |
| `src/attackiq_cli/scenario_wizard.py` | Local Scenario Wizard image-tar prepare planning/apply orchestration and compatibility exports. | Focused create/image/package/process/bundle-runtime/validation implementation and Typer rendering. |
| `src/attackiq_cli/scenario_wizard_create.py` | Scenario Wizard create dry-run planning, isolated apply execution, temporary configuration transport, runtime dependency setup, and generated-file result collection. | Runtime-bundle preparation, package execution, image-tar extraction, and Typer rendering. |
| `src/attackiq_cli/scenario_wizard_image.py` | Scenario Wizard image-tar runtime inspection, bounded layer spooling, Docker whiteout/index handling, selected-file materialization, safe path normalization, sensitive-file exclusion, and requirements credential filtering. | High-level destination planning/apply orchestration, create/package execution, subprocess handling, and Typer rendering. |
| `src/attackiq_cli/scenario_wizard_package.py` | Scenario Wizard package planning/apply behavior, runtime site-package linking, dependency copying, and package result collection. | Runtime-bundle preparation, generated-scenario validation, and Typer rendering. |
| `src/attackiq_cli/scenario_wizard_process.py` | Allowlisted subprocess environments and redacted process output capture for local Scenario Wizard workflows. | Scenario Wizard domain planning, runtime extraction, and CLI rendering. |
| `src/attackiq_cli/scenario_wizard_runtime.py` | Scenario Wizard cache resolution, wrapper ZIP inspection with sensitive-file suppression, runtime-bundle validation summaries, and bundle-copy planning/apply behavior. | Image-tar indexing/materialization, create/package execution, subprocess handling, and Typer rendering. |
| `src/attackiq_cli/scenario_wizard_validation.py` | Runtime bundle validation, generated scenario validation, checksum helpers, and secret-like metadata screening. | Keep validation reusable without coupling it to apply-time subprocess execution. |
| `src/attackiq_cli/backup.py` | Backup domain orchestration, manifest writing, output-directory validation, and compatibility exports for backup helper modules. | Domain fetchers, artifact redaction, and artifact writing. |
| `src/attackiq_cli/backup_artifacts.py` | Backup payload redaction, artifact JSON writing, endpoint-catalog redaction classification checks, and file permission tightening. | Network fetching, domain selection, and endpoint-catalog loading. |
| `src/attackiq_cli/backup_fetchers.py` | Backup domain fetchers, endpoint-catalog read-only fetch execution, pagination response validation, and source-type request derivation. | Output-directory validation, manifest writing, artifact redaction, and artifact file writing. |
| `src/attackiq_cli/backup_catalog.py` | Backup endpoint-catalog model, loading, validation, and requested-domain safety checks. | Keep catalog expansion reviewable without coupling it to fetch or redaction changes. |

Extraction rules:

1. Move behavior behind tests before moving call sites.
2. Preserve CLI help, output schemas, dry-run/apply behavior, and redaction semantics.
3. Keep one extraction theme per change.
4. Prefer service-layer boundaries that can be reused by CLI and TUI rather than UI-specific helpers.

Recent CLI decomposition moved `call`, `export`, `scenarios`, `assessments`, `tests`, `join`, and
`tui` into focused command modules. Future decomposition should continue one command family or
helper boundary at a time, preserving the compatibility imports from `src/attackiq_cli/cli.py`
when external tests or users may still import old symbols.

## Adapter Pattern

Adapters should expose small, typed functions:

- `validate_source(path_or_config)`
- `iter_records(source)`
- `summarize(records)`
- `build_plan(records, options)`

Adapters should not write to AttackIQ directly. The CLI command or service layer decides whether to
apply a plan.

## Contract Versioning

Every external file contract should include a version field or be wrapped by metadata that provides
one. Consumers must reject unsupported major versions with a clear error.

## Security Defaults

- Never log or echo secrets.
- Redact headers and credential-like fields in previews.
- Keep TLS verification enabled by default.
- Set explicit timeouts for every network call.
- Require explicit scope or path inputs for sibling repo ingestion.
- Treat screenshots and captured browser artifacts as sensitive until reviewed.

## Quality Gate Parity

Release-critical checks should not diverge between local and CI entrypoints.

- `scripts/quality_gate.py` is the local source of truth for the standard release gate.
- GitHub Actions should either call the same script or mirror its release-critical checks,
  including script lint targets, AIQ Assist MCP contract checks, public-safety checks, public
  mirror checks, architecture boundaries, mypy, pytest, and documentation checks.
- When a new release, evidence, public-safety, or contract script is added, update both the local
  gate and CI in the same change or explicitly track the drift before release.

## Historical First Refactor Targets

The initial decomposition review used these targets to establish the current boundaries. Future
work should follow the ownership table and checked 800-line limit above rather than treating this
list as an active queue.

1. Extract shared dry-run/apply output handling from mutation commands.
2. Move custom scenario upload into an out-of-spec AttackIQ adapter.
3. Add a catalog adapter package for BAS catalog ingestion.
4. Add shared plan/result models for assessment planning.
5. Split TUI provider/cache behavior from tab rendering.
6. Split backup endpoint-catalog validation from artifact fetching and redaction.
