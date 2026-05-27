# AIQ Assist MCP Provider Intake

This page tracks the external provider wire-contract source required before `aiq-cli` can consume
AIQ Assist MCP through CLI or TUI surfaces.

The current repo-local consumer contract is `docs/AIQ_ASSIST_MCP_CONTRACT.md`. The canonical server
contract source is still pending from the AIQ Assist MCP service owner, so this repo must keep MCP
work at the planning, fixture, and guardrail layer only.

## Current Status

- Status file: `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json`
- Status: pending provider source
- Endpoint path: `/aiq-assist/mcp`
- CLI/TUI MCP consumption: blocked
- Live MCP checks: blocked by default

Run the local intake guard with:

```bash
.venv/bin/python scripts/check_aiq_assist_mcp_contract.py
```

The guard validates the status file and scans `src/` for AIQ Assist MCP consumer code while the
provider source is pending.

## Required Provider Evidence

The provider source must document:

- transport and MCP protocol version
- endpoint path ownership and whether `/aiq-assist/mcp` is tenant-relative
- OAuth auth behavior
- regular token auth behavior
- request and response shapes for discovery and tool invocation
- provider error shapes
- timeout and retry expectations
- redaction requirements for auth, tenant URLs, prompts, and assistant/tool context
- live-test opt-in requirements

Raw MCP transcripts are not acceptable as the canonical source and must not be committed.

## Intake Decision

After the provider source is obtained, update `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json` with the
source reference, version, and owner. Keep `allow_cli_tui_consumption` false until the repo has
adapter-level mocked tests and redaction behavior for both auth modes and failure paths.
