# GA Stable Contract Inventory

Status: completed contract-test baseline for General Availability (GA) Gate 2. Gate 4 separately
prepared `v1.1.0` as an explicitly non-GA stable candidate; this document does not declare GA or
authorize tenant activity. `v0.1.27` remains the current production-ready Beta.

## Contract Boundary

The proposed stable contract covers repository-owned, operator-observable behavior:

- documented command paths, arguments, option names, aliases, defaults, and validation behavior
- persisted configuration keys, defaults, validation, and environment-variable precedence
- process exit categories
- repository-owned JSON envelopes, CSV serialization, and dry-run call-plan shapes

Presence in this inventory is not authorization to run a workflow. Production authorization remains
defined by `docs/PRODUCTION_OPERATOR_RUNBOOK.md`, and the GA rollout uses only the bounded roster
below. Provider-owned response fields may add fields without changing this repository-owned
contract.

The proposed contract excludes:

- every `--apply` execution path, including scenario upload, assessment/test mutations, Scenario
  Wizard local execution, and DET pipeline writes
- generic `attackiq call` use for a write operation unless `--dry-run` prevents the request
- the experimental `attackiq platform-api parity` command and experimental `--api-backend
  platform-api` selections
- AIQ Assist MCP consumption, which remains disabled
- PyPI and broad public-package availability
- provider schemas, tenant-specific values, raw responses, and third-party Scenario Wizard output

Mixed dry-run/apply commands retain their current option names in CLI help. Only their no-request
dry-run behavior is proposed for GA certification; listing `--apply` here does not certify or
approve it.

## Bounded GA Rollout Roster

The rollout roster is the exact low-risk command set built by `scripts/live_smoke.py`. The tenant
calls use explicit page 1, a default page size of 5, explicit timeouts, and output files outside
git. The harness rejects page sizes above 5, and mutation plans use only the reserved fake UUIDs
defined by the harness. Before live execution, its preflight fails closed unless the effective base
URL uses `https://` and persisted configuration enables TLS verification. Plan-only `--dry-run`
remains offline and does not require configured tenant access.

| Category | Command | Required rollout boundary |
| --- | --- | --- |
| Configuration | `attackiq config validate` | Effective configuration only; no tenant request. |
| Local spec | `attackiq spec list --limit 3 --fields operation_id,method,path` | Bundled local schema only. |
| Read-only | `attackiq tags list --page 1 --page-size 5 --output <scratch>/tags.json` | One bounded page. |
| Read-only | `attackiq scenarios list --page 1 --page-size 5 --output <scratch>/scenarios.json` | One bounded page. |
| Read-only | `attackiq assets list --page 1 --page-size 5 --output <scratch>/assets.json` | One bounded page. |
| Read-only | `attackiq assessments list --page 1 --page-size 5 --output <scratch>/assessments.json` | One bounded page. |
| Read-only | `attackiq tests list --page 1 --page-size 5 --output <scratch>/tests.json` | One bounded page. |
| Fake-ID dry-run | `attackiq assessments create` | Fake scenario UUID; no `--apply`. |
| Fake-ID dry-run | `attackiq tests create` | Fake assessment UUID; no `--apply`. |
| Fake-ID dry-run | `attackiq tests add-scenarios` | Fake test and scenario UUIDs; no `--apply`. |
| Fake-ID dry-run | `attackiq assessments run` | Fake assessment UUID; no `--apply`. |

Changing this roster, its pagination bounds, its fake-ID requirement, or its no-apply invariant is a
GA scope change and requires separate review.

## Command And Option Inventory

Every command supports `--help`. The root also exposes Typer's `--install-completion` and
`--show-completion` options. Required positional arguments are shown in angle brackets; optional
positionals are shown in brackets. Option pairs separated by `/` are aliases or boolean pairs.

