# Detection Rule Wrapper Review

This review records the configuration-backup follow-up from issue #57: whether
detection/alert-rule candidates need a separate first-class read-only wrapper instead of remaining
available only through redacted backup capture.

## Current Surface

`attackiq backup configs` includes `detection-rules` in its default domains. The backup flow fetches
the records through `v1_unified_mitigations_with_relations_list`, writes
`detection-rules.json`, redacts secret-like values before writing, records the source operation in
`manifest.json`, and keeps raw responses in memory only.

The bundled schema describes `v1_unified_mitigations_with_relations_list` as a read-only endpoint
for unified mitigations with related projects and detection results. The same schema family also
contains nearby retrieve, related-detail, and vendor-import operations, while the base
`v1_unified_mitigations` family contains create, update, and delete operations.

## Decision

Do not add a separate `attackiq detection-rules ...` wrapper in the current release-readiness
sequence.

Detection-rule candidates should remain backup-only until the wrapper shape is explicitly designed.
The existing backup capture already gives operators a redacted evidence artifact for recovery
planning. A first-class wrapper would expose an inspectable operator surface, so it needs a narrower
summary projection, command naming, and redaction contract before it is safe to publish as routine
CLI output.

## Rationale

- The endpoint name is mitigation-oriented while operator language in docs is
  detection/alert-rule-oriented; wrapper naming should avoid creating a misleading domain boundary.
- List responses include related project and detection-result context, so default output could carry
  tenant-sensitive operational details even when the endpoint itself is read-only.
- The backup path already redacts secret-like values and stores artifacts outside the repository;
  ordinary wrapper output would be easier to pipe, save, or paste.
- Nearby import and base mutation endpoints make service boundaries important. Any wrapper should
  bind only to the read-only list/retrieve operations and tests should prove no write operation is
  reachable.

## Future Wrapper Criteria

A future read-only wrapper issue is reasonable once these conditions are met:

- Define the command surface, likely `attackiq detection-rules list` and optionally
  `attackiq detection-rules show <id>`, with no import, create, update, delete, or apply mode.
- Specify a default summary projection before implementation. Candidate fields should be limited to
  stable identifiers, names, integration/source metadata, severity/stage/status, active state,
  modified timestamps, and bounded counts for related projects or detection results.
- Keep rule content, notes, related project details, detection-result detail payloads, signed URLs,
  and connector configuration fields out of default text, JSON, and CSV summaries unless a later
  redaction review approves them.
- Reuse existing service, pagination, timeout, TLS, auth, JSON, and CSV output patterns.
- Add service-boundary tests first, including a test that the wrapper never calls
  `v1_unified_mitigations_create`, `v1_unified_mitigations_partial_update`,
  `v1_unified_mitigations_destroy`, or
  `v1_unified_mitigations_with_relations_import_vendor_rules_create`.
- Add CLI tests for page controls, filters, summary output, CSV output, and redaction behavior.

## Out Of Scope

- Restore or apply automation.
- Vendor-rule import.
- Raw detection-rule payload export.
- Connector secret/configuration output.
- TUI preview or mutation planning for detection-rule changes.

## Validation Commands

This decision record is documentation-only. Validate future wrapper implementation PRs with focused
service and CLI tests plus the standard docs checks. For this review, use:

```bash
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
python -m mkdocs build
python3 scripts/quality_gate.py --no-mkdocs
```
