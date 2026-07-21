# Project Direction Review
Date: 2026-07-08
Scope: current `master` direction, implementation state, release/test posture, milestone
issues, and practical next work selection.

This is a documentation-only planning artifact. It does not change code behavior, generate
artifacts, prepare a release, tag a release, close issues, or approve tenant-facing workflow
changes. Follow-up notes dated 2026-07-16 record implementation work that was selected from this
review and should be validated with focused code and documentation gates.

## Executive Summary

The project direction is sound: the CLI has moved from a monolithic command module toward focused
command-family modules, mature read-only wrappers, redacted backup capture, release evidence
automation, and explicit AIQ Assist MCP/TUI guardrails. The current production-ready release
remains `v0.1.26`; current `master` includes the cumulative architecture and TUI handoff merged by
PR #133 without preparing a new release.

The next work should not be another broad expansion. The identified large-module decomposition is
complete, its 800-line boundary is enforced locally and in CI, and issue #55 is complete. Issue
#59 is also closed after all seven approved TUI previews passed their read-only acceptance gates.
The highest-value direction is to keep wrapper expansion behind a redaction/output-retention
selection gate, keep AIQ Assist MCP blocked until provider ownership is documented, and preserve
the completed preview no-apply boundary.

## Review Inputs

Local repository snapshot captured on 2026-07-08:

| Input | Result |
| --- | --- |
| Branch | `master` |
| Current commit | `5b330b20e704ed4bea13658af087c4551447c0ee` |
| Release position | `v0.1.26-2-g5b330b2` |
| Worktree before this docs pass | Clean by `git status -sb` and `git status --porcelain=v1` |
| CLI version | `attackiq-cli version 0.1.26` |
| Open issues | #55, #59, #60, and #61 only |
| Test collection | 603 tests collected with `.venv/bin/python -m pytest --collect-only -q` |

Commands used for evidence gathering:

- `git status -sb`
- `git log --oneline -20`
- `gh issue list --state open --limit 100`
- `gh issue view 55`
- `gh issue view 59`
- `gh issue view 60`
- `gh issue view 61`
- `gh pr list --state merged --limit 20`
- `.venv/bin/attackiq --help`
- `.venv/bin/attackiq call --help`
- `.venv/bin/attackiq join --help`
- `.venv/bin/attackiq tui --help`
- `.venv/bin/attackiq export assessments --help`
- `.venv/bin/attackiq backup configs --help`
- `wc -l src/attackiq_cli/*.py src/attackiq_cli/joiner/*.py`
- `python3 scripts/deterministic_review.py --stdout`
- `.venv/bin/python -m pytest --collect-only -q`

Initial review evidence found that the deterministic review script reported `Worktree: dirty` even
when `git status --short` was empty because its helper converted empty command output to
`unknown`. The trusted worktree source for this review remains the direct `git status` evidence
above. Follow-up on 2026-07-16 fixed the script to distinguish clean, dirty, and unknown worktree
states.

Recent merged PRs from GitHub:

| PR | Title | Merged |
| --- | --- | --- |
| #132 | Document optional observable field mappings backup | 2026-07-03 |
| #131 | Align CLI architecture docs | 2026-06-23 |
| #130 | Split CLI command modules | 2026-06-23 |
| #129 | Extract scenario wizard CLI commands | 2026-06-05 |
| #128 | Extract backup CLI commands | 2026-06-05 |
| #127 | Extract build CLI commands | 2026-06-05 |
| #126 | Extract platform API CLI commands | 2026-06-04 |
| #125 | Extract catalog CLI commands | 2026-06-04 |
| #124 | Extract spec CLI commands | 2026-06-04 |
| #123 | Extract validation results CLI module | 2026-06-03 |
| #122 | Extract results CLI module | 2026-06-03 |
| #121 | Extract templates CLI module | 2026-06-03 |
| #120 | Extract tags CLI module | 2026-06-03 |
| #119 | Extract assets CLI module | 2026-06-03 |
| #118 | Extract asset groups CLI module | 2026-06-03 |
| #117 | Extract integrations CLI module | 2026-06-03 |
| #116 | Add EDR scan schedules wrapper | 2026-06-02 |
| #115 | Select next wrapper risk review | 2026-06-02 |
| #114 | Extract blueprints CLI module | 2026-06-02 |
| #113 | Extract source types CLI module | 2026-06-02 |

Milestone issue status (refreshed 2026-07-18):

| Issue | Status from live GitHub state | Direction |
| --- | --- | --- |
| #55 | Completed architecture-decomposition epic with all identified oversized modules below the enforced 800-line boundary. | Keep the local and CI check enabled; open a focused issue for any future ownership-driven extraction. |
| #59 | Closed as completed by PR #133 on 2026-07-18. | Preserve the seven approved read-only previews; require a new reviewed scope for any expansion. |
| #60 | Open read-only wrapper expansion epic. | Keep open; select the next family only after a fresh risk gate. |
| #61 | Open supply-chain provenance and release-evidence epic. | Keep open only as a policy/watch epic, not an active release blocker. |

## Current Status By Track

### Release Stewardship

