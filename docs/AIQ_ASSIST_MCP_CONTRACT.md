# AIQ Assist MCP Consumer Contract

Status: planning contract for future `aiq-cli` consumption, with an initial synthetic fixture gate.
This document does not define the server's canonical MCP wire contract.

## Boundary

- Consumer contract name: `aiq-assist-mcp-consumer`
- Consumer contract version: `v0`
- Endpoint path: `/aiq-assist/mcp`
- Provider contract source: tracked in `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json`, currently
  pending the AIQ Assist MCP service owner.
- Provider intake notes: `docs/AIQ_ASSIST_MCP_PROVIDER_INTAKE.md`
- Integration card: `docs/integration-cards/AIQ_ASSIST_MCP.md`
- Boundary rules: `docs/INTEGRATION_BOUNDARIES.md`

Until the provider contract source is documented, no CLI/TUI MCP command should be added and no
default live MCP call should run from local checks.

The local quality gate includes `scripts/check_aiq_assist_mcp_contract.py`, which validates the
provider-source status file and blocks AIQ Assist MCP consumer code while that source remains
pending.

## Endpoint Resolution

Future consumers must use an explicit full MCP URL for live tests and operator evidence. A future
adapter may derive the URL from an AttackIQ base URL only after the provider contract confirms that
`/aiq-assist/mcp` is tenant-relative.

Proposed opt-in live-test variables:

- `AIQ_ASSIST_MCP_LIVE=1`
- `AIQ_ASSIST_MCP_URL=<full https URL ending in /aiq-assist/mcp>`
- `AIQ_ASSIST_MCP_AUTH_MODE=oauth|token`

Live tests must skip when these variables are absent.

## Auth Modes

Both supported auth paths are in scope from the first implementation milestone:

- OAuth: use an explicit access token or documented OAuth flow from the provider contract.
- Regular token: use an explicitly supplied bearer or service token from a dedicated secret source.

Future implementations must not read browser sessions, cookies, captured network artifacts, or
undocumented local files. Operator-facing errors and saved evidence must redact Authorization
headers, token-like values, tenant URLs, prompt text, and assistant/tool context.

## Minimum Fixture Strategy

Before adding CLI/TUI consumption, keep synthetic fixtures that cover:

- successful tool/resource discovery
- successful tool invocation
- OAuth auth failure
- regular token auth failure
- timeout or connection failure
- malformed or unsupported MCP response
- provider error response with token-like text that must be redacted

Fixtures must be compact, deterministic, and free of tenant/customer data. Raw live transcripts are
not fixtures and must stay outside git.

Initial consumer-contract fixtures live under `tests/fixtures/aiq_assist_mcp/` and are validated by
`scripts/check_aiq_assist_mcp_fixtures.py`. The gate checks the required case set, `/aiq-assist/mcp`
endpoint path, consumer contract name/version, no-live-fixture marker, and redacted secret-shaped
content.

Run the local fixture gate with:

```bash
.venv/bin/python scripts/check_aiq_assist_mcp_fixtures.py
```

## Adapter Acceptance Gates

Any future `aiq-cli` MCP adapter must provide:

- explicit timeout configuration
- fail-closed auth selection
- no implicit writes or tool invocations without a documented user action
- redacted error reporting
- mocked HTTP/MCP tests for both auth modes and failure paths
- opt-in live test coverage that is skipped by default

Public CLI/TUI commands should remain out of scope until this contract moves beyond `v0` and the
provider contract source is documented.