`tests/fixtures/ga_cli_inventory.json` explicitly classifies every command and option in this
inventory, including the shared `--help` option, as `proposed-stable` or `excluded`. It also
classifies the documented experimental `platform-api` option values. `proposed-stable` describes a
surface name that is eligible for the future GA contract within the boundaries above; it does not
authorize its use. CI runs
`python3 scripts/check_ga_cli_inventory.py` to reject a documented surface that is absent from the
committed Typer/Click metadata and to require a reviewed classification for every new surface.

### Root, Configuration, And Local Discovery

```text
attackiq
  --version/-V, --spec-path, --install-completion, --show-completion
attackiq spec list
  --tag, --limit, --offset, --fields
attackiq spec find <query>
  --tag, --limit, --offset, --fields
attackiq spec search <query>
  --tag, --limit, --offset, --fields
attackiq spec show <operation-id>
attackiq config show
attackiq config validate
attackiq config set
  --base-url, --verify-tls, --no-verify-tls, --timeout,
  --log-json/--no-log-json, --log-level
attackiq auth set
  --account-token, --jwt
attackiq auth clear
```

### Generic Call, TUI, Local Build, And Join

```text
attackiq call <operation-id>
  --param/-p, --header/-H, --cookie, --body, --body-file, --form, --form-file,
  --interactive/-i, --output, --output-format, --base-url, --timeout,
  --log-json/--no-log-json, --log-level, --verbose/-v, --auth-scheme, --insecure,
  --dry-run
attackiq tui
  --page-size, --order-by, --search, --tag, --filter-debounce, --timeout,
  --auth-scheme, --insecure
attackiq build assessment from-template
  --template-id, --name, --blueprint-id, --output, --print-call, --strict-spec
attackiq build test create
  --assessment-id, --name, --output, --print-call, --strict-spec
attackiq build test add-scenarios <test-id>
  --scenario-id, --scenario-ids-file, --output, --print-call, --strict-spec
attackiq join [mode]
  --assessments, --scenarios, --issues, --outdir, --project-id, --apply,
  --dry-run/--no-dry-run, --top-k, --top-n-per-issue, --force-tool-label,
  --allow-append-sections, --timestamp, --fail-on-missing-scenario/
  --no-fail-on-missing-scenario, --fail-on-malformed-scenario-technique/
  --no-fail-on-malformed-scenario-technique
```

`attackiq join` apply behavior remains excluded. The local datasets mode and DET pipeline dry-run
artifacts are inventory inputs, but neither is part of the bounded rollout roster.

### Read-Only Tenant Commands

