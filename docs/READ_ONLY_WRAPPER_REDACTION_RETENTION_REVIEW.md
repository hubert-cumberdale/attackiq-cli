# Read-Only Wrapper Redaction And Retention Review

This review records the #60 follow-up gate for selecting another read-only wrapper family after the
`source-types` and `assessment-schedules` slices.

## Review Standard

First-class wrappers are easier to pipe, save, paste, and automate than configuration backup
artifacts. A wrapper can therefore be safe only when its default output is a bounded summary
projection. Raw response output, secret-bearing fields, signed URLs, binary payloads, connector
configuration containers, and tenant-specific operational details must stay out of default JSON and
CSV output unless a later review explicitly approves the field set.

Safe wrapper candidates must meet these conditions:

- Bind only to read-only `GET` operations.
- Omit raw response output modes.
- Use service-layer response-shape validation before CLI option forwarding tests.
- Prefer derived counts or booleans over raw identifiers for scoped tenant data.
- Keep output files under normal wrapper semantics; backup-style retention requirements belong to
  `attackiq backup configs`, not routine wrapper output.
- Add negative tests or explicit service boundaries when nearby create, update, delete, import, or
  apply-like operations exist in the same OpenAPI family.

## Candidate Classification

| Candidate | Classification | Decision |
| --- | --- | --- |
| Detection rule candidates | Medium/high retention risk. The list family includes raw rule `content`, notes, related project context, detection-result context, and nearby import/mutation operations. | Keep backup-only under `docs/DETECTION_RULE_WRAPPER_REVIEW.md` until a dedicated summary projection is approved. |
| Connector setup detail | Medium/high redaction risk. Connector setup payloads can carry configuration containers, credentials, URLs, headers, and tenant-specific connection metadata. | Defer until a safe projection is specified and fixture-backed redaction tests exist. |
| Result artifacts | High retention risk. Artifact schemas include URL, decryption key, payload, MIME type, hashes, and encryption fields. | Defer until there is a separate artifact retention policy, explicit output-location guidance, and redaction tests. |
| EDR scan schedule list | Medium risk but summary-safe. The read-only list operation exposes schedule metadata and `target_asset_ids`; adjacent operations include create, update, delete, retrieve, and runs history. | Select as the next wrapper candidate only for list summaries that omit raw `target_asset_ids` and exclude retrieve/runs behavior. |
| EDR scan schedule detail/runs | Medium/high retention risk. Detail includes `recent_runs`, and runs history can expose operational timing/state beyond schedule inventory. | Defer until a separate detail/runs projection and retention review exists. |
| Other schedule endpoints | Mixed. Public assessment schedule update is write-like and existing assessment schedule list coverage is already summary-only. | Keep write-like schedule endpoints out of wrapper expansion. |

## Selected Next Wrapper

Select `v1_emm_edr_scan_schedules_list` as the next read-only wrapper family for implementation.

Command surface:

- `attackiq edr-scan-schedules list`
- Filters: `--data-source`, `--enabled`, `--schedule-type`, `--targeted`, `--page`, and
  `--page-size`.
- Output: JSON or CSV summary records only.

Default summary fields should be limited to:

- `id`
- `name`
- `data_source_id`
- `data_source`
- `schedule_type`
- `fire_at`
- `time_of_day`
- `days_of_week`
- `day_of_week`
- `week_interval`
- `enabled`
- `last_fired_at`
- `created`
- `modified`
- derived `targeted` or `target_asset_count`, without raw `target_asset_ids`

Out of scope for the implementation slice:

- `v1_emm_edr_scan_schedules_retrieve`
- `v1_emm_edr_scan_schedules_runs_retrieve`
- `v1_emm_edr_scan_schedules_create`
- `v1_emm_edr_scan_schedules_update`
- `v1_emm_edr_scan_schedules_partial_update`
- `v1_emm_edr_scan_schedules_destroy`
- Raw `target_asset_ids`
- Any schedule enable/disable or apply-mode workflow

## Acceptance Criteria For Implementation

- Add a focused service module or focused service helpers for EDR scan schedule query parameters,
  summary records, pagination, and response-shape validation.
- Add service-boundary tests before CLI forwarding/output tests.
- Validate `enabled` and `targeted` as explicit booleans, and validate `schedule_type` against
  accepted values before loading configuration.
- Confirm tests bind only to `v1_emm_edr_scan_schedules_list` and never call adjacent write,
  retrieve, or runs-history operations.
- Add CLI tests for JSON output, CSV output requiring `--output`, malformed response errors, and
  summary projection that omits raw `target_asset_ids`.
- Update `README.md`, `docs/STATE.md`, the production runbook, roadmap, and this inventory after
  the command is implemented.

## Validation Commands

This review is documentation-only. Validate the review with:

```bash
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
.venv/bin/python -m mkdocs build
.venv/bin/python scripts/quality_gate.py --no-mkdocs
```
