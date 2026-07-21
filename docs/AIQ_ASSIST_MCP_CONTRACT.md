# AIQ Assist MCP Consumer Contract

Status: planning contract for future `aiq-cli` consumption, with an initial synthetic fixture gate.
This document does not define the server's canonical MCP wire contract.

## Boundary

- Consumer contract name: `aiq-assist-mcp-consumer`
- Consumer contract version: `v0`
- Endpoint path: `/aiq-assist/mcp`
- Provider contract source: tracked in `docs/AIQ_ASSIST_MCP_PROVIDER_SOURCE.json`; status remains
  `pending_provider_source` until a named AIQ Assist MCP service owner supplies the canonical
  provider MCP wire-contract source.
- Status owner: `aiq-cli` maintainers own the repo-local status record, fixture gate, and consumer
  guardrails. They do not own or infer the provider wire contract.
- Provider intake notes: `docs/AIQ_ASSIST_MCP_PROVIDER_INTAKE.md`
- Adapter design: `docs/AIQ_ASSIST_MCP_ADAPTER_DESIGN.md`
- Integration card: `docs/integration-cards/AIQ_ASSIST_MCP.md`
- Boundary rules: `docs/INTEGRATION_BOUNDARIES.md`

Until the provider contract source is documented, no CLI/TUI MCP command should be added and no
default live MCP call should run from local checks.

The local quality gate includes `scripts/check_aiq_assist_mcp_contract.py`, which validates the
provider-source status file and blocks AIQ Assist MCP consumer code until the provider source is
documented, `allow_cli_tui_consumption` is explicitly true, and `adapter_mock_tests` is explicitly
true. Merely changing the provider-source status does not unlock consumer code.

The pending state is final for the current release-readiness sequence: adapter implementation must
not start by treating synthetic fixtures, raw MCP transcripts, browser captures, or local
assumptions as the canonical provider source.

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

- successful tool/resource discovery for OAuth and regular token auth
- successful tool invocation for OAuth and regular token auth
- OAuth auth failure
- regular token auth failure
- timeout or connection failure
- malformed or unsupported MCP response
- provider error response with token-like text that must be redacted

Fixtures must be compact, deterministic, and free of tenant/customer data. Each committed fixture
is limited to 16 KiB (16,384 bytes), enforced before JSON parsing. Raw live transcripts are not
fixtures and must stay outside git. Fixture JSON must not contain duplicate object names at any
nesting level; the gate rejects them before contract validation to avoid parser-dependent evidence.
Numeric values must remain finite after decoding, so the decoder rejects `NaN`, `Infinity`,
`-Infinity`, and exponent forms such as `1e999` or `-1e999` that would overflow to infinity before
contract validation.

Initial consumer-contract fixtures live under `tests/fixtures/aiq_assist_mcp/` and are validated by
`scripts/check_aiq_assist_mcp_fixtures.py`. The gate checks the required case set, `/aiq-assist/mcp`
endpoint path, consumer contract name/version, no-live-fixture marker, redacted secret-shaped
content, request method/ID consistency, explicit redaction expectations, and outcome-specific
synthetic response shapes. Success fixtures require a JSON-RPC result, auth/provider failures
require an error envelope with a failure status and bounded details, timeouts cannot contain a
response, and the malformed-response case must remain intentionally invalid. These checks validate
repo-local fixture consistency; they do not define or infer the provider wire contract.

Sensitive fixture keys accept only exact redaction placeholders: `<redacted>`,
`Bearer <redacted>`, or `Token <redacted>` after case and surrounding-whitespace normalization.
Auth-mode marker words such as `oauth` and `token` are not redaction placeholders for sensitive
keys. Embedding a placeholder beside other text is rejected. Key classification uses each literal
JSON object name rather than a dot-separated diagnostic path, so punctuation inside an extension
key cannot hide a sensitive or raw-transcript-shaped name. URLs are parsed before validation; only
valid HTTPS URLs on the exact synthetic hosts `example.com`, `example.invalid`, and `example.test`
are allowed. Other schemes, invalid ports, and credentials embedded in URLs are rejected.
Raw-transcript-shaped keys are also prohibited.

