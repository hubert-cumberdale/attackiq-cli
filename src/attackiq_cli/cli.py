from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import typer
from rich.console import Console

from attackiq_cli import __version__
from attackiq_cli.cli_assessment_schedules import (
    assessment_schedules_app,
)
from attackiq_cli.cli_assessment_schedules import (
    list_assessment_schedules as list_assessment_schedules,
)
from attackiq_cli.cli_assessments import (
    AssessmentFilters as AssessmentFilters,
)
from attackiq_cli.cli_assessments import (
    assessments_app,
)
from attackiq_cli.cli_assessments import (
    create_assessment as create_assessment,
)
from attackiq_cli.cli_assessments import (
    create_assessment_from_template as create_assessment_from_template,
)
from attackiq_cli.cli_assessments import (
    list_assessments as list_assessments,
)
from attackiq_cli.cli_assessments import (
    run_assessment as run_assessment,
)
from attackiq_cli.cli_assessments import (
    show_assessment as show_assessment,
)
from attackiq_cli.cli_assessments import (
    update_assessment_defaults as update_assessment_defaults,
)
from attackiq_cli.cli_asset_groups import (
    asset_groups_app,
)
from attackiq_cli.cli_asset_groups import (
    list_asset_groups as list_asset_groups,
)
from attackiq_cli.cli_asset_groups import (
    show_asset_group as show_asset_group,
)
from attackiq_cli.cli_assets import (
    assets_app,
)
from attackiq_cli.cli_assets import (
    list_assets as list_assets,
)
from attackiq_cli.cli_assets import (
    show_asset as show_asset,
)
from attackiq_cli.cli_backup import (
    backup_app,
)
from attackiq_cli.cli_backup import (
    backup_configs as backup_configs,
)
from attackiq_cli.cli_blueprints import (
    blueprints_app,
)
from attackiq_cli.cli_blueprints import (
    list_blueprints as list_blueprints,
)
from attackiq_cli.cli_build import (
    build_app,
)
from attackiq_cli.cli_build import (
    build_assessment_app as build_assessment_app,
)
from attackiq_cli.cli_build import (
    build_assessment_from_template as build_assessment_from_template,
)
from attackiq_cli.cli_build import (
    build_test_add_scenarios as build_test_add_scenarios,
)
from attackiq_cli.cli_build import (
    build_test_app as build_test_app,
)
from attackiq_cli.cli_build import (
    build_test_create as build_test_create,
)
from attackiq_cli.cli_call import (
    call as call,
)
from attackiq_cli.cli_call import (
    coerce_params as coerce_params,
)
from attackiq_cli.cli_call import (
    handle_response as handle_response,
)
from attackiq_cli.cli_call import (
    parse_cookie_header as parse_cookie_header,
)
from attackiq_cli.cli_call import (
    parse_form_files as parse_form_files,
)
from attackiq_cli.cli_call import (
    prompt_for_body as prompt_for_body,
)
from attackiq_cli.cli_call import (
    prompt_for_missing_required as prompt_for_missing_required,
)
from attackiq_cli.cli_call import (
    segregate_params as segregate_params,
)
from attackiq_cli.cli_call import (
    validate_header_values as validate_header_values,
)
from attackiq_cli.cli_catalog import (
    catalog_app,
)
from attackiq_cli.cli_catalog import (
    list_catalog_records as list_catalog_records,
)
from attackiq_cli.cli_catalog import (
    summarize_catalog_coverage as summarize_catalog_coverage,
)
from attackiq_cli.cli_catalog import (
    validate_catalog as validate_catalog,
)
from attackiq_cli.cli_config import (
    auth_app,
    config_app,
)
from attackiq_cli.cli_config import (
    clear_auth as clear_auth,
)
from attackiq_cli.cli_config import (
    mask_secret as mask_secret,
)
from attackiq_cli.cli_config import (
    set_auth as set_auth,
)
from attackiq_cli.cli_config import (
    set_config as set_config,
)
from attackiq_cli.cli_config import (
    show_config as show_config,
)
from attackiq_cli.cli_config import (
    validate_config as validate_config,
)
from attackiq_cli.cli_edr_scan_schedules import (
    edr_scan_schedules_app,
)
from attackiq_cli.cli_edr_scan_schedules import (
    list_edr_scan_schedules as list_edr_scan_schedules,
)
from attackiq_cli.cli_export import (
    export_app,
)
from attackiq_cli.cli_export import (
    export_assessments as export_assessments,
)
from attackiq_cli.cli_export import (
    export_scenarios as export_scenarios,
)
from attackiq_cli.cli_export import (
    export_templates as export_templates,
)
from attackiq_cli.cli_export import (
    export_tests as export_tests,
)
from attackiq_cli.cli_integrations import (
    integrations_app,
)
from attackiq_cli.cli_integrations import (
    list_integrations as list_integrations,
)
from attackiq_cli.cli_join import (
    join_exports as join_exports,
)
from attackiq_cli.cli_platform_api import (
    platform_api_app,
)
from attackiq_cli.cli_platform_api import (
    platform_api_parity as platform_api_parity,
)
from attackiq_cli.cli_results import (
    list_result_logs as list_result_logs,
)
from attackiq_cli.cli_results import (
    list_result_phases as list_result_phases,
)
from attackiq_cli.cli_results import (
    list_results as list_results,
)
from attackiq_cli.cli_results import (
    results_app,
)
from attackiq_cli.cli_scenario_wizard import (
    inspect_scenario_wizard_runtime as inspect_scenario_wizard_runtime,
)
from attackiq_cli.cli_scenario_wizard import (
    package_scenario_wizard_scenario as package_scenario_wizard_scenario,
)
from attackiq_cli.cli_scenario_wizard import (
    plan_scenario_wizard_create as plan_scenario_wizard_create,
)
from attackiq_cli.cli_scenario_wizard import (
    prepare_scenario_wizard_runtime as prepare_scenario_wizard_runtime,
)
from attackiq_cli.cli_scenario_wizard import (
    scenario_wizard_app as scenario_wizard_app,
)
from attackiq_cli.cli_scenario_wizard import (
    scenario_wizard_runtime_app as scenario_wizard_runtime_app,
)
from attackiq_cli.cli_scenario_wizard import (
    validate_scenario_wizard_runtime as validate_scenario_wizard_runtime,
)
from attackiq_cli.cli_scenarios import (
    list_scenarios as list_scenarios,
)
from attackiq_cli.cli_scenarios import (
    scenarios_app,
)
from attackiq_cli.cli_scenarios import (
    show_scenario as show_scenario,
)
from attackiq_cli.cli_scenarios import (
    upload_scenario_packages as upload_scenario_packages,
)
from attackiq_cli.cli_source_types import (
    list_source_types as list_source_types,
)
from attackiq_cli.cli_source_types import (
    source_types_app,
)
from attackiq_cli.cli_spec import (
    format_security as format_security,
)
from attackiq_cli.cli_spec import (
    list_operations as list_operations,
)
from attackiq_cli.cli_spec import (
    normalize_spec_fields as normalize_spec_fields,
)
from attackiq_cli.cli_spec import (
    render_operations_table as render_operations_table,
)
from attackiq_cli.cli_spec import (
    search_operations as search_operations,
)
from attackiq_cli.cli_spec import (
    show_operation as show_operation,
)
from attackiq_cli.cli_spec import (
    slice_operations as slice_operations,
)
from attackiq_cli.cli_spec import (
    spec_app,
)
from attackiq_cli.cli_tags import (
    list_tags as list_tags,
)
from attackiq_cli.cli_tags import (
    search_tags as search_tags,
)
from attackiq_cli.cli_tags import (
    show_tag as show_tag,
)
from attackiq_cli.cli_tags import (
    tags_app,
)
from attackiq_cli.cli_templates import (
    list_template_tests as list_template_tests,
)
from attackiq_cli.cli_templates import (
    list_templates as list_templates,
)
from attackiq_cli.cli_templates import (
    show_template as show_template,
)
from attackiq_cli.cli_templates import (
    templates_app,
)
from attackiq_cli.cli_tests import (
    TestFilters as TestFilters,
)
from attackiq_cli.cli_tests import (
    add_test_scenarios as add_test_scenarios,
)
from attackiq_cli.cli_tests import (
    create_test as create_test,
)
from attackiq_cli.cli_tests import (
    get_test_status as get_test_status,
)
from attackiq_cli.cli_tests import (
    list_tests as list_tests,
)
from attackiq_cli.cli_tests import (
    show_test as show_test,
)
from attackiq_cli.cli_tests import (
    tests_app,
)
from attackiq_cli.cli_tui import (
    tui as tui,
)
from attackiq_cli.cli_validation_results import (
    list_validation_result_asset_executions as list_validation_result_asset_executions,
)
from attackiq_cli.cli_validation_results import (
    list_validation_result_scenario_executions as list_validation_result_scenario_executions,
)
from attackiq_cli.cli_validation_results import (
    list_validation_results as list_validation_results,
)
from attackiq_cli.cli_validation_results import (
    list_validation_results_by_asset as list_validation_results_by_asset,
)
from attackiq_cli.cli_validation_results import (
    validation_results_app,
)
from attackiq_cli.services import (
    build_client as build_client,
)

