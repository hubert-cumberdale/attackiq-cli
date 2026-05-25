# Skill: Documentation Updates

## Purpose
Update docs and guidance to reflect new behavior or workflows.

## Constraints
- Keep docs concise, accurate, and scoped to the change.
- Avoid duplicating content across files; link instead.
- Use ASCII unless the file already uses Unicode.

## Standard Steps
1. Identify the correct doc(s) and update only relevant sections.
2. Add examples that mirror actual CLI behavior.
3. Cross-link related docs instead of repeating content.
4. Verify references to files or commands are accurate.

## Example Commands
- `attackiq --help`
- `pytest -k docs` (if doc-driven tests exist)

## Test Expectations
- Docs-only changes do not require tests.