The fixture directory is a closed inventory of the required case filenames. The gate rejects
unexpected artifacts, subdirectories, symbolic links, non-directory fixture roots, and JSON files
whose declared case does not match the filename. This prevents ignored transcript-like side files
or misleading fixture renames from sitting outside the validated synthetic case set.

Synthetic requests use a minimal case-insensitive header envelope containing exactly
`Authorization` and `Content-Type`. Authorization must be an exact redacted placeholder,
`Content-Type` must be `application/json`, duplicate normalized header names are rejected, and
cookie or other session-source headers are not allowed. This validates only repo-local fixture
shape; it does not establish provider authentication behavior.

Method-specific synthetic parameters are also bounded. `tools/list` requests use an empty params
object. `tools/call` requests contain exactly a non-empty synthetic `name` and an `arguments`
object. The gate does not require a particular tool name or argument schema because those details
must come from the pending provider contract.

Successful synthetic response containers remain method-specific but provider-neutral.
`tools/list` results require a non-empty `tools` list, and `tools/call` results require a non-empty
`content` list. List item structure is intentionally not validated before the provider contract
defines canonical discovery and tool-result schemas.

Synthetic auth-failure and provider-error envelopes require a non-boolean integer `code` and a
non-empty string `message`. The gate does not require a particular error code or require the code
to equal the HTTP status because those semantics must come from the pending provider contract.

Repo-owned fixture maps use closed field sets: the top-level fixture wrapper, expectation metadata,
request wrapper, request JSON-RPC envelope, response transport wrapper, and timeout error wrapper
reject undeclared fields. Provider response bodies, result containers and items, and provider error
data remain open because their extension fields must come from the pending provider contract.

Stored synthetic HTTP responses require a non-boolean integer status from 100 through 599.
Provider-error outcomes further require a status from 400 through 599; success and auth-failure
outcomes retain their existing exact status rules. Unassigned codes inside those numeric ranges are
allowed, and JSON-RPC error codes remain independent of HTTP status values.

The current failure/redaction case set includes:

- `malformed_response`: unsupported JSON-RPC response shape.
- `timeout_failure`: configured deadline failure.
- `provider_error_redaction`: provider error text with token-like content already redacted.

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
- tests that reject partial redaction placeholders, non-example hosts, URL credentials, and raw
  transcript keys
- tests that reject auth-mode marker words in sensitive fields instead of treating them as
  redaction placeholders
- tests that reject punctuated sensitive and raw-transcript keys without closing provider fields
- tests that reject non-HTTPS fixture URLs and invalid URL ports
- tests that reject fixture files over the 16 KiB retention limit before parsing
- tests that reject duplicate JSON object names before contract validation
- tests that reject non-finite JSON numeric constants and exponent-overflow floats before contract
  validation
- tests that reject unexpected fixture artifacts, symbolic links, and filename/case drift
- tests that reject missing, duplicate, non-JSON, or cookie/session-style request headers
- tests that reject discovery/tool-call parameter drift without asserting provider tool schemas
- tests that reject missing or empty discovery/tool-call success lists without asserting item
  schemas
- tests that reject missing, non-integer, or blank failure-envelope details without asserting
  provider error-code semantics
- tests that reject undeclared fields in repo-owned fixture wrappers without closing provider-owned
  response data
- tests that reject out-of-range HTTP statuses without pinning provider status values or JSON-RPC
  error-code relationships
- opt-in live test coverage that is skipped by default

Public CLI/TUI commands should remain out of scope until this contract moves beyond `v0` and the
provider contract source is documented. Future adapter implementation must also satisfy
`docs/AIQ_ASSIST_MCP_ADAPTER_DESIGN.md`.
