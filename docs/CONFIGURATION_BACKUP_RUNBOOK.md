# Configuration Backup Runbook

Use this workflow to capture redacted tenant/customer configuration for incident recovery planning.
It is a backup capture workflow only; it does not restore, apply, or mutate configuration.

## Preflight

Run the checks from a release checkout or validated development checkout:

```bash
attackiq --version
attackiq config validate
attackiq spec list --limit 3 --fields operation_id,method,path
```

Create a clean output directory outside git with restrictive permissions:

```bash
BACKUP_DIR="/tmp/aiq-config-backup-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$BACKUP_DIR"
```

Do not use a repo-tracked directory. Do not collect or retain browser cookies, bearer tokens, HAR
files, raw screenshots with tenant data, or raw API response bodies.

## Command

Default safe coverage is `integrations,source-types,detection-rules`:

```bash
attackiq backup configs \
  --output-dir "$BACKUP_DIR" \
  --tenant-alias <operator-safe-alias> \
  --page-size 200 \
  --max-pages 5
```

Use `--include DOMAIN[,DOMAIN...]` to narrow coverage. Use `--company-id <uuid>` only when source
types cannot derive the company ID from the integration connector records.

The command writes only redacted JSON artifacts plus `manifest.json`. There is no raw-response
option.

## Manifest Requirements

Every backup manifest records:

- command path
- UTC timestamp
- CLI version
- tenant alias
- operation/source for each artifact
- record counts
- redaction status and redacted field counts
- skipped domains and reasons

Retain raw backup directories only for the approved evidence window. Commit only aggregate,
redacted summaries.

## Current Safe Coverage

- `integrations`: fetched through `v1_company_connectors_list`, aligned with
  `attackiq integrations list`; first-class backup artifacts redact connector configuration
  containers and secret-like fields before writing.
- `source-types`: fetched through `v1_source_types_list`; company and connector IDs are derived
  from integrations, or company ID may be supplied with `--company-id`.
- `detection-rules`: fetched through the read-only
  `v1_unified_mitigations_with_relations_list` endpoint as detection/alert-rule candidates.
  Fields remain subject to review, so backup redaction stays enabled.

## Excluded For Now

- MSSP SSO and global-property endpoints, because the current workflow is not MSSP/customer mode.
- Raw integration connector configuration through `attackiq call`; generic call output does not
  redact before writing.
- Restore, apply, or other configuration-changing flows.
- Browser cookies, bearer tokens, raw HAR files, raw response bodies, or tenant-data screenshots.

## Endpoint Discovery Intake

For domains missing from the bundled OpenAPI schema, record sanitized endpoint metadata only:

- method
- relative path
- required parameters
- request and response field names
- pagination behavior
- suspected secret fields

Classify each endpoint as one of `backup-safe`, `needs-redaction`, `write-like`, or `unsupported`.
Only `GET` endpoints classified as `backup-safe` or `needs-redaction` can be used by
`attackiq backup configs`, and `needs-redaction` entries must declare `sensitive_fields`.

Never commit cookies, bearer tokens, raw HAR files, screenshots with tenant data, or raw response
bodies. Treat discovered endpoints like the existing scenario-upload precedent: documented,
reviewed, fixture-backed, and explicitly opted in before a first-class wrapper is added.

Catalog reference files:

- Schema: [CONFIGURATION_BACKUP_ENDPOINT_CATALOG.schema.json](CONFIGURATION_BACKUP_ENDPOINT_CATALOG.schema.json)
- Sanitized example:
  [CONFIGURATION_BACKUP_ENDPOINT_CATALOG.example.json](CONFIGURATION_BACKUP_ENDPOINT_CATALOG.example.json)