`v0.1.26` remains the current production-ready release. `docs/STATE.md` records source tag,
public mirror, tag-time CI, enterprise package, SBOM, dependency-integrity, provenance,
Artifactory-promotion, signing-attestation, combined evidence verification, and no-Artifactory
install evidence. Current `master` has later documentation commits, so the next tag still needs
normal release-prep evidence and CI confirmation.

Near-term direction: maintain the release evidence standard, but do not prepare or publish a new
release from this review.

### Architecture

Command-family extraction is substantially complete. `src/attackiq_cli/cli.py` is now top-level app
wiring, global option handling, command registration, and compatibility imports while focused
`cli_*.py` modules own command-family parsing and orchestration.

At the time of the initial review, the remaining architecture risk was concentrated in these
large modules:

| Module | Lines |
| --- | ---: |
| `src/attackiq_cli/tui.py` | 5084 |
| `src/attackiq_cli/scenario_wizard.py` | 1531 |
| `src/attackiq_cli/joiner/det_pipeline.py` | 907 |
| `src/attackiq_cli/tui_provider.py` | 853 |

The initial direction was to keep #55 open and pick one narrow no-behavior-change extraction at a
time, starting with a TUI boundary because `tui.py` was the largest concentration of UI state,
rendering, actions, and defensive exception handling.
Follow-up on 2026-07-16 split TUI task lifecycle and blocking executor handoff helpers into
`src/attackiq_cli/tui_tasks.py`, pure structured-filter parsing and sort resolution into
`src/attackiq_cli/tui_filters.py`, pure record text builders into
`src/attackiq_cli/tui_record_text.py`, and pure result grouping plus list sort/filter helpers into
`src/attackiq_cli/tui_record_lists.py`, then pure shortcut/palette/error display helpers into
`src/attackiq_cli/tui_display.py`, and shared widgets/status tab into
`src/attackiq_cli/tui_widgets.py`, followed by the shared Textual stylesheet into
`src/attackiq_cli/tui_styles.py`, and shared TUI export path/file-writing helpers into
`src/attackiq_cli/tui_exports.py`, and Settings tab record/detail builders into
`src/attackiq_cli/tui_settings.py`. Follow-up on 2026-07-17 moved the Settings tab state,
rendering, filtering, and export actions into `src/attackiq_cli/tui_settings.py`, reducing
`src/attackiq_cli/tui.py` from 5084 to 3077 lines without changing TUI behavior. A subsequent
2026-07-17 slice moved the Scenarios tab state, async loading, rendering, filtering, paging,
detail, exports, and view-state restoration into `src/attackiq_cli/tui_scenarios.py`, reducing
`src/attackiq_cli/tui.py` to 2653 lines without changing TUI behavior. The next 2026-07-17 slice
moved the Assessments tab state, async loading, rendering, filtering, paging, detail, exports, and
view-state restoration into `src/attackiq_cli/tui_assessments.py`, reducing
`src/attackiq_cli/tui.py` to 2267 lines without changing TUI behavior. The subsequent 2026-07-17
slice moved the Tests tab state, async loading, rendering, filtering, paging, detail, exports, and
view-state restoration into `src/attackiq_cli/tui_tests.py`, reducing `src/attackiq_cli/tui.py` to
1884 lines without changing TUI behavior. The next 2026-07-17 slice moved the Assets tab state,
async loading, rendering, filtering, paging, detail, exports, and view-state restoration into
`src/attackiq_cli/tui_assets.py`, reducing `src/attackiq_cli/tui.py` to 1492 lines without changing
TUI behavior. The next 2026-07-17 slice moved the Results tab models, state, async loading,
view-mode grouping, rendering, filtering, paging, detail, exports, and view-state restoration into
`src/attackiq_cli/tui_results.py`, reducing `src/attackiq_cli/tui.py` to 900 lines without changing
TUI behavior. The final 2026-07-17 slice moved the Textual app shell, tab orchestration,
command-palette dispatch, cache/status actions, paging/export routing, help, and focus controls into
`src/attackiq_cli/tui_app.py`, reducing `src/attackiq_cli/tui.py` to a 402-line compatibility facade
and launcher without changing TUI behavior. A subsequent 2026-07-17 slice moved the TUI runtime
state model and pure auth, base URL, spec cache, environment-label, and workspace-display
derivation into `src/attackiq_cli/tui_provider_state.py`, reducing
`src/attackiq_cli/tui_provider.py` from 853 to 758 lines while preserving service calls, cache
behavior, workspace resolution, and compatibility imports. The next 2026-07-17 slice moved
Scenario Wizard create dry-run planning, isolated apply execution, temporary configuration
transport, runtime dependency setup, and generated-file result collection into
`src/attackiq_cli/scenario_wizard_create.py`, reducing `src/attackiq_cli/scenario_wizard.py` from
1531 to 1240 lines while preserving CLI behavior, subprocess injection, environment isolation,
redaction, and compatibility imports. The subsequent 2026-07-17 slice moved cache resolution,
wrapper ZIP inspection with sensitive-file suppression, runtime-bundle validation summaries,
bundle-copy dry-run planning, and bundle-copy apply behavior into
`src/attackiq_cli/scenario_wizard_runtime.py`, reducing `src/attackiq_cli/scenario_wizard.py` to
1019 lines while preserving validation, CLI behavior, and compatibility imports. The final
2026-07-17 Scenario Wizard slice moved image-tar runtime inspection, bounded layer spooling, Docker
whiteout/index handling, selected-file materialization, safe path normalization, sensitive-file
exclusion, and requirements credential filtering into
`src/attackiq_cli/scenario_wizard_image.py`, reducing `src/attackiq_cli/scenario_wizard.py` to a
305-line orchestration and compatibility facade while preserving image prepare behavior and
security controls.

