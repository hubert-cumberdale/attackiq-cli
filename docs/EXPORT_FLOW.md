# Export and Pagination Flow

Implementation-aligned contract for export commands and list pagination semantics across scenarios, tags, and export pipelines.

## Command surface
Command: `attackiq export [assessments|scenarios|templates|tests]`

- None
Subcommands:
- `assessments`: `--output`, `--format`, `--page-size`, `--max-pages`, `--asset-group-id`, `--blueprint-id`, `--execution-strategy`, `--has-default-schedule`, `--name`, `--report-instance-type`, `--search`, `--use-scenario-alert-rules`, `--version`, `--zones-ordering`, `--insecure`, `--timeout`
- `scenarios`: `--output`, `--format`, `--page-size`, `--insecure`, `--timeout`
- `templates`: `--output`, `--format`, `--page-size`, `--include-empty`, `--scenario-details`, `--scenario-details-lenient`, `--scenario-details-retries`, `--scenario-concurrency`, `--insecure`, `--timeout`
- `tests`: `--output`, `--format`, `--page-size`, `--insecure`, `--timeout`

## Invariants and guardrails
- `paginate_results(...)` uses `page` as a starting page and advances until no `next` or no results.
- `export templates|scenarios|tests --page-size` requires `>= 1`.
- `export templates --scenario-concurrency` requires `>= 1`.
- `tags list --page N` and `scenarios list --page N` fetch one explicit page; without `--page`, they auto-paginate.

## Artifacts and outputs
- Deterministic JSON output (sorted keys, pretty indentation).
- CSV files for normalized records with stable field ordering per workflow.
- Template scenario-detail enrichment artifacts in CSV/JSON output payloads.

## Code references
- `src/attackiq_cli/cli.py` -> `export_templates`
- `src/attackiq_cli/cli.py` -> `export_scenarios`
- `src/attackiq_cli/cli.py` -> `export_assessments`
- `src/attackiq_cli/cli.py` -> `export_tests`
- `src/attackiq_cli/cli.py` -> `list_scenarios`
- `src/attackiq_cli/cli.py` -> `list_tags`
- `src/attackiq_cli/cli.py` -> `search_tags`
- `src/attackiq_cli/client.py` -> `paginate_results`
- `src/attackiq_cli/exporter.py` -> `resolve_format`
- `src/attackiq_cli/exporter.py` -> `write_json`
- `src/attackiq_cli/exporter.py` -> `write_csv_records`
- `src/attackiq_cli/exporter.py` -> `build_scenario_export_records`
- `src/attackiq_cli/services.py` -> `build_assessment_summary_records`
- `src/attackiq_cli/services.py` -> `build_test_summary_records`

## Tests
- `tests/test_cli_export_templates.py`
- `tests/test_cli_export_scenarios.py`
- `tests/test_cli_export_assessments.py`
- `tests/test_cli_export_tests.py`
- `tests/test_cli_scenarios.py`
- `tests/test_cli_tags.py`
- `tests/test_exporter.py`

## CLI help validation targets
- `attackiq export --help`
  - options: `assessments`, `scenarios`, `templates`, `tests`
- `attackiq export templates --help`
  - options: `--output`, `--format`, `--page-size`, `--include-empty`, `--scenario-details`, `--scenario-details-lenient`, `--scenario-details-retries`, `--scenario-concurrency`, `--insecure`, `--timeout`
- `attackiq export assessments --help`
  - options: `--output`, `--format`, `--page-size`, `--max-pages`, `--asset-group-id`, `--blueprint-id`, `--execution-strategy`, `--has-default-schedule`, `--name`, `--report-instance-type`, `--search`, `--use-scenario-alert-rules`, `--version`, `--zones-ordering`, `--insecure`, `--timeout`