console = Console()
default_spec_path = Path(__file__).resolve().parent / "openapi.yaml"
COMPLETION_SHELL_ALIASES = {
    "bash": "bash",
    "fish": "fish",
    "powershell": "powershell",
    "powershell.exe": "powershell",
    "pwsh": "pwsh",
    "pwsh.exe": "pwsh",
    "zsh": "zsh",
}


def _completion_shell_from_env() -> str | None:
    raw = os.getenv("ATTACKIQ_COMPLETION_SHELL") or os.getenv("SHELL") or ""
    shell_name = Path(raw).name.lower()
    return COMPLETION_SHELL_ALIASES.get(shell_name)


def _patch_typer_completion_shell_detection() -> None:
    try:
        import typer.completion as typer_completion
    except ImportError:  # pragma: no cover - Typer is a required dependency.
        return

    shellingham = getattr(typer_completion, "shellingham", None)
    if shellingham is None or getattr(shellingham, "_attackiq_env_shell_fallback", False):
        return

    original_detect_shell = shellingham.detect_shell

    def detect_shell_with_env_fallback(*args: Any, **kwargs: Any) -> tuple[str, str | None]:
        if env_shell := _completion_shell_from_env():
            return env_shell, None
        return cast(tuple[str, str | None], original_detect_shell(*args, **kwargs))

    shellingham.detect_shell = detect_shell_with_env_fallback
    shellingham._attackiq_env_shell_fallback = True


