# Integration Boundaries

This document defines how `attackiq-cli` should interact with external tools, services, and local
artifacts.

## Allowed Integration Methods

| Method | Use |
| --- | --- |
| YAML/JSON catalog files | Scenario catalog ingestion. |
| CSV/JSONL exports | Findings, exposure summaries, and reporting inputs. |
| Documented HTTP APIs | Mature service integrations with auth, timeouts, and versioning. |
| MCP over documented HTTP APIs | Tool/resource integration after endpoint, auth, timeout, and transcript handling are documented. |
| CLI subprocess calls | Only when a stable file/API contract is unavailable and the command is safe. |

## Disallowed Defaults

- Direct imports from unrelated repositories.
- Implicit writes into external repositories or artifact locations.
- Hidden assumptions about local checkout paths.
- Live external writes without `--apply` or an equivalent explicit gate.
- Browser-captured credentials, cookies, HAR files, or session artifacts in repo files.
- Raw MCP transcripts, OAuth tokens, bearer tokens, or assistant context dumps in repo files.

## Catalog Boundary

Catalog sources own:

- record source files
- technique mappings
- coverage gaps
- domain-specific limitations
- source validation tools

`attackiq-cli` owns:

- ingesting catalog records from an explicit path
- summarizing coverage
- planning AttackIQ assessment inputs
- uploading custom templates when an operator explicitly runs an apply-gated workflow
- exporting operator reports

## External Findings Boundary

External exposure or findings platforms own their inventory model, source confidence, evidence,
risk scoring, and remediation state. `attackiq-cli` may consume sanitized exports through a
documented file or API contract. It should not duplicate the upstream inventory model.

## AIQ Assist MCP Boundary

The AIQ Assist MCP server owns:

- MCP protocol behavior exposed at `/aiq-assist/mcp`
- tool/resource discovery
- OAuth authentication behavior
- regular token authentication behavior
- assistant/tool response schemas

`attackiq-cli` may later consume AIQ Assist MCP capabilities through an explicit adapter or command
surface. Before that happens, the integration must satisfy the planning contract in
`docs/AIQ_ASSIST_MCP_CONTRACT.md`, including request/response contracts, timeout/retry behavior,
auth selection, redaction, fixture strategy, and live-call opt-in.

The provider contract source status is tracked in `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json` and
validated by `scripts/check_aiq_assist_mcp_contract.py`. While that status remains pending, CLI/TUI
consumer code and default live MCP checks stay blocked.

No MCP integration may rely on hidden credential discovery, browser-captured sessions, committed
tokens, or committed raw MCP transcripts.

## Integration Card

Each external integration should include an integration card. Use
`docs/integration-cards/AIQ_INTEGRATION.md` as the starting point and keep it updated when outputs
or validation commands change.

## Review Requirements

Any new adapter must document:

- source contract and version
- accepted input paths or endpoints
- auth and secret handling
- timeout/retry behavior
- dry-run/apply behavior
- test fixture strategy
- failure modes when the external source is absent