### Read-Only Wrappers

Read-only wrapper coverage is broad: tags, scenarios, assessments, tests, templates, assets, asset
groups, blueprints, integrations, source types, assessment schedules, EDR scan schedules, results,
and validation results all have first-class surfaces. Recent wrapper work added assessment schedule
and summary-only EDR scan schedule coverage with explicit no-write boundaries.

Follow-up status: the fresh 2026-07-17 redaction/output-retention gate selected no new family and
placed #60 in watch mode. Detection-rule candidates, connector setup detail, result artifacts, EDR
detail/runs, and other schedule endpoints remain deferred until one named operator workflow defines
the bounded summary projection, sanitized fixtures, retention/redaction rules, and service boundary.

### Configuration Backup Maturity

`attackiq backup configs` is redacted, read-only, and backed by endpoint-catalog validation.
Default coverage remains `integrations,source-types,detection-rules`. Observable field mappings are
documented as an optional endpoint-catalog backup domain with `needs-redaction` classification,
explicit opt-in, and no default-domain enablement.

Near-term direction: backup maturity is in maintenance mode. Future domains should be endpoint
catalog slices with sanitized intake notes, fixtures, redaction tests, and no restore/apply path.

### AIQ Assist MCP

AIQ Assist MCP remains a planning contract, not a user-facing integration. The repo-local consumer
contract, provider-source status file, adapter design, fixture gate, and contract gate are present,
but provider source status remains `pending_provider_source`. No CLI/TUI MCP command should be
added until a named provider owner supplies the canonical provider contract source.

Near-term direction: keep maturing only the contract and fixtures unless provider ownership changes.
Do not implement adapter consumption from synthetic fixtures, raw transcripts, browser captures, or
local assumptions.

Follow-up on 2026-07-18 hardened the provider-source transition: documented status alone no longer
stops the consumer-code scan. The guard requires explicit boolean consumption approval and adapter
mock-test evidence, and keeps source markers blocked until both are true. The repo remains in
`pending_provider_source` with consumption and live checks disabled.

The subsequent fixture-gate hardening rejects synthetic outcome drift by cross-checking request
method/ID, redaction expectation, response status, JSON-RPC result/error polarity, timeout absence
of a response, and intentionally malformed envelopes. This strengthens only repo-local offline
evidence and does not infer the pending provider contract.

The next fixture-redaction hardening closes partial-placeholder and deceptive-hostname bypasses.
Sensitive fields now accept only exact redaction placeholders; URL checks parse and exactly
allowlist synthetic example hosts, reject embedded credentials, and continue rejecting raw
transcript keys. Provider status and all consumption/live/network behavior remain unchanged.

The subsequent fixture-inventory hardening closes the directory around the nine expected JSON
case files. Unexpected artifacts, subdirectories, symbolic links, invalid fixture roots, and
filename/case drift now fail the offline gate rather than sitting outside its validated set. This
does not change provider status or authorize adapter, CLI/TUI, live-check, or network behavior.

The next request-envelope hardening requires each synthetic request to carry only exact redacted
authorization and JSON content-type headers. Header names are case-insensitive; omissions,
duplicate normalized names, non-JSON content types, and cookie/session-style sources fail the
offline gate. This remains non-canonical fixture evidence and does not change provider status.

The 2026-07-19 request-parameter hardening binds synthetic params to the declared method: discovery
uses an empty object, while tool calls require exactly a non-empty synthetic name and arguments
object. No provider tool name or argument schema is asserted, and provider/runtime status remains
unchanged.

The subsequent success-result hardening requires non-empty synthetic `tools` and `content` lists
for discovery and tool calls. List item schemas remain deliberately unconstrained until provider
documentation exists, so the gate strengthens offline consistency without inferring wire details.

The next failure-envelope hardening requires non-boolean integer error codes and non-empty messages
for synthetic auth/provider failures. Code values and their relationship to HTTP statuses remain
unconstrained until provider documentation exists, preserving the non-canonical fixture boundary.

The subsequent fixture-schema hardening closes repo-owned fixture, expectation, request,
response-transport, and timeout wrappers to undeclared fields. Provider response bodies, result
data, and provider error extensions remain unconstrained, so the gate does not infer provider
schema from synthetic evidence.

The next status-range hardening bounds stored synthetic HTTP statuses to 100 through 599 and
provider-error outcomes to 400 through 599. Unassigned in-range values remain allowed, and JSON-RPC
error codes remain independent, so the gate does not pin provider-specific transport behavior.

