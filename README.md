# AttackIQ CLI
[![CI](https://github.com/hubert-cumberdale/attackiq-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/hubert-cumberdale/attackiq-cli/actions/workflows/ci.yml)

Enterprise-friendly Python CLI for the AttackIQ API, generated from the provided OpenAPI 3.0 schema (`openapi.yaml`). The tool helps you explore endpoints, validate parameters against the spec, and invoke operations with secure defaults.

Agent governance hub: `docs/GOVERNANCE.md`.
Session bootstrap guide: `docs/SESSION_BOOTSTRAP.md`.
Local MkDocs site: `mkdocs.yml` with source pages under `docs/`.
Production readiness checklist: `docs/PRODUCTION_READINESS.md`.
Production operator runbook: `docs/PRODUCTION_OPERATOR_RUNBOOK.md`.
Public release and enterprise delivery: `docs/PUBLIC_RELEASE.md`.
Security policy: `SECURITY.md`.

## Features
- Loads the bundled OpenAPI schema to index all operations and parameters.
- Lists and describes operations (by tag or `operationId`).
- Invokes any operation with validated path/query parameters and JSON bodies.
- Supports both AttackIQ auth schemes (`Account Token` and `JSON Web Token`) with secure header handling.
- Config persistence in a user config directory with opt-in TLS override.
- Structured output using Rich plus optional file output via `--output`.
- `attackiq call` supports `--output-format` for pretty JSON, raw text, or CSV output.
- `attackiq call` supports interactive prompts and form/multipart payloads.
- List/show tags with `attackiq tags list|show` (filters and CSV output supported for list).
- Search tags with `attackiq tags search` (table output by default).
- List/show assessment templates with `attackiq templates list|show`, and inspect template tests
  with `attackiq templates tests`.
- List/show assets with `attackiq assets list|show` (filters and CSV output supported).
- List/show asset groups with `attackiq asset-groups list|show` (filters and CSV output supported).
- List blueprints with `attackiq blueprints list` to discover IDs used by assessment workflows.
- List installed integration connectors with `attackiq integrations list` using summary output that
  omits connector configuration fields.
- Capture redacted tenant configuration backups with `attackiq backup configs`.
- List result summaries, phase results, and phase logs with `attackiq results list|phases|logs`
  (read-only JSON/CSV output supported).
- List validation results by scenario or asset, and inspect validation executions with
  `attackiq validation-results list|by-asset|asset-executions|scenario-executions`.
- Export datasets (`attackiq export assessments|scenarios|tests|templates`) with CSV/JSON output.
- Read-only TUI with a Landing/Status tab plus scenarios/assessments/tests/assets/settings list-detail and results view modes.
- TUI command palette (`Ctrl+K`) with grouped context-aware commands, keyword/alias search, and standardized feedback.
- TUI command palette includes a global `Clear all TUI caches` action for manual invalidation.
- TUI keybinding help overlay (`?`/`h`, dismiss with `Esc`) and read-only export shortcuts (`e` JSON, `c` CSV) on workflow tabs.
- TUI status diagnostics include auth/base-url source, spec cache status/source, runtime source
  precedence, and per-domain cache-entry totals.
- TUI structured filters support list sorting (`sort`, `dir`) and results filtering (`outcome`, `source`, `key`).
- TUI scenarios/results panes include inline structured-filter key maps with copyable examples.
- TUI provider requests use in-session caching across workflow domains; refresh clears tab-specific cache before reload.
- TUI provider caches list/detail paths across active workflow tabs (scenarios/results/assessments/tests/assets/templates).
- TUI cache size is bounded per cache by `ATTACKIQ_TUI_CACHE_MAX` (default `128` entries).
- Optional cache TTL can be set with `ATTACKIQ_TUI_CACHE_TTL` (seconds); default is disabled.
- Expired TTL entries are invalidated before cache stats/diagnostics are reported.
- Settings tab diagnostics include per-domain cache entries and aggregate totals.
- TUI detail panes include staged load-status text; scenario detail includes Parameters and Relationships sections.
- Deterministic joiner for AttackIQ exports and GitLab issues CSVs.
- Build create payloads for assessments/tests (no network) to use with `attackiq call`.
- Create assessments/tests via dedicated commands (dry-run by default; `--apply` performs the request).

## Quickstart
```bash
python -m venv .venv
source .venv/bin/activate
.\.venv\Scripts\activate  # Windows
pip install -e ".[dev]"

# Show available operations
attackiq spec list --tag AEV --limit 10 --offset 0

# Search operations (optional fields/pagination)
attackiq spec search scenario --fields operation_id,method,path --limit 5 --offset 5

# Describe one operation
attackiq spec show v1_assets_list

# Call an operation (example)
attackiq call v1_assets_list --param page=1 --param page_size=20 --output assets.json

# List assets (example)
attackiq assets list --search "agent"
attackiq assets list --activity-type DEVICE --deployment-state-id 2 --output-format csv --output assets.csv
attackiq assets show <asset-id>

# List asset groups (example)
attackiq asset-groups list --search "Linux"
attackiq asset-groups list --name "Linux Agents" --output-format csv --output asset-groups.csv
attackiq asset-groups show <asset-group-id>

# List blueprints (example)
attackiq blueprints list --search "Default"
attackiq blueprints list --output-format csv --output blueprints.csv

# List integration connectors (example)
attackiq integrations list --status ACTIVE
attackiq integrations list --display-name "Sentinel" --output-format csv --output integrations.csv

# Redacted configuration backup (example)
attackiq backup configs --output-dir /tmp/aiq-config-backup-20260521T120000Z --tenant-alias tenant-a

# List results (example)
attackiq results list --mode summaries
attackiq results list --mode phases --search "credential"
attackiq results phases --result-summary-id <result-summary-id>
attackiq results logs --scenario-job-id <scenario-job-id> --output-format csv --output phase-logs.csv

# List validation results (example)
attackiq validation-results list --days 7
attackiq validation-results by-asset --project-ids <assessment-id>
attackiq validation-results asset-executions <asset-id>
attackiq validation-results scenario-executions <scenario-id>

# List tags (example)
attackiq tags list --search "detection"
attackiq tags list --search "detection" --output-format csv --output tags.csv
attackiq tags list --page 2 --page-size 10
attackiq tags show <tag-id>

# List assessment templates (example)
attackiq templates list --search "credential"
attackiq templates list --template-name "Template Name" --output-format csv --output templates.csv
attackiq templates show <template-id>
attackiq templates tests --template-id <template-id>

# Search tags (example)
attackiq tags search "detection" --limit 10

# Build payloads (no network) for create flows (then apply with `attackiq call`)
attackiq build assessment from-template \
  --template-id d09d29ba-eed8-4212-bff2-4d1ee11ed80c \
  --name "Test Assessment" \
  --blueprint-id ee15c9ab-2dbc-4d3f-9b86-35c00d0d1796 \
  --output create_assessment.json
attackiq call v1_assessments_project_from_template_create --body-file create_assessment.json

# First-class assessment creation from a template (dry-run by default)
attackiq assessments create-from-template \
  --template-id d09d29ba-eed8-4212-bff2-4d1ee11ed80c \
  --name "Test Assessment"

attackiq build test create \
  --assessment-id ef900dfe-1bb9-475d-944a-07ffaeb26ad4 \
  --name "API Test" \
  --output create_test.json
attackiq call v1_tests_create --body-file create_test.json

attackiq build test add-scenarios 03fef867-3227-4d47-a858-90f9ad8cf217 \
  --scenario-id 00000000-0000-0000-0000-000000000000 \
  --output add_scenarios.json
attackiq call v1_tests_bulk_add_scenarios_create \
  --param id=03fef867-3227-4d47-a858-90f9ad8cf217 \
  --body-file add_scenarios.json
```

## Local Documentation Site
The repo includes a MkDocs site for operator workflows, production readiness, configuration
backup, architecture, and release guidance.

```bash
pip install -e ".[docs]"
mkdocs build
mkdocs serve --dev-addr 127.0.0.1:8000
```

Use `pip install -e ".[dev,docs]"` when you want both development and docs tooling in the same
virtual environment. The generated `site/` directory is disposable output and should not be
committed.

## Shell autocomplete
Install shell completion for your current shell:
```bash
attackiq --install-completion
```

Preview completion script output:
```bash
attackiq --show-completion
ATTACKIQ_COMPLETION_SHELL=bash attackiq --show-completion
```

## Configuration
- Base URL: set via `ATTACKIQ_BASE_URL` env var or `attackiq config set --base-url https://your-tenant/api`.
- Tokens:
  - Account Token: `attackiq auth set --account-token <token>`
  - JWT: `attackiq auth set --jwt <token>`
  - Overrides: `ATTACKIQ_ACCOUNT_TOKEN` or `ATTACKIQ_JWT` env vars.
- Inspect config: `attackiq config show` to view the effective settings.
- Clear saved tokens: `attackiq auth clear` removes stored credentials (env vars remain in effect).
- Defaults: `attackiq config set` supports `--timeout`, `--verify-tls/--no-verify-tls`,
  `--log-json/--no-log-json`, and `--log-level`.
- TLS: On by default. Use `--insecure` only when required on networked commands that expose it.
- Logging: `attackiq config set --log-json --log-level INFO` for structured output.
- Validate: `attackiq config validate` checks effective config and warns on risky settings.
- Verbose: `attackiq call ... --verbose` enables detailed request logs (redacted).
- Spec override: `attackiq --spec-path /path/to/openapi.yaml` or `ATTACKIQ_OPENAPI_PATH`.

Example:
```bash
attackiq config validate
```
Example output:
```text
Warnings:
- No auth token configured (Account Token or JWT).
Config OK
```

Config is stored in a platform-appropriate user config directory (overridable via `ATTACKIQ_CONFIG_DIR`). File permissions are tightened where supported.

## Exporting responses
- If `--output-format` is omitted, response bodies are written only when `--output` is set.
- Use `--output-format pretty-json|raw|csv` to print to stdout or control file formatting.
- CSV output requires a JSON array of objects.
- Maintainer deep dive: `docs/CALL_FLOW.md`.

`attackiq call` flags (selected):
- `--param/-p`, `--header/-H`, and `--cookie` accept `key=value` pairs.
- `--dry-run` previews the request without sending it and redacts auth headers.
- `--interactive` to prompt for missing parameters or request bodies.
- `--body` or `--body-file` sends JSON; `--form` and `--form-file` send form or multipart
  payloads. JSON body options and form options are mutually exclusive.
- `--auth-scheme auto|account-token|jwt|none` to override auth resolution.
- `--base-url`, `--timeout`, `--insecure`, `--log-json/--no-log-json`, and `--log-level` for
  per-call overrides.

Example:
```bash
attackiq call v1_assets_list --param page=1 --param page_size=20 --output assets.json
attackiq call v1_assets_list --param page=1 --param page_size=20 --output-format pretty-json
attackiq call v1_assets_list --param page=1 --param page_size=20 --output-format csv --output assets.csv
attackiq call v1_example_upload --interactive --form-file upload=sample.txt
```

## Exporting datasets
Use the export subcommands to pull common datasets to CSV or JSON.
Maintainer deep dive: `docs/EXPORT_FLOW.md`.

Common export options: `--output`, `--format`, `--page-size`, `--timeout`, `--insecure`.

Template export options:
- `--include-empty` (CSV only).
- `--scenario-details`, `--scenario-details-lenient/--scenario-details-strict`.
- `--scenario-details-retries`, `--scenario-concurrency` (`>= 1`).

Assessment export filters:
- `--max-pages`, `--asset-group-id`, `--blueprint-id`.
- `--name`.
- `--has-default-schedule/--no-has-default-schedule`, `--report-instance-type`.
- `--use-scenario-alert-rules/--no-use-scenario-alert-rules`, `--version`, `--zones-ordering`.

Examples:
```bash
attackiq export templates --output assessment_templates.csv
attackiq export templates --output assessment_templates.json --format json --scenario-details
attackiq export scenarios --output scenarios.csv
attackiq export assessments --output assessments.json --format json
attackiq export assessments --output assessments.csv --execution-strategy 1 --search "credential"
```

Notes:
- `attackiq tags list --page N` returns one explicit page (`N`) and does not auto-paginate.
- Export command `--page-size` values must be `>= 1`.

## Scenario commands
- `attackiq scenarios list --search "credential" --output-format json`
- `attackiq scenarios list --modified-after 2026-05-21T00:00:00Z`
- `attackiq scenarios show <scenario-id>`
- `attackiq scenarios upload scenario.zip` previews the captured custom scenario upload request.
- `attackiq scenarios upload scenario.zip --apply` uploads a Scenario Wizard package through the
  out-of-spec `/v1/scenario_templates` endpoint captured from the UI.

Notes:
- `scenarios list` uses the current `modified_after` API filter; `--last-updated` remains a
  compatibility alias.
- `scenarios upload` posts multipart form-data using field `zip_file`.
- Uploads are dry-run by default; pass `--apply` to create the custom scenario template.

## Scenario Wizard commands
- `attackiq scenario-wizard runtime inspect --zip /path/to/scenario-wizard-0.0.3.zip`
- `attackiq scenario-wizard runtime inspect --zip /path/to/scenario-wizard-0.0.3.zip --output inspect.json`
- `attackiq scenario-wizard runtime validate --bundle ~/.cache/attackiq-cli/scenario-wizard/0.0.3 --wizard-version 0.0.3`
- `attackiq scenario-wizard runtime prepare --from-bundle /path/to/runtime-bundle --wizard-version 0.0.3`
- `attackiq scenario-wizard runtime prepare --from-bundle /path/to/runtime-bundle --wizard-version 0.0.3 --apply`
- `attackiq scenario-wizard runtime prepare --from-image-tar /path/to/scenario-wizard-image.tar --wizard-version 0.0.3`
- `attackiq scenario-wizard runtime prepare --from-image-tar /path/to/scenario-wizard-image.tar --wizard-version 0.0.3 --apply`
- `attackiq scenario-wizard create --dry-run --config scenario_configuration.json --output generated-scenarios --runtime-bundle ~/.cache/attackiq-cli/scenario-wizard/0.0.3`
- `attackiq scenario-wizard create --apply --config scenario_configuration.json --output generated-scenarios --runtime-bundle ~/.cache/attackiq-cli/scenario-wizard/0.0.3 --timeout 300`
- `attackiq scenario-wizard package --scenario generated-scenarios/example`
- `attackiq scenario-wizard package --apply --scenario generated-scenarios/example --timeout 300`

Notes:
- Runtime inspection is read-only and performs no network calls.
- Runtime validation checks manifest metadata, required runtime paths, Python 3.12 compatibility,
  sensitive files, and wheelhouse checksum consistency when a checksum is declared.
- Runtime preparation accepts exactly one source: `--from-bundle` copies an explicit prebuilt
  bundle, and `--from-image-tar` converts a trusted filesystem tar or Docker-save layer tar into a
  cache bundle by extracting only runtime scripts, templates, wheelhouse files, and requirements.
  It does not run Docker.
- Image-tar preparation can auto-detect common paths or accept `--runtime-root`,
  `--wheelhouse-path`, `--requirements-path`, and `--python-version`.
- `scenario-wizard create --apply` creates a local venv, installs from the runtime bundle wheelhouse
  with `--no-index` when extracted site-packages are unavailable, imports the Scenario Wizard
  `make_scenario` module directly from the bundle `runtime/` and `python/` directories, and captures
  bounded redacted subprocess output.
- `scenario-wizard package --apply` creates or reuses a scenario-local `venv`, installs from the
  scenario `.pipdownload` directory with `--no-index`, and reports generated zips under `target/`.
  For image-backed scenarios it links the extracted Scenario Wizard runtime into the venv, stages
  venv-installed dependencies into `bin/`, and compresses locally instead of using the image
  packaging stage that can fall back to PyPI.
- Sensitive package configuration files such as `pip.conf` are reported as present but their
  contents and checksums are suppressed.
- The output reports wrapper version, wrapper-only status, and the expected local runtime bundle
  path used by the planned no-container create flow.

## Catalog commands
- `attackiq catalog validate --path catalog`
- `attackiq catalog list --path catalog --provider aws --technique T1550`
- `attackiq catalog list --path catalog --output-format csv --output catalog.csv`
- `attackiq catalog coverage --path catalog`
- `attackiq catalog coverage --path catalog --include-techniques`

Notes:
- Catalog commands are read-only and perform no network calls.
- The default catalog path is `catalog`.
- Catalog records are normalized into the shared contract concepts documented in
  `docs/CATALOG_CONTRACT.md`.

## Template commands
- `attackiq templates list --search "credential" --output-format json`
- `attackiq templates show <template-id>`
- `attackiq templates tests --template-id <template-id>`
- `attackiq templates tests --template-id <template-id> --output-format csv --output template-tests.csv`

Notes:
- `templates list` supports `--page`, `--page-size`, `--search`, `--template-name`,
  `--project-name`, `--category`, `--assessment-type`, `--behavior`, `--output-format`,
  `--output`, `--insecure`, and `--timeout`.
- `templates tests` supports `--page`, `--page-size`, `--template-id`/`--project-template-id`,
  `--output-format`, `--output`, `--insecure`, and `--timeout`.
- CSV output requires `--output`.

## Assets commands
- `attackiq assets list --search "agent" --output-format json`
- `attackiq assets list --hostname "agent-host" --activity-type DEVICE`
- `attackiq assets list --deployment-state-id 2 --asset-group <asset-group-id> --output-format csv --output assets.csv`
- `attackiq assets show <asset-id>`

Notes:
- `assets list` supports `--page`, `--page-size`, `--search`, `--hostname`, `--ipv4-address`,
  `--ipv6-address`, `--deployment-state-id`, `--asset-group`, `--activity-type`, `--ordering`,
  `--deepsurface-last-seen-in-host-analysis-at`, `--deepsurface-sync-state`, and
  `--deepsurface-sync-state-changed-at`.
- CSV output requires `--output`.

## Asset Group commands
- `attackiq asset-groups list --search "Linux" --output-format json`
- `attackiq asset-groups list --company-id <company-id> --output-format csv --output asset-groups.csv`
- `attackiq asset-groups show <asset-group-id>`

Notes:
- `asset-groups list` supports `--page`, `--page-size`, `--search`, `--id`/`--asset-group-id`,
  `--name`, `--description`, `--company`, `--company-id`, `--user`, `--user-id`, `--created`,
  `--created-after`, `--modified`, and `--ordering`.
- CSV output requires `--output`.

## Blueprint commands
- `attackiq blueprints list --search "Default" --output-format json`
- `attackiq blueprints list --output-format csv --output blueprints.csv`

Notes:
- `blueprints list` supports `--page`, `--page-size`, `--search`, `--output-format`,
  `--output`, `--insecure`, and `--timeout`.
- CSV output requires `--output`.

## Integration commands
- `attackiq integrations list --status ACTIVE --output-format json`
- `attackiq integrations list --display-name "Sentinel" --output-format csv --output integrations.csv`

Notes:
- `integrations list` supports `--page`, `--page-size`, `--alert-correlation-plan`,
  `--company-connector-manager-setup`, `--company-connector-manager-setup-id`,
  `--description`, `--display-name`, `--implemented-mixins`, `--is-deleted true|false`,
  `--mode`, `--mttd-timezone`, `--status`, `--ordering`, `--output-format`, `--output`,
  `--insecure`, and `--timeout`.
- JSON and CSV output use a summary record shape that omits connector `configuration` and
  `additional_configuration_options`; use `attackiq call v1_company_connectors_list` only when an
  approved workflow explicitly needs the raw payload.
- CSV output requires `--output`.

## Backup commands
- `attackiq backup configs --output-dir /tmp/aiq-config-backup-20260521T120000Z --tenant-alias tenant-a`
- `attackiq backup configs --output-dir /tmp/aiq-config-backup-20260521T120000Z --include integrations,source-types --max-pages 5`

Notes:
- `backup configs` defaults to `integrations,source-types,detection-rules`.
- Artifacts and `manifest.json` are written to an output directory outside git with redaction
  enabled; there is no raw-response option.
- Use `--endpoint-catalog` only for sanitized, reviewed discovered endpoints. Write-like and
  unsupported catalog entries are rejected.
- Maintainer/operator runbook: `docs/CONFIGURATION_BACKUP_RUNBOOK.md`.

## Results commands
- `attackiq results list --mode summaries`
- `attackiq results list --mode phases --search "credential" --output-format json`
- `attackiq results list --mode logs --page 2 --page-size 50`
- `attackiq results phases --result-summary-id <result-summary-id>`
- `attackiq results logs --scenario-job-id <scenario-job-id> --output-format csv --output logs.csv`

Notes:
- Results commands are read-only and fetch one explicit page at a time.
- `results list --mode summaries` uses the assessment-results summaries endpoint and supports
  `--tag-id`.
- `results list --mode phases|logs` supports `--search`.
- `results phases` and `results logs` require exactly one of `--result-summary-id` or
  `--scenario-job-id`.
- CSV output requires `--output`.

## Validation Results Commands
- `attackiq validation-results list --days 7 --output-format json`
- `attackiq validation-results by-asset --project-ids <assessment-id>`
- `attackiq validation-results asset-executions <asset-id> --tag-ids <tag-id>`
- `attackiq validation-results scenario-executions <scenario-id> --output-format csv --output validation.csv`

Notes:
- Validation results commands are read-only.
- `list` and `by-asset` fetch one explicit page at a time with `--page` and `--page-size`.
- Shared filters are `--days`, `--project-ids`, `--scope-id`, and `--tag-ids`.
- CSV output requires `--output`.

## Assessments and tests commands
The CLI includes first-class `assessments` and `tests` groups for list/detail and mutation flows.
Mutation commands are dry-run by default; pass `--apply` to execute the network request.

Assessments:
- `attackiq assessments list --search "credential" --output-format json`
- `attackiq assessments list --id-in <assessment-id> --tag-id <tag-id>`
- `attackiq assessments show <assessment-id>`
- `attackiq assessments create --name "My Assessment" --scenario-id <scenario-uuid> [--scenario-id <scenario-uuid>] [--apply]`
- `attackiq assessments create-from-template --template-id <template-id> --name "My Assessment" [--blueprint-id <blueprint-id>] [--apply]`
- `attackiq assessments update-defaults <assessment-id> --asset-id <asset-uuid> [--asset-id <asset-uuid>] [--asset-group-id <asset-group-uuid>] [--apply]`
- `attackiq assessments run <assessment-id> [--apply]`

Assessment list notes:
- `assessments list` supports `--id`/`--id-in`, `--tag-id`, and repeatable or comma-separated
  `--tag-ids` in addition to the existing list filters.

Tests:
- `attackiq tests list --name "API Test" --output-format json`
- `attackiq tests show <test-id>`
- `attackiq tests create --assessment-id <assessment-id> --name "API Test" [--apply]`
- `attackiq tests add-scenarios <test-id> --scenario-id <scenario-uuid> [--scenario-id <scenario-uuid>] [--apply]`
- `attackiq tests get-status <test-id> [--apply]`

Notes:
- `assessments create` and `tests add-scenarios` also support `--scenario-ids-file <path>` with
  UUIDs (one per line or comma-separated).
- Dry-run output is consistent across mutation commands: call-plan JSON with
  `operation_id`, `path_params`, `query_params`, and `json_body` when the request has a body.

Known-safe dry-run examples (omit `--apply`):
```bash
attackiq assessments create --name "My Assessment" --scenario-id 00000000-0000-0000-0000-000000000000
attackiq assessments create-from-template --template-id d09d29ba-eed8-4212-bff2-4d1ee11ed80c --name "Template Assessment"
attackiq assessments update-defaults ef900dfe-1bb9-475d-944a-07ffaeb26ad4 --asset-id b77596ec-e4bf-418f-ae33-520555a6105a
attackiq assessments run ef900dfe-1bb9-475d-944a-07ffaeb26ad4
attackiq tests create --assessment-id ef900dfe-1bb9-475d-944a-07ffaeb26ad4 --name "API Test"
attackiq tests add-scenarios 03fef867-3227-4d47-a858-90f9ad8cf217 --scenario-id 00000000-0000-0000-0000-000000000000
attackiq tests get-status 03fef867-3227-4d47-a858-90f9ad8cf217
```

## TUI
Launch the read-only TUI with:
```bash
attackiq tui
```

Common options:
```bash
attackiq tui --page-size 50 --search "credential" --tag "windows"
attackiq tui --filter-debounce 0.25
```

Keybindings (TUI):
- `Ctrl+K` command palette
- `?` / `h` toggle keybinding help
- `Esc` dismiss overlays
- `[` previous tab
- `]` next tab
- `n` next page
- `p` previous page
- `r` refresh
- `e` export current workflow view as JSON
- `c` export current workflow view as CSV
- `Tab` focus next
- `q` quit
- `Enter` apply filters (also applied automatically on change)

Notes:
- Landing / Status, Scenarios, Assessments, Tests, Assets, Results, and Settings tabs are active.
- Results includes view modes (Summaries/Phases/Logs) via the view selector.
- Workflow tab state (filters/page/selection/view mode) persists across tab switches for Scenarios, Assessments, Tests, Assets, Results, and Settings.
- Maintainer deep dive: `docs/TUI_FLOW.md`.
- Structured filter examples:
  - Scenarios: `sort=name dir=asc`
  - Results summaries: `sort=scenario dir=asc outcome=pass`
  - Results grouped views: `source=scenario_job_id key=job-`

## Joining datasets
Use the deterministic joiner to combine AttackIQ exports (assessments + scenarios) with a GitLab issues CSV.
The `attackiq join` command supports two modes:
- `datasets` (default): deterministic CSV joins and manifest creation.
- `det-pipeline`: staged normalization/reconciliation/recommendation/patch-planning pipeline.

See `docs/JOINER.md` for the full workflow, outputs, and join semantics.

Example:
```bash
attackiq join datasets \
  --assessments assessments.csv \
  --scenarios scenarios.csv \
  --issues gitlab_issues.csv \
  --outdir joined \
  --timestamp 2026-01-26T00:00:00Z

attackiq join det-pipeline \
  --issues gitlab_issues.csv \
  --scenarios scenarios.csv \
  --outdir joined \
  --project-id 12345
```

Notes:
- `det-pipeline` requires `--issues`, `--scenarios`, `--outdir`, and `--project-id` even in dry-run.
- `--dry-run/--no-dry-run`, `--apply`, and recommendation/patch-plan flags are det-pipeline-only controls.

Module entrypoints:
```bash
python -m attackiq_cli.joiner.cli join \
  --assessments assessments.csv \
  --scenarios scenarios.csv \
  --issues gitlab_issues.csv \
  --outdir joined \
  --timestamp 2026-01-26T00:00:00Z

# Compatibility alias
python -m aiq_cli.joiner.cli join \
  --assessments assessments.csv \
  --scenarios scenarios.csv \
  --issues gitlab_issues.csv \
  --outdir joined
```

Key outputs:
- `assessment_scenario.csv`, `issue_scenario.csv`, `assessment_scenario_issue.csv`
- `issues_unmapped.csv`, `manifest.json`

## Security Practices
- Authorization headers are injected only at request time and are never echoed to stdout.
- Verbose and dry-run output redacts headers that include tokens, JWTs, or API keys.
- TLS verification is enabled by default; `--insecure` is an explicit per-command opt-out for
  networked flows that expose it.
- Timeouts and minimal request logging help avoid secret leakage.
- Retries use exponential backoff for transient failures (timeouts/5xx/429) on safe methods.
- Request body validation is a lightweight client-side preflight (types, required fields,
  selected formats, string length/pattern, numeric bounds, and common collection limits);
  complex API-side validation remains server-authoritative.

## Dependency Governance
- Keep `pyproject.toml`/`requirements.txt` ranges conservative and add a pinned lockfile for releases.
- Recommended tooling:
  - `constraints.txt` pins the validated dev/release/audit environment for CI installs.
  - `python3 scripts/check_dependency_constraints.py` verifies direct dependency metadata and
    constraints coverage.
  - `python3 scripts/build_enterprise_package.py --source-ref vX.Y.Z --output-dir <dir>` builds
    credential-free enterprise package promotion artifacts and package provenance from a public release tag.
  - `python3 scripts/verify_enterprise_package.py <dir>` verifies the package manifest,
    checksums, provenance, safe artifact names, and wheel public-safety status before or after Artifactory.
  - `pip-audit` against the installed release environment, plus `pip-audit -r requirements.txt`
    and any lockfile when auditing dependency files directly.
- Record remediation steps in release notes when dependency CVEs require upgrades.

## Development
```bash
pip install -e ".[dev,docs]"
pytest
```

Run the standard local quality gate:
```bash
python3 scripts/check_public_safety.py
python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel
python3 scripts/quality_gate.py
python3 scripts/quality_gate.py --dry-run
```

Deep-dive docs maintenance:
```bash
python3 scripts/check_dependency_constraints.py
python3 scripts/render_deep_dives.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
mkdocs build
```

## Contributing for Agents
- Follow governance rules in `docs/GOVERNANCE.md` and `docs/sub-agent-scope.md`.
- Use `docs/SESSION_BOOTSTRAP.md` for the repo-specific deep-dive/parity loop and
  command checklist.
- Use skills from `skills/README.md` when tasks match their scope.
- Reuse shared snippets from `docs/agent-snippets.md` instead of rewriting helpers.
- Docs-only updates do not require tests; code changes should add or update pytest coverage.
- See `CONTRIBUTING.md` for full contribution guidance.

## Notes
- The CLI depends on the bundled `src/attackiq_cli/openapi.yaml`.
- If you change the schema, re-run the CLI; no code regeneration is required.
