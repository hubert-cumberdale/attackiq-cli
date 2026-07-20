from __future__ import annotations

from pathlib import Path

from rich.console import Console

from attackiq_cli.config import (
    ConfigError,
)
from attackiq_cli.exporter import (
    ASSESSMENT_FIELD_ORDER as ASSESSMENT_FIELD_ORDER,
)
from attackiq_cli.exporter import (
    SCENARIO_FIELD_ORDER as SCENARIO_FIELD_ORDER,
)
from attackiq_cli.exporter import (
    TEST_FIELD_ORDER as TEST_FIELD_ORDER,
)
from attackiq_cli.services import (
    AssessmentFilters as AssessmentFilters,
)
from attackiq_cli.services import (
    ScenarioFilters as ScenarioFilters,
)
from attackiq_cli.services import (
    build_assessment_query_params as build_assessment_query_params,
)
from attackiq_cli.services import (
    build_assessment_summary_records as build_assessment_summary_records,
)
from attackiq_cli.services import (
    build_asset_summary_records as build_asset_summary_records,
)
from attackiq_cli.services import (
    build_scenario_summary_records as build_scenario_summary_records,
)
from attackiq_cli.services import (
    build_test_summary_records as build_test_summary_records,
)
from attackiq_cli.services import (
    load_service_context,
)
from attackiq_cli.tui_app import AttackIQTuiApp
from attackiq_cli.tui_assessments import AssessmentsTab as AssessmentsTab
from attackiq_cli.tui_assets import WorkflowAssetsTab as WorkflowAssetsTab
from attackiq_cli.tui_display import (
    _format_runtime_error as _format_runtime_error,
)
from attackiq_cli.tui_display import (
    _palette_entry_matches as _palette_entry_matches,
)
from attackiq_cli.tui_display import (
    _palette_group_hint as _palette_group_hint,
)
from attackiq_cli.tui_display import (
    _tab_shortcuts_text as _tab_shortcuts_text,
)
from attackiq_cli.tui_domains import (
    CommandPaletteEntry as CommandPaletteEntry,
)
from attackiq_cli.tui_domains import (
    allowed_command_ids_for_tab as allowed_command_ids_for_tab,
)
from attackiq_cli.tui_domains import (
    build_command_palette_entries as build_command_palette_entries,
)
from attackiq_cli.tui_domains import (
    filter_help_for_tab as filter_help_for_tab,
)
from attackiq_cli.tui_domains import (
    focus_prefix_for_tab as focus_prefix_for_tab,
)
from attackiq_cli.tui_domains import (
    tab_id_for_short_name as tab_id_for_short_name,
)
from attackiq_cli.tui_exports import (
    _utc_timestamp as _utc_timestamp,
)
from attackiq_cli.tui_exports import (
    build_tui_export_path as build_tui_export_path,
)
from attackiq_cli.tui_exports import (
    write_tui_export as write_tui_export,
)
from attackiq_cli.tui_filters import (
    _clean_filter_value as _clean_filter_value,
)
from attackiq_cli.tui_filters import (
    _parse_assessment_filter as _parse_assessment_filter,
)
from attackiq_cli.tui_filters import (
    _parse_asset_filter as _parse_asset_filter,
)
from attackiq_cli.tui_filters import (
    _parse_filter_bool as _parse_filter_bool,
)
from attackiq_cli.tui_filters import (
    _parse_filter_int as _parse_filter_int,
)
from attackiq_cli.tui_filters import (
    _parse_filter_list as _parse_filter_list,
)
from attackiq_cli.tui_filters import (
    _parse_results_filter as _parse_results_filter,
)
from attackiq_cli.tui_filters import (
    _parse_scenario_filter as _parse_scenario_filter,
)
from attackiq_cli.tui_filters import (
    _parse_test_filter as _parse_test_filter,
)
from attackiq_cli.tui_filters import (
    _resolve_assessments_sort as _resolve_assessments_sort,
)
from attackiq_cli.tui_filters import (
    _resolve_assets_sort as _resolve_assets_sort,
)
from attackiq_cli.tui_filters import (
    _resolve_results_sort as _resolve_results_sort,
)
from attackiq_cli.tui_filters import (
    _resolve_results_source_filter as _resolve_results_source_filter,
)
from attackiq_cli.tui_filters import (
    _resolve_scenarios_sort as _resolve_scenarios_sort,
)
from attackiq_cli.tui_filters import (
    _resolve_tests_sort as _resolve_tests_sort,
)
from attackiq_cli.tui_preview import (
    AssessmentDefaultsPreviewScreen as AssessmentDefaultsPreviewScreen,
)
from attackiq_cli.tui_preview import (
    AssessmentFromTemplatePreviewScreen as AssessmentFromTemplatePreviewScreen,
)
from attackiq_cli.tui_preview import (
    AssessmentRunPreviewScreen as AssessmentRunPreviewScreen,
)
from attackiq_cli.tui_preview import (
    NewAssessmentPreviewScreen as NewAssessmentPreviewScreen,
)
from attackiq_cli.tui_preview import (
    NewTestPreviewScreen as NewTestPreviewScreen,
)
from attackiq_cli.tui_preview import (
    TestScenariosPreviewScreen as TestScenariosPreviewScreen,
)
from attackiq_cli.tui_preview import (
    TestStatusPreviewScreen as TestStatusPreviewScreen,
)
from attackiq_cli.tui_preview import (
    build_assessment_defaults_preview as build_assessment_defaults_preview,
)
from attackiq_cli.tui_preview import (
    build_assessment_from_template_preview as build_assessment_from_template_preview,
)
from attackiq_cli.tui_preview import (
    build_assessment_run_preview as build_assessment_run_preview,
)
from attackiq_cli.tui_preview import (
    build_new_assessment_preview as build_new_assessment_preview,
)
from attackiq_cli.tui_preview import (
    build_new_test_preview as build_new_test_preview,
)
from attackiq_cli.tui_preview import (
    build_test_scenarios_preview as build_test_scenarios_preview,
)
from attackiq_cli.tui_preview import (
    build_test_status_preview as build_test_status_preview,
)
from attackiq_cli.tui_preview import (
    render_mutation_preview as render_mutation_preview,
)
from attackiq_cli.tui_provider import (
    ResultsViewMode as ResultsViewMode,
)
from attackiq_cli.tui_provider import (
    TuiDataProvider,
    TuiOptions,
)
from attackiq_cli.tui_provider import (
    TuiState as TuiState,
)
from attackiq_cli.tui_provider import (
    _cache_domain_totals as _cache_domain_totals,
)
from attackiq_cli.tui_provider import (
    _format_cache_entries_runtime as _format_cache_entries_runtime,
)
from attackiq_cli.tui_provider import (
    _format_cache_totals_compact as _format_cache_totals_compact,
)
from attackiq_cli.tui_provider import (
    _resolve_tui_cache_max_entries as _resolve_tui_cache_max_entries,
)
from attackiq_cli.tui_provider import (
    _resolve_tui_cache_ttl_seconds as _resolve_tui_cache_ttl_seconds,
)
from attackiq_cli.tui_record_lists import (
    ResultsGroup as ResultsGroup,
)
from attackiq_cli.tui_record_lists import (
    _build_group_metadata as _build_group_metadata,
)
from attackiq_cli.tui_record_lists import (
    _build_metadata as _build_metadata,
)
from attackiq_cli.tui_record_lists import (
    _build_outcome_summary as _build_outcome_summary,
)
from attackiq_cli.tui_record_lists import (
    _build_scenario_summary as _build_scenario_summary,
)
from attackiq_cli.tui_record_lists import (
    _filter_results_groups as _filter_results_groups,
)
from attackiq_cli.tui_record_lists import (
    _filter_results_summaries as _filter_results_summaries,
)
from attackiq_cli.tui_record_lists import (
    _group_by_join_key as _group_by_join_key,
)
from attackiq_cli.tui_record_lists import (
    _missing_join_key as _missing_join_key,
)
from attackiq_cli.tui_record_lists import (
    _resolve_join_key as _resolve_join_key,
)
from attackiq_cli.tui_record_lists import (
    _sort_assessment_records as _sort_assessment_records,
)
from attackiq_cli.tui_record_lists import (
    _sort_asset_records as _sort_asset_records,
)
from attackiq_cli.tui_record_lists import (
    _sort_results_groups as _sort_results_groups,
)
from attackiq_cli.tui_record_lists import (
    _sort_results_summaries as _sort_results_summaries,
)
from attackiq_cli.tui_record_lists import (
    _sort_scenarios_records as _sort_scenarios_records,
)
from attackiq_cli.tui_record_lists import (
    _sort_test_records as _sort_test_records,
)
from attackiq_cli.tui_record_lists import (
    _summarize_logs as _summarize_logs,
)
from attackiq_cli.tui_record_lists import (
    _summarize_phases as _summarize_phases,
)
from attackiq_cli.tui_record_text import (
    _assessment_name as _assessment_name,
)
from attackiq_cli.tui_record_text import (
    _assessment_type as _assessment_type,
)
from attackiq_cli.tui_record_text import (
    _asset_deployment_state as _asset_deployment_state,
)
from attackiq_cli.tui_record_text import (
    _asset_hostname as _asset_hostname,
)
from attackiq_cli.tui_record_text import (
    _build_assessment_config as _build_assessment_config,
)
from attackiq_cli.tui_record_text import (
    _build_assessment_execution as _build_assessment_execution,
)
from attackiq_cli.tui_record_text import (
    _build_assessment_metadata as _build_assessment_metadata,
)
from attackiq_cli.tui_record_text import (
    _build_asset_metadata as _build_asset_metadata,
)
from attackiq_cli.tui_record_text import (
    _build_asset_network as _build_asset_network,
)
from attackiq_cli.tui_record_text import (
    _build_asset_status as _build_asset_status,
)
from attackiq_cli.tui_record_text import (
    _build_scenario_config as _build_scenario_config,
)
from attackiq_cli.tui_record_text import (
    _build_scenario_description as _build_scenario_description,
)
from attackiq_cli.tui_record_text import (
    _build_scenario_metadata as _build_scenario_metadata,
)
from attackiq_cli.tui_record_text import (
    _build_scenario_parameters as _build_scenario_parameters,
)
from attackiq_cli.tui_record_text import (
    _build_scenario_relationships as _build_scenario_relationships,
)
from attackiq_cli.tui_record_text import (
    _build_scenario_tags as _build_scenario_tags,
)
from attackiq_cli.tui_record_text import (
    _build_test_config as _build_test_config,
)
from attackiq_cli.tui_record_text import (
    _build_test_execution as _build_test_execution,
)
from attackiq_cli.tui_record_text import (
    _build_test_metadata as _build_test_metadata,
)
from attackiq_cli.tui_record_text import (
    _extract_assessment_id as _extract_assessment_id,
)
from attackiq_cli.tui_record_text import (
    _extract_asset_id as _extract_asset_id,
)
from attackiq_cli.tui_record_text import (
    _extract_scenario_id as _extract_scenario_id,
)
from attackiq_cli.tui_record_text import (
    _extract_test_id as _extract_test_id,
)
from attackiq_cli.tui_record_text import (
    _scenario_name as _scenario_name,
)
from attackiq_cli.tui_record_text import (
    _stringify as _stringify,
)
from attackiq_cli.tui_record_text import (
    _test_name as _test_name,
)
from attackiq_cli.tui_record_text import (
    _test_project as _test_project,
)
from attackiq_cli.tui_results import (
    PhaseLog as PhaseLog,
)
from attackiq_cli.tui_results import (
    PhaseResult as PhaseResult,
)
from attackiq_cli.tui_results import (
    ResultGroupKey as ResultGroupKey,
)
from attackiq_cli.tui_results import (
    ResultsQuery as ResultsQuery,
)
from attackiq_cli.tui_results import (
    ResultsTab as ResultsTab,
)
from attackiq_cli.tui_results import (
    ResultSummary as ResultSummary,
)
from attackiq_cli.tui_scenarios import ScenariosTab as ScenariosTab
from attackiq_cli.tui_settings import (
    WorkflowSettingsTab as WorkflowSettingsTab,
)
from attackiq_cli.tui_settings import (
    build_settings_detail as build_settings_detail,
)
from attackiq_cli.tui_settings import (
    build_settings_records as build_settings_records,
)
from attackiq_cli.tui_styles import TUI_CSS as TUI_CSS
from attackiq_cli.tui_tasks import (
    _cancel_and_await_tasks as _cancel_and_await_tasks,
)
from attackiq_cli.tui_tasks import (
    _cancel_task as _cancel_task,
)
from attackiq_cli.tui_tasks import (
    _consume_task as _consume_task,
)
from attackiq_cli.tui_tasks import (
    _replace_task as _replace_task,
)
from attackiq_cli.tui_tasks import (
    _run_blocking as _run_blocking,
)
from attackiq_cli.tui_tasks import (
    _schedule_debounced as _schedule_debounced,
)
from attackiq_cli.tui_tests import WorkflowTestsTab as WorkflowTestsTab
from attackiq_cli.tui_widgets import (
    BannerBar as BannerBar,
)
from attackiq_cli.tui_widgets import (
    DetailPane as DetailPane,
)
from attackiq_cli.tui_widgets import (
    FilterBar as FilterBar,
)
from attackiq_cli.tui_widgets import (
    HeaderBar as HeaderBar,
)
from attackiq_cli.tui_widgets import (
    ListPane as ListPane,
)
from attackiq_cli.tui_widgets import (
    StatusTab as StatusTab,
)
from attackiq_cli.tui_widgets import (
    WorkflowTab as WorkflowTab,
)

console = Console()


def run_tui(
    *,
    spec_path: Path,
    page_size: int,
    order_by: str | None,
    search: str | None,
    tag: str | None,
    filter_debounce: float,
    insecure: bool,
    timeout: float | None,
    auth_scheme: str,
) -> None:
    try:
        context = load_service_context(spec_path, preferred_scheme=auth_scheme)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    effective_timeout = timeout if timeout is not None else context.config.timeout
    timeout_source = "cli" if timeout is not None else "config"
    if insecure:
        effective_insecure = True
        insecure_source = "cli"
    else:
        effective_insecure = not context.config.verify_tls
        insecure_source = "config"
    options = TuiOptions(
        page_size=page_size,
        order_by=order_by,
        search=search,
        tag=tag,
        filter_debounce=filter_debounce,
        insecure=effective_insecure,
        insecure_source=insecure_source,
        timeout=effective_timeout,
        timeout_source=timeout_source,
    )
    provider = TuiDataProvider(context, options)
    state = provider.build_state()
    app = AttackIQTuiApp(state, provider)
    app.run()
