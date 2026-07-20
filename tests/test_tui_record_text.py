from __future__ import annotations

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_record_text


def test_extract_id_supports_nested_and_scalar_values() -> None:
    assert tui_record_text._extract_id({"uuid": "nested-id"}) == "nested-id"
    assert tui_record_text._extract_id(42) == "42"
    assert tui_record_text._extract_id(None) is None


def test_scenario_record_text_summarizes_parameters_and_relationships() -> None:
    scenario = {
        "id": "scenario-1",
        "name": "Credential access",
        "parameters": [{"name": "target"}, {"key": "timeout"}],
        "capabilities": [{"name": "Windows"}, "Linux"],
        "scenario_template_instance": "template-1",
        "assessments": [{"id": "assessment-1"}],
    }

    assert "Scenario ID: scenario-1" in tui_record_text._build_scenario_metadata(scenario)
    assert tui_record_text._build_scenario_parameters(scenario) == "target, timeout"
    relationships = tui_record_text._build_scenario_relationships(scenario)
    assert "Capabilities: Windows, Linux" in relationships
    assert "Template Instance: template-1" in relationships
    assert "Assessments: 1" in relationships


def test_assessment_asset_and_test_text_helpers_preserve_fallbacks() -> None:
    assert tui_record_text._assessment_name({"assessment_id": "assessment-1"}) == "assessment-1"
    assert (
        tui_record_text._asset_deployment_state({"deployment_state": {"name": "Installed"}})
        == "Installed"
    )
    assert (
        tui_record_text._test_project({"project": {"display_name": "Template A"}})
        == "Template A"
    )


def test_tui_module_reexports_record_text_helpers_for_compatibility() -> None:
    assert tui_module._extract_scenario_id is tui_record_text._extract_scenario_id
    assert tui_module._build_scenario_parameters is tui_record_text._build_scenario_parameters
    assert tui_module._stringify is tui_record_text._stringify