_patch_typer_completion_shell_detection()

def _typer(**kwargs: Any) -> typer.Typer:
    return typer.Typer(pretty_exceptions_show_locals=False, **kwargs)


app = _typer(add_completion=True, no_args_is_help=True)

app.command("call")(call)
app.command("join", help="Join AttackIQ exports with GitLab issues.")(join_exports)
app.command("tui")(tui)
app.add_typer(spec_app, name="spec")
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")
app.add_typer(export_app, name="export")
app.add_typer(backup_app, name="backup")
app.add_typer(catalog_app, name="catalog")
app.add_typer(scenario_wizard_app, name="scenario-wizard")
app.add_typer(scenarios_app, name="scenarios")
app.add_typer(tags_app, name="tags")
app.add_typer(templates_app, name="templates")
app.add_typer(platform_api_app, name="platform-api")
app.add_typer(assessments_app, name="assessments")
app.add_typer(assessment_schedules_app, name="assessment-schedules")
app.add_typer(tests_app, name="tests")
app.add_typer(assets_app, name="assets")
app.add_typer(asset_groups_app, name="asset-groups")
app.add_typer(blueprints_app, name="blueprints")
app.add_typer(integrations_app, name="integrations")
app.add_typer(edr_scan_schedules_app, name="edr-scan-schedules")
app.add_typer(source_types_app, name="source-types")
app.add_typer(results_app, name="results")
app.add_typer(validation_results_app, name="validation-results")
app.add_typer(build_app, name="build")


def version_callback(value: bool) -> None:
    if value:
        console.print(f"attackiq-cli version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        is_flag=True,
        help="Show version and exit.",
    ),
    spec_path: Path = typer.Option(
        default_spec_path,
        "--spec-path",
        envvar="ATTACKIQ_OPENAPI_PATH",
        exists=True,
        readable=True,
        help="Path to the OpenAPI 3.0 schema to load.",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["spec_path"] = spec_path


def app_main() -> None:  # pragma: no cover - console entrypoint
    app()


if __name__ == "__main__":  # pragma: no cover
    app_main()