The subsequent fixture-URL hardening detects hierarchical scheme URLs and permits only valid HTTPS
on exact synthetic example hosts. Other schemes, invalid ports, credentials, and non-example hosts
fail the offline gate without defining provider response fields or adding live behavior.

The next fixture-retention hardening limits each committed synthetic fixture to 16 KiB and rejects
oversized files before JSON parsing. The budget prevents fixture storage from drifting toward raw
transcripts or responses without constraining provider response schemas.

The subsequent fixture-decoding hardening rejects duplicate JSON object names at every nesting
level before contract validation. This keeps synthetic evidence deterministic across JSON parsers
without closing provider-owned response fields or adding adapter, network, CLI, or TUI behavior.

The next fixture-number hardening rejects `NaN`, `Infinity`, and `-Infinity` before contract
validation, including inside provider-owned extension data. This keeps committed fixtures within
interoperable JSON syntax without constraining finite values or provider response schemas.

The subsequent fixture-key hardening classifies sensitive and raw-transcript fields from literal
JSON object names rather than dot-separated diagnostic paths. Dotted provider-extension keys can no
longer bypass redaction or retention checks, while provider response schemas remain open.

The next fixture-placeholder hardening removes the `oauth` and `token` sensitive-value exemption.
Those auth-mode markers remain valid in the dedicated `auth_mode` field but cannot substitute for
exact redaction placeholders in provider extensions. Provider/runtime status remains unchanged.

The subsequent fixture numeric-overflow hardening routes JSON floating-point decoding through a
finite-value check. Exponent forms such as `1e999` and `-1e999` can no longer decode as infinity and
bypass the fixture contract. Representable finite values, provider schemas, and runtime status
remain unchanged.

### TUI Dry-Run Previews

The TUI is still read-only. The design document, shared mutation plan helpers, redacted preview
adapter, and all seven approved contextual modals exist: new-assessment,
assessment-from-template, assessment-default targets, assessment-run, new-test, test-scenario
assignment, and test-status. Current tests prove the preview paths do not expose `--apply`, client
construction, apply callbacks, mutation execution, or write-like command IDs.

Near-term direction: issue #59 is closed as completed after PR #133 merged all seven approved
previews and their help/status language. Any additional operation requires a new scope review and
must reuse the shared plan and adapter boundaries with the same read-only tests.

### Supply-Chain Evidence

The post-#75 supply-chain checklist is complete: SBOM generation, dependency-integrity records,
secret scanning, dependency constraints, release-prep evidence, post-download package acceptance,
external signing/attestation field groups, Artifactory-promotion evidence, and combined enterprise
evidence verification are documented and tested.

Near-term direction: #61 can stay open as a policy-change and future-provenance epic. It should not
block routine wrapper, architecture, backup, or documentation slices unless release evidence policy
actually changes.

## Test And Release Posture

The current test inventory is broad enough to support targeted slices: pytest collected 603 tests,
while the deterministic review counted 524 `def test_` functions before parametrization expansion.
High-coverage areas include Scenario Wizard CLI behavior, mutation planning, enterprise package and
evidence verification, TUI provider cache behavior, generic `attackiq call` validation, services,
backup redaction, and TUI layout/results behavior.

Current release evidence for `v0.1.26` already includes the full local quality gate, tag-time CI on
Python 3.10 through 3.12, public safety, secret scan, public mirror, AIQ Assist MCP gates, Ruff,
mypy, pytest, doc links, MkDocs, dependency audit, and enterprise evidence verification. Current
`master` is not itself a release candidate; any future tag still needs fresh release-prep evidence.

For the initial docs-only review, targeted docs and safety gates were sufficient. The 2026-07-16
follow-up touched code, scripts, and tests, so it requires focused pytest and lint validation in
addition to documentation checks.

## Findings

### 1. High - Architecture risk moved from CLI wiring to large workflow modules

At the time of the initial review, the command-family split had moved the line-count risk into
`tui.py`, `scenario_wizard.py`, `joiner/det_pipeline.py`, and `tui_provider.py`. The size of
`tui.py` made unrelated TUI changes hard to review and regression-test.

Recommended slice: choose one #55 child that extracts a TUI state/action/rendering boundary without
changing behavior, help, keybindings, or network paths.

