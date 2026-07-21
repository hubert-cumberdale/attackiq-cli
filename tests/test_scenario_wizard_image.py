from attackiq_cli import scenario_wizard, scenario_wizard_image


def test_scenario_wizard_reexports_image_tar_symbols() -> None:
    assert (
        scenario_wizard.inspect_image_tar_runtime
        is scenario_wizard_image.inspect_image_tar_runtime
    )
    assert scenario_wizard.RUNTIME_SCRIPT_NAMES is scenario_wizard_image.RUNTIME_SCRIPT_NAMES
    assert (
        scenario_wizard.RUNTIME_BIN_SCRIPT_NAMES
        is scenario_wizard_image.RUNTIME_BIN_SCRIPT_NAMES
    )
    assert scenario_wizard._image_tar_index is scenario_wizard_image._image_tar_index
    assert (
        scenario_wizard._materialize_runtime_bundle_from_image_tar
        is scenario_wizard_image._materialize_runtime_bundle_from_image_tar
    )
    assert scenario_wizard._normalize_tar_path is scenario_wizard_image._normalize_tar_path
    assert scenario_wizard._safe_relative_path is scenario_wizard_image._safe_relative_path
    assert (
        scenario_wizard._sanitize_requirements_lock
        is scenario_wizard_image._sanitize_requirements_lock
    )
