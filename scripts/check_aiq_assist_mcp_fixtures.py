"""Validate synthetic AIQ Assist MCP consumer-contract fixtures."""

from __future__ import annotations

import json
import math
import re
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "aiq_assist_mcp"
CONTRACT_NAME = "aiq-assist-mcp-consumer"
CONTRACT_VERSION = "v0"
ENDPOINT_PATH = "/aiq-assist/mcp"
MAX_FIXTURE_BYTES = 16 * 1024

EXPECTED_CASES = {
    "discovery_success": ("oauth", "success"),
    "token_discovery_success": ("token", "success"),
    "oauth_tool_invocation_success": ("oauth", "success"),
    "tool_invocation_success": ("token", "success"),
    "oauth_auth_failure": ("oauth", "auth_failure"),
    "token_auth_failure": ("token", "auth_failure"),
    "timeout_failure": ("oauth", "timeout"),
    "malformed_response": ("token", "malformed_response"),
    "provider_error_redaction": ("token", "provider_error"),
}

EXPECTED_REQUEST_METHODS = {
    "discovery_success": "tools/list",
    "token_discovery_success": "tools/list",
    "oauth_tool_invocation_success": "tools/call",
    "tool_invocation_success": "tools/call",
    "oauth_auth_failure": "tools/list",
    "token_auth_failure": "tools/list",
    "timeout_failure": "tools/list",
    "malformed_response": "tools/list",
    "provider_error_redaction": "tools/call",
}
EXPECTED_FILENAMES = {f"{case}.json": case for case in EXPECTED_CASES}
EXPECTED_REQUEST_HEADERS = {"authorization", "content-type"}
COMMON_FIXTURE_FIELDS = {
    "auth_mode",
    "case",
    "contract",
    "contract_version",
    "endpoint_path",
    "expected",
    "live",
    "request",
}
EXPECTED_FIELDS = {"outcome", "redacted"}
REQUEST_FIELDS = {"body", "headers", "method", "path"}
REQUEST_BODY_FIELDS = {"id", "jsonrpc", "method", "params"}
RESPONSE_FIELDS = {"body", "status_code"}
TIMEOUT_ERROR_FIELDS = {"message", "type"}

SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "jwt",
    "secret",
    "password",
)
RAW_TRANSCRIPT_KEY_RE = re.compile(r"(?i)raw[_ -]?transcript")
BEARER_VALUE_RE = re.compile(r"(?i)\bBearer\s+(?!<redacted>\b)[A-Za-z0-9._~+/=-]+")
TOKEN_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:token|jwt|secret|password)\s*[:=]\s*(?!<redacted>\b)[A-Za-z0-9._~+/=-]{8,}"
)
SCHEME_URL_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\"')>]+", re.IGNORECASE)
EXAMPLE_HOSTS = {"example.com", "example.invalid", "example.test"}


class _DuplicateJsonObjectNameError(ValueError):
    pass


class _NonFiniteJsonNumberError(ValueError):
    pass


def _reject_duplicate_object_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for name, value in pairs:
        if name in data:
            raise _DuplicateJsonObjectNameError
        data[name] = value
    return data


def _reject_non_finite_number(_value: str) -> NoReturn:
    raise _NonFiniteJsonNumberError


def _parse_finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise _NonFiniteJsonNumberError
    return number


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if path.stat().st_size > MAX_FIXTURE_BYTES:
        return None, f"{path}: fixture must not exceed {MAX_FIXTURE_BYTES} bytes"
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_object_names,
            parse_constant=_reject_non_finite_number,
            parse_float=_parse_finite_float,
        )
    except _DuplicateJsonObjectNameError:
        return None, f"{path}: fixture must not contain duplicate JSON object names"
    except _NonFiniteJsonNumberError:
        return None, f"{path}: fixture must not contain non-finite JSON numbers"
    except json.JSONDecodeError as exc:
        return None, f"{path}: invalid JSON: {exc}"
    if not isinstance(data, dict):
        return None, f"{path}: fixture must be a JSON object"
    return data, None


