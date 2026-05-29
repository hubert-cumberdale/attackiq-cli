# Architecture Standards

These standards define how new capabilities should be added to `aiq-cli`.

## Module Boundaries

| Layer | Owns | Must avoid |
| --- | --- | --- |
| `src/attackiq_cli/cli.py` | Typer commands, input validation, user-facing orchestration, dry-run/apply gates. | Business rules that need reuse by TUI, tests, or adapters. |
| `client.py` | HTTP transport, auth selection, retries, redaction, response status handling. | Domain-specific payload building. |
| `service_core.py` | Shared service context, auth/client setup, and small normalization helpers. | Domain-specific operation selection and output shaping. |
| `services.py` | Compatibility surface for service helpers plus domain query builders that have not been split yet. | Command-specific rendering and terminal UX. |
| `services_tags.py` | Tag query builders, tag resolution, summaries, and tag fetch helpers. | Non-tag service workflows and write behavior. |
| `services_source_types.py` | Source-type query builders, summaries, and read-only list fetch helpers. | Connector configuration output and write behavior. |
| `exporter.py` | CSV/JSON output normalization and file writing helpers. | Network calls. |
| `tui.py` | Textual UI state and display affordances over service-layer APIs. | Endpoint-specific logic that should live in services. |
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

1. Keep Typer-only parsing, `--output` handling, and command help in `src/attackiq_cli/cli.py`.
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

Large modules may remain temporarily when they preserve existing command behavior, but new
capabilities should reduce pressure on current oversized files rather than adding broad new
sections to them.

Current planned decomposition targets from the 2026-05-27 enterprise maturity review:

| Module | Current role | Preferred extraction direction |
| --- | --- | --- |
| `src/attackiq_cli/cli.py` | Typer command tree, validation, dry-run/apply orchestration, output handling. | Shared mutation plan/output helpers, command-family modules, and reusable validation helpers. |
| `src/attackiq_cli/tui.py` | Textual app shell, tabs, filters, exports, and status UI. | Per-domain controllers and service-backed query contracts. |
| `src/attackiq_cli/tui_provider.py` | TUI provider/cache behavior and runtime state derivation. | Keep provider/cache contracts reusable by tabs without adding write behavior. |
| `src/attackiq_cli/service_core.py` | Shared service context, auth/client construction, and low-level normalization helpers. | Keep domain operation logic in focused service modules. |
| `src/attackiq_cli/services.py` | Backwards-compatible service facade plus remaining domain query builders, operation selection, summaries, and fetch helpers. | Focused service submodules by domain family when helpers grow beyond one command family. |
| `src/attackiq_cli/services_tags.py` | Tag filter normalization, tag name resolution, tag summaries, and tag list/detail/search fetch helpers. | Keep read-only tag behavior isolated without adding write behavior. |
| `src/attackiq_cli/services_source_types.py` | Source-type filter normalization, summary records, and list fetch helper for `v1_source_types_list`. | Keep connector configuration output out of this read-only wrapper family. |
| `src/attackiq_cli/scenario_wizard.py` | Local Scenario Wizard runtime preparation, create/package execution, and compatibility exports. | Runtime adapter and package builder modules. |
| `src/attackiq_cli/scenario_wizard_validation.py` | Runtime bundle validation, generated scenario validation, checksum helpers, and secret-like metadata screening. | Keep validation reusable without coupling it to apply-time subprocess execution. |
| `src/attackiq_cli/backup.py` | Backup fetching, redaction, and artifact writing. | Redaction helpers and domain fetchers. |
| `src/attackiq_cli/backup_catalog.py` | Backup endpoint-catalog model, loading, validation, and requested-domain safety checks. | Keep catalog expansion reviewable without coupling it to fetch or redaction changes. |

Extraction rules:

1. Move behavior behind tests before moving call sites.
2. Preserve CLI help, output schemas, dry-run/apply behavior, and redaction semantics.
3. Keep one extraction theme per change.
4. Prefer service-layer boundaries that can be reused by CLI and TUI rather than UI-specific helpers.

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
  mirror checks, mypy, pytest, and documentation checks.
- When a new release, evidence, public-safety, or contract script is added, update both the local
  gate and CI in the same change or explicitly track the drift before release.

## First Refactor Targets

1. Extract shared dry-run/apply output handling from mutation commands.
2. Move custom scenario upload into an out-of-spec AttackIQ adapter.
3. Add a catalog adapter package for BAS catalog ingestion.
4. Add shared plan/result models for assessment planning.
5. Split TUI provider/cache behavior from tab rendering.
6. Split backup endpoint-catalog validation from artifact fetching and redaction.
