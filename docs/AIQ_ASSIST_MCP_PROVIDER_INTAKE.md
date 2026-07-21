# AIQ Assist MCP Provider Intake

This page tracks the external provider wire-contract source required before `aiq-cli` can consume
AIQ Assist MCP through CLI or TUI surfaces.

The current repo-local consumer contract is `docs/AIQ_ASSIST_MCP_CONTRACT.md`. The canonical server
contract source is still pending from the AIQ Assist MCP service owner, so this repo must keep MCP
work at the planning, fixture, and guardrail layer only.

The fail-closed adapter design is tracked in `docs/AIQ_ASSIST_MCP_ADAPTER_DESIGN.md`.

## Current Status

- Status file: `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json`
- Status: pending provider source
- Repo status owner: `aiq-cli` maintainers
- Provider owner: pending named AIQ Assist MCP service owner
- Endpoint path: `/aiq-assist/mcp`
- CLI/TUI MCP consumption: blocked
- Live MCP checks: blocked by default

Run the local intake guard with:

```bash
.venv/bin/python scripts/check_aiq_assist_mcp_contract.py
```

The guard validates the status file and scans `src/` for AIQ Assist MCP consumer code until the
provider source is documented and both CLI/TUI consumption approval and adapter mock-test evidence
are explicitly true.

## Ownership Boundary

The AIQ Assist MCP service owner owns the canonical provider MCP wire contract, including endpoint
path ownership, protocol behavior, auth behavior, request/response shapes, provider errors,
timeout/retry expectations, and redaction requirements.

`aiq-cli` maintainers own only the repo-local consumer planning contract, the provider-source status
record, synthetic fixtures, validation gates, and documentation guardrails. They must not infer the
provider wire contract from raw transcripts, browser captures, fixture examples, or local adapter
assumptions.

While `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json` is `pending_provider_source`, keep
`provider_contract_source`, `provider_contract_version`, and `provider_owner` null. The
`provider_owner_status` field records that the named service owner is still pending, and
`status_owner` records who maintains the repo-local gate.

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
source reference, version, and named provider owner. Keep `allow_cli_tui_consumption` false until
the repo has adapter-level mocked tests and redaction behavior for both auth modes and failure
paths, following `docs/AIQ_ASSIST_MCP_ADAPTER_DESIGN.md`. A documented provider source must record
`adapter_mock_tests` as a boolean. Consumer code remains blocked until both that field and
`allow_cli_tui_consumption` are true.
