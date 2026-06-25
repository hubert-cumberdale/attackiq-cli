# Backup Domain Intake: Observable Field Mappings

Intake date: 2026-06-02

## Decision

Select `observable-field-mappings` as the next configuration-backup domain candidate for fixture
and redaction review.

Do not add it to default backup coverage or operator examples yet. The current default remains
`integrations,source-types,detection-rules`.

## Sanitized Endpoint Metadata

The candidate is represented by the sanitized example entry in
`docs/CONFIGURATION_BACKUP_ENDPOINT_CATALOG.example.json`.

| Field | Value |
| --- | --- |
| Domain | `observable-field-mappings` |
| Method | `GET` |
| Relative path | `/v1/observable_field_mappings` |
| Classification | `needs-redaction` |
| Pagination | `page` |
| Response kind | `paginated-list` |
| Required parameters | none |
| Default query parameters | `include_inactive=false` |
| Sensitive fields declared | `api_token`, `client_secret`, `configuration` |

This endpoint is an endpoint-catalog candidate, not a first-class bundled backup helper. Operators
must not infer that it is enabled by default.

## Classification Rationale

Use `needs-redaction`, not `backup-safe`.

Observable field mappings may include configuration containers, integration-derived metadata,
mapping rules, or credential-like values depending on tenant setup. The backup path must assume
secret-bearing fields can appear until fixture-backed tests prove the redaction policy handles the
payload shape.

The endpoint remains eligible for backup review because it is a `GET` endpoint, uses a relative
path, and has page-based list pagination in the sanitized catalog entry.

## Required Follow-Up Before Enablement

Before enabling this domain in docs, CLI defaults, or bundled examples beyond the sanitized catalog
entry, add:

- compact synthetic fixtures for successful page responses: complete
- compact synthetic fixtures with declared sensitive fields: complete
- redaction tests proving `api_token`, `client_secret`, and `configuration` are redacted: complete
- fail-closed tests for unclassified sensitive-looking fields in this domain: complete
- manifest assertions for domain name, source, operation ID or endpoint-catalog path, record count,
  classification, and redacted-field counts: complete
- retention guidance that keeps generated artifacts outside git and records only aggregate
  summaries in public docs: complete

The fixture-backed tests exercise the endpoint-catalog path through `run_configuration_backup`
without adding the domain to default coverage.

## Retention And Manifest Guidance

If this candidate is enabled in a future PR, its generated artifact should remain
`observable-field-mappings.json` and its manifest entry should keep:

- `domain`: `observable-field-mappings`
- `source`: `endpoint-catalog` until a first-class bundled helper is approved
- `operation_id`: `endpoint-catalog:/v1/observable_field_mappings`
- `classification`: `needs-redaction`
- `record_count`: the redacted record count written to the artifact
- `redaction_status`, `redacted_field_count`, and `redacted_paths`: copied from the artifact
  writer summary

Generated backup directories for this candidate must stay outside git, use the existing backup
output permission model, and be retained only for the approved evidence window. Public docs may
record aggregate status such as command success, record count, redaction status, and skipped
domains. Do not commit the artifact JSON, raw response bodies, local output paths, tenant aliases,
operator names, or field values from a real tenant.

Do not expand the production operator runbook examples for this candidate until a future PR enables
the domain and includes the final fixture, manifest, and retention validation evidence.

## Out Of Scope

- Adding `observable-field-mappings` to `DEFAULT_CONFIG_BACKUP_DOMAINS`.
- Adding a first-class CLI wrapper for observable field mappings.
- Restore, apply, or mutation behavior.
- Raw response output.
- Capturing tenant names, credentials, screenshots, HAR files, browser cookies, or local evidence
  directories in repository docs.

## Validation Commands

Use these commands for the follow-up implementation PR:

```bash
.venv/bin/python -m pytest tests/test_backup.py tests/test_cli_backup.py tests/test_backup_artifacts.py tests/test_backup_fetchers.py
python3 scripts/check_public_safety.py --skip-wheel
python3 scripts/check_secret_scan.py
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
git diff --check
```
