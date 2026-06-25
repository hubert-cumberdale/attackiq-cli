# AIQ Assist MCP Adapter Design

Status: design-only guardrail for future `aiq-cli` adapter work. This document does not implement
an adapter, add CLI/TUI commands, or authorize live MCP calls in default checks.

## Preconditions

Adapter implementation must not start until:

- `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json` is updated from `pending_provider_source` to
  `documented_provider_source`.
- The provider source records a canonical source reference, provider contract version, and named
  AIQ Assist MCP service owner.
- `allow_cli_tui_consumption` remains false until adapter-level mocked tests cover both auth modes
  and failure paths.
- The consumer contract and synthetic fixture gates pass locally and in CI.

## Adapter Boundary

The adapter may only be a consumer of a documented MCP HTTP endpoint. It must not infer provider
behavior from synthetic fixtures, raw transcripts, browser captures, or local assumptions.

Allowed future adapter responsibilities:

- Resolve an explicit MCP endpoint URL.
- Select exactly one supported auth mode per request.
- Send bounded MCP discovery or tool-invocation requests after a documented user action.
- Parse expected JSON-RPC/MCP response shapes.
- Return redacted errors and bounded response summaries to callers.

Disallowed responsibilities:

- Import vendor rules, mutate AttackIQ configuration, or invoke write-like provider behavior.
- Discover credentials from browsers, cookies, raw HAR files, captured transcripts, shell history,
  or undocumented local session files.
- Run live provider calls from default CI, the default quality gate, or import-time code.
- Persist prompt text, assistant context, tool context, tenant URLs, Authorization headers, tokens,
  cookies, or raw MCP transcripts in repo-owned files.

## Endpoint Resolution

Default behavior must fail closed unless the caller supplies an explicit full HTTPS URL ending in
`/aiq-assist/mcp`.

A future adapter may derive the MCP URL from an AttackIQ base URL only after the provider contract
documents that the endpoint is tenant-relative and names the URL derivation rule. Until then, tests
and operator evidence must use the explicit URL path.

## Auth Selection

The adapter must require an explicit auth mode:

- `oauth`: use only an explicit access token or a provider-documented OAuth flow.
- `token`: use only an explicitly supplied bearer or service token from a dedicated secret source.

The adapter must reject ambiguous auth input. If both auth modes are supplied, no auth mode is
supplied, or the requested auth mode lacks its required secret source, the adapter must fail before
sending a request.

Rejected auth sources:

- browser session stores
- cookies or cookie jars
- local session files
- captured HAR files or raw MCP transcripts
- undocumented workstation files
- committed fixture files

## Request Execution

The adapter must use explicit timeouts for every network request. Retry behavior is out of scope
until the provider contract documents retry expectations. If retry support is later approved, tests
must prove retry attempts do not duplicate tool invocations with side effects.

Discovery requests and tool invocations must be separate code paths. Tool invocation requires a
documented user action and must not run as part of endpoint validation, command help, TUI startup,
or default health checks.

## Redaction

Operator-facing errors, logs, saved evidence, and test failure output must redact:

- Authorization headers
- bearer, OAuth, JWT, token, secret, password, and cookie-like values
- tenant URLs and private hostnames
- prompt text
- assistant responses
- MCP tool arguments and tool context
- provider request identifiers when the provider contract marks them sensitive

Redaction tests must include provider error text containing token-like content and must verify only
redacted placeholders appear in output.

## Test Strategy

Default tests must use mocked HTTP/MCP responses and compact synthetic fixtures. They must cover:

- OAuth discovery success and auth failure.
- Regular-token discovery success and auth failure.
- OAuth tool-invocation success.
- Regular-token tool-invocation success.
- Malformed or unsupported response shapes.
- Provider error responses with token-like text.
- Timeout or connection failure.
- Rejection of browser, cookie, transcript, and local session-file auth sources.
- Rejection of ambiguous or missing auth mode selection.
- No request is sent for validation, help, TUI startup, or auth-selection failures.

Live tests must be skipped unless all opt-in conditions are present:

- `AIQ_ASSIST_MCP_LIVE=1`
- `AIQ_ASSIST_MCP_URL=<full https URL ending in /aiq-assist/mcp>`
- `AIQ_ASSIST_MCP_AUTH_MODE=oauth|token`
- the matching explicit secret source for the selected auth mode

Live tests must not write raw transcripts. Any operator-owned evidence must stay outside git and
must use redacted summaries only.

## Acceptance Checklist

Future adapter implementation PRs must include:

- provider-source status updated to documented with a named provider owner
- adapter-level mocked tests for both auth modes and listed failure paths
- tests proving rejected auth sources fail before network I/O
- tests proving default live tests are skipped
- redaction tests for provider errors and saved evidence
- no CLI/TUI command exposure until the adapter tests pass

## Validation Commands

```bash
python3 scripts/check_aiq_assist_mcp_contract.py
python3 scripts/check_aiq_assist_mcp_fixtures.py
.venv/bin/python -m pytest tests/test_aiq_assist_mcp_contract.py tests/test_aiq_assist_mcp_fixtures.py
python3 scripts/check_doc_links.py
```
