# Deterministic Review Automation

Use these scripts to run architecture/security/test reviews in a repeatable format.

## 1) Generate a review scaffold

```bash
python3 scripts/deterministic_review.py
```

Default output:
- `docs/reviews/REVIEW_<YYYY-MM-DD>`

Options:
- `--output <path>` write to a custom file.
- `--stdout` print generated report to terminal.
- `--repo-root <path>` scan a different repo root.

To enforce the architecture boundary without generating a report:

```bash
python3 scripts/deterministic_review.py --check-architecture
```

This command exits nonzero when any Python module under `src/` exceeds 800 lines. The standard
local quality gate and GitHub Actions both run it.

## 2) Add judgement-backed findings

Edit the generated report:
- Fill `## Findings` with severity-ordered issues.
- Include concrete `path:line` references.
- Keep risk statements explicit and testable.

## 3) Convert findings into commit tasks

```bash
python3 scripts/review_findings_to_tasks.py --review docs/reviews/REVIEW_<YYYY-MM-DD>
```

Default output:
- `docs/reviews/TASKS_<review-stem>`

Options:
- `--output <path>` write to a custom file.
- `--stdout` print generated task list to terminal.

## 4) Validate before merge

```bash
python3 scripts/deterministic_review.py --check-architecture
ruff check src tests
python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy
pytest
```
