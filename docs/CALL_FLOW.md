# `attackiq call` Execution Flow

Implementation-aligned contract for request construction, validation, and output formatting in `attackiq call`.

## Command surface
Command: `attackiq call <operation_id>`

| Option | Required | Default | Allowed |
| --- | --- | --- | --- |
| `--param` | no | `null` | `-` |
| `--header` | no | `null` | `-` |
| `--cookie` | no | `null` | `-` |
| `--body` | no | `null` | `-` |
| `--body-file` | no | `null` | `-` |
| `--form` | no | `null` | `-` |
| `--form-file` | no | `null` | `-` |
| `--interactive` | no | `False` | `-` |
| `--output` | no | `null` | `-` |
| `--output-format` | no | `null` | `pretty-json, raw, csv` |
| `--base-url` | no | `null` | `-` |
| `--timeout` | no | `null` | `-` |
| `--log-json/--no-log-json` | no | `--no-log-json` | `-` |
| `--log-level` | no | `null` | `-` |
| `--verbose` | no | `False` | `-` |
| `--auth-scheme` | no | `auto` | `auto, account-token, jwt, none` |
| `--insecure` | no | `False` | `-` |
| `--dry-run` | no | `False` | `-` |

## Invariants and guardrails
- JSON body flags (`--body`, `--body-file`) and form flags (`--form`, `--form-file`) are mutually exclusive.
- Required path/header/cookie parameters from OpenAPI are enforced before send.
- JSON request-body validation covers basic types, required fields, additionalProperties=false, selected formats, string length/pattern checks, numeric bounds, and common object/array count constraints.
- Header values containing CR/LF are rejected before request execution.
- Dry-run mode never sends a network request and redacts sensitive headers.
- Safe-method retries apply only to `GET`, `HEAD`, and `OPTIONS` requests.

## Artifacts and outputs
- Response payload output to stdout/file according to `--output` and `--output-format`.
- Optional CSV output when response body is a JSON array of objects.
- Dry-run request preview output with redacted sensitive fields.

## Code references
- `src/attackiq_cli/cli_call.py` -> `call`
- `src/attackiq_cli/cli_call.py` -> `handle_response`
- `src/attackiq_cli/cli_call.py` -> `coerce_params`
- `src/attackiq_cli/utils.py` -> `parse_key_value_pairs`
- `src/attackiq_cli/utils.py` -> `coerce_value_from_schema`
- `src/attackiq_cli/utils.py` -> `validate_json_payload`
- `src/attackiq_cli/service_core.py` -> `load_service_context`
- `src/attackiq_cli/service_core.py` -> `ensure_auth`
- `src/attackiq_cli/client.py` -> `AttackIQClient`
- `src/attackiq_cli/client.py` -> `send`

## Tests
- `tests/test_cli_call.py`
- `tests/test_cli_call_body_validation.py`
- `tests/test_cli_call_output.py`

## CLI help validation targets
- `attackiq call --help`
  - options: `--param`, `--header`, `--cookie`, `--body`, `--body-file`, `--form`, `--form-file`, `--interactive`, `--output`, `--output-format`, `--base-url`, `--timeout`, `--log-json`, `--log-level`, `--verbose`, `--auth-scheme`, `--insecure`, `--dry-run`
