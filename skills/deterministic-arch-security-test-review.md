# Skill: Deterministic Architecture/Security/Test Review

## Purpose
Run repeatable, evidence-first codebase reviews focused on architecture risks, security posture,
and test coverage gaps, then convert findings into small commit-sized tasks.

## When to Use
- User asks for a repo review with architecture/security/testing focus.
- User asks to make reviews deterministic/repeatable.
- User asks to break findings into small committable tasks.

## Inputs
- Target repository root.
- Optional output locations for generated review and task docs.

## Standard Workflow
1. Generate a deterministic review scaffold:
   - `python3 scripts/deterministic_review.py`
   - Optional custom path: `python3 scripts/deterministic_review.py --output docs/reviews/REVIEW_2026-02-12`
2. Read the generated report and add human judgement in `## Findings`:
   - Order findings by severity.
   - Add concrete file/line references.
   - Keep claims evidence-backed.
3. Convert findings into commit tasks:
   - `python3 scripts/review_findings_to_tasks.py --review <review_path>`
4. Execute tasks in order, one logical change per commit.

## Constraints
- Prefer deterministic command/script outputs over ad-hoc one-off searches.
- Treat tokens/secrets/cookies as sensitive in findings and examples.
- Keep tasks small and independently verifiable.

## Output Contract
- A review markdown document with:
  - Snapshot metadata
  - Architecture signals
  - Security signals
  - Test signals
  - Severity-ordered findings
- A task markdown document with small sequential tasks and validation commands.

## Validation Commands
- `ruff check src tests`
- `python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`
- `pytest`
