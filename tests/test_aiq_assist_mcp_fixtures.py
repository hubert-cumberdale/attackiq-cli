from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_aiq_assist_mcp_fixtures.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("check_aiq_assist_mcp_fixtures", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
fixture_check = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = fixture_check
_SCRIPT_SPEC.loader.exec_module(fixture_check)


def test_repo_aiq_assist_mcp_fixtures_pass_contract_gate() -> None:
    assert fixture_check.validate_fixture_set() == []


def test_fixture_gate_rejects_unredacted_bearer_value(tmp_path: Path) -> None:
    fixture_path = tmp_path / "provider_error_redaction.json"
    fixture = {
        "case": "provider_error_redaction",
        "contract": fixture_check.CONTRACT_NAME,
        "contract_version": fixture_check.CONTRACT_VERSION,
        "endpoint_path": fixture_check.ENDPOINT_PATH,
        "live": False,
        "auth_mode": "token",
        "request": {
            "method": "POST",
            "path": fixture_check.ENDPOINT_PATH,
            "body": {
                "jsonrpc": "2.0",
                "id": "fixture-provider-error",
                "method": "tools/call",
                "params": {},
            },
        },
        "response": {
            "status_code": 502,
            "body": {
                "jsonrpc": "2.0",
                "id": "fixture-provider-error",
                "error": {
                    "message": "Provider rejected Authorization: Bearer live-secret-token"
                },
            },
        },
        "expected": {"outcome": "provider_error", "redacted": True},
    }
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    errors = fixture_check.validate_fixture_file(fixture_path)

    assert any("unredacted bearer value" in error for error in errors)


def test_fixture_gate_requires_complete_case_set(tmp_path: Path) -> None:
    errors = fixture_check.validate_fixture_set(tmp_path)

    assert any("missing fixture case 'discovery_success'" in error for error in errors)