Follow-up status: eighteen small TUI boundaries were completed on 2026-07-16 and 2026-07-17 by
extracting task
cancellation/replacement/debounce scheduling helpers, blocking executor handoff helpers, pure
structured-filter parsing/sort resolution helpers, pure record text builders, pure result
grouping/list sort/filter helpers, pure shortcut/palette/error display helpers, shared
widgets/status tab, the shared Textual stylesheet, and shared export path/file-writing helpers.
Settings tab record/detail builders and the Settings tab state/action/rendering class were also
split out, followed by the complete Scenarios tab state/action/rendering boundary. Additional TUI
state/action/rendering work then moved the complete Assessments and Tests tab boundaries.
Additional TUI state/action/rendering work then moved the complete Assets tab boundary. Further
TUI state/action/rendering work then moved the complete Results tab boundary, leaving the main
module responsible for the app shell. The app shell was then split into `tui_app.py`, leaving
`tui.py` as the compatibility facade and launcher. Runtime state derivation was then split from
`tui_provider.py`, bringing that provider below the architecture threshold. Scenario Wizard
create planning/execution was subsequently split into `scenario_wizard_create.py`, followed by
wrapper ZIP and bundle-source runtime preparation in `scenario_wizard_runtime.py`, leaving
image-tar inspection/materialization. That final engine moved into `scenario_wizard_image.py`,
bringing Scenario Wizard below the architecture threshold. The final identified oversized-module
slice moved GitLab retry/client handling and the apply-gated GitLab/AttackIQ mutation executors
from `joiner/det_pipeline.py` into `joiner/det_pipeline_apply.py`, reducing the pipeline module
from 907 to 789 lines. The 2026-07-18 closeout added a fail-closed architecture mode to
`scripts/deterministic_review.py`, wired it into the local quality gate and GitHub Actions, and
proved the 800/801-line boundary with focused tests. Issue #55 is complete; future extraction
requires a new ownership-driven scope rather than keeping the decomposition epic open.

### 2. High - TUI preview work was guarded before the user-facing UX was implemented

The TUI preview design and adapter guardrails are in place, and tests prove the current adapter has
no apply path. That is not the same as completed preview UX. Treating #59 as only help/status work
would skip the actual form/control layer and its tests.

Recommended slice: implement one read-only preview UX for a single approved CLI dry-run operation,
with adapter tests first, TUI command-palette/context tests second, and help/status wording last.

Follow-up status: completed on 2026-07-17 for `assessments run`. The contextual Assessments-tab
modal validates or prefills the assessment UUID, reuses the shared CLI plan builder and redacted
adapter, renders `No request sent`, and has no client, apply, service-mutation, export, or
persistence path. A second contextual slice completed the same boundary for `tests get-status`:
the Tests-tab-only modal validates or prefills the test UUID and renders its GET call plan without
client construction, service calls, export, or persistence. A third contextual slice completed the
boundary for `tests create`: the Assessments-tab-only modal validates or prefills the selected
assessment UUID, requires a test name, and renders the bounded request body without client
construction, service calls, export, or persistence. A fourth contextual slice completed the
boundary for `tests add-scenarios`: the Tests-tab-only modal validates or prefills the selected test
UUID, validates and stably deduplicates comma-separated scenario UUIDs, and renders the bounded
request body without client construction, service calls, export, or persistence. A fifth contextual
slice completed the boundary for `assessments update-defaults`: the Assessments-tab-only modal
validates or prefills the assessment UUID, accepts optional asset and asset-group UUID lists while
requiring at least one target type, and renders the bounded request body without client
construction, service calls, export, or persistence. A sixth contextual slice completed the
boundary for `assessments create`: the Scenarios-tab-only modal validates or prefills a scenario
UUID, validates and stably deduplicates comma-separated scenario UUIDs, requires an assessment
name, and renders the bounded request body without client construction, service calls, export, or
persistence. A seventh contextual slice completed the boundary for
`assessments create-from-template`: the Assessments-tab-only modal requires a validated template
UUID and assessment name, accepts an optional validated blueprint UUID, and renders the bounded
request body without client construction, service calls, export, or persistence. This completes
every operation in the approved preview design scope.

### 3. Medium - Wrapper expansion needs another selection gate before implementation

The wrapper inventory is mature, but the remaining candidates have higher retention or redaction
risk than source types, assessment schedules, and EDR scan schedule summaries. Starting a wrapper
without a new gate would blur the default-output safety standard.

Recommended slice: run a docs-first #60 selection review for exactly one candidate, or explicitly
defer all candidates until a concrete operator workflow justifies the risk.

Follow-up status: completed on 2026-07-17 by explicitly deferring all remaining candidates. The
review found no concrete unmet operator workflow that justified the residual retention/redaction
risk and documented exact re-entry criteria for a future single-candidate gate.

### 4. Medium - AIQ Assist MCP should remain blocked on provider-source ownership

The contract and fixture path is useful, but the provider wire contract is still not owned by a
named provider team in the repository evidence. Implementing a consumer now would encode local
assumptions as integration behavior.

Recommended slice: update provider-source status only when the provider owner, source reference,
contract version, and CLI/TUI consumption gate are documented. Otherwise keep the current blocked
state.

### 5. Low - Supply-chain evidence is mature enough to move from active epic to watch mode

#61's post-#75 follow-up checklist is complete for the current release standard. Keeping the issue
open is reasonable for future lock, signing, trust-root, or release-channel policy changes, but it
should not create default work for every planning cycle.

Recommended slice: no implementation now. Reopen active work only for a concrete policy change,
runtime-lock prototype, release-channel change, or enterprise evidence requirement.

### 6. Low - Deterministic review status reporting should distinguish clean from unknown

`scripts/deterministic_review.py` converted empty `git status --short` output to `unknown`, which
then rendered as dirty. The direct git evidence for this review was clean, but the automation
signal was confusing.

Follow-up status: fixed on 2026-07-16 with focused tests for clean, dirty, and command-failure
status handling.

## Future Work Roadmap

