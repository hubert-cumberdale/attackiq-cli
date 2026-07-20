# Read-Only Wrapper Selection Review

Date: 2026-07-17

This review records the fresh issue #60 redaction and output-retention gate requested by the
2026-07-08 project direction review. It evaluates exactly the deferred candidates left after
summary-only source types, assessment schedules, and EDR scan schedules were implemented.

## Decision

Do not select another read-only wrapper family now. Keep issue #60 open in watch mode until a
named operator workflow justifies one candidate and supplies the safe summary projection,
retention boundary, and fixture-backed redaction evidence described below.

This is an explicit deferral, not approval to implement the least-risk remaining endpoint. Broad
first-class coverage already exists, and no current repository evidence identifies an unmet
workflow whose value outweighs the remaining retention or redaction risk.

## Evidence Reviewed

- `docs/READ_ONLY_WRAPPER_INVENTORY.md` and the prior selection review.
- `docs/DETECTION_RULE_WRAPPER_REVIEW.md`.
- Bundled OpenAPI operation families inspected through `attackiq spec search` and
  `src/attackiq_cli/openapi.yaml`.
- Existing summary-only integrations, results, assessment-schedule, and EDR-schedule wrappers.
- Issue #60, confirmed open on 2026-07-17 with no next wrapper selected after the EDR schedule
  implementation.

No live tenant responses, private endpoint captures, connector configurations, result artifacts,
or generated backup data were used.

## Candidate Decisions

| Candidate | Current value and coverage | Decision |
| --- | --- | --- |
| Detection rule candidates | Redacted backup already captures recovery-planning evidence. The read-only relation endpoint can include rule content plus recent project and detection-result context, and the same family has import and adjacent base mutation operations. | Defer until command naming, a field-level summary projection, and fixtures prove that content, notes, related details, URLs, and connector configuration cannot reach output. |
| Connector setup detail | `attackiq integrations list` already provides configuration-safe connector inventory. Setup detail can contain tenant URLs, headers, credentials, and configuration containers. | Defer until a specific troubleshooting workflow identifies the minimum fields and fixture-backed redaction tests cover configuration-shaped payloads. |
| Result artifacts | Existing results, phases, and logs commands cover routine result navigation. Artifact schemas include payload, URL, decryption-key, MIME, hash, and encryption fields. | Defer until an artifact-specific retention policy, output-location contract, size limits, and redaction tests exist. Do not add a raw artifact output mode. |
| EDR schedule detail and runs | `attackiq edr-scan-schedules list` already provides bounded cadence and target-count summaries. Detail includes recent runs and the operation family also contains create, update, partial-update, and delete endpoints. | Defer until a named operational workflow needs run history and defines a bounded, identifier-safe summary that excludes raw target asset IDs. |
| Other schedule endpoints | Assessment and EDR schedule list summaries cover the approved inventory workflows; remaining nearby endpoints are duplicate detail or write-like schedule behavior. | Do not select under the read-only wrapper track. Any future schedule detail requires its own projection review; writes require a separate dry-run/apply design. |

## Re-Entry Criteria

A future #60 selection gate must provide all of the following for exactly one candidate:

1. A named operator workflow that existing commands and redacted backup artifacts do not satisfy.
2. Exact read-only operation IDs and negative scope for adjacent create, update, delete, import,
   apply, retrieve-detail, or history operations.
3. A field-by-field default JSON/CSV summary projection with raw response output excluded.
4. Sanitized fixtures covering sensitive, malformed, and empty response shapes.
5. Redaction and retention rules for identifiers, URLs, configuration containers, payloads,
   decryption material, and output files as applicable.
6. Service-boundary tests planned before CLI option-forwarding and rendering tests.

Until those inputs exist, the correct implementation scope is zero new wrapper code.

## Validation

This decision is documentation-only and changes no CLI, service, network, or output behavior.
Validate it with:

```bash
python3 scripts/check_public_safety.py --skip-wheel
python3 scripts/check_secret_scan.py
python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
.venv/bin/python -m mkdocs build
git diff --check
```