```text
attackiq scenarios list
  --output-format, --output/-o, --page, --page-size, --order-by, --search, --tag,
  --name, --modified-after, --last-updated, --mitre-platforms, --hierarchy,
  --object-fingerprint, --parameters-description, --scenario-template-instance,
  --api-backend, --insecure, --timeout
attackiq scenarios show <scenario-id>
  --output/-o, --insecure, --timeout
attackiq tags list
  --search, --name, --display-name, --content-type, --exclude-tag-set,
  --object-fingerprint, --page-size, --page, --output-format, --output/-o,
  --insecure, --timeout
attackiq tags show <tag-id>
  --output/-o, --insecure, --timeout
attackiq tags search <query>
  --limit, --output-format, --output/-o, --insecure, --timeout
attackiq templates list
  --search, --template-name, --project-name, --category, --assessment-type,
  --behavior, --page-size, --page, --output-format, --output/-o, --insecure,
  --timeout
attackiq templates show <template-id>
  --output/-o, --insecure, --timeout
attackiq templates tests
  --template-id/--project-template-id, --page-size, --page, --output-format,
  --output/-o, --insecure, --timeout
attackiq assessments list
  --output-format, --output/-o, --page, --page-size, --search, --name,
  --asset-group-id, --blueprint-id, --execution-strategy,
  --has-default-schedule/--no-has-default-schedule, --id/--id-in,
  --report-instance-type, --tag-id, --tag-ids,
  --use-scenario-alert-rules/--no-use-scenario-alert-rules, --version,
  --zones-ordering, --insecure, --timeout
attackiq assessments show <assessment-id>
  --output/-o, --insecure, --timeout
attackiq tests list
  --output-format, --output/-o, --page, --page-size, --name,
  --project-template-test-id,
  --run-in-hosted-agent-preferably/--no-run-in-hosted-agent-preferably,
  --use-hosted-agent/--no-use-hosted-agent, --insecure, --timeout
attackiq tests show <test-id>
  --output/-o, --insecure, --timeout
attackiq assets list
  --output-format, --output/-o, --page, --page-size, --search, --hostname,
  --ipv4-address, --ipv6-address, --deployment-state-id,
  --deepsurface-last-seen-in-host-analysis-at, --deepsurface-sync-state,
  --deepsurface-sync-state-changed-at, --asset-group, --activity-type, --ordering,
  --api-backend, --insecure, --timeout
attackiq assets show <asset-id>
  --output/-o, --insecure, --timeout
attackiq asset-groups list
  --search, --id/--asset-group-id, --name, --description, --company, --company-id,
  --user, --user-id, --created, --created-after, --modified, --ordering,
  --page-size, --page, --output-format, --output/-o, --insecure, --timeout
attackiq asset-groups show <asset-group-id>
  --output/-o, --insecure, --timeout
attackiq blueprints list
  --search, --page-size, --page, --output-format, --output/-o, --insecure,
  --timeout
attackiq integrations list
  --alert-correlation-plan, --company-connector-manager-setup,
  --company-connector-manager-setup-id, --description, --display-name,
  --implemented-mixins, --is-deleted, --mode, --mttd-timezone, --status,
  --ordering, --page-size, --page, --output-format, --output/-o, --insecure,
  --timeout
attackiq source-types list
  --company-id, --connector-id, --object-fingerprint, --unassigned-for,
  --page-size, --page, --output-format, --output/-o, --insecure, --timeout
attackiq assessment-schedules list
  --output-format, --output/-o, --insecure, --timeout
attackiq edr-scan-schedules list
  --data-source, --enabled, --schedule-type, --targeted, --page-size, --page,
  --output-format, --output/-o, --insecure, --timeout
attackiq results list
  --mode, --output-format, --output/-o, --page, --page-size, --search, --tag-id,
  --insecure, --timeout
attackiq results phases
  --result-summary-id, --scenario-job-id, --output-format, --output/-o, --page,
  --page-size, --insecure, --timeout
attackiq results logs
  --result-summary-id, --scenario-job-id, --output-format, --output/-o, --page,
  --page-size, --insecure, --timeout
attackiq validation-results list
  --output-format, --output/-o, --page, --page-size, --days, --project-ids,
  --scope-id, --tag-ids, --insecure, --timeout
attackiq validation-results by-asset
  --output-format, --output/-o, --page, --page-size, --days, --project-ids,
  --scope-id, --tag-ids, --insecure, --timeout
attackiq validation-results asset-executions <asset-id>
  --output-format, --output/-o, --days, --project-ids, --scope-id, --tag-ids,
  --insecure, --timeout
attackiq validation-results scenario-executions <scenario-id>
  --output-format, --output/-o, --days, --project-ids, --scope-id, --tag-ids,
  --insecure, --timeout
```

Experimental `platform-api` backend values remain excluded even though the native `--api-backend`
option name is inventoried.

### Read-Only Exports, Backup, And Local Catalog

