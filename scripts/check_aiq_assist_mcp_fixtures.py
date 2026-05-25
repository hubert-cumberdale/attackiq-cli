"""Validate synthetic AIQ Assist MCP consumer-contract fixtures."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "aiq_assist_mcp"
CONTRACT_NAME = "aiq-assist-mcp-consumer"
CONTRACT_VERSION = "v0"
ENDPOINT_PATH = "/aiq-assist/mcp"

EXPECTED_CASES = {
    "discovery_success": ("oauth", "success"),
    "tool_invocation_success": ("token", "success"),
    "oauth_auth_failure": ("oauth", "auth_failure"),
    "token_auth_failure": ("token", "auth_failure"),
    "timeout_failure": ("oauth", "timeout"),
    "malformed_response": ("token", "malformed_response"),
    "provider_error_redaction": ("token", "provider_error"),
}

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
PRIVATE_URL_RE = re.compile(r"https?://(?!example\.(?:com|invalid|test)\b)[^\s\"')>]+")


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"{path}: invalid JSON: {exc}"
    if not isinstance(data, dict):
        return None, f"{path}: fixture must be a JSON object"
    return data, None


def _walk_json(value: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_json(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json(child, f"{path}[{index}]")


def _is_redacted(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return normalized in {"<redacted>", "bearer <redacted>", "token <redacted>"} or (
        "<redacted>" in normalized and not BEARER_VALUE_RE.search(value)
    )


def _sensitive_text_errors(path: Path, data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for json_path, value in _walk_json(data):
        key = json_path.rsplit(".", 1)[-1].lower()
        if RAW_TRANSCRIPT_KEY_RE.search(key):
            errors.append(f"{path}: {json_path} must not store raw MCP transcripts")
        if any(part in key for part in SENSITIVE_KEY_PARTS) and not _is_redacted(value):
            if isinstance(value, str) and value in {"oauth", "token"}:
                continue
            errors.append(f"{path}: {json_path} must contain only a redacted placeholder")
        if isinstance(value, str):
            if BEARER_VALUE_RE.search(value):
                errors.append(f"{path}: {json_path} contains an unredacted bearer value")
            if TOKEN_ASSIGNMENT_RE.search(value):
                errors.append(f"{path}: {json_path} contains an unredacted token assignment")
            if PRIVATE_URL_RE.search(value):
                errors.append(f"{path}: {json_path} contains a non-example URL")
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

    if case not in EXPECTED_CASES:
        errors.append(f"{path}: case must be one of {', '.join(sorted(EXPECTED_CASES))}")
    else:
        expected_auth_mode, expected_outcome = EXPECTED_CASES[str(case)]
        if data.get("auth_mode") != expected_auth_mode:
            errors.append(f"{path}: auth_mode must be {expected_auth_mode!r}")
        if not isinstance(expected, dict) or expected.get("outcome") != expected_outcome:
            errors.append(f"{path}: expected.outcome must be {expected_outcome!r}")

    if data.get("contract") != CONTRACT_NAME:
        errors.append(f"{path}: contract must be {CONTRACT_NAME!r}")
    if data.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"{path}: contract_version must be {CONTRACT_VERSION!r}")
    if data.get("endpoint_path") != ENDPOINT_PATH:
        errors.append(f"{path}: endpoint_path must be {ENDPOINT_PATH!r}")
    if data.get("live") is not False:
        errors.append(f"{path}: live must be false for repo fixtures")

    if not isinstance(request, dict):
        errors.append(f"{path}: request must be an object")
    else:
        if request.get("method") != "POST":
            errors.append(f"{path}: request.method must be 'POST'")
        if request.get("path") != ENDPOINT_PATH:
            errors.append(f"{path}: request.path must be {ENDPOINT_PATH!r}")
        body = request.get("body", {})
        if isinstance(body, dict) and body.get("jsonrpc") != "2.0":
            errors.append(f"{path}: request.body.jsonrpc must be '2.0'")
        elif not isinstance(body, dict):
            errors.append(f"{path}: request.body must be an object")

    errors.extend(_sensitive_text_errors(path, data))
    return errors


def validate_fixture_set(root: Path = FIXTURE_DIR) -> list[str]:
    errors: list[str] = []
    if not root.exists():
        return [f"{root}: fixture directory does not exist"]

    seen: set[str] = set()
    for path in sorted(root.glob("*.json")):
        data, load_error = _load_json(path)
        if load_error:
            errors.append(load_error)
            continue
        assert data is not None
        case = data.get("case")
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
