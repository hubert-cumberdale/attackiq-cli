# Architecture Standards

These standards define how new capabilities should be added to `aiq-cli`.

## Module Boundaries

| Layer | Owns | Must avoid |
| --- | --- | --- |
| `src/attackiq_cli/cli.py` | Typer commands, input validation, user-facing orchestration, dry-run/apply gates. | Business rules that need reuse by TUI, tests, or adapters. |
| `client.py` | HTTP transport, auth selection, retries, redaction, response status handling. | Domain-specific payload building. |
| `services.py` | Shared domain helpers, operation builders, list/export/query workflows. | Command-specific rendering and terminal UX. |
| `exporter.py` | CSV/JSON output normalization and file writing helpers. | Network calls. |
| `tui.py` | Textual UI state and display affordances over service-layer APIs. | Endpoint-specific logic that should live in services. |
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

## First Refactor Targets

1. Extract shared dry-run/apply output handling from mutation commands.
2. Move custom scenario upload into an out-of-spec AttackIQ adapter.
3. Add a catalog adapter package for BAS catalog ingestion.
4. Add shared plan/result models for assessment planning.