```text
attackiq export templates
  --output/-o, --format, --page-size, --include-empty,
  --scenario-details/--no-scenario-details,
  --scenario-details-lenient/--scenario-details-strict, --scenario-details-retries,
  --scenario-concurrency, --insecure, --timeout
attackiq export scenarios
  --output/-o, --format, --page-size, --insecure, --timeout
attackiq export assessments
  --output/-o, --format, --page-size, --max-pages, --asset-group-id,
  --blueprint-id, --execution-strategy,
  --has-default-schedule/--no-has-default-schedule, --name, --report-instance-type,
  --search, --use-scenario-alert-rules/--no-use-scenario-alert-rules, --version,
  --zones-ordering, --insecure, --timeout
attackiq export tests
  --output/-o, --format, --page-size, --insecure, --timeout
attackiq backup configs
  --output-dir, --page-size, --max-pages, --company-id, --include,
  --endpoint-catalog, --tenant-alias, --insecure, --timeout
attackiq catalog validate
  --path/-p, --output/-o
attackiq catalog list
  --path/-p, --provider, --status, --technique, --surface, --search, --limit,
  --output-format, --output/-o
attackiq catalog coverage
  --path/-p, --include-techniques, --output/-o
```

### Dry-Run Mutation And Scenario Wizard Commands

```text
attackiq scenarios upload <packages...>
  --apply, --endpoint, --field-name, --output/-o, --raw-response, --auth-scheme,
  --insecure, --timeout
attackiq assessments create
  --name, --scenario-id, --scenario-ids-file, --apply, --output/-o, --insecure,
  --timeout
attackiq assessments create-from-template
  --template-id, --name, --blueprint-id, --apply, --output/-o, --insecure,
  --timeout
attackiq assessments update-defaults <assessment-id>
  --asset-id, --asset-ids-file, --asset-group-id, --asset-group-ids-file,
  --apply, --output/-o, --insecure, --timeout
attackiq assessments run <assessment-id>
  --apply, --output/-o, --insecure, --timeout
attackiq tests create
  --assessment-id, --name, --apply, --output/-o, --insecure, --timeout
attackiq tests add-scenarios <test-id>
  --scenario-id, --scenario-ids-file, --apply, --output/-o, --insecure, --timeout
attackiq tests get-status <test-id>
  --apply, --output/-o, --insecure, --timeout
attackiq scenario-wizard runtime inspect
  --zip, --cache-dir, --output/-o
attackiq scenario-wizard runtime validate
  --bundle, --wizard-version, --output/-o
attackiq scenario-wizard runtime prepare
  --from-bundle, --from-image-tar, --cache-dir, --wizard-version, --force,
  --runtime-root, --wheelhouse-path, --requirements-path, --python-version,
  --dry-run/--apply, --output/-o
attackiq scenario-wizard create
  --config, --output, --runtime-bundle, --wizard-version, --python, --force,
  --dry-run/--apply, --timeout, --plan-output
attackiq scenario-wizard package
  --scenario, --python, --force, --dry-run/--apply, --timeout, --output/-o
```

Only the no-request/no-execution branch of each mixed command is proposed for GA certification.
Scenario Wizard commands are not part of the production-tenant rollout roster.

### Experimental Inventory Outside The Proposed Contract

```text
attackiq platform-api parity <resource>
  --search, --page, --page-size, --order-by, --deployment-state-id, --output/-o,
  --fail-on-mismatch/--no-fail-on-mismatch, --insecure, --timeout
attackiq scenarios list --api-backend platform-api
attackiq assets list --api-backend platform-api
```

These surfaces remain documented as experimental and are not stable GA surfaces.

## Persisted Configuration Inventory

The persisted file is `config.json` under the platform configuration directory. Unknown keys are
ignored when loading; secrets are masked by `config show`. Environment variables override only the
fields identified below.

| Key | Type and default | Observable contract |
| --- | --- | --- |
| `base_url` | string or null; null | Normalized HTTP(S) URL without embedded credentials, query, fragment, or trailing slash. `ATTACKIQ_BASE_URL` takes precedence. |
| `account_token` | string or null; null | Stored credential, masked in display. `ATTACKIQ_ACCOUNT_TOKEN` takes precedence. |
| `jwt` | string or null; null | Stored credential, masked in display. `ATTACKIQ_JWT` takes precedence. |
| `verify_tls` | boolean; true | TLS verification is enabled unless explicitly disabled in persisted config or per-command `--insecure` handling. |
| `timeout` | number; 30.0 | Inclusive finite range 1.0 through 120.0 seconds; booleans and non-finite values are rejected. |
| `log_json` | boolean; false | Enables structured logging where supported. |
| `log_level` | string; `INFO` | One of `CRITICAL`, `ERROR`, `WARNING`, `INFO`, or `DEBUG`; normalized to uppercase. |

