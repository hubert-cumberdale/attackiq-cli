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

## Artifacts and outputs
- Runtime diagnostics shown in Status and Settings tabs (auth/base-url/spec/cache/runtime sources).
- Export files under `<workspace>/exports/` from workflow tabs (`e`/`c` shortcuts).
- In-memory cache statistics surfaced via command palette cache commands.

## Code references
- `src/attackiq_cli/tui.py` -> `run_tui`
- `src/attackiq_cli/tui.py` -> `TuiDataProvider`
- `src/attackiq_cli/tui.py` -> `AttackIQTuiApp`
- `src/attackiq_cli/tui.py` -> `StatusTab`
- `src/attackiq_cli/tui.py` -> `ScenariosTab`
- `src/attackiq_cli/tui.py` -> `ResultsTab`
- `src/attackiq_cli/tui.py` -> `AssessmentsTab`
- `src/attackiq_cli/tui.py` -> `WorkflowTestsTab`
- `src/attackiq_cli/tui.py` -> `WorkflowAssetsTab`
- `src/attackiq_cli/tui.py` -> `WorkflowSettingsTab`

## Tests
- `tests/test_cli_tui.py`
- `tests/test_tui_layout.py`
- `tests/test_tui_provider_cache.py`
- `tests/test_tui_results.py`
- `tests/test_tui_results_provider.py`

## CLI help validation targets
- `attackiq tui --help`
  - options: `--page-size`, `--order-by`, `--search`, `--tag`, `--filter-debounce`, `--timeout`, `--auth-scheme`, `--insecure`
