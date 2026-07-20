# Read-Only Wrapper Inventory

This inventory tracks candidate first-class wrappers from existing TUI/export usage and common
operator workflows. Each selected family must stay read-only, use service-boundary tests first, and
avoid raw configuration or secret-bearing fields by default.

The fresh 2026-07-17 selection gate in
[Read-only wrapper selection review](READ_ONLY_WRAPPER_2026-07-17_SELECTION_REVIEW.md) selects no
new family. Issue #60 remains in watch mode until a named operator workflow meets the documented
projection, fixture, redaction, retention, and service-boundary criteria.

## Existing Coverage

| Family | Current wrapper surface | Source workflow |
| --- | --- | --- |
| Tags | `attackiq tags list|show|search` | Operator filters, scenario/template tagging, exports. |
| Scenarios | `attackiq scenarios list|show` | TUI scenarios tab and scenario exports. |
| Assessments | `attackiq assessments list|show` | TUI assessments tab and assessment exports. |
| Tests | `attackiq tests list|show` | TUI tests tab and test exports. |
| Templates | `attackiq templates list|show|tests` | Template exports and assessment planning. |
| Assets | `attackiq assets list|show` | TUI assets tab and asset scoping. |
| Asset groups | `attackiq asset-groups list|show` | Assessment filters and production smoke checks. |
| Blueprints | `attackiq blueprints list` | Assessment creation prerequisites. |
| Integrations | `attackiq integrations list` | Configuration inventory with summary-only output. |
| Source types | `attackiq source-types list` | Integration connector source-type mapping review. |
| Assessment schedules | `attackiq assessment-schedules list` | Recurring assessment schedule review. |
| EDR scan schedules | `attackiq edr-scan-schedules list` | Endpoint-data scan cadence review. |
| Results | `attackiq results list|phases|logs` | TUI results modes and troubleshooting. |
| Validation results | `attackiq validation-results list|by-asset|asset-executions|scenario-executions` | Validation follow-up workflows. |

## Candidate Families

| Candidate | Operator value | Write-risk | Current source | Decision |
| --- | --- | --- | --- | --- |
| Source types | Correlates integration connector IDs to source-type mappings used by backup and alert/detection configuration review. | Low: `GET /v1/source_types` with required `company` and `connector` query parameters. | `backup configs` already fetches source types through `v1_source_types_list`. | Implemented in #75 as the first family. |
| Detection rule candidates | Helps inspect alert/detection-rule candidates currently captured only through redacted backup. | Medium: payload may require redaction and endpoint naming is mitigation-oriented. | `backup configs` uses `v1_unified_mitigations_with_relations_list`. | Reviewed in [Detection Rule Wrapper Review](DETECTION_RULE_WRAPPER_REVIEW.md); keep backup-only until a safe summary projection and wrapper boundary are specified. |
| Connector setup detail | Useful for integration troubleshooting. | Medium: connector setup payloads may expose configuration fields. | Integration and backup workflows. | Defer until safe field projection is specified. |
| Result artifacts | Completes the TUI logs/artifacts mental model. | Medium: artifacts may contain tenant data and larger binary/text payloads. | Results TUI tab placeholder and result troubleshooting. | Defer until retention/output guidance exists. |
| Assessment schedules | Common operator question for recurring assessments. | Low for `GET /v1/assessments/schedule_list`; medium for adjacent schedule CRUD and public schedule mutation endpoints. | Assessment runbooks and defaults workflows. | Implemented as project schedule list summaries only. |
| EDR scan schedules | Helps review endpoint-data scan cadence without changing schedules. | Medium: list payloads include `target_asset_ids`, and adjacent create/update/delete/retrieve/runs operations exist. | OpenAPI `v1_emm_edr_scan_schedules_list`. | Implemented as summary-only list output after [Read-only wrapper redaction and retention review](READ_ONLY_WRAPPER_REDACTION_RETENTION_REVIEW.md). |

## Current Selection Status

No fourth wrapper family is selected. Detection-rule candidates, connector setup detail, result
artifacts, EDR schedule detail/runs, and other schedule endpoints remain deferred under the
2026-07-17 selection review. Revisit exactly one candidate only when a concrete workflow supplies
the safe field projection and retention/redaction evidence required by that review.

## Completed Slice

The first wrapper family was source types:

- Command: `attackiq source-types list`.
- Operation: `v1_source_types_list`.
- Required inputs: `--company-id` and `--connector-id`.
- Optional filters: `--object-fingerprint`, `--unassigned-for`, `--page`, and `--page-size`.
- Output: JSON or CSV summary records. The summary shape includes source-type, connector,
  vendor-product, company, user, ignore, fingerprint, sync timestamp, created, and modified fields.
