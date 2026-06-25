from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_aiq_assist_mcp_contract.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("check_aiq_assist_mcp_contract", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
contract_check = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = contract_check
_SCRIPT_SPEC.loader.exec_module(contract_check)


def _pending_status() -> dict[str, object]:
    return {
        "contract": contract_check.CONTRACT_NAME,
        "contract_version": contract_check.CONTRACT_VERSION,
        "endpoint_path": contract_check.ENDPOINT_PATH,
        "status": contract_check.PENDING_STATUS,
        "provider_contract_source": None,
        "provider_contract_version": None,
        "provider_owner": None,
        "provider_owner_status": "pending_named_aiq_assist_mcp_service_owner",
        "status_owner": "aiq-cli maintainers",
        "consumer_contract": "docs/AIQ_ASSIST_MCP_CONTRACT.md",
        "integration_card": "docs/integration-cards/AIQ_ASSIST_MCP.md",
        "allow_cli_tui_consumption": False,
        "allow_live_mcp_checks": False,
        "last_reviewed": "2026-05-21",
        "next_action": "Obtain provider source.",
        "required_source_properties": sorted(contract_check.REQUIRED_SOURCE_PROPERTIES),
    }


def test_repo_provider_source_status_passes_gate() -> None:
    assert contract_check.validate_provider_status() == []


def test_provider_source_status_blocks_consumption_while_pending(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status = _pending_status()
    status["allow_cli_tui_consumption"] = True
    status_path.write_text(json.dumps(status), encoding="utf-8")

    errors = contract_check.validate_provider_status(status_path, source_roots=())

    assert any("allow_cli_tui_consumption must be false" in error for error in errors)


def test_provider_source_status_requires_repo_status_owner(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status = _pending_status()
    status.pop("status_owner")
    status_path.write_text(json.dumps(status), encoding="utf-8")

    errors = contract_check.validate_provider_status(status_path, source_roots=())

    assert any("status_owner is required" in error for error in errors)


def test_provider_source_status_requires_pending_provider_owner_status(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status = _pending_status()
    status.pop("provider_owner_status")
    status_path.write_text(json.dumps(status), encoding="utf-8")

    errors = contract_check.validate_provider_status(status_path, source_roots=())

    assert any("provider_owner_status is required" in error for error in errors)


def test_provider_source_status_scans_for_pending_consumer_code(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(_pending_status()), encoding="utf-8")
    source_root = tmp_path / "src" / "attackiq_cli"
    source_root.mkdir(parents=True)
    (source_root / "aiq_assist.py").write_text(
        'ENDPOINT = "/aiq-assist/mcp"\n',
        encoding="utf-8",
    )

    errors = contract_check.validate_provider_status(status_path, source_roots=(source_root,))

    assert any("consumer code is blocked" in error for error in errors)
