"""Validate AIQ Assist MCP provider-contract intake status."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "AIQ_ASSIST_MCP_PROVIDER_SOURCE.json"
ENDPOINT_PATH = "/aiq-assist/mcp"
CONTRACT_NAME = "aiq-assist-mcp-provider-source"
CONTRACT_VERSION = "v0"
PENDING_STATUS = "pending_provider_source"
DOCUMENTED_STATUS = "documented_provider_source"
SOURCE_ROOTS = (ROOT / "src" / "attackiq_cli", ROOT / "src" / "aiq_cli")

REQUIRED_SOURCE_PROPERTIES = {
    "transport",
    "mcp_protocol_version",
    "endpoint_path",
    "tenant_relative_url_rule",
    "oauth_auth",
    "token_auth",
    "discovery_request_response",
    "tool_invocation_request_response",
    "provider_error_shape",
    "timeout_retry_expectations",
    "redaction_rules",
    "live_test_opt_in",
}

FORBIDDEN_PENDING_SOURCE_MARKERS = (
    "/aiq-assist/mcp",
    "aiq_assist_mcp",
    "aiq_assist",
    "AIQ Assist MCP",
)


def _load_status(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{path}: provider source status file is missing"
    except json.JSONDecodeError as exc:
        return None, f"{path}: invalid JSON: {exc}"
    if not isinstance(data, dict):
        return None, f"{path}: provider source status must be a JSON object"
    return data, None


def _relative_doc_exists(value: Any) -> bool:
    return isinstance(value, str) and (ROOT / value).is_file()


def _none_or_empty(value: Any) -> bool:
    return value is None or value == ""


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _iter_python_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        yield from sorted(root.rglob("*.py"))


def _source_marker_errors(roots: Iterable[Path]) -> list[str]:
    errors: list[str] = []
    for path in _iter_python_files(roots):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_PENDING_SOURCE_MARKERS:
            if marker in text:
                rel_path = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
                errors.append(
                    f"{rel_path}: AIQ Assist MCP consumer code is blocked until the provider "
                    "wire-contract source is documented"
                )
                break
    return errors


def validate_provider_status(
    path: Path = STATUS_PATH,
    *,
    source_roots: Iterable[Path] = SOURCE_ROOTS,
) -> list[str]:
    data, load_error = _load_status(path)
    if load_error:
        return [load_error]
    assert data is not None

    errors: list[str] = []
    if data.get("contract") != CONTRACT_NAME:
        errors.append(f"{path}: contract must be {CONTRACT_NAME!r}")
    if data.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"{path}: contract_version must be {CONTRACT_VERSION!r}")
    if data.get("endpoint_path") != ENDPOINT_PATH:
        errors.append(f"{path}: endpoint_path must be {ENDPOINT_PATH!r}")
    if not _relative_doc_exists(data.get("consumer_contract")):
        errors.append(f"{path}: consumer_contract must point to an existing repo file")
    if not _relative_doc_exists(data.get("integration_card")):
        errors.append(f"{path}: integration_card must point to an existing repo file")
    if data.get("allow_live_mcp_checks") is not False:
        errors.append(f"{path}: allow_live_mcp_checks must stay false in the local quality gate")
    if not _non_empty_string(data.get("status_owner")):
        errors.append(f"{path}: status_owner is required for the repo-local gate")

    raw_required = data.get("required_source_properties")
    if not isinstance(raw_required, list) or not all(
        isinstance(item, str) for item in raw_required
    ):
        errors.append(f"{path}: required_source_properties must be a list of strings")
    else:
        missing = sorted(REQUIRED_SOURCE_PROPERTIES - set(raw_required))
        if missing:
            errors.append(f"{path}: missing required_source_properties: {', '.join(missing)}")

    status = data.get("status")
    if status not in {PENDING_STATUS, DOCUMENTED_STATUS}:
        errors.append(f"{path}: status must be {PENDING_STATUS!r} or {DOCUMENTED_STATUS!r}")
        return errors

    if status == PENDING_STATUS:
        for key in ("provider_contract_source", "provider_contract_version", "provider_owner"):
            if not _none_or_empty(data.get(key)):
                errors.append(f"{path}: {key} must be null while provider source is pending")
        if not _non_empty_string(data.get("provider_owner_status")):
            errors.append(
                f"{path}: provider_owner_status is required while provider source is pending"
            )
        if data.get("allow_cli_tui_consumption") is not False:
            errors.append(
                f"{path}: allow_cli_tui_consumption must be false while source is pending"
            )
        if not _non_empty_string(data.get("next_action")):
            errors.append(f"{path}: next_action is required while provider source is pending")
        errors.extend(_source_marker_errors(source_roots))
    else:
        for key in ("provider_contract_source", "provider_contract_version", "provider_owner"):
            if not _non_empty_string(data.get(key)):
                errors.append(f"{path}: {key} is required once provider source is documented")
        if (
            data.get("allow_cli_tui_consumption") is True
            and data.get("adapter_mock_tests") is not True
        ):
            errors.append(f"{path}: adapter_mock_tests must be true before CLI/TUI MCP consumption")

    return errors


def main() -> int:
    errors = validate_provider_status()
    if errors:
        print("AIQ Assist MCP provider contract check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("AIQ Assist MCP provider contract status OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
