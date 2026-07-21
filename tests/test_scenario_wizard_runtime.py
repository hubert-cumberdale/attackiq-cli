from attackiq_cli import scenario_wizard, scenario_wizard_runtime


def test_scenario_wizard_reexports_bundle_runtime_symbols() -> None:
    assert (
        scenario_wizard.ENV_SCENARIO_WIZARD_CACHE_DIR
        is scenario_wizard_runtime.ENV_SCENARIO_WIZARD_CACHE_DIR
    )
    assert scenario_wizard.RUNTIME_SENTINELS is scenario_wizard_runtime.RUNTIME_SENTINELS
    assert (
        scenario_wizard.build_runtime_prepare_plan
        is scenario_wizard_runtime.build_runtime_prepare_plan
    )
    assert scenario_wizard.inspect_runtime_bundle is scenario_wizard_runtime.inspect_runtime_bundle
    assert (
        scenario_wizard.inspect_scenario_wizard_zip
        is scenario_wizard_runtime.inspect_scenario_wizard_zip
    )
    assert (
        scenario_wizard.prepare_runtime_bundle_from_bundle
        is scenario_wizard_runtime.prepare_runtime_bundle_from_bundle
    )
    assert (
        scenario_wizard.scenario_wizard_cache_dir
        is scenario_wizard_runtime.scenario_wizard_cache_dir
    )
