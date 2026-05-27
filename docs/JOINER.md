# Joiner workflows

The joiner combines AttackIQ export CSVs (assessments + scenarios) with a GitLab issues
CSV to produce deterministic outputs and a manifest.
Maintainer deep dive: `docs/JOINER_FLOW.md`.

## Mode overview
- `attackiq join [MODE]` defaults to `datasets` mode.
- Supported modes:
  - `datasets`: deterministic CSV joins + manifest.
  - `det-pipeline`: staged DET workflow with optional apply mode.

## Inputs
- Assessments export CSV (from `attackiq export assessments`).
- Scenarios export CSV (from `attackiq export scenarios`).
- GitLab issues CSV containing MITRE technique labels (e.g., `T1059` or `T1059.001`).

## Recommended workflow
1) Export the AttackIQ datasets.
```bash
attackiq export assessments --output assessments.csv --format csv
attackiq export scenarios --output scenarios.csv --format csv
```

2) Export the GitLab issues CSV.
- Ensure the CSV includes the MITRE technique tokens you want to match.

3) Run the joiner.
```bash
attackiq join datasets --assessments assessments.csv --scenarios scenarios.csv \
  --issues gitlab_issues.csv --outdir joined --timestamp 2026-01-26T00:00:00Z
```

## Outputs
- `assessment_scenario.csv`: assessments joined to scenarios by `scenario_id`.
- `issue_scenario.csv`: issues joined to scenarios by explicit MITRE technique labels.
- `assessment_scenario_issue.csv`: left-join of assessments to matched issues by scenario.
- `issues_unmapped.csv`: issues with no technique labels or no scenario match.
- `manifest.json`: deterministic manifest with hashes and runtime metadata.

## Join semantics
- Assessments -> scenarios join on `assessments.scenario_id == scenarios.id`.
- Issues -> scenarios join on exact technique token matches (`T####` or `T####.###`).
- Scenario techniques are validated; malformed values fail fast by default.

## Flags and behavior
- `--timestamp <utc>`: override manifest timestamp (default: current UTC).
- `--fail-on-missing-scenario/--no-fail-on-missing-scenario`: control behavior when a
  scenario_id is missing from the scenarios export.
- `--fail-on-malformed-scenario-technique/--no-fail-on-malformed-scenario-technique`:
  control behavior when scenario techniques are malformed.
- `--dry-run/--no-dry-run`, `--apply`, `--top-k`, `--top-n-per-issue`,
  `--force-tool-label`, and `--allow-append-sections` apply only to `det-pipeline` mode.

## Module entrypoints
```bash
python -m attackiq_cli.joiner.cli join --assessments assessments.csv \
  --scenarios scenarios.csv --issues gitlab_issues.csv --outdir joined

# Compatibility alias
python -m aiq_cli.joiner.cli join --assessments assessments.csv \
  --scenarios scenarios.csv --issues gitlab_issues.csv --outdir joined
```

## DET pipeline (stages A-E)

The DET pipeline adds deterministic issue normalization, reconciliation, recommendation,
assessment planning, and GitLab patch planning.

Dry-run is the default behavior. Network calls happen only with `--apply`.
`--project-id` is required by the top-level `attackiq join det-pipeline` command.

### Orchestrator command
```bash
# dry-run
attackiq join det-pipeline \
  --issues gitlab_issues.csv \
  --scenarios scenarios.csv \
  --outdir joined \
  --project-id 12345

# apply (GitLab + AttackIQ create requests)
attackiq join det-pipeline \
  --issues gitlab_issues.csv \
  --scenarios scenarios.csv \
  --outdir joined \
  --project-id 12345 \
  --apply
```

### Stage subcommands (module CLI)
```bash
python -m attackiq_cli.joiner.cli det-stage-a --issues gitlab_issues.csv --outdir joined
python -m attackiq_cli.joiner.cli det-stage-b --issues gitlab_issues.csv --outdir joined
python -m attackiq_cli.joiner.cli det-stage-c --issues gitlab_issues.csv --scenarios scenarios.csv --outdir joined
python -m attackiq_cli.joiner.cli det-stage-d --issues gitlab_issues.csv --scenarios scenarios.csv --outdir joined
python -m attackiq_cli.joiner.cli det-stage-e --issues gitlab_issues.csv --scenarios scenarios.csv --outdir joined
```

### Required env vars for apply mode
- `GITLAB_BASE_URL`
- `GITLAB_TOKEN`

### DET pipeline artifacts (`<outdir>/artifacts`)
- `issues_normalized.jsonl`
- `issues_findings.csv`
- `manifest.json`
- `technique_reconciliation.json`
- `recommendations.json`
- `issue_to_scenario_candidates.csv`
- `assessment_plan.json`
- `assessment_plan.csv`
- `attackiq_create_requests.ndjson`
- `gitlab_patch_plan.json`
- `gitlab_description_previews.jsonl`
- `apply_report.json`
