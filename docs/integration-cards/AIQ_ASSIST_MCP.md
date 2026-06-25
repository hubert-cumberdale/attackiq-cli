# AIQ Assist MCP Integration Card

## Service Role

AIQ Assist MCP exposes assistant capabilities through an MCP server hosted at `/aiq-assist/mcp`.
The service owns MCP protocol behavior, tool/resource discovery, auth validation, and assistant
response schemas.

## Consumed By

- aiq-cli, after the integration contract and fixture strategy are stable.

## Contract

- Contract name: AIQ Assist MCP
- Contract version: consumer contract `v0` with synthetic fixture gate; provider wire contract TBD
- Consumer contract source: `docs/AIQ_ASSIST_MCP_CONTRACT.md`
- Canonical provider contract source: tracked in `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json`;
  currently pending and must be documented before CLI/TUI consumption.
- Provider owner: pending named AIQ Assist MCP service owner.
- Repo-local status owner: `aiq-cli` maintainers.
- Provider intake notes: `docs/AIQ_ASSIST_MCP_PROVIDER_INTAKE.md`
- Adapter design: `docs/AIQ_ASSIST_MCP_ADAPTER_DESIGN.md`
- Endpoint path: `/aiq-assist/mcp`
- Auth modes: OAuth and regular token

## Outputs

- MCP tool and resource discovery responses.
- MCP tool invocation responses.
- Assistant/tool error responses.

Raw MCP transcripts may contain tenant, auth, prompt, or assistant context and must not be
committed.

## Validation

- Current local validation:
  - `.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py`
  - `.venv/bin/python scripts/check_aiq_assist_mcp_contract.py`
  - `.venv/bin/python -m pytest tests/test_aiq_assist_mcp_fixtures.py -q`
  - `.venv/bin/python scripts/quality_gate.py --dry-run --no-mkdocs`
  - `.venv/bin/python scripts/check_doc_links.py`
  - `.venv/bin/python scripts/check_release_governance.py`
  - `git diff --check`
- Future code validation:
  - adapter-level mocked HTTP/MCP tests for OAuth auth, regular token auth, timeouts, invalid
    responses, and redaction.
  - live tests only behind explicit opt-in environment variables.

## Security Notes

- Do not commit OAuth tokens, bearer tokens, cookies, browser sessions, raw MCP transcripts, or
  assistant context dumps.
- Redact token-like values, Authorization headers, tenant URLs, and private host/user data in
  operator-facing errors and saved evidence.
- Prefer synthetic fixtures for tests; live MCP evidence must stay outside git.

## Sync Checklist

- Update this card when the endpoint path, auth modes, contract source, or validation commands
  change.
- Update `docs/INTEGRATION_BOUNDARIES.md` when the adapter boundary changes.
- Update `docs/ROADMAP.md` when the MCP maturity target changes.
- Keep raw MCP outputs and transcripts out of source control unless explicitly approved and
  sanitized.
