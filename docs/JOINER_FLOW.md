# Joiner and DET Pipeline Flow

Implementation-aligned contract for deterministic dataset joins and staged `det-pipeline` behavior, including apply-mode mutation boundaries.

## Command surface
Command: `attackiq join [datasets|det-pipeline]`

| Option | Required | Default | Allowed |
| --- | --- | --- | --- |
| `--assessments` | no | `null` | `-` |
| `--scenarios` | no | `null` | `-` |
| `--issues` | no | `null` | `-` |
| `--outdir` | no | `null` | `-` |
| `--project-id` | no | `null` | `-` |
| `--apply` | no | `False` | `-` |
| `--dry-run/--no-dry-run` | no | `--dry-run` | `-` |
| `--top-k` | no | `5` | `-` |
| `--top-n-per-issue` | no | `1` | `-` |
| `--force-tool-label` | no | `False` | `-` |
| `--allow-append-sections` | no | `False` | `-` |
| `--timestamp` | no | `null` | `-` |
| `--fail-on-missing-scenario/--no-fail-on-missing-scenario` | no | `--fail-on-missing-scenario` | `-` |
| `--fail-on-malformed-scenario-technique/--no-fail-on-malformed-scenario-technique` | no | `--fail-on-malformed-scenario-technique` | `-` |

## Invariants and guardrails
- `datasets` mode emits deterministic CSVs and manifest hashes from stable sorted outputs.
- `det-pipeline` requires `--issues`, `--scenarios`, `--outdir`, and `--project-id`.
- Network mutation only occurs when `--apply` is set.
- Dry-run artifacts are still generated for review in det-pipeline mode.

## Artifacts and outputs
- Dataset mode outputs: `assessment_scenario.csv`, `issue_scenario.csv`, `assessment_scenario_issue.csv`, `issues_unmapped.csv`, `manifest.json`.
- Det-pipeline stage artifacts under `<outdir>/artifacts`.
- Det-pipeline always writes `apply_report.json`.

## Code references
- `src/attackiq_cli/cli.py` -> `join_exports`
- `src/attackiq_cli/joiner/cli.py` -> `run_join`
- `src/attackiq_cli/joiner/det_pipeline.py` -> `run_det_pipeline`
- `src/attackiq_cli/joiner/det_pipeline.py` -> `_apply_attackiq_assessments`
- `src/attackiq_cli/joiner/det_pipeline.py` -> `_apply_gitlab_updates`

## Tests
- `tests/test_cli_joiner.py`
- `tests/test_joiner_join.py`
- `tests/test_joiner_outputs.py`
- `tests/test_joiner_parse_labels.py`
- `tests/test_joiner_det_pipeline.py`

## CLI help validation targets
- `attackiq join --help`
  - options: `--assessments`, `--scenarios`, `--issues`, `--outdir`, `--project-id`, `--apply`, `--dry-run`, `--top-k`, `--top-n-per-issue`, `--force-tool-label`, `--allow-append-sections`, `--timestamp`, `--fail-on-missing-scenario`, `--fail-on-malformed-scenario-technique`
