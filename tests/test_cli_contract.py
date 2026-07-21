from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import cast

_RENDERER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_cli_contract.py"
_RENDERER_SPEC = importlib.util.spec_from_file_location("render_cli_contract", _RENDERER_PATH)
assert _RENDERER_SPEC is not None
assert _RENDERER_SPEC.loader is not None
render_cli_contract = importlib.util.module_from_spec(_RENDERER_SPEC)
sys.modules[_RENDERER_SPEC.name] = render_cli_contract
_RENDERER_SPEC.loader.exec_module(render_cli_contract)


def _fixture() -> dict:
    return cast(
        dict,
        json.loads(render_cli_contract.FIXTURE_PATH.read_text(encoding="utf-8")),
    )


def _command(contract: dict, path: str) -> dict:
    return next(command for command in contract["commands"] if command["path"] == path)


def _parameter(command: dict, name: str) -> dict:
    return next(parameter for parameter in command["parameters"] if parameter["name"] == name)


def test_committed_cli_contract_matches_typer_click_metadata():
    assert _fixture() == render_cli_contract.build_contract(), (
        "CLI metadata changed; review the stable contract and run "
        "scripts/render_cli_contract.py when the change is intentional"
    )


def test_cli_contract_fixture_captures_required_contract_dimensions():
    contract = _fixture()
    commands = contract["commands"]
    parameter_fields = {
        "count",
        "default",
        "envvar",
        "flag_value",
        "help",
        "hidden",
        "is_eager",
        "is_flag",
        "kind",
        "metavar",
        "multiple",
        "name",
        "nargs",
        "opts",
        "required",
        "secondary_opts",
        "show_choices",
        "show_default",
        "source",
        "type",
    }

    assert contract["schema_version"] == 1
    assert contract["root"] == "attackiq"
    assert contract["command_count"] == len(commands)
    assert contract["declared_parameter_count"] == sum(
        1
        for command in commands
        for parameter in command["parameters"]
        if parameter["source"] == "declared"
    )
    assert len({command["path"] for command in commands}) == len(commands)
    assert all(
        set(parameter) == parameter_fields
        for command in commands
        for parameter in command["parameters"]
    )
    assert all(
        parameter["opts"] for command in commands for parameter in command["parameters"]
    )
    assert all(
        sum(
            parameter["source"] == "automatic-help"
            and parameter["opts"] == ["--help"]
            for parameter in command["parameters"]
        )
        == 1
        for command in commands
    )

    root = _command(contract, "attackiq")
    version = _parameter(root, "_version")
    assert version["opts"] == ["--version", "-V"]
    assert version["required"] is False
    assert version["default"] is False

    spec_path = _parameter(root, "spec_path")
    assert spec_path["default"] == "package://attackiq_cli/openapi.yaml"
    assert spec_path["envvar"] == "ATTACKIQ_OPENAPI_PATH"
    assert spec_path["type"]["exists"] is True
    assert spec_path["type"]["readable"] is True

    scenario_id = _parameter(_command(contract, "attackiq scenarios show"), "scenario_id")
    assert scenario_id["kind"] == "argument"
    assert scenario_id["required"] is True
    assert scenario_id["default"] is None

    join_mode = _parameter(_command(contract, "attackiq join"), "mode")
    assert join_mode["kind"] == "argument"
    assert join_mode["required"] is False
    assert join_mode["default"] == "datasets"

    dry_run = _parameter(_command(contract, "attackiq join"), "dry_run")
    assert dry_run["opts"] == ["--dry-run"]
    assert dry_run["secondary_opts"] == ["--no-dry-run"]

    retries = _parameter(
        _command(contract, "attackiq export templates"), "scenario_details_retries"
    )
    assert retries["type"]["param_type"] == "IntRange"
    assert retries["type"]["min"] == 0
    assert retries["help"]