Recommended next slices, in order:

1. Keep the completed #55 architecture check enabled and open focused ownership-driven work only
   when a concrete boundary needs to change.
2. Keep #60 in watch mode until a named workflow satisfies the 2026-07-17 re-entry criteria.
3. Preserve the completed #59 no-apply boundary after PR #133; require a new review and issue for
   any scope expansion.
4. Keep AIQ Assist MCP in contract/fixture mode until provider-source ownership is documented.
5. Keep #61 open for policy changes, but do not schedule supply-chain implementation by default.

Out of scope for this planning artifact:

- release prep, release tagging, package generation, or public mirror publication
- issue closure
- code behavior changes
- raw tenant data, raw API responses, browser captures, MCP transcripts, or generated backup output
- TUI apply mode or write-capable preview controls
- new read-only wrapper implementation without a fresh selection and redaction gate

## Validation Results

The initial docs-only patch that added this review passed:

| Check | Result |
| --- | --- |
| `python3 scripts/check_public_safety.py --skip-wheel` | Pass |
| `python3 scripts/check_secret_scan.py` | Pass |
| `python3 scripts/check_doc_links.py` | Pass |
| `python3 scripts/render_deep_dives.py --check` | Pass |
| `python3 scripts/verify_deep_dives.py` | Pass |
| `.venv/bin/python -m mkdocs build` | Pass |
| `git diff --check` | Pass |

The 2026-07-16 follow-up implementation passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_tui_settings.py tests/test_tui_exports.py tests/test_tui_styles.py tests/test_tui_widgets.py tests/test_tui_display.py tests/test_tui_record_lists.py tests/test_tui_record_text.py tests/test_tui_filters.py tests/test_tui_tasks.py tests/test_review_automation_scripts.py tests/test_tui_layout.py::test_tui_structured_filters_accept_schema_drift_keys tests/test_tui_layout.py::test_tui_assessment_query_params_use_schema_backed_filters tests/test_tui_layout.py::test_tui_assessment_query_params_validate_typed_filters tests/test_tui_layout.py::test_scenario_detail_builders_parameters_and_relationships tests/test_tui_layout.py::test_format_runtime_error_connect_error tests/test_tui_layout.py::test_tui_command_palette_group_hint_and_alias_search tests/test_tui_layout.py::test_status_refresh_updates_runtime_diagnostics tests/test_tui_layout.py::test_tui_header_env_and_workspace_display tests/test_tui_layout.py::test_tui_banner_bar_hidden_by_default tests/test_tui_layout.py::test_settings_tab_key_actions tests/test_tui_layout.py::test_settings_tab_includes_cache_entry_diagnostics tests/test_tui_layout.py::test_settings_tab_export_palette_command tests/test_tui_results.py::test_parse_results_filter_supports_aliases tests/test_tui_results.py::test_resolve_results_source_filter_supports_aliases tests/test_tui_results.py::test_results_tab_banner_available` | Pass |
| `.venv/bin/python -m ruff check src/attackiq_cli/tui.py src/attackiq_cli/tui_settings.py src/attackiq_cli/tui_exports.py src/attackiq_cli/tui_styles.py src/attackiq_cli/tui_widgets.py src/attackiq_cli/tui_display.py src/attackiq_cli/tui_record_lists.py src/attackiq_cli/tui_record_text.py src/attackiq_cli/tui_filters.py src/attackiq_cli/tui_tasks.py scripts/deterministic_review.py tests/test_tui_settings.py tests/test_tui_exports.py tests/test_tui_styles.py tests/test_tui_widgets.py tests/test_tui_display.py tests/test_tui_record_lists.py tests/test_tui_record_text.py tests/test_tui_filters.py tests/test_tui_tasks.py tests/test_review_automation_scripts.py` | Pass |
| `python3 scripts/check_doc_links.py` | Pass |
| `.venv/bin/python -m mkdocs build` | Pass |
| `git diff --check` | Pass |

The 2026-07-17 Settings, Scenarios, Assessments, Tests, Assets, and Results tab
state/action/rendering extractions, app-shell extraction, and cumulative handoff passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 647 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_tui_app.py tests/test_tui_styles.py tests/test_tui_results.py tests/test_tui_assets.py tests/test_tui_tests.py tests/test_tui_assessments.py tests/test_tui_scenarios.py tests/test_tui_layout.py tests/test_tui_filters.py tests/test_tui_record_text.py tests/test_tui_record_lists.py` | Pass, 96 tests. |
| `.venv/bin/python -m pytest tests/test_deep_dive_contracts.py` | Pass, 3 tests. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `.venv/bin/attackiq --help` | Pass |
| `.venv/bin/attackiq tui --help` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-17 TUI provider runtime-state extraction passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 648 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_tui_provider_state.py tests/test_tui_provider_cache.py tests/test_tui_layout.py` | Pass, 78 tests. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-17 Scenario Wizard create-workflow extraction passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 649 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_scenario_wizard_create.py tests/test_cli_scenario_wizard.py tests/test_scenario_wizard_package.py tests/test_scenario_wizard_process.py` | Pass, 46 tests. |
| `.venv/bin/attackiq scenario-wizard --help` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-17 Scenario Wizard bundle-runtime extraction passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 650 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_scenario_wizard_runtime.py tests/test_scenario_wizard_create.py tests/test_cli_scenario_wizard.py tests/test_scenario_wizard_package.py tests/test_scenario_wizard_process.py` | Pass, 47 tests. |
| `.venv/bin/attackiq scenario-wizard runtime --help` | Pass |
| `git diff --check` | Pass |

The final 2026-07-17 Scenario Wizard image-engine extraction passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 651 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_scenario_wizard_image.py tests/test_scenario_wizard_runtime.py tests/test_scenario_wizard_create.py tests/test_cli_scenario_wizard.py tests/test_scenario_wizard_package.py tests/test_scenario_wizard_process.py` | Pass, 48 tests. |
| `.venv/bin/attackiq scenario-wizard runtime prepare --help` | Pass |
| `git diff --check` | Pass |