## Environment Variable Inventory

| Variable | Scope | Observable contract |
| --- | --- | --- |
| `ATTACKIQ_CONFIG_DIR` | Configuration | Overrides the platform configuration directory. |
| `ATTACKIQ_BASE_URL` | Configuration/network | Overrides persisted `base_url`. |
| `ATTACKIQ_ACCOUNT_TOKEN` | Authentication | Overrides the persisted Account Token. |
| `ATTACKIQ_JWT` | Authentication | Overrides the persisted JWT. |
| `ATTACKIQ_OPENAPI_PATH` | Global CLI | Supplies `--spec-path`; the path must exist and be readable. |
| `ATTACKIQ_COMPLETION_SHELL` | Completion | Provides the shell name when automatic detection is unavailable. |
| `ATTACKIQ_SPEC_CACHE_DISABLE` | Spec cache | Case-insensitive `1`, `true`, `yes`, or `on` disables spec caching. |
| `ATTACKIQ_SPEC_CACHE_DIR` | Spec cache | Overrides the spec cache directory. |
| `ATTACKIQ_TUI_CACHE_MAX` | TUI | Positive integer per-cache entry bound; unset or invalid uses default 128. |
| `ATTACKIQ_TUI_CACHE_TTL` | TUI | Positive finite cache TTL in seconds; unset or invalid disables TTL expiry. |
| `ATTACKIQ_SCENARIO_WIZARD_CACHE_DIR` | Scenario Wizard | Overrides the local runtime-bundle cache directory. |

`GITLAB_TOKEN`, `GITLAB_BASE_URL`, and apply-only subprocess inputs are not GA configuration
surfaces because their workflows are excluded. `ATTACKIQ_LIVE_SMOKE` belongs to the operator smoke
harness rather than the installed CLI; it must equal `1` before the harness contacts a tenant.

## Exit Behavior Inventory

| Exit | Proposed stable meaning |
| --- | --- |
| `0` | Help, version, validation without errors, successful read/local action, or successful dry-run plan. Warnings alone do not make `config validate` fail. |
| `1` | Handled configuration, network, provider, parsing-after-invocation, output, or local workflow failure. |
| `2` | Typer/Click command usage or option validation failure. Experimental parity mismatch also uses 2 when `--fail-on-mismatch` is enabled, but that behavior is outside the stable contract. |

The live-smoke harness additionally returns `124` for a subprocess timeout. Signal-derived and
unexpected interpreter exits are not portable CLI contract values.

## Machine-Readable Output Inventory

- Common JSON writers emit UTF-8 JSON with two-space indentation, sorted object keys, and a final
  newline. List commands emit arrays; detail commands emit objects. Provider-owned object fields
  remain extensible.
- Common CSV writers emit a header when fields exist, preserve repository-defined preferred field
  order, append other fields in sorted order, render null as empty text, JSON-encode nested values,
  and escape embedded newlines as `\\n`.
- Dedicated assessment/test dry-runs emit an object with `operation_id`, `path_params`,
  `query_params`, and optional `json_body`. The GA roster requires an operation ID and forbids
  `--apply`.
- Build commands emit only the validated JSON request body; `--print-call` guidance is written to
  stderr so stdout/file JSON remains parseable.
- `attackiq call --output-format` supports `pretty-json`, `raw`, and `csv`. CSV requires a JSON
  array of objects. Generic call dry-run rendering is human-oriented and must not be treated as the
  dedicated mutation call-plan envelope.
- Wrapper `--output-format` values are `json` or `csv`, except `tags search`, which also supports
  `table`. CSV output rules that require a file remain part of command validation.