def _walk_json(
    value: Any,
    path: str = "$",
    object_name: str | None = None,
) -> Iterator[tuple[str, str | None, Any]]:
    yield path, object_name, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_json(child, f"{path}.{key}", str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json(child, f"{path}[{index}]")


def _is_redacted(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return normalized in {"<redacted>", "bearer <redacted>", "token <redacted>"}


def _contains_disallowed_url(value: str) -> bool:
    for match in SCHEME_URL_RE.finditer(value):
        try:
            parsed = urlsplit(match.group(0))
            port = parsed.port
        except ValueError:
            return True
        if parsed.scheme.lower() != "https":
            return True
        hostname = parsed.hostname.lower() if parsed.hostname is not None else None
        if hostname not in EXAMPLE_HOSTS:
            return True
        if parsed.username is not None or parsed.password is not None:
            return True
        if port is not None and not 1 <= port <= 65535:
            return True
    return False


def _exact_field_errors(
    path: Path,
    json_path: str,
    value: Mapping[str, Any],
    expected_fields: set[str],
) -> list[str]:
    if set(value) == expected_fields:
        return []
    names = ", ".join(sorted(expected_fields))
    return [f"{path}: {json_path} must contain exactly {names}"]


def _is_http_status(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599


def _is_provider_error_status(value: Any) -> bool:
    return _is_http_status(value) and value >= 400


def _sensitive_text_errors(path: Path, data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for json_path, object_name, value in _walk_json(data):
        key = object_name.lower() if object_name is not None else ""
        if RAW_TRANSCRIPT_KEY_RE.search(key):
            errors.append(f"{path}: {json_path} must not store raw MCP transcripts")
        if any(part in key for part in SENSITIVE_KEY_PARTS) and not _is_redacted(value):
            errors.append(f"{path}: {json_path} must contain only a redacted placeholder")
        if isinstance(value, str):
            if BEARER_VALUE_RE.search(value):
                errors.append(f"{path}: {json_path} contains an unredacted bearer value")
            if TOKEN_ASSIGNMENT_RE.search(value):
                errors.append(f"{path}: {json_path} contains an unredacted token assignment")
            if _contains_disallowed_url(value):
                errors.append(f"{path}: {json_path} contains a disallowed URL")
    return errors


def _request_header_errors(path: Path, request: Mapping[str, Any]) -> list[str]:
    headers = request.get("headers")
    if not isinstance(headers, Mapping):
        return [f"{path}: request.headers must be an object"]

    errors: list[str] = []
    normalized_headers: dict[str, Any] = {}
    for name, value in headers.items():
        normalized_name = str(name).strip().lower()
        if normalized_name in normalized_headers:
            errors.append(
                f"{path}: request.headers contains duplicate header {normalized_name!r}"
            )
            continue
        normalized_headers[normalized_name] = value

    if set(normalized_headers) != EXPECTED_REQUEST_HEADERS:
        errors.append(
            f"{path}: request.headers must contain exactly Authorization and Content-Type"
        )
    authorization = normalized_headers.get("authorization")
    if "authorization" in normalized_headers and not _is_redacted(authorization):
        errors.append(
            f"{path}: request.headers.Authorization must contain only a redacted placeholder"
        )
    content_type = normalized_headers.get("content-type")
    if "content-type" in normalized_headers and content_type != "application/json":
        errors.append(f"{path}: request.headers.Content-Type must be 'application/json'")
    return errors


def _request_params_errors(path: Path, method: str, params: Mapping[str, Any]) -> list[str]:
    if method == "tools/list":
        if params:
            return [f"{path}: tools/list request.body.params must be empty"]
        return []

    errors: list[str] = []
    if set(params) != {"name", "arguments"}:
        errors.append(
            f"{path}: tools/call request.body.params must contain exactly name and arguments"
        )
    name = params.get("name")
    if "name" in params and (not isinstance(name, str) or not name.strip()):
        errors.append(f"{path}: tools/call request.body.params.name must be a non-empty string")
    arguments = params.get("arguments")
    if "arguments" in params and not isinstance(arguments, Mapping):
        errors.append(f"{path}: tools/call request.body.params.arguments must be an object")
    return errors


def _success_result_errors(
    path: Path,
    request_method: str | None,
    result: Mapping[str, Any],
) -> list[str]:
    if request_method == "tools/list":
        tools = result.get("tools")
        if not isinstance(tools, list) or not tools:
            return [f"{path}: tools/list response.body.result.tools must be a non-empty list"]
    elif request_method == "tools/call":
        content = result.get("content")
        if not isinstance(content, list) or not content:
            return [f"{path}: tools/call response.body.result.content must be a non-empty list"]
    return []


def _error_envelope_errors(
    path: Path,
    error: Mapping[str, Any],
    *,
    outcome: str,
) -> list[str]:
    errors: list[str] = []
    code = error.get("code")
    if not isinstance(code, int) or isinstance(code, bool):
        errors.append(f"{path}: {outcome} fixture response.body.error.code must be an integer")
    message = error.get("message")
    if not isinstance(message, str) or not message.strip():
        errors.append(
            f"{path}: {outcome} fixture response.body.error.message must be a non-empty string"
        )
    return errors


def _response_shape_errors(
    path: Path,
    data: Mapping[str, Any],
    *,
    outcome: str,
    request_id: str | None,
    request_method: str | None,
) -> list[str]:
    errors: list[str] = []
    if outcome == "timeout":
        if "response" in data:
            errors.append(f"{path}: timeout fixture must not contain a response")
        error = data.get("error")
        if not isinstance(error, Mapping) or error.get("type") != "timeout":
            errors.append(f"{path}: timeout fixture error.type must be 'timeout'")
        else:
            errors.extend(_exact_field_errors(path, "error", error, TIMEOUT_ERROR_FIELDS))
            if not isinstance(error.get("message"), str) or not error["message"].strip():
                errors.append(f"{path}: timeout fixture error.message must be non-empty")
        return errors

    response = data.get("response")
    if not isinstance(response, Mapping):
        return [f"{path}: {outcome} fixture response must be an object"]
    errors.extend(_exact_field_errors(path, "response", response, RESPONSE_FIELDS))

    status_code = response.get("status_code")
    if not _is_http_status(status_code):
        errors.append(f"{path}: response.status_code must be an integer from 100 through 599")

    body = response.get("body")
    if outcome == "malformed_response":
        is_valid_envelope = (
            isinstance(body, Mapping)
            and body.get("jsonrpc") == "2.0"
            and body.get("id") == request_id
            and (("result" in body) != ("error" in body))
        )
        if is_valid_envelope:
            errors.append(
                f"{path}: malformed_response fixture must not contain a valid JSON-RPC envelope"
            )
        return errors

    if not isinstance(body, Mapping):
        return [*errors, f"{path}: response.body must be an object"]
    if body.get("jsonrpc") != "2.0":
        errors.append(f"{path}: response.body.jsonrpc must be '2.0'")
    if body.get("id") != request_id:
        errors.append(f"{path}: response.body.id must match request.body.id")

    has_result = "result" in body
    has_error = "error" in body
    if outcome == "success":
        if status_code != 200:
            errors.append(f"{path}: success fixture response.status_code must be 200")
        if not has_result or has_error:
            errors.append(f"{path}: success fixture must contain result and no error")
        elif not isinstance(body.get("result"), Mapping):
            errors.append(f"{path}: success fixture response.body.result must be an object")
        else:
            errors.extend(_success_result_errors(path, request_method, body["result"]))
    elif outcome == "auth_failure":
        if status_code not in {401, 403}:
            errors.append(f"{path}: auth_failure fixture status must be 401 or 403")
        if not has_error or has_result:
            errors.append(f"{path}: auth_failure fixture must contain error and no result")
        elif not isinstance(body.get("error"), Mapping):
            errors.append(f"{path}: auth_failure fixture response.body.error must be an object")
        else:
            errors.extend(_error_envelope_errors(path, body["error"], outcome=outcome))
    elif outcome == "provider_error":
        if not _is_provider_error_status(status_code):
            errors.append(f"{path}: provider_error fixture status must be from 400 through 599")
        if not has_error or has_result:
            errors.append(f"{path}: provider_error fixture must contain error and no result")
        elif not isinstance(body.get("error"), Mapping):
            errors.append(f"{path}: provider_error fixture response.body.error must be an object")
        else:
            errors.extend(_error_envelope_errors(path, body["error"], outcome=outcome))
    return errors


def validate_fixture_file(path: Path) -> list[str]:
    data, load_error = _load_json(path)
    if load_error:
        return [load_error]
    assert data is not None

    errors: list[str] = []
    case = data.get("case")
    expected = data.get("expected", {})
    request = data.get("request", {})
    expected_outcome: str | None = None
    expected_method = EXPECTED_REQUEST_METHODS.get(str(case))

    if case not in EXPECTED_CASES:
        errors.append(f"{path}: case must be one of {', '.join(sorted(EXPECTED_CASES))}")
    else:
        expected_auth_mode, expected_outcome = EXPECTED_CASES[str(case)]
        outcome_field = "error" if expected_outcome == "timeout" else "response"
        fixture_fields = {*COMMON_FIXTURE_FIELDS, outcome_field}
        errors.extend(_exact_field_errors(path, "fixture", data, fixture_fields))
        if data.get("auth_mode") != expected_auth_mode:
            errors.append(f"{path}: auth_mode must be {expected_auth_mode!r}")
        if not isinstance(expected, dict) or expected.get("outcome") != expected_outcome:
            errors.append(f"{path}: expected.outcome must be {expected_outcome!r}")
        if not isinstance(expected, dict) or expected.get("redacted") is not True:
            errors.append(f"{path}: expected.redacted must be true")
        if isinstance(expected, dict):
            errors.extend(_exact_field_errors(path, "expected", expected, EXPECTED_FIELDS))

    if data.get("contract") != CONTRACT_NAME:
        errors.append(f"{path}: contract must be {CONTRACT_NAME!r}")
    if data.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"{path}: contract_version must be {CONTRACT_VERSION!r}")
    if data.get("endpoint_path") != ENDPOINT_PATH:
        errors.append(f"{path}: endpoint_path must be {ENDPOINT_PATH!r}")
    if data.get("live") is not False:
        errors.append(f"{path}: live must be false for repo fixtures")

    request_id: str | None = None
    if not isinstance(request, dict):
        errors.append(f"{path}: request must be an object")
    else:
        errors.extend(_exact_field_errors(path, "request", request, REQUEST_FIELDS))
        if request.get("method") != "POST":
            errors.append(f"{path}: request.method must be 'POST'")
        if request.get("path") != ENDPOINT_PATH:
            errors.append(f"{path}: request.path must be {ENDPOINT_PATH!r}")
        errors.extend(_request_header_errors(path, request))
        body = request.get("body", {})
        if not isinstance(body, dict):
            errors.append(f"{path}: request.body must be an object")
        else:
            errors.extend(_exact_field_errors(path, "request.body", body, REQUEST_BODY_FIELDS))
            if body.get("jsonrpc") != "2.0":
                errors.append(f"{path}: request.body.jsonrpc must be '2.0'")
            raw_request_id = body.get("id")
            if not isinstance(raw_request_id, str) or not raw_request_id.strip():
                errors.append(f"{path}: request.body.id must be a non-empty string")
            else:
                request_id = raw_request_id
            if expected_method is not None and body.get("method") != expected_method:
                errors.append(f"{path}: request.body.method must be {expected_method!r}")
            params = body.get("params")
            if not isinstance(params, dict):
                errors.append(f"{path}: request.body.params must be an object")
            elif expected_method is not None:
                errors.extend(_request_params_errors(path, expected_method, params))

    if expected_outcome is not None:
        errors.extend(
            _response_shape_errors(
                path,
                data,
                outcome=expected_outcome,
                request_id=request_id,
                request_method=expected_method,
            )
        )

    errors.extend(_sensitive_text_errors(path, data))
    return errors


def validate_fixture_set(root: Path = FIXTURE_DIR) -> list[str]:
    errors: list[str] = []
    if not root.exists():
        return [f"{root}: fixture directory does not exist"]
    if root.is_symlink() or not root.is_dir():
        return [f"{root}: fixture root must be a regular directory"]

    seen: set[str] = set()
    for path in sorted(root.iterdir()):
        if path.is_symlink():
            errors.append(f"{path}: fixture inventory must not contain symbolic links")
            continue
        if not path.is_file():
            errors.append(f"{path}: fixture inventory must contain only regular files")
            continue
        expected_case = EXPECTED_FILENAMES.get(path.name)
        if expected_case is None:
            errors.append(f"{path}: unexpected artifact in closed fixture inventory")
            continue
        data, load_error = _load_json(path)
        if load_error:
            errors.append(load_error)
            continue
        assert data is not None
        case = data.get("case")
        if case != expected_case:
            errors.append(f"{path}: filename requires case {expected_case!r}")
        if isinstance(case, str):
            if case in seen:
                errors.append(f"{path}: duplicate fixture case {case!r}")
            seen.add(case)
        errors.extend(validate_fixture_file(path))

    missing = sorted(set(EXPECTED_CASES) - seen)
    for case in missing:
        errors.append(f"{root}: missing fixture case {case!r}")
    return errors


def main() -> int:
    errors = validate_fixture_set()
    if errors:
        print("AIQ Assist MCP fixture check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("AIQ Assist MCP fixtures OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
