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
- The provider-source status records `adapter_mock_tests` as a boolean; the contract guard keeps
  consumer code blocked until both `adapter_mock_tests` and `allow_cli_tui_consumption` are true.
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
exact redacted placeholders appear in output. A sensitive field must not pass merely because it
contains `<redacted>` beside other text or because its value is an auth-mode marker such as `oauth`
or `token`.

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

Committed synthetic fixture files must not exceed 16 KiB. The offline gate must reject oversized
files before JSON parsing so fixtures cannot become raw transcript or response-retention storage.
This byte budget does not define provider response schemas.

The fixture decoder must reject duplicate JSON object names at every nesting level before contract
validation. Duplicate-name rejection keeps repository evidence deterministic across JSON parsers;
it does not constrain provider-owned response fields or define the provider wire schema.

The fixture decoder must also reject non-finite numeric constants (`NaN`, `Infinity`, and
`-Infinity`) and exponent forms such as `1e999` or `-1e999` that would decode as infinity before
contract validation. This preserves finite numeric evidence even inside provider-owned extension
data without defining the provider response schema.

The repo-local fixture gate must also reject outcome drift: success, auth failure, provider error,
timeout, and malformed-response fixtures must remain internally consistent with their declared
outcomes. It must reject raw-transcript-shaped keys, parse fixture URLs, allow only exact synthetic
example hosts over HTTPS, and reject other schemes, invalid ports, or credentials embedded in any
URL. These are synthetic consumer-contract invariants, not provider-source evidence.

Sensitive and raw-transcript key classification must inspect literal JSON object names rather than
derive names from diagnostic paths. Provider extension keys may remain otherwise unconstrained,
but punctuation in a key or an auth-mode marker value must not bypass redaction or retention checks.

The fixture directory must remain a closed inventory of regular, non-symlink JSON files. Each
filename must match its declared synthetic case, and unexpected files or subdirectories must fail
the gate instead of being ignored.

Synthetic request fixtures must contain only a redacted `Authorization` header and an
`application/json` content type. Header names are case-insensitive, duplicate normalized names
fail, and cookie or other session-source headers are prohibited. This remains fixture consistency
evidence rather than a provider auth contract.

Synthetic `tools/list` requests must use empty params. Synthetic `tools/call` requests must contain
exactly a non-empty tool name and an arguments object, but the fixture gate must not require a
specific tool name or argument schema before provider-source documentation exists.

Synthetic success responses must keep a non-empty `tools` list for discovery and a non-empty
`content` list for tool invocation. The fixture gate must not validate list item schemas until the
canonical provider contract defines them.

Synthetic auth and provider failures must carry an integer error code and non-empty error message.
Boolean values are not valid integer codes. The fixture gate must not require a specific code or
couple error codes to HTTP statuses until the canonical provider contract defines those semantics.

Repo-owned synthetic fixture wrappers must reject undeclared fields at the fixture, expectation,
request, request-body, response-transport, and timeout-error layers. Provider response bodies,
result data, and provider error extensions must remain unconstrained until the canonical provider
contract defines them.

Synthetic HTTP response statuses must be integers from 100 through 599, and provider-error outcomes
must use the 400 through 599 range. Unassigned values inside those ranges remain valid fixture data,
and HTTP statuses must not be coupled to JSON-RPC error codes before the provider contract defines
that relationship.

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