The final identified 2026-07-17 DET pipeline apply-executor extraction passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 659 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_joiner_det_pipeline_apply.py tests/test_joiner_det_pipeline.py tests/test_cli_joiner.py tests/test_joiner_join.py tests/test_joiner_outputs.py tests/test_joiner_parse_labels.py` | Pass, 21 tests. |
| `.venv/bin/attackiq join --help` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-17 docs-first #60 wrapper selection gate passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/check_public_safety.py --skip-wheel` | Pass |
| `.venv/bin/python scripts/check_secret_scan.py` | Pass |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass |
| `.venv/bin/python scripts/check_doc_links.py` | Pass |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `.venv/bin/python -m mkdocs build` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-17 first #59 TUI request-preview UX passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 666 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_mutation_plans.py tests/test_tui_mutation_preview.py tests/test_tui_preview.py tests/test_tui_domains.py tests/test_tui_app.py tests/test_tui_layout.py tests/test_tui_assessments.py tests/test_tui_styles.py tests/test_tui_widgets.py` | Pass, 88 tests. |
| `.venv/bin/attackiq tui --help` | Pass |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-17 second #59 TUI request-preview UX passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 671 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_mutations.py tests/test_cli_mutations.py tests/test_mutation_plans.py tests/test_tui_mutation_preview.py tests/test_tui_preview.py tests/test_tui_domains.py tests/test_tui_app.py tests/test_tui_layout.py tests/test_tui_assessments.py tests/test_tui_tests.py tests/test_tui_styles.py tests/test_tui_widgets.py` | Pass, 124 tests. |
| `.venv/bin/attackiq tui --help` | Pass |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-18 third #59 TUI request-preview UX passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 676 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_mutations.py tests/test_cli_mutations.py tests/test_mutation_plans.py tests/test_tui_mutation_preview.py tests/test_tui_preview.py tests/test_tui_domains.py tests/test_tui_app.py tests/test_tui_layout.py tests/test_tui_assessments.py tests/test_tui_tests.py tests/test_tui_styles.py tests/test_tui_widgets.py` | Pass, 129 tests. |
| `.venv/bin/attackiq tui --help` | Pass |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-18 fourth #59 TUI request-preview UX passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 683 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_mutations.py tests/test_cli_mutations.py tests/test_mutation_plans.py tests/test_tui_mutation_preview.py tests/test_tui_preview.py tests/test_tui_domains.py tests/test_tui_app.py tests/test_tui_layout.py tests/test_tui_assessments.py tests/test_tui_tests.py tests/test_tui_styles.py tests/test_tui_widgets.py` | Pass, 136 tests. |
| `.venv/bin/attackiq tui --help` | Pass |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-18 fifth #59 TUI request-preview UX passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 691 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_mutations.py tests/test_cli_mutations.py tests/test_mutation_plans.py tests/test_tui_mutation_preview.py tests/test_tui_preview.py tests/test_tui_domains.py tests/test_tui_app.py tests/test_tui_layout.py tests/test_tui_assessments.py tests/test_tui_tests.py tests/test_tui_styles.py tests/test_tui_widgets.py` | Pass, 144 tests. |
| `.venv/bin/attackiq tui --help` | Pass |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-18 sixth #59 TUI request-preview UX passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 696 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_mutations.py tests/test_cli_mutations.py tests/test_mutation_plans.py tests/test_tui_mutation_preview.py tests/test_tui_preview.py tests/test_tui_domains.py tests/test_tui_app.py tests/test_tui_layout.py tests/test_tui_assessments.py tests/test_tui_tests.py tests/test_tui_styles.py tests/test_tui_widgets.py` | Pass, 149 tests. |
| `.venv/bin/attackiq tui --help` | Pass |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-18 seventh #59 TUI request-preview UX passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 702 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_mutations.py tests/test_cli_mutations.py tests/test_mutation_plans.py tests/test_tui_mutation_preview.py tests/test_tui_preview.py tests/test_tui_domains.py tests/test_tui_app.py tests/test_tui_layout.py tests/test_tui_assessments.py tests/test_tui_tests.py tests/test_tui_styles.py tests/test_tui_widgets.py` | Pass, 155 tests. |
| `.venv/bin/attackiq tui --help` | Pass |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass |
| `git diff --check` | Pass |

