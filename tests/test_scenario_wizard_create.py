from attackiq_cli import scenario_wizard, scenario_wizard_create


def test_scenario_wizard_reexports_create_planning_symbols() -> None:
    assert scenario_wizard.CREATE_SCENARIO_SNIPPET is scenario_wizard_create.CREATE_SCENARIO_SNIPPET
    assert (
        scenario_wizard.build_scenario_wizard_create_plan
        is scenario_wizard_create.build_scenario_wizard_create_plan
    )
