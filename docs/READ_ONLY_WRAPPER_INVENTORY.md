# Read-Only Wrapper Inventory

This inventory tracks candidate first-class wrappers from existing TUI/export usage and common
operator workflows. Each selected family must stay read-only, use service-boundary tests first, and
avoid raw configuration or secret-bearing fields by default.

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
| Results | `attackiq results list|phases|logs` | TUI results modes and troubleshooting. |
| Validation results | `attackiq validation-results list|by-asset|asset-executions|scenario-executions` | Validation follow-up workflows. |

## Candidate Families

| Candidate | Operator value | Write-risk | Current source | Decision |
| --- | --- | --- | --- | --- |
| Source types | Correlates integration connector IDs to source-type mappings used by backup and alert/detection configuration review. | Low: `GET /v1/source_types` with required `company` and `connector` query parameters. | `backup configs` already fetches source types through `v1_source_types_list`. | Selected as first family. |
| Detection rule candidates | Helps inspect alert/detection-rule candidates currently captured only through redacted backup. | Medium: payload may require redaction and endpoint naming is mitigation-oriented. | `backup configs` uses `v1_unified_mitigations_with_relations_list`. | Defer until summary/redaction shape is reviewed. |
| Connector setup detail | Useful for integration troubleshooting. | Medium: connector setup payloads may expose configuration fields. | Integration and backup workflows. | Defer until safe field projection is specified. |
| Result artifacts | Completes the TUI logs/artifacts mental model. | Medium: artifacts may contain tenant data and larger binary/text payloads. | Results TUI tab placeholder and result troubleshooting. | Defer until retention/output guidance exists. |
| Assessment schedules | Common operator question for recurring assessments. | Medium: schedule endpoints may sit near write/update flows. | Assessment runbooks and defaults workflows. | Defer until endpoint classification is complete. |

## Selected Slice

The first wrapper family is source types:

- Command: `attackiq source-types list`.
- Operation: `v1_source_types_list`.
- Required inputs: `--company-id` and `--connector-id`.
- Optional filters: `--object-fingerprint`, `--unassigned-for`, `--page`, and `--page-size`.
- Output: JSON or CSV summary records. The summary shape includes source-type, connector,
  vendor-product, company, user, ignore, fingerprint, sync timestamp, created, and modified fields.
- Out of scope: no source-type writes, no connector configuration output, no automatic connector
  discovery, and no backup artifact generation.

## Validation

Focused validation for this slice:

```bash
.venv/bin/ruff check src/attackiq_cli/services_source_types.py src/attackiq_cli/services.py src/attackiq_cli/cli.py tests/test_services_source_types.py tests/test_cli_source_types.py
.venv/bin/python -m mypy src/attackiq_cli/services_source_types.py src/attackiq_cli/services.py src/attackiq_cli/cli.py tests/test_services_source_types.py tests/test_cli_source_types.py --cache-dir /tmp/aiq-cli-mypy-source-types
.venv/bin/pytest tests/test_services_source_types.py tests/test_cli_source_types.py
python3 scripts/check_doc_links.py
```