The subsequent 2026-07-18 #59 closeout acceptance audit passed:

| Check | Result |
| --- | --- |
| Live issue #59 acceptance review | All seven approved previews are merged; the keyboard help overlay and Status tab explicitly preserve the read-only/no-request boundary. PR #133 closed the issue as completed. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including public-safety, secret-scan, public-mirror, Ruff, mypy, 702 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python -m pytest tests/test_tui_layout.py tests/test_tui_app.py tests/test_tui_widgets.py` | Pass, 65 tests. |
| `git diff --check` | Pass |
| PR #133 CI | Pass on Python 3.10, 3.11, and 3.12. |
| Post-merge CI run `29631047260` | Pass on Python 3.10, 3.11, and 3.12 for merge commit `8ecb6ba6ee05c4ed2563a35defad2e5bba04648b`. |

The subsequent 2026-07-18 #55 architecture-boundary closeout passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python scripts/deterministic_review.py --check-architecture` | Pass; no Python module under `src/` exceeds 800 lines. |
| `.venv/bin/python -m pytest tests/test_review_automation_scripts.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 11 tests, including the 800-line pass and 801-line failure cases. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including the new architecture check, public-safety, secret-scan, public-mirror, MCP, Ruff, mypy, 703 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-18 AIQ Assist MCP transition-guard hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_contract.py tests/test_aiq_assist_mcp_fixtures.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 19 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 707 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-18 AIQ Assist MCP fixture-outcome hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 26 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with all synthetic cases internally consistent. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 714 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-18 AIQ Assist MCP fixture-redaction hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 31 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with exact sensitive placeholders and parsed synthetic-host URL validation. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 719 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-18 AIQ Assist MCP fixture-inventory hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 36 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with a closed, filename-bound fixture inventory. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 724 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-18 AIQ Assist MCP request-envelope hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 42 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with minimal redacted request headers. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 730 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP request-parameter hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 47 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with method-specific synthetic request params. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 735 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP success-result hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 49 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with method-specific non-empty success result lists. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 737 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP failure-envelope hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 53 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with bounded synthetic auth/provider error details. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 741 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP fixture-schema hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 60 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with closed repo-owned fixture wrappers. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 748 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP status-range hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 63 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with bounded synthetic HTTP statuses. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 751 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP fixture-URL hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 65 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with HTTPS-only scheme-qualified fixture URLs. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 753 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP fixture-retention hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 66 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with a 16 KiB per-fixture retention limit. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 754 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP fixture-decoding hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 67 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with duplicate JSON object names rejected before contract validation. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 755 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP fixture-number hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 68 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with non-finite JSON numeric constants rejected before contract validation. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 756 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-19 AIQ Assist MCP fixture-key hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 70 tests. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with literal object-name redaction and retention classification. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 758 pytest tests, doc-link, and MkDocs checks. |
| `.venv/bin/python scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `.venv/bin/python scripts/render_deep_dives.py --check` | Pass. |
| `.venv/bin/python scripts/verify_deep_dives.py` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-20 AIQ Assist MCP fixture-placeholder hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 71 tests. |
| `.venv/bin/ruff check scripts/check_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_fixtures.py` | Pass. |
| `.venv/bin/python -m mypy scripts/check_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_fixtures.py --cache-dir /tmp/aiq-cli-mypy-doc-handoff` | Pass. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with auth-mode markers rejected as sensitive-field placeholders. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 759 pytest tests, doc-link, and MkDocs checks. |
| `python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass. |
| `python3 scripts/check_doc_links.py` | Pass. |
| `python3 scripts/render_deep_dives.py --check` | Pass. |
| `python3 scripts/verify_deep_dives.py` | Pass. |
| `.venv/bin/mkdocs build --strict` | Pass. |
| `git diff --check` | Pass. |

The subsequent 2026-07-20 AIQ Assist MCP fixture numeric-overflow hardening passed:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_contract.py tests/test_quality_gate.py tests/test_ci_quality_gate_parity.py -q` | Pass, 72 tests. |
| `.venv/bin/ruff check scripts/check_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_fixtures.py` | Pass. |
| `.venv/bin/python -m mypy scripts/check_aiq_assist_mcp_fixtures.py tests/test_aiq_assist_mcp_fixtures.py --cache-dir /tmp/aiq-cli-mypy-doc-handoff` | Pass. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py` | Pass with exponent-overflow floats rejected before contract validation. |
| `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py` | Pass with provider source still pending and consumption disabled. |
| `.venv/bin/python scripts/quality_gate.py` | Pass, including architecture/MCP gates, public-safety, secret-scan, public-mirror, Ruff, mypy, 760 pytest tests, doc-link, and MkDocs checks. |
| `python3 scripts/check_doc_links.py` | Pass. |
| `python3 scripts/render_deep_dives.py --check` | Pass. |
| `python3 scripts/verify_deep_dives.py` | Pass. |
| `.venv/bin/mkdocs build --strict` | Pass. |
| `git diff --check` | Pass. |
