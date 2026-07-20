# Skill: Security Reviews and Redaction

## Purpose
Review changes for security issues and ensure secrets/PII are redacted.

## Constraints
- Never log tokens, credentials, or customer data.
- Validate inputs and prefer allowlists over denylists.
- Avoid shelling out or dynamic code execution.

## Standard Steps
1. Identify all inputs, outputs, and logging points.
2. Confirm TLS verification and explicit timeouts on network calls.
3. Review error handling to avoid leaking sensitive data.
4. Ensure headers/fields are redacted before logging.
5. Add tests for redaction and validation if behavior changes.

## Example Commands
- `ruff check src tests`
- `pytest -k redact`

## Test Expectations
- Add or update tests that verify redaction and validation behavior.
