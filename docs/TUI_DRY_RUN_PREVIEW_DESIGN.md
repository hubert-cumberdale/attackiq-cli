# TUI Dry-Run Preview Design

Status: design and adapter guardrail for future `attackiq tui` preview work. The repository now has
shared mutation plan helpers and a read-only TUI preview adapter, but this document does not add TUI
mutation actions, add apply-mode execution, or change the current read-only TUI behavior.

## Current Surface

The TUI is read-only. It loads `ServiceContext`, displays list/detail workflow tabs through
`TuiDataProvider`, and exposes command-palette actions for tab switching, refresh, cache
diagnostics, paging, filter help, focus, and exports.

Approved CLI assessment and test mutation commands are dry-run by default. Their current dry-run
payload is call-plan JSON with:

- `operation_id`
- `path_params`
- `query_params`
- `json_body` when the request has a body

Apply-mode execution is separate from dry-run output. `run_mutation_command` writes the call plan
before preparing apply context, building an HTTP client, or invoking the apply request.

Shared call-plan construction lives in `src/attackiq_cli/mutation_plans.py`. The read-only TUI
preview adapter lives in `src/attackiq_cli/tui_mutation_preview.py` and renders in-memory plan
summaries with `No request sent` status.

## Preview Scope

The first TUI preview implementation should cover only approved assessment and test mutation plans
that already have CLI dry-run support:

- `assessments create`
- `assessments create-from-template`
- `assessments update-defaults`
- `assessments run`
- `tests create`
- `tests add-scenarios`
- `tests get-status`

The preview is a rendered call plan, not an execution path. It may help operators inspect the
request that a matching CLI dry-run would produce, but it must not send the request, persist tenant
payloads by default, or expose `--apply` from the TUI.

Out of initial scope:

- scenario upload previews
- Scenario Wizard local create/package previews
- DET pipeline previews
- backup restore or apply planning
- generic OpenAPI browser behavior
- detection-rule mutation planning
- any TUI action that sends POST/PATCH/PUT/DELETE requests

## Required Inputs

Each preview action must collect the same operation-specific inputs required by the matching CLI
dry-run command. Inputs may come from selected TUI rows only when the selected record contains the
required stable identifier. Otherwise the preview form must require explicit operator input.

Required input examples:

- `assessments create`: assessment name and one or more scenario IDs.
- `assessments create-from-template`: template ID, assessment name, and optional blueprint ID.
- `assessments update-defaults`: assessment ID plus one or more asset IDs or asset group IDs.
- `assessments run`: assessment ID.
- `tests create`: assessment ID and test name.
- `tests add-scenarios`: test ID and one or more scenario IDs.
- `tests get-status`: test ID.

Preview generation does not require auth validation or a live network call. It may use the loaded
spec index and synthetic operation builders, but it must not require a fresh provider refresh just
to compute a plan.

## Call-Plan Display Shape

The TUI should display a bounded, inspectable plan derived from the existing dry-run payload and
operation metadata:

| Field | Source | Display behavior |
| --- | --- | --- |
| Operation | `operation_id` | Always shown. |
| Method | `Operation.method` | Uppercase. |
| Path | `Operation.path` | Show path template, not tenant base URL. |
| Path params | call plan | Show key/value rows. |
| Query params | call plan | Show key/value rows; show empty when absent. |
| JSON body summary | call plan | Show redacted, pretty JSON with bounded depth/length. |
| Request status | preview adapter | Always show `No request sent`. |

The future adapter may return a richer in-memory display model, but the source of truth for request
shape should remain the same pure call-plan data used by CLI dry-runs. Do not change CLI dry-run
JSON solely to support TUI rendering.

## Redaction

Preview output must redact or omit:

- Authorization headers and auth mode secrets
- account tokens, JWTs, bearer tokens, passwords, cookies, and API keys
- tenant base URLs and private hostnames
- raw selected-row detail payloads beyond fields needed for the plan
- signed URLs or download URLs
- long free-text fields unless the specific preview requires them

The default display should prefer identifiers, counts, and explicit operator-entered values over
full source objects. JSON body display should use bounded formatting so large scenario, asset, or
asset-group lists cannot flood the terminal.

Preview exports are out of scope for the first implementation. If export is later added, it must be
opt-in, write outside repository paths by default, and use the same redaction policy.

## Read-Only Adapter Boundary

The read-only preview adapter is intentionally separate from future UI controls. The adapter:

- accept typed preview inputs, an operation reference, and pure call-plan data
- reuse `build_dry_run_call_plan` or a shared pure builder that produces the same payload shape
- resolve operation metadata from `ServiceContext.spec` or reviewed synthetic operation builders
- return an in-memory display model for the TUI
- reject unsupported operation IDs before rendering

The adapter must not:

- accept an `apply` flag
- accept `prepare_context` or `apply_request` callbacks
- call `build_client`
- instantiate `AttackIQClient`
- call service apply functions such as `create_test` or `run_assessment`
- add write-like command IDs to the default TUI command palette

Future TUI controls should consume the shared plan builders instead of copying command logic or
calling apply-mode service functions with `check_auth=False`.

## TUI UX Boundary

Preview controls should be explicit and contextual:

- show preview actions only on relevant assessment/test surfaces
- keep current list/detail/export/filter shortcuts unchanged
- label preview state as `No request sent`
- keep the existing read-only status language until the preview is implemented and tested
- keep apply-mode language out of TUI controls, help, and command-palette labels

The command palette may gain preview commands only after tests prove the commands are read-only.
Preview command IDs should remain distinct from apply terminology, for example
`preview:assessment-run` rather than `run` or `apply`.

## Cancellation And Error States

Preview generation should be cancellable before rendering if the operator closes the form or
switches context. Cancellation is local UI state only and must not require cleanup of network work.

Validation failures should report the missing or malformed input and should not build a partial
network request. Examples:

- missing assessment, test, scenario, asset, asset-group, template, or blueprint IDs
- malformed UUID values
- empty assessment or test names
- unsupported operation ID
- operation metadata missing from the bundled spec

Spec or synthetic-operation lookup failures should fail closed with a local error. They must not
fall back to generic `attackiq call` behavior.

## Test Strategy

Implementation PRs should add tests before exposing preview controls:

- pure adapter tests proving each supported preview returns expected call-plan fields
- redaction tests for token-like body values and private hostnames
- tests proving preview generation does not call `build_client` or apply-mode service functions
- TUI command-palette tests proving preview commands are unavailable until a supported tab/context
- TUI tests proving preview commands cannot reach `--apply` or mutation execution paths
- cancellation and invalid-input tests proving no network request is attempted

Current adapter coverage lives in:

- `tests/test_tui_layout.py`
- `tests/test_mutation_plans.py`
- `tests/test_tui_mutation_preview.py`

Focused validation for preview implementation:

```bash
.venv/bin/python -m pytest tests/test_mutations.py tests/test_cli_mutations.py tests/test_mutation_plans.py tests/test_tui_mutation_preview.py
.venv/bin/python -m pytest tests/test_cli_tui.py tests/test_tui_layout.py tests/test_tui_results.py tests/test_tui_provider_cache.py
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
```

## Acceptance Checklist

Future preview implementation is acceptable only when:

- supported preview scope and required inputs match approved CLI dry-run commands
- call-plan rendering shows operation, method, path, params, redacted body summary, and
  `No request sent`
- adapter tests prove no HTTP client or apply-mode service path is reachable
- TUI tests prove no apply command, apply flag, or write-like palette action is exposed
- help/status language still communicates the TUI read-only boundary clearly
