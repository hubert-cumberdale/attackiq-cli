# TUI Runtime, State, and Cache Flow

Implementation-aligned contract for `attackiq tui` runtime option resolution, tab workflows, and in-session caching behavior.

## Command surface
Command: `attackiq tui`

| Option | Required | Default | Allowed |
| --- | --- | --- | --- |
| `--page-size` | no | `20` | `-` |
| `--order-by` | no | `last_updated` | `-` |
| `--search` | no | `null` | `-` |
| `--tag` | no | `null` | `-` |
| `--filter-debounce` | no | `0.4` | `-` |
| `--timeout` | no | `null` | `-` |
| `--auth-scheme` | no | `auto` | `auto, account-token, jwt, none` |
| `--insecure` | no | `False` | `-` |

## Invariants and guardrails
- `run_tui` resolves timeout and TLS mode from CLI flags first, then config defaults.
- Workflow tabs are read-only and use shared service abstractions, not direct endpoint logic in widgets.
- Cache entries are bounded (`ATTACKIQ_TUI_CACHE_MAX`) and optionally TTL-pruned (`ATTACKIQ_TUI_CACHE_TTL`).
- Status diagnostics refresh on explicit status refresh actions and tab activation transitions.
- The Scenarios, Assessments, and Tests tabs expose contextual local `new-assessment`, `assessment-from-template`, `assessment-defaults`, `assessment-run`, `new-test`, `test-scenarios`, and `test-status` call-plan previews with `No request sent` status; the TUI does not expose apply-mode execution.

## Artifacts and outputs
- Runtime diagnostics shown in Status and Settings tabs (auth/base-url/spec/cache/runtime sources).
- Export files under `<workspace>/exports/` from workflow tabs (`e`/`c` shortcuts).
- In-memory cache statistics surfaced via command palette cache commands.
- In-memory new-assessment, assessment-from-template, assessment-default targets, assessment-run, new-test, test-scenario assignment, and test-status request previews; preview export and persistence are not available.

## Code references
- `src/attackiq_cli/tui.py` -> `run_tui`
- `src/attackiq_cli/tui_provider.py` -> `TuiDataProvider`
- `src/attackiq_cli/tui_provider_state.py` -> `build_tui_state`
- `src/attackiq_cli/tui_app.py` -> `AttackIQTuiApp`
- `src/attackiq_cli/tui_preview.py` -> `AssessmentDefaultsPreviewScreen`
- `src/attackiq_cli/tui_preview.py` -> `AssessmentFromTemplatePreviewScreen`
- `src/attackiq_cli/tui_preview.py` -> `AssessmentRunPreviewScreen`
- `src/attackiq_cli/tui_preview.py` -> `NewTestPreviewScreen`
- `src/attackiq_cli/tui_preview.py` -> `NewAssessmentPreviewScreen`
- `src/attackiq_cli/tui_preview.py` -> `TestScenariosPreviewScreen`
- `src/attackiq_cli/tui_preview.py` -> `TestStatusPreviewScreen`
- `src/attackiq_cli/tui_mutation_preview.py` -> `build_tui_mutation_preview`
- `src/attackiq_cli/tui_widgets.py` -> `StatusTab`
- `src/attackiq_cli/tui_scenarios.py` -> `ScenariosTab`
- `src/attackiq_cli/tui_results.py` -> `ResultsTab`
- `src/attackiq_cli/tui_assessments.py` -> `AssessmentsTab`
- `src/attackiq_cli/tui_tests.py` -> `WorkflowTestsTab`
- `src/attackiq_cli/tui_assets.py` -> `WorkflowAssetsTab`
- `src/attackiq_cli/tui_settings.py` -> `WorkflowSettingsTab`

## Tests
- `tests/test_cli_tui.py`
- `tests/test_tui_app.py`
- `tests/test_tui_assessments.py`
- `tests/test_tui_assets.py`
- `tests/test_tui_layout.py`
- `tests/test_tui_provider_cache.py`
- `tests/test_tui_provider_state.py`
- `tests/test_tui_preview.py`
- `tests/test_tui_mutation_preview.py`
- `tests/test_tui_results.py`
- `tests/test_tui_results_provider.py`
- `tests/test_tui_scenarios.py`
- `tests/test_tui_settings.py`
- `tests/test_tui_tests.py`
- `tests/test_tui_widgets.py`

## CLI help validation targets
- `attackiq tui --help`
  - options: `--page-size`, `--order-by`, `--search`, `--tag`, `--filter-debounce`, `--timeout`, `--auth-scheme`, `--insecure`