- Export commands support `csv` and `json`, selected explicitly or inferred from the output suffix;
  an unknown suffix defaults to CSV.
- Backup, join, catalog, Scenario Wizard, and TUI exports own additional documented artifact
  schemas. Their filenames, manifests, redaction, and retention boundaries require dedicated
  fixtures before they can be frozen as stable output contracts.

## Contract-Test Backlog

Gate 2's contract-test backlog is complete. Tasks 1-8 were completed on 2026-07-21; the Python 3.13
qualification that completed task 8 is Gate 3 evidence and does not change the current release:

1. Completed: `tests/fixtures/cli_command_tree.json` is generated from Typer/Click metadata and
   freezes every command path, positional argument, option name, alias, boolean pair,
   required/default value, and help-visible value constraint. CI runs
   `python3 scripts/render_cli_contract.py --check`; after reviewing an intentional public CLI
   change, regenerate the fixture with `python3 scripts/render_cli_contract.py`.
2. Completed: `tests/fixtures/ga_cli_inventory.json` explicitly classifies each documented command,
   option token, and experimental option value. `scripts/check_ga_cli_inventory.py` rejects
   documentation/CLI metadata drift, stale classifications, unclassified new surfaces, and any
   attempt to classify apply or experimental platform behavior as proposed-stable. The check runs
   in local and GitHub quality gates.
3. Completed: `tests/test_ga_config_contract.py` freezes the seven persisted keys, exact defaults,
   strict value types, unknown-key behavior, string and URL normalization, finite inclusive timeout
   bounds, secret masking, POSIX permission hardening with best-effort fallback, and precedence for
   the three environment variables that override persisted values. CLI timeout validation coverage
   is retained in `tests/test_cli_config_commands.py`; the three persisted-field overrides are also
   covered by the completed environment contract suite.
4. Completed: `tests/test_ga_environment_contract.py` freezes the exact documented and installed
   package `ATTACKIQ_*` inventory, valid and invalid value behavior, defaults, CLI-over-environment
   precedence, and local path/cache resolution. It also proves that the live-smoke opt-in,
   GitLab apply credentials, and Scenario Wizard subprocess-only output variable remain outside the
   GA table and ambient subprocess environment. Non-finite TUI cache TTLs now fail closed to the
   documented disabled-expiry behavior.
5. Completed: `tests/test_ga_exit_contract.py` freezes successful local and warning-only validation
   exits, handled malformed-configuration failure, Typer/Click usage failure, the experimental
   parity-mismatch exit, and the live-smoke timeout exit with token and tenant-URL redaction. It
   also parses this inventory to keep stable exits exactly 0, 1, and 2 while leaving experimental
   parity and live-smoke behavior outside the installed stable contract.
6. Completed: `tests/fixtures/ga_machine_output_contract.json` and
   `tests/test_ga_machine_output_contract.py` freeze common JSON and CSV serialization, dedicated
   dry-run call plans, build payloads, generic call formats, export field orders, backup manifests,
   join artifacts, catalog results, Scenario Wizard plans, and TUI exports using offline synthetic
   data. Repository-owned envelopes and headers are exact while raw provider records may add fields.
7. Completed: the GA scope guard imports the live-smoke roster and freezes its command count,
   categories, page bounds, fake UUIDs, and no-`--apply` invariant. The harness also fails closed
   before launching commands unless the effective base URL uses HTTPS and persisted configuration
   enables TLS verification. Warning-only `config validate` behavior remains unchanged for normal
   CLI use.
8. Completed: GitHub Actions runs the contract suite and full quality-gate-equivalent checks on
   Python 3.10 through 3.13, with an exact matrix contract test preventing supported-runtime drift.
   The fresh constrained CPython 3.13.12 quality gate and both dependency audits passed as Gate 3
   evidence recorded in `docs/STATE.md`.

No task above may enable apply mode, add tenant calls, record raw tenant evidence, or consume AIQ
Assist MCP.
