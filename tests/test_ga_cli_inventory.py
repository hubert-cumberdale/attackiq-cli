from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import cast

_CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_ga_cli_inventory.py"
_CHECKER_SPEC = importlib.util.spec_from_file_location("check_ga_cli_inventory", _CHECKER_PATH)
assert _CHECKER_SPEC is not None
assert _CHECKER_SPEC.loader is not None
check_ga_cli_inventory = importlib.util.module_from_spec(_CHECKER_SPEC)
sys.modules[_CHECKER_SPEC.name] = check_ga_cli_inventory
_CHECKER_SPEC.loader.exec_module(check_ga_cli_inventory)


def _json(path: Path) -> dict:
    return cast(dict, json.loads(path.read_text(encoding="utf-8")))


def _document() -> str:
    return cast(str, check_ga_cli_inventory.DOCUMENT_PATH.read_text(encoding="utf-8"))


def test_ga_cli_inventory_matches_metadata_and_classifications():
    documented = check_ga_cli_inventory.parse_documented_inventory(_document())

    assert check_ga_cli_inventory.validate_inventory(
        documented,
        _json(check_ga_cli_inventory.CLI_FIXTURE_PATH),
        _json(check_ga_cli_inventory.CLASSIFICATION_PATH),
    ) == []


def test_new_documented_command_requires_explicit_classification():
    changed_document = _document().replace(
        "attackiq spec list\n  --tag",
        "attackiq spec\nattackiq spec list\n  --tag",
        1,
    )
    documented = check_ga_cli_inventory.parse_documented_inventory(changed_document)

    errors = check_ga_cli_inventory.validate_inventory(
        documented,
        _json(check_ga_cli_inventory.CLI_FIXTURE_PATH),
        _json(check_ga_cli_inventory.CLASSIFICATION_PATH),
    )

    assert "unclassified documented commands: attackiq spec" in errors
    assert "unclassified documented option command groups: attackiq spec" in errors
    assert not any("absent from CLI metadata" in error for error in errors)


def test_documented_option_absent_from_cli_metadata_is_rejected():
    changed_document = _document().replace(
        "--version/-V, --spec-path",
        "--version/-V, --not-a-real-option, --spec-path",
        1,
    )
    documented = check_ga_cli_inventory.parse_documented_inventory(changed_document)
    classifications = copy.deepcopy(_json(check_ga_cli_inventory.CLASSIFICATION_PATH))
    classifications["options"]["attackiq"]["--not-a-real-option"] = "proposed-stable"

    errors = check_ga_cli_inventory.validate_inventory(
        documented,
        _json(check_ga_cli_inventory.CLI_FIXTURE_PATH),
        classifications,
    )

    assert (
        "documented option absent from CLI metadata: attackiq --not-a-real-option" in errors
    )


def test_documented_command_absent_from_cli_metadata_is_rejected():
    changed_document = _document().replace(
        "attackiq spec list\n  --tag",
        "attackiq not-a-real-command\nattackiq spec list\n  --tag",
        1,
    )
    documented = check_ga_cli_inventory.parse_documented_inventory(changed_document)
    classifications = copy.deepcopy(_json(check_ga_cli_inventory.CLASSIFICATION_PATH))
    classifications["commands"]["attackiq not-a-real-command"] = "proposed-stable"
    classifications["options"]["attackiq not-a-real-command"] = {
        "--help": "proposed-stable"
    }

    errors = check_ga_cli_inventory.validate_inventory(
        documented,
        _json(check_ga_cli_inventory.CLI_FIXTURE_PATH),
        classifications,
    )

    assert "documented command absent from CLI metadata: attackiq not-a-real-command" in errors


def test_apply_and_experimental_surfaces_remain_excluded():
    classifications = _json(check_ga_cli_inventory.CLASSIFICATION_PATH)

    assert classifications["commands"]["attackiq platform-api parity"] == "excluded"
    assert all(
        value == "excluded"
        for value in classifications["options"]["attackiq platform-api parity"].values()
    )
    assert all(
        options.get("--apply") in {None, "excluded"}
        for options in classifications["options"].values()
    )
    assert classifications["option_values"] == {
        "attackiq assets list": {"--api-backend=platform-api": "excluded"},
        "attackiq scenarios list": {"--api-backend=platform-api": "excluded"},
    }

    unsafe = copy.deepcopy(classifications)
    unsafe["commands"]["attackiq platform-api parity"] = "proposed-stable"
    unsafe["options"]["attackiq assessments create"]["--apply"] = "proposed-stable"
    unsafe["option_values"]["attackiq assets list"][
        "--api-backend=platform-api"
    ] = "proposed-stable"
    errors = check_ga_cli_inventory.validate_inventory(
        check_ga_cli_inventory.parse_documented_inventory(_document()),
        _json(check_ga_cli_inventory.CLI_FIXTURE_PATH),
        unsafe,
    )

    assert "experimental command must remain excluded: attackiq platform-api parity" in errors
    assert "apply option must remain excluded: attackiq assessments create --apply" in errors
    assert (
        "experimental option value must remain excluded: "
        "attackiq assets list --api-backend=platform-api"
    ) in errors
