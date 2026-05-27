# Skill: CLI Command Creation

## Purpose
Create or extend CLI commands in `src/attackiq_cli/cli.py` using Typer conventions.

## Constraints
- Follow repository style (Python 3.10+, 4-space indent, 100-char line length).
- Use `AttackIQClient` with explicit timeouts and TLS verification settings.
- Avoid logging secrets; redact sensitive fields in logs.

## Standard Steps
1. Identify the OpenAPI `operation_id` or feature scope.
2. Add Typer command with explicit options and clear help text.
3. Load config, initialize logging, build `AttackIQClient`.
4. Call the operation via `client.send` or `paginate_results`.
5. Format output (JSON/CSV or minimal text) and handle errors.

## Example Commands
- `attackiq --help`
- `attackiq spec list --tag scenarios`
- `attackiq export scenarios --page-size 200`

## Test Expectations
- Add focused pytest coverage for new behavior.
- Run `pytest -k <test_name>` for targeted changes.
