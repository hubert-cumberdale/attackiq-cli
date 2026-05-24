from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_script_module(name: str):
    module_path = Path(__file__).resolve().parent.parent / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render_deep_dives = _load_script_module("render_deep_dives")
verify_deep_dives = _load_script_module("verify_deep_dives")


class _DummyCalled(Exception):
    pass


def test_contract_schema_validation_requires_core_keys() -> None:
    contract = {
        "version": 1,
        "domain": "call",
    }
    with pytest.raises(ValueError, match="Missing required contract keys"):
        render_deep_dives.validate_contract(contract)


def test_renderer_is_deterministic_for_call_contract() -> None:
    contracts = render_deep_dives.load_contracts(domains={"call"})
    assert len(contracts) == 1
    contract = contracts[0]

    first = render_deep_dives.render_contract(contract)
    second = render_deep_dives.render_contract(contract)

    assert first == second
    assert "# `attackiq call` Execution Flow" in first
    assert "## Command surface" in first
    assert "`src/attackiq_cli/cli.py` -> `call`" in first


def test_verifier_reports_render_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    contract = {
        "version": 1,
        "domain": "tmp",
        "title": "Temp",
        "summary": "Temp summary",
        "template": "docs/contracts/templates/deep_dive.md.j2",
        "generated_doc": "docs/TMP_FLOW.md",
        "command_surface": {"command": "attackiq tmp", "options": []},
        "invariants": ["always true"],
        "artifacts": ["none"],
        "code_references": [{"path": "src/attackiq_cli/cli.py", "symbol": "call"}],
        "test_references": [{"path": "tests/test_cli_call.py"}],
        "help_checks": [{"command": ["attackiq", "--help"], "options": ["call"]}],
    }

    target_doc = tmp_path / "docs" / "TMP_FLOW.md"
    target_doc.parent.mkdir(parents=True, exist_ok=True)
    target_doc.write_text("outdated\n", encoding="utf-8")

    monkeypatch.setattr(render_deep_dives, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(render_deep_dives, "CONTRACTS_DIR", tmp_path / "docs" / "contracts")
    monkeypatch.setattr(verify_deep_dives, "REPO_ROOT", tmp_path)

    (tmp_path / "docs" / "contracts" / "templates").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "contracts" / "templates" / "deep_dive.md.j2").write_text(
        "# {{TITLE}}\n\n{{SUMMARY}}\n",
        encoding="utf-8",
    )

    (tmp_path / "src" / "attackiq_cli").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "attackiq_cli" / "cli.py").write_text(
        "def call() -> None:\n    pass\n",
        encoding="utf-8",
    )

    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_cli_call.py").write_text(
        "def test_ok():\n    pass\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(verify_deep_dives, "run_help_command", lambda _args: "call\n")

    errors = verify_deep_dives.collect_verification_errors([contract])
    assert any(item.startswith("render drift:") for item in errors)