- Out of scope: no source-type writes, no connector configuration output, no automatic connector
  discovery, and no backup artifact generation.

## Implemented Assessment Schedule Slice

The second wrapper family was assessment project schedules:

- Command: `attackiq assessment-schedules list`.
- Accepted operation: `get_project_schedule_list`, `GET /v1/assessments/schedule_list`.
- Endpoint classification: read-only list, no request body, no write-like method, and no schedule
  mutation semantics. The endpoint is unpaginated in the bundled schema, so implementation tests
  validate response-shape handling without adding client-side mutation or fetch loops.
- Output: JSON or CSV summary records. The summary shape should include project ID, project name,
  project template name, schedule version, crontab minute, hour, day of week, day of month, month,
  timezone, and a derived schedule-present flag.
- Out of scope: `v1_public_assessment_set_schedule_create`, EDR scan schedule create/update/delete,
  EDR schedule run history, raw `target_asset_ids`, schedule enable/disable behavior, default
  schedule changes, and any apply-mode workflow.

## Implemented EDR Scan Schedule Slice

The third wrapper family was EDR scan schedules:

- Command: `attackiq edr-scan-schedules list`.
- Accepted operation: `v1_emm_edr_scan_schedules_list`, `GET /v1/emm/edr_scan_schedules`.
- Endpoint classification: read-only list with adjacent create, update, delete, retrieve, and runs
  history operations in the same family.
- Output: JSON or CSV summary records that omit raw `target_asset_ids` and may include only derived
  target-scope fields such as `targeted` or `target_asset_count`.
- Out of scope: EDR scan schedule retrieve, runs history, create, update, partial update, delete,
  raw target asset IDs, schedule enable/disable behavior, and any apply-mode workflow.

## Validation

Focused validation for the completed source-types slice:

```bash
.venv/bin/ruff check src/attackiq_cli/services_source_types.py src/attackiq_cli/services.py src/attackiq_cli/cli.py tests/test_services_source_types.py tests/test_cli_source_types.py
.venv/bin/python -m mypy src/attackiq_cli/services_source_types.py src/attackiq_cli/services.py src/attackiq_cli/cli.py tests/test_services_source_types.py tests/test_cli_source_types.py --cache-dir /tmp/aiq-cli-mypy-source-types
.venv/bin/pytest tests/test_services_source_types.py tests/test_cli_source_types.py
python3 scripts/check_doc_links.py
```

Focused validation for the assessment-schedules implementation includes service response-shape tests
before CLI option forwarding tests, then the repository documentation gates.

```bash
.venv/bin/python -m pytest tests/test_services_assessment_schedules.py tests/test_cli_assessment_schedules.py
.venv/bin/ruff check src/attackiq_cli/services_assessment_schedules.py src/attackiq_cli/services.py src/attackiq_cli/cli.py tests/test_services_assessment_schedules.py tests/test_cli_assessment_schedules.py
.venv/bin/python -m mypy src/attackiq_cli/services_assessment_schedules.py src/attackiq_cli/services.py src/attackiq_cli/cli.py tests/test_services_assessment_schedules.py tests/test_cli_assessment_schedules.py --cache-dir /tmp/aiq-cli-mypy-assessment-schedules
python3 scripts/check_doc_links.py
```

The EDR scan schedule selection review is documentation-only and should be validated with:

```bash
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
.venv/bin/python -m mkdocs build
```

Focused validation for the EDR scan schedule implementation includes service response-shape tests
before CLI option forwarding tests, then the repository documentation gates.

```bash
.venv/bin/python -m pytest tests/test_services_edr_scan_schedules.py tests/test_cli_edr_scan_schedules.py
.venv/bin/ruff check src/attackiq_cli/services_edr_scan_schedules.py src/attackiq_cli/services.py src/attackiq_cli/cli_edr_scan_schedules.py src/attackiq_cli/cli.py tests/test_services_edr_scan_schedules.py tests/test_cli_edr_scan_schedules.py
.venv/bin/python -m mypy src/attackiq_cli/services_edr_scan_schedules.py src/attackiq_cli/services.py src/attackiq_cli/cli_edr_scan_schedules.py src/attackiq_cli/cli.py tests/test_services_edr_scan_schedules.py tests/test_cli_edr_scan_schedules.py --cache-dir /tmp/aiq-cli-mypy-edr-scan-schedules
python3 scripts/check_doc_links.py
```
