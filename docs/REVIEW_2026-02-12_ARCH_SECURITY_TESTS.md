# Architecture, Security, and Test Review
Date: 2026-02-12
Scope: `src/attackiq_cli/*`, `tests/*`

## Decisions Captured
- Cookie/header secrecy: `Cookie` values must be fully redacted anywhere request headers are shown or logged.
- Request body validation scope: keep current lightweight client-side validation; do not expand to full OpenAPI constraint enforcement. Server-side remains source of truth for deeper constraints.

## Findings (Ordered by Severity)

### 1) High - Secret leakage risk for `Cookie` headers
- File references:
  - `src/attackiq_cli/client.py:339`
  - `src/attackiq_cli/client.py:169`
  - `src/attackiq_cli/cli.py:717`
- Detail:
  - `_redact_headers` redacts known auth/token headers, but not `Cookie`.
  - Debug request logs and `--dry-run` previews rely on this redactor.
  - Session cookies can therefore appear in logs/terminal output.
- Risk:
  - Credential/session disclosure to local logs, CI output, shell history captures, or support transcripts.

### 2) Medium - Large mixed-responsibility modules increase change risk
- File references:
  - `src/attackiq_cli/cli.py`
  - `src/attackiq_cli/tui.py`
- Detail:
  - `src/attackiq_cli/cli.py` combines command declaration, validation, transport orchestration, output formatting, and error UX.
  - `src/attackiq_cli/tui.py` combines app shell, tab workflows, caching, sorting/filter parsing, and export handling.
  - Similar executor/task lifecycle patterns are duplicated across tabs.
- Risk:
  - Regression probability rises when touching unrelated behavior.
  - Harder code review and targeted testing.

### 3) Medium - Private API coupling (`src/attackiq_cli/cli.py` imports `_redact_headers`)
- File references:
  - `src/attackiq_cli/cli.py:19`
  - `src/attackiq_cli/client.py:339`
- Detail:
  - CLI imports a private helper from `client.py`.
- Risk:
  - Fragile refactors; unclear ownership of redaction behavior.

### 4) Low-Medium - No explicit CLI-level control-character guard for header values
- File references:
  - `src/attackiq_cli/utils.py:12`
  - `src/attackiq_cli/cli.py:626`
  - `src/attackiq_cli/client.py:191`
- Detail:
  - Header values pass through directly after parsing/coercion.
  - Downstream libraries may reject malformed values, but CLI currently lacks explicit deterministic checks and error messages.
- Risk:
  - Inconsistent failure UX and reliance on downstream behavior.

### 5) Low - Body validation intentionally partial
- File references:
  - `src/attackiq_cli/utils.py:115`
  - `src/attackiq_cli/utils.py:269`
- Detail:
  - Local validator covers type/enum/combinators/format, but not full constraint sets (`minimum`, `maximum`, `minLength`, `maxLength`, `pattern`, etc.).
- Risk:
  - Some invalid payloads pass local checks and fail at API boundary.
- Accepted direction:
  - Keep this scope lightweight and explicitly document limitations.

## Test Gaps

### Gap A - Missing redaction coverage for `Cookie`
- Missing:
  - Unit test ensuring `_redact_headers` masks `Cookie`.
  - CLI dry-run test ensuring cookie content is redacted in preview output.
- Existing nearby coverage:
  - `tests/test_client.py` covers auth/token headers but not cookie.

### Gap B - Missing deterministic header-value rejection tests
- Missing:
  - Tests for CR/LF (header injection primitives) with clear CLI error output.

### Gap C - Missing boundary contract coverage for redaction API
- Missing:
  - Tests and structure that establish a public redaction function consumed by CLI and client code (instead of private-symbol import coupling).

### Gap D - Missing explicit contract tests/documentation for lightweight validator scope
- Missing:
  - Tests/docs that codify non-goals for deeper schema constraints so scope remains intentional.

## Commit Plan (Small, Sequential Tasks)

### Task 1 - Fix cookie redaction in one place
- Change:
  - Treat `cookie` as sensitive in header redaction logic.
- Files:
  - `src/attackiq_cli/client.py`
- Tests:
  - `tests/test_client.py` add `Cookie` redaction assertions.
- Commit size:
  - Small, isolated security fix.

### Task 2 - Add CLI dry-run redaction regression test
- Change:
  - Add/extend `attackiq call --dry-run` test to ensure cookie values are masked.
- Files:
  - `tests/test_cli_call.py` (or `tests/test_cli_call_output.py` if preferred)
- Commit size:
  - Small, test-only regression guard.

### Task 3 - Remove private API coupling for redaction
- Change:
  - Promote redaction helper to a public utility (or dedicated module) and update imports.
- Files:
  - `src/attackiq_cli/client.py`
  - `src/attackiq_cli/cli.py`
  - Optional: `src/attackiq_cli/utils.py` or shared redaction helpers in `src/attackiq_cli/client.py`
- Tests:
  - Update existing tests to target public function path.
- Commit size:
  - Small-medium refactor, no behavior change expected.

### Task 4 - Add explicit header value safety checks
- Change:
  - Reject header values containing control chars (`\r`, `\n`, optionally other ASCII controls except tab if desired).
  - Emit user-facing `typer.BadParameter` with clear message.
- Files:
  - `src/attackiq_cli/cli.py` and/or `src/attackiq_cli/utils.py`
- Tests:
  - New tests in `tests/test_cli_call.py` for invalid header values.
- Commit size:
  - Small, scoped hardening.

### Task 5 - Document validator scope as intentional
- Change:
  - Add explicit note in user docs and/or state docs that body validation is lightweight and server remains authoritative.
- Files:
  - `README.md`
  - `docs/STATE.md`
- Tests:
  - None required for docs-only.
- Commit size:
  - Small docs update.

### Task 6 - Add guardrail tests for validator non-goals
- Change:
  - Add tests that make current scope explicit (or at minimum add a single test documenting expected pass-through for unsupported constraints).
- Files:
  - `tests/test_cli_call_body_validation.py`
- Commit size:
  - Small, clarifies maintenance contract.

### Task 7 - Architecture debt follow-up (optional, multi-PR track)
- Change:
  - Incremental extraction from `src/attackiq_cli/cli.py` and `src/attackiq_cli/tui.py`
    (for example redaction/output/error helpers first, then per-tab controller helpers).
- Files:
  - `src/attackiq_cli/cli.py`
  - `src/attackiq_cli/tui.py`
  - New helper modules as needed.
- Tests:
  - Preserve behavior with focused regression tests each extraction step.
- Commit size:
  - Keep each PR narrowly scoped (one extraction theme at a time).

## Suggested Execution Order
1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7 (as separate roadmap stream)

## Validation Checklist Per Task
- Run targeted tests for touched area first.
- Run full suite before merge: `pytest`.
- Run lint/type checks if code changed:
  - `ruff check src tests`
  - `python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy`
