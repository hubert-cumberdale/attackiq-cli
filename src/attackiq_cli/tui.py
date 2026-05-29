from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import functools
import shlex
from collections import Counter
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    DataTable,
    Input,
    LoadingIndicator,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from attackiq_cli.config import (
    ConfigError,
)
from attackiq_cli.exporter import (
    ASSESSMENT_FIELD_ORDER,
    SCENARIO_FIELD_ORDER,
    TEST_FIELD_ORDER,
    write_csv_records,
    write_json,
)
from attackiq_cli.services import (
    AssessmentFilters,
    ScenarioFilters,
    build_assessment_query_params,
    build_assessment_summary_records,
    build_asset_summary_records,
    build_scenario_summary_records,
    build_test_summary_records,
    load_service_context,
)
from attackiq_cli.tui_provider import (
    ResultsViewMode,
    TuiDataProvider,
    TuiOptions,
    TuiState,
    _cache_domain_totals,
    _format_cache_entries_runtime,
    _format_cache_totals_compact,
    _resolve_tui_cache_max_entries,
    _resolve_tui_cache_ttl_seconds,
)

console = Console()


@dataclass
class ResultsQuery:
    operation_id: str
    query_params: dict[str, Any]


@dataclass
class ResultSummary:
    result_summary_id: str | None
    scenario_job_id: str | None
    scenario_name: str | None
    outcome: str | None
    completed: str | None


@dataclass
class PhaseResult:
    result_summary_id: str | None
    scenario_job_id: str | None
    phase_number: int | None
    status: str | None


@dataclass
class PhaseLog:
    result_summary_id: str | None
    scenario_job_id: str | None
    message: str | None
    created: str | None


@dataclass
class ResultGroupKey:
    result_summary_id: str | None
    scenario_job_id: str | None


@dataclass
class ResultsGroup:
    key: str
    source: str
    result_summary_id: str | None
    scenario_job_id: str | None
    items: list[dict[str, Any]]

    @property
    def count(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class CommandPaletteEntry:
    command_id: str
    label: str
    group: str
    shortcut: str | None = None
    keywords: tuple[str, ...] = ()


class HeaderBar(Container):
    def __init__(self, state: TuiState) -> None:
        super().__init__(id="header_bar")
        self.state = state

    def compose(self) -> ComposeResult:
        auth_label = "Authenticated" if self.state.authenticated else "Unauthenticated"
        yield Static("AttackIQ TUI", id="header_title", classes="header-item")
        yield Static("", id="header_spacer")
        yield Static(f"Auth: {auth_label}", id="header_auth", classes="header-item")
        yield Static(f"Env: {self.state.env_display}", id="header_env", classes="header-item")
        yield Static(
            f"Workspace: {self.state.workspace_display}",
            id="header_workspace",
            classes="header-item",
        )


class BannerBar(Container):
    def __init__(self) -> None:
        super().__init__(id="banner_bar")
        self.display = False

    def compose(self) -> ComposeResult:
        yield Static("", id="banner_message")

    def set_message(self, message: str) -> None:
        banner = self.query_one("#banner_message", Static)
        banner.update(message)
        self.display = bool(message)


class FilterBar(Horizontal):
    def __init__(self, prefix: str) -> None:
        super().__init__(id=f"{prefix}_filter_bar", classes="filter-bar")
        self.prefix = prefix

    def compose(self) -> ComposeResult:
        yield Static("Search", classes="filter_label")
        yield Input(placeholder="Search", id=f"{self.prefix}_filter_search")
        yield Static("Filter", classes="filter_label")
        yield Input(placeholder="Filter", id=f"{self.prefix}_filter_structured")


class ListPane(Vertical):
    def __init__(self, title: str, prefix: str, authenticated: bool) -> None:
        super().__init__(id=f"{prefix}_list_pane", classes="list-pane")
        self.title = title
        self.prefix = prefix
        self.authenticated = authenticated

    def compose(self) -> ComposeResult:
        yield Static(self.title, classes="pane-title")
        yield FilterBar(self.prefix)
        if self.authenticated:
            message = "No data loaded (read-only)."
        else:
            message = "Authentication required to view content."
        yield Static(message, id=f"{self.prefix}_list_placeholder", classes="pane-placeholder")


class DetailPane(Vertical):
    def __init__(self, title: str, prefix: str, authenticated: bool) -> None:
        super().__init__(id=f"{prefix}_detail_pane", classes="detail-pane")
        self.title = title
        self.prefix = prefix
        self.authenticated = authenticated

    def compose(self) -> ComposeResult:
        yield Static(self.title, classes="pane-title")
        if self.authenticated:
            lines = [
                "Metadata",
                "Relationships",
                "Last Run / Results",
                "Logs / Artifacts (read-only)",
                "Export Actions",
            ]
            content = "\n".join(f"- {line}" for line in lines)
        else:
            content = "Authentication required to view detail."
        yield Static(content, id=f"{self.prefix}_detail_placeholder", classes="pane-placeholder")


class WorkflowTab(Container):
    BINDINGS = [
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "refresh", "Refresh"),
        ("e", "export_json", "Export JSON"),
        ("c", "export_csv", "Export CSV"),
    ]

    def __init__(self, title: str, prefix: str, authenticated: bool) -> None:
        super().__init__(id=f"{prefix}_tab", classes="workflow-tab")
        self.title = title
        self.prefix = prefix
        self.authenticated = authenticated

    def compose(self) -> ComposeResult:
        with Horizontal(classes="split-pane"):
            yield ListPane(f"{self.title} List", self.prefix, self.authenticated)
            yield DetailPane(f"{self.title} Detail", self.prefix, self.authenticated)
        yield Static(
            _tab_shortcuts_text(include_export=True),
            id=f"{self.prefix}_footer",
            classes="footer-bar",
        )

    def action_refresh(self) -> None:
        self._set_banner(f"{self.title} is read-only placeholder; nothing to refresh yet.")

    def action_next_page(self) -> None:
        self._set_banner(f"{self.title} is read-only placeholder; paging is not available.")

    def action_prev_page(self) -> None:
        self._set_banner(f"{self.title} is read-only placeholder; paging is not available.")

    def action_export_json(self) -> None:
        self._set_banner(f"{self.title} is read-only placeholder; export is not available yet.")

    def action_export_csv(self) -> None:
        self._set_banner(f"{self.title} is read-only placeholder; export is not available yet.")

    def _set_banner(self, message: str) -> None:
        app = self.app
        if app is None:
            return
        with contextlib.suppress(Exception):
            app.query_one(BannerBar).set_message(message)


class StatusTab(Vertical):
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("e", "export_json", "Export JSON"),
        ("c", "export_csv", "Export CSV"),
    ]

    def __init__(self, state: TuiState, options: TuiOptions, provider: TuiDataProvider) -> None:
        super().__init__(id="status_tab", classes="status-tab")
        self.state = state
        self.options = options
        self.provider = provider

    def compose(self) -> ComposeResult:
        auth_label = "Authenticated" if self.state.authenticated else "Unauthenticated"
        runtime_line = self._build_runtime_line()
        yield Static("Landing / Status", classes="pane-title")
        yield Static(
            "\n".join(
                [
                    f"Auth Status: {auth_label}",
                    f"API Env: {self.state.base_url}",
                    f"Workspace: {self.state.workspace_display}",
                    "Use the tabs to browse data in read-only mode.",
                ]
            ),
            id="status_summary",
            classes="pane-placeholder",
        )
        yield Static(
            "\n".join(
                [
                    (
                        "Diagnostics: "
                        f"auth_mode={self.state.auth_mode} "
                        f"auth_source={self.state.auth_source}"
                    ),
                    f"Base URL source: {self.state.base_url_source}",
                    (
                        "Spec cache: "
                        f"{self.state.spec_cache_status} "
                        f"({self.state.spec_cache_dir_source}) {self.state.spec_cache_dir}"
                    ),
                    f"Spec load source: {self.state.spec_load_source}",
                ]
            ),
            id="status_diagnostics",
            classes="status-hint",
        )
        yield Static(
            runtime_line,
            id="status_runtime",
            classes="status-hint",
        )
        yield Static(
            "Tabs: Scenarios | Assessments | Tests | Assets | Results | Settings",
            id="status_nav",
            classes="status-nav",
        )
        yield Static("Read-only mode. No data loaded.", id="status_hint", classes="status-hint")
        yield Static(
            "Use the tabs to browse data. Enter search/filter values and press Enter to apply. "
            f"{_tab_shortcuts_text(include_export=True)}",
            id="status_usage_help",
            classes="filter-help",
        )

    def refresh_runtime(self) -> None:
        self.query_one("#status_runtime", Static).update(self._build_runtime_line())

    def action_refresh(self) -> None:
        self.refresh_runtime()
        app = self.app
        if app is None:
            return
        with contextlib.suppress(Exception):
            app.query_one(BannerBar).set_message("Command: Refreshed status diagnostics.")

    def action_export_json(self) -> None:
        app = self.app
        if app is None:
            return
        with contextlib.suppress(Exception):
            app.query_one(BannerBar).set_message(
                "Command: Export JSON is not available on Landing / Status."
            )

    def action_export_csv(self) -> None:
        app = self.app
        if app is None:
            return
        with contextlib.suppress(Exception):
            app.query_one(BannerBar).set_message(
                "Command: Export CSV is not available on Landing / Status."
            )

    def _build_runtime_line(self) -> str:
        timeout = "default" if self.options.timeout is None else str(self.options.timeout)
        insecure = "yes" if self.options.insecure else "no"
        cache_max = _resolve_tui_cache_max_entries()
        cache_ttl = _resolve_tui_cache_ttl_seconds()
        cache_ttl_display = "none" if cache_ttl is None else str(cache_ttl)
        cache_entries = _format_cache_entries_runtime(_cache_domain_totals(self.provider))
        return (
            "Runtime: "
            f"page_size={self.options.page_size} "
            f"timeout={timeout} ({self.options.timeout_source}) "
            f"insecure={insecure} ({self.options.insecure_source}) "
            f"cache_max={cache_max} "
            f"cache_ttl={cache_ttl_display} "
            f"{cache_entries}"
        )


class ResultsTab(Container):
    BINDINGS = [
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "refresh", "Refresh"),
        ("e", "export_json", "Export JSON"),
        ("c", "export_csv", "Export CSV"),
    ]

    def __init__(self, state: TuiState, provider: TuiDataProvider) -> None:
        super().__init__(id="results_tab", classes="workflow-tab")
        self.state = state
        self.provider = provider
        self.view_mode = ResultsViewMode.SUMMARIES
        self.page = 1
        self.has_next = False
        self.records: list[dict[str, Any]] = []
        self.groups: list[ResultsGroup] = []
        self.search: str | None = None
        self.structured_filter: str | None = None
        self.sort_field: str | None = None
        self.sort_desc = False
        self.filter_outcome: str | None = None
        self.filter_source: str | None = None
        self.filter_key: str | None = None
        self._restoring_view_state = False
        self._suppressed_filter_change_events = 0
        self._filter_task: asyncio.Task | None = None
        self._load_task: asyncio.Task | None = None
        self._detail_task: asyncio.Task | None = None
        self._export_task: asyncio.Task | None = None
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="split-pane"):
                with Vertical(id="results_list_pane", classes="list-pane"):
                    yield Static(
                        "Results (Summaries)",
                        id="results_list_title",
                        classes="pane-title",
                    )
                    yield FilterBar("results")
                    yield Static(
                        "Filter keys: sort (order), dir (direction), outcome (status), "
                        "source (summary|job), key (join_key). Examples: sort=scenario dir=asc "
                        "outcome=pass | source=job key=job-",
                        id="results_filter_help",
                        classes="filter-help",
                    )
                    with Horizontal(id="results_view_selector", classes="view-selector"):
                        yield Static("View", classes="filter_label")
                        yield Select(
                            [(mode.value, mode.value) for mode in ResultsViewMode],
                            id="results_view_select",
                            value=ResultsViewMode.SUMMARIES.value,
                        )
                    yield LoadingIndicator(id="results_list_loading")
                    yield LoadingIndicator(id="results_export_loading")
                    yield DataTable(id="results_table")
                    yield Static("", id="results_list_status")
                with Vertical(id="results_detail_pane", classes="detail-pane"):
                    yield Static("Result Detail", id="results_detail_title", classes="pane-title")
                    yield LoadingIndicator(id="results_detail_loading")
                    yield Static("", id="results_detail_status", classes="filter-help")
                    yield Static("Metadata", classes="section-title")
                    yield Static("", id="results_section_metadata", classes="section-body")
                    yield Static("Scenario summary", classes="section-title")
                    yield Static("", id="results_section_scenario", classes="section-body")
                    yield Static("Outcome", classes="section-title")
                    yield Static("", id="results_section_outcome", classes="section-body")
                    yield Static("Phases", classes="section-title")
                    yield Static("", id="results_section_phases", classes="section-body")
                    yield Static("Logs", classes="section-title")
                    yield Static("", id="results_section_logs", classes="section-body")
                    yield Static("Export", classes="section-title")
                    yield Static(
                        "Shortcuts: e=Export JSON, c=Export CSV (current list view).",
                        id="results_section_export",
                        classes="section-body",
                    )
            yield Static(
                _tab_shortcuts_text(include_export=True),
                id="results_footer",
                classes="footer-bar",
            )

    async def on_mount(self) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="attackiq-results",
        )
        self.query_one("#results_list_loading", LoadingIndicator).display = False
        self.query_one("#results_export_loading", LoadingIndicator).display = False
        self.query_one("#results_detail_loading", LoadingIndicator).display = False
        self._configure_table()
        self._reset_detail()
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view results.")
            return
        await self._load_list(1)
        self.query_one("#results_filter_search", Input).focus()

    def action_refresh(self) -> None:
        if not self.state.authenticated:
            return
        self.provider.clear_results_cache()
        self._load_task = _replace_task(self._load_task, self._load_list(self.page))

    def action_next_page(self) -> None:
        if not self.has_next or not self.state.authenticated:
            self._update_list_status("No next page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page + 1))

    def action_prev_page(self) -> None:
        if self.page <= 1 or not self.state.authenticated:
            self._update_list_status("Already at first page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page - 1))

    def action_export_json(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("json"))

    def action_export_csv(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("csv"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id not in {"results_filter_search", "results_filter_structured"}:
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id not in {"results_filter_search", "results_filter_structured"}:
            return
        if self._suppressed_filter_change_events > 0:
            self._suppressed_filter_change_events -= 1
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "results_view_select":
            return
        try:
            mode = ResultsViewMode(event.value)
        except ValueError:
            return
        self._set_view_mode(mode)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "results_table":
            return
        if self.view_mode == ResultsViewMode.SUMMARIES:
            item = self._selected_record()
            if item is None:
                return
            self._detail_task = _replace_task(self._detail_task, self._load_summary_detail(item))
            return
        group = self._selected_group()
        if group is None:
            return
        if self.view_mode == ResultsViewMode.PHASES:
            self._detail_task = _replace_task(
                self._detail_task,
                self._load_group_detail(group, load_phases=True),
            )
            return
        self._detail_task = _replace_task(
            self._detail_task,
            self._load_group_detail(group, load_phases=False),
        )

    def _set_view_mode(self, mode: ResultsViewMode) -> None:
        if mode == self.view_mode:
            return
        self.view_mode = mode
        self.page = 1
        self.records = []
        self.groups = []
        self._configure_table()
        self._update_list_title()
        self._reset_detail()
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view results.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(1))

    async def _load_list(self, page: int) -> None:
        loading = self.query_one("#results_list_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Loading {self.view_mode.value} page {page}...")
        parsed_filter = _parse_results_filter(self.structured_filter)
        self.sort_field, self.sort_desc = _resolve_results_sort(
            self.view_mode,
            parsed_filter.get("sort"),
            parsed_filter.get("dir"),
        )
        self.filter_outcome = _clean_filter_value(parsed_filter.get("outcome", ""))
        self.filter_source = _resolve_results_source_filter(parsed_filter.get("source"))
        self.filter_key = _clean_filter_value(parsed_filter.get("key", ""))
        try:
            records, has_next = await self._run_blocking(
                self.provider.fetch_results_list,
                mode=self.view_mode,
                page=page,
                page_size=self.provider.options.page_size,
                search=self.search,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Results load failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to load results.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self.page = page
        self.has_next = has_next
        self.records = _filter_results_summaries(records, outcome=self.filter_outcome)
        if self.view_mode == ResultsViewMode.SUMMARIES:
            self.records = _sort_results_summaries(
                self.records,
                sort_field=self.sort_field,
                descending=self.sort_desc,
            )
            self.groups = []
        else:
            grouped = _group_by_join_key(records)
            grouped = _filter_results_groups(
                grouped,
                source=self.filter_source,
                key_query=self.filter_key,
            )
            self.groups = _sort_results_groups(
                grouped,
                sort_field=self.sort_field,
                descending=self.sort_desc,
            )
        self._render_table()
        self._update_list_status(self._build_list_status())

    def _render_table(self) -> None:
        table = self.query_one("#results_table", DataTable)
        table.clear()
        if self.view_mode == ResultsViewMode.SUMMARIES:
            for record in self.records:
                table.add_row(
                    str(record.get("id") or record.get("result_summary_id") or ""),
                    _stringify(record.get("scenario_name") or record.get("scenario") or ""),
                    _stringify(record.get("outcome") or record.get("status") or ""),
                    _stringify(
                        record.get("modified")
                        or record.get("completed")
                        or record.get("created")
                        or ""
                    ),
                )
            return
        for group in self.groups:
            table.add_row(group.key, group.source, str(group.count))

    def _configure_table(self) -> None:
        table = self.query_one("#results_table", DataTable)
        table.clear(columns=True)
        if self.view_mode == ResultsViewMode.SUMMARIES:
            table.add_columns("Result ID", "Scenario", "Outcome", "Completed")
        else:
            table.add_columns("Join Key", "Source", "Count")

    def _update_list_title(self) -> None:
        title = self.query_one("#results_list_title", Static)
        title.update(f"Results ({self.view_mode.value})")

    def _update_list_status(self, message: str) -> None:
        self.query_one("#results_list_status", Static).update(message)

    def _update_filters_from_inputs(self) -> None:
        self.search = _clean_filter_value(self.query_one("#results_filter_search", Input).value)
        self.structured_filter = _clean_filter_value(
            self.query_one("#results_filter_structured", Input).value
        )

    def _schedule_filter_reload(self) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view results.")
            return
        self._filter_task = _schedule_debounced(
            self._filter_task,
            self.provider.options.filter_debounce,
            self._reload_page_one,
        )
        self._filter_task.add_done_callback(_consume_task)

    async def _reload_page_one(self) -> None:
        await self._load_list(1)

    async def on_unmount(self) -> None:
        await _cancel_and_await_tasks(
            self._filter_task,
            self._load_task,
            self._detail_task,
            self._export_task,
        )
        self._filter_task = None
        self._load_task = None
        self._detail_task = None
        self._export_task = None
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    async def _run_blocking(
        self,
        func: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        executor = self._executor
        if executor is None:
            return func(*args, **kwargs)
        loop = asyncio.get_running_loop()
        bound = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, bound)

    def _build_list_status(self) -> str:
        filters = []
        if self.search:
            filters.append(f"search={self.search}")
        if self.sort_field:
            direction = "desc" if self.sort_desc else "asc"
            filters.append(f"sort={self.sort_field}:{direction}")
        if self.filter_outcome:
            filters.append(f"outcome={self.filter_outcome}")
        if self.filter_source:
            filters.append(f"source={self.filter_source}")
        if self.filter_key:
            filters.append(f"key={self.filter_key}")
        if self.structured_filter:
            filters.append("filter=custom")
        filter_note = f" | Filters: {', '.join(filters)}" if filters else ""
        return f"Page {self.page}{filter_note}"

    def _selected_record(self) -> dict[str, Any] | None:
        table = self.query_one("#results_table", DataTable)
        if table.row_count == 0:
            return None
        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self.records):
            return None
        return self.records[row_index]

    def _selected_group(self) -> ResultsGroup | None:
        table = self.query_one("#results_table", DataTable)
        if table.row_count == 0:
            return None
        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self.groups):
            return None
        return self.groups[row_index]

    async def _load_summary_detail(self, summary: dict[str, Any]) -> None:
        self._set_detail_loading(True)
        self._set_detail_status("Loading detail metadata...")
        result_summary_id = (
            summary.get("id")
            or summary.get("result_summary_id")
            or summary.get("result_summary")
        )
        metadata = _build_metadata(summary)
        scenario = _build_scenario_summary(summary)
        outcome = _build_outcome_summary(summary)
        if not result_summary_id:
            self._update_detail_sections(
                metadata=metadata,
                scenario=scenario,
                outcome=outcome,
                phases=_missing_join_key(),
                logs=_missing_join_key(),
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load complete.")
            return
        try:
            self._set_detail_status("Loading phases (1/2)...")
            phases = await self._run_blocking(
                self.provider.fetch_phase_results,
                result_summary_id=str(result_summary_id),
            )
            self._set_detail_status("Loading logs (2/2)...")
            logs = await self._run_blocking(
                self.provider.fetch_phase_logs,
                result_summary_id=str(result_summary_id),
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Detail load failed: {_format_runtime_error(exc)}")
            self._update_detail_sections(
                metadata=metadata,
                scenario=scenario,
                outcome=outcome,
                phases="Failed to load phases.",
                logs="Failed to load logs.",
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load failed.")
            return
        self._set_banner("")
        self._update_detail_sections(
            metadata=metadata,
            scenario=scenario,
            outcome=outcome,
            phases=_summarize_phases(phases),
            logs=_summarize_logs(logs),
        )
        self._set_detail_loading(False)
        self._set_detail_status("Detail load complete.")

    async def _load_group_detail(self, group: ResultsGroup, *, load_phases: bool) -> None:
        self._set_detail_loading(True)
        self._set_detail_status("Loading grouped detail...")
        metadata = _build_group_metadata(group)
        scenario = _build_scenario_summary(group.items[0] if group.items else {})
        outcome = _build_outcome_summary(group.items[0] if group.items else {})
        join_key = _resolve_join_key(group)
        if not join_key:
            phases_text = _missing_join_key()
            logs_text = _missing_join_key()
            if self.view_mode == ResultsViewMode.LOGS:
                logs_text = _summarize_logs(group.items)
            self._update_detail_sections(
                metadata=metadata,
                scenario=scenario,
                outcome=outcome,
                phases=phases_text,
                logs=logs_text,
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load complete.")
            return
        result_summary_id, scenario_job_id = join_key
        logs_text = _summarize_logs(group.items) if self.view_mode == ResultsViewMode.LOGS else ""
        phases_text = "Not loaded (optional in Logs view)." if not load_phases else ""
        try:
            step = 1
            if load_phases:
                self._set_detail_status(f"Loading phases ({step}/2)...")
                phases = await self._run_blocking(
                    self.provider.fetch_phase_results,
                    result_summary_id=result_summary_id,
                    scenario_job_id=scenario_job_id,
                )
                phases_text = _summarize_phases(phases)
                step += 1
            if self.view_mode == ResultsViewMode.PHASES:
                self._set_detail_status(f"Loading logs ({step}/2)...")
                logs = await self._run_blocking(
                    self.provider.fetch_phase_logs,
                    result_summary_id=result_summary_id,
                    scenario_job_id=scenario_job_id,
                )
                logs_text = _summarize_logs(logs)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Detail load failed: {_format_runtime_error(exc)}")
            self._update_detail_sections(
                metadata=metadata,
                scenario=scenario,
                outcome=outcome,
                phases="Failed to load phases.",
                logs="Failed to load logs.",
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load failed.")
            return
        self._set_banner("")
        if self.view_mode == ResultsViewMode.LOGS and not logs_text:
            logs_text = _summarize_logs(group.items)
        self._update_detail_sections(
            metadata=metadata,
            scenario=scenario,
            outcome=outcome,
            phases=phases_text,
            logs=logs_text,
        )
        self._set_detail_loading(False)
        self._set_detail_status("Detail load complete.")

    def _reset_detail(self) -> None:
        self._update_detail_sections(
            metadata="Select a result to view details.",
            scenario="",
            outcome="",
            phases="",
            logs="",
        )
        self._set_detail_status("")

    def _update_detail_sections(
        self,
        *,
        metadata: str,
        scenario: str,
        outcome: str,
        phases: str,
        logs: str,
    ) -> None:
        self.query_one("#results_section_metadata", Static).update(metadata)
        self.query_one("#results_section_scenario", Static).update(scenario)
        self.query_one("#results_section_outcome", Static).update(outcome)
        self.query_one("#results_section_phases", Static).update(phases)
        self.query_one("#results_section_logs", Static).update(logs)

    def _set_detail_loading(self, value: bool) -> None:
        self.query_one("#results_detail_loading", LoadingIndicator).display = value

    def _set_detail_status(self, message: str) -> None:
        self.query_one("#results_detail_status", Static).update(message)

    def _set_banner(self, message: str) -> None:
        self.app.query_one(BannerBar).set_message(message)

    async def _export_current(self, fmt: str) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to export results.")
            return
        if self.view_mode == ResultsViewMode.SUMMARIES:
            records = [dict(item) for item in self.records]
        else:
            records = [
                {
                    "join_key": group.key,
                    "source": group.source,
                    "count": group.count,
                    "result_summary_id": group.result_summary_id,
                    "scenario_job_id": group.scenario_job_id,
                }
                for group in self.groups
            ]
        if not records:
            self._update_list_status("No results to export on this page.")
            return
        output = self._default_export_path(fmt)
        loading = self.query_one("#results_export_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Exporting results page {self.page} to {fmt.upper()}...")

        def _write_export() -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "json":
                write_json(output, records)
            else:
                write_csv_records(output, records)

        try:
            await self._run_blocking(_write_export)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Results export failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to export results.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self._update_list_status(f"Exported results to {output}")

    def _default_export_path(self, fmt: str) -> Path:
        mode = self.view_mode.value.lower()
        name = f"results_{mode}_page{self.page}_{_utc_timestamp()}.{fmt}"
        return Path(self.state.workspace_full) / "exports" / name

    def export_view_state(self) -> dict[str, Any]:
        table = self.query_one("#results_table", DataTable)
        return {
            "page": self.page,
            "search": self.search,
            "structured_filter": self.structured_filter,
            "view_mode": self.view_mode.value,
            "selected_row": table.cursor_row,
        }

    def restore_view_state(self, state: dict[str, Any]) -> None:
        search_value = state.get("search")
        structured_value = state.get("structured_filter")
        _cancel_task(self._filter_task)
        self._filter_task = None
        self._restoring_view_state = True
        try:
            self.search = (
                _clean_filter_value(search_value) if isinstance(search_value, str) else None
            )
            self.structured_filter = (
                _clean_filter_value(structured_value) if isinstance(structured_value, str) else None
            )
            search_input = self.query_one("#results_filter_search", Input)
            structured_input = self.query_one("#results_filter_structured", Input)
            changed_inputs = (
                int(search_input.value != (self.search or ""))
                + int(structured_input.value != (self.structured_filter or ""))
            )
            # Textual may emit multiple changed events for programmatic updates around tab
            # activation; suppress a short burst so restore doesn't trigger page-1 reloads.
            self._suppressed_filter_change_events = max(
                self._suppressed_filter_change_events,
                changed_inputs * 4,
            )
            search_input.value = self.search or ""
            structured_input.value = self.structured_filter or ""
            mode_value = state.get("view_mode")
            if isinstance(mode_value, str):
                with contextlib.suppress(ValueError):
                    mode = ResultsViewMode(mode_value)
                    self.view_mode = mode
            self._configure_table()
            self._update_list_title()
            selected_row = state.get("selected_row")
            page = state.get("page")
            if not isinstance(page, int) or page < 1:
                page = 1
            needs_reload = self.page != page or not self.records
            self.page = page
            if needs_reload:
                if self.state.authenticated:
                    self._load_task = _replace_task(self._load_task, self._load_list(page))
                return
            self._render_table()
            self._update_list_status(self._build_list_status())
            if isinstance(selected_row, int) and selected_row >= 0:
                table = self.query_one("#results_table", DataTable)
                max_index = max(0, table.row_count - 1)
                table.move_cursor(row=min(selected_row, max_index), column=0)
        finally:
            self._restoring_view_state = False


class ScenariosTab(Container):
    BINDINGS = [
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "refresh", "Refresh"),
        ("e", "export_json", "Export JSON"),
        ("c", "export_csv", "Export CSV"),
    ]

    def __init__(self, state: TuiState, provider: TuiDataProvider) -> None:
        super().__init__(id="scenarios_tab", classes="workflow-tab")
        self.state = state
        self.provider = provider
        self.page = 1
        self.has_next = False
        self.records: list[dict[str, Any]] = []
        self.search = provider.options.search
        self.structured_filter: str | None = None
        self.order_by = provider.options.order_by
        self.tag = provider.options.tag
        self.sort_field: str | None = None
        self.sort_desc = False
        self._restoring_view_state = False
        self._suppressed_filter_change_events = 0
        self._filter_task: asyncio.Task | None = None
        self._load_task: asyncio.Task | None = None
        self._detail_task: asyncio.Task | None = None
        self._export_task: asyncio.Task | None = None
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="split-pane"):
                with Vertical(id="scenarios_list_pane", classes="list-pane"):
                    yield Static("Scenarios", id="scenarios_list_title", classes="pane-title")
                    yield FilterBar("scenarios")
                    yield Static(
                        "Filter keys: search, tag, name, order_by (order), modified_after "
                        "(updated, last_updated), mitre_platforms (mitre), hierarchy, "
                        "object_fingerprint (fingerprint), parameters_description (parameters), "
                        "scenario_template_instance (template), sort, dir. "
                        "Examples: sort=name dir=asc | tag=windows name=credential",
                        id="scenarios_filter_help",
                        classes="filter-help",
                    )
                    yield LoadingIndicator(id="scenarios_list_loading")
                    yield LoadingIndicator(id="scenarios_export_loading")
                    yield DataTable(id="scenarios_table")
                    yield Static("", id="scenarios_list_status")
                with Vertical(id="scenarios_detail_pane", classes="detail-pane"):
                    yield Static(
                        "Scenario Detail",
                        id="scenarios_detail_title",
                        classes="pane-title",
                    )
                    yield LoadingIndicator(id="scenarios_detail_loading")
                    yield Static("", id="scenarios_detail_status", classes="filter-help")
                    yield Static("Metadata", classes="section-title")
                    yield Static("", id="scenarios_section_metadata", classes="section-body")
                    yield Static("Description", classes="section-title")
                    yield Static("", id="scenarios_section_description", classes="section-body")
                    yield Static("Tags", classes="section-title")
                    yield Static("", id="scenarios_section_tags", classes="section-body")
                    yield Static("Parameters", classes="section-title")
                    yield Static("", id="scenarios_section_parameters", classes="section-body")
                    yield Static("Relationships", classes="section-title")
                    yield Static("", id="scenarios_section_relationships", classes="section-body")
                    yield Static("Configuration", classes="section-title")
                    yield Static("", id="scenarios_section_config", classes="section-body")
            yield Static(
                _tab_shortcuts_text(include_export=True),
                id="scenarios_footer",
                classes="footer-bar",
            )

    async def on_mount(self) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="attackiq-scenarios",
        )
        self.query_one("#scenarios_list_loading", LoadingIndicator).display = False
        self.query_one("#scenarios_export_loading", LoadingIndicator).display = False
        self.query_one("#scenarios_detail_loading", LoadingIndicator).display = False
        if self.search:
            self.query_one("#scenarios_filter_search", Input).value = self.search
        self._configure_table()
        self._reset_detail()
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view scenarios.")
            return
        await self._load_list(1)
        self.query_one("#scenarios_filter_search", Input).focus()

    def action_refresh(self) -> None:
        if not self.state.authenticated:
            return
        self.provider.clear_scenarios_cache()
        self._load_task = _replace_task(self._load_task, self._load_list(self.page))

    def action_next_page(self) -> None:
        if not self.has_next or not self.state.authenticated:
            self._update_list_status("No next page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page + 1))

    def action_prev_page(self) -> None:
        if self.page <= 1 or not self.state.authenticated:
            self._update_list_status("Already at first page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page - 1))

    def action_export_json(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("json"))

    def action_export_csv(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("csv"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id not in {"scenarios_filter_search", "scenarios_filter_structured"}:
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id not in {"scenarios_filter_search", "scenarios_filter_structured"}:
            return
        if self._suppressed_filter_change_events > 0:
            self._suppressed_filter_change_events -= 1
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "scenarios_table":
            return
        item = self._selected_record()
        if item is None:
            return
        self._detail_task = _replace_task(self._detail_task, self._load_detail(item))

    async def _load_list(self, page: int) -> None:
        loading = self.query_one("#scenarios_list_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Loading scenarios page {page}...")
        filters = self._build_filters()
        try:
            records, has_next = await self._run_blocking(
                self.provider.fetch_scenarios_page,
                page=page,
                page_size=self.provider.options.page_size,
                filters=filters,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Scenarios load failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to load scenarios.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self.page = page
        self.has_next = has_next
        self.records = _sort_scenarios_records(
            records,
            sort_field=self.sort_field,
            descending=self.sort_desc,
        )
        self._render_table()
        self._update_list_status(self._build_list_status(filters))

    async def _load_detail(self, item: dict[str, Any]) -> None:
        self._set_detail_loading(True)
        self._set_detail_status("Loading scenario detail...")
        scenario_id = _extract_scenario_id(item)
        if not scenario_id:
            self._update_detail_sections(
                metadata=_build_scenario_metadata(item),
                description=_build_scenario_description(item),
                tags=_build_scenario_tags(item),
                parameters=_build_scenario_parameters(item),
                relationships=_build_scenario_relationships(item),
                config=_build_scenario_config(item),
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load complete.")
            return
        try:
            detail = await self._run_blocking(
                self.provider.fetch_scenario_detail,
                scenario_id=scenario_id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Scenario detail failed: {_format_runtime_error(exc)}")
            self._update_detail_sections(
                metadata=_build_scenario_metadata(item),
                description="Failed to load description.",
                tags="Failed to load tags.",
                parameters="Failed to load parameters.",
                relationships="Failed to load relationships.",
                config="Failed to load configuration.",
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load failed.")
            return
        self._set_banner("")
        self._update_detail_sections(
            metadata=_build_scenario_metadata(detail),
            description=_build_scenario_description(detail),
            tags=_build_scenario_tags(detail),
            parameters=_build_scenario_parameters(detail),
            relationships=_build_scenario_relationships(detail),
            config=_build_scenario_config(detail),
        )
        self._set_detail_loading(False)
        self._set_detail_status("Detail load complete.")

    def _configure_table(self) -> None:
        table = self.query_one("#scenarios_table", DataTable)
        table.clear(columns=True)
        table.add_columns("Scenario ID", "Name", "Type", "Updated")

    def _render_table(self) -> None:
        table = self.query_one("#scenarios_table", DataTable)
        table.clear()
        for record in self.records:
            table.add_row(
                _stringify(_extract_scenario_id(record)),
                _stringify(_scenario_name(record)),
                _stringify(record.get("scenario_type") or record.get("scenario_type_id") or ""),
                _stringify(
                    record.get("modified")
                    or record.get("updated_at")
                    or record.get("last_updated")
                    or ""
                ),
            )

    def _update_list_status(self, message: str) -> None:
        self.query_one("#scenarios_list_status", Static).update(message)

    def _update_filters_from_inputs(self) -> None:
        self.search = _clean_filter_value(self.query_one("#scenarios_filter_search", Input).value)
        self.structured_filter = _clean_filter_value(
            self.query_one("#scenarios_filter_structured", Input).value
        )

    def _schedule_filter_reload(self) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view scenarios.")
            return
        self._filter_task = _schedule_debounced(
            self._filter_task,
            self.provider.options.filter_debounce,
            self._reload_page_one,
        )
        self._filter_task.add_done_callback(_consume_task)

    async def _reload_page_one(self) -> None:
        await self._load_list(1)

    async def on_unmount(self) -> None:
        await _cancel_and_await_tasks(
            self._filter_task,
            self._load_task,
            self._detail_task,
            self._export_task,
        )
        self._filter_task = None
        self._load_task = None
        self._detail_task = None
        self._export_task = None
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    async def _run_blocking(
        self,
        func: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        executor = self._executor
        if executor is None:
            return func(*args, **kwargs)
        loop = asyncio.get_running_loop()
        bound = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, bound)

    def _build_filters(self) -> ScenarioFilters:
        parsed = _parse_scenario_filter(self.structured_filter)
        order_by = parsed.get("order_by", self.order_by)
        search = parsed.get("search", self.search)
        tag = parsed.get("tag", self.tag)
        self.sort_field, self.sort_desc = _resolve_scenarios_sort(
            parsed.get("sort"),
            parsed.get("dir"),
        )
        return ScenarioFilters(
            order_by=order_by,
            search=search,
            tag=tag,
            name=parsed.get("name"),
            modified_after=parsed.get("modified_after"),
            mitre_platforms=parsed.get("mitre_platforms"),
            hierarchy=parsed.get("hierarchy"),
            object_fingerprint=parsed.get("object_fingerprint"),
            parameters_description=parsed.get("parameters_description"),
            scenario_template_instance=parsed.get("scenario_template_instance"),
        )

    def _build_list_status(self, filters: ScenarioFilters) -> str:
        summary = []
        if filters.search:
            summary.append(f"search={filters.search}")
        if filters.tag:
            summary.append(f"tag={filters.tag}")
        if self.sort_field:
            direction = "desc" if self.sort_desc else "asc"
            summary.append(f"sort={self.sort_field}:{direction}")
        if self.structured_filter:
            summary.append("filter=custom")
        suffix = f" | Filters: {', '.join(summary)}" if summary else ""
        return f"Page {self.page}{suffix}"

    def _selected_record(self) -> dict[str, Any] | None:
        table = self.query_one("#scenarios_table", DataTable)
        if table.row_count == 0:
            return None
        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self.records):
            return None
        return self.records[row_index]

    def _reset_detail(self) -> None:
        self._update_detail_sections(
            metadata="Select a scenario to view details.",
            description="",
            tags="",
            parameters="",
            relationships="",
            config="",
        )
        self._set_detail_status("")

    def _update_detail_sections(
        self,
        *,
        metadata: str,
        description: str,
        tags: str,
        parameters: str,
        relationships: str,
        config: str,
    ) -> None:
        self.query_one("#scenarios_section_metadata", Static).update(metadata)
        self.query_one("#scenarios_section_description", Static).update(description)
        self.query_one("#scenarios_section_tags", Static).update(tags)
        self.query_one("#scenarios_section_parameters", Static).update(parameters)
        self.query_one("#scenarios_section_relationships", Static).update(relationships)
        self.query_one("#scenarios_section_config", Static).update(config)

    def _set_detail_loading(self, value: bool) -> None:
        self.query_one("#scenarios_detail_loading", LoadingIndicator).display = value

    def _set_detail_status(self, message: str) -> None:
        self.query_one("#scenarios_detail_status", Static).update(message)

    def _set_banner(self, message: str) -> None:
        self.app.query_one(BannerBar).set_message(message)

    async def _export_current(self, fmt: str) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to export scenarios.")
            return
        records = build_scenario_summary_records(self.records)
        if not records:
            self._update_list_status("No scenarios to export on this page.")
            return
        output = self._default_export_path(fmt)
        loading = self.query_one("#scenarios_export_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Exporting scenarios page {self.page} to {fmt.upper()}...")

        def _write_export() -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "json":
                write_json(output, records)
            else:
                write_csv_records(
                    output,
                    records,
                    preferred_fields=SCENARIO_FIELD_ORDER,
                    include_preferred_missing=True,
                    include_other_fields=False,
                )

        try:
            await self._run_blocking(_write_export)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Scenarios export failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to export scenarios.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self._update_list_status(f"Exported scenarios to {output}")

    def _default_export_path(self, fmt: str) -> Path:
        name = f"scenarios_page{self.page}_{_utc_timestamp()}.{fmt}"
        return Path(self.state.workspace_full) / "exports" / name

    def export_view_state(self) -> dict[str, Any]:
        table = self.query_one("#scenarios_table", DataTable)
        return {
            "page": self.page,
            "search": self.search,
            "structured_filter": self.structured_filter,
            "selected_row": table.cursor_row,
        }

    def restore_view_state(self, state: dict[str, Any]) -> None:
        search_value = state.get("search")
        structured_value = state.get("structured_filter")
        _cancel_task(self._filter_task)
        self._filter_task = None
        self._restoring_view_state = True
        try:
            self.search = (
                _clean_filter_value(search_value) if isinstance(search_value, str) else None
            )
            self.structured_filter = (
                _clean_filter_value(structured_value) if isinstance(structured_value, str) else None
            )
            search_input = self.query_one("#scenarios_filter_search", Input)
            structured_input = self.query_one("#scenarios_filter_structured", Input)
            changed_inputs = (
                int(search_input.value != (self.search or ""))
                + int(structured_input.value != (self.structured_filter or ""))
            )
            # Textual may emit multiple changed events for programmatic updates around tab
            # activation; suppress a short burst so restore doesn't trigger page-1 reloads.
            self._suppressed_filter_change_events = max(
                self._suppressed_filter_change_events,
                changed_inputs * 4,
            )
            search_input.value = self.search or ""
            structured_input.value = self.structured_filter or ""
            selected_row = state.get("selected_row")
            page = state.get("page")
            if not isinstance(page, int) or page < 1:
                page = 1
            needs_reload = self.page != page or not self.records
            self.page = page
            if needs_reload:
                if self.state.authenticated:
                    self._load_task = _replace_task(self._load_task, self._load_list(page))
                return
            filters = self._build_filters()
            self._configure_table()
            self._render_table()
            self._update_list_status(self._build_list_status(filters))
            if isinstance(selected_row, int) and selected_row >= 0:
                table = self.query_one("#scenarios_table", DataTable)
                max_index = max(0, table.row_count - 1)
                table.move_cursor(row=min(selected_row, max_index), column=0)
        finally:
            self._restoring_view_state = False


class AssessmentsTab(Container):
    BINDINGS = [
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "refresh", "Refresh"),
        ("e", "export_json", "Export JSON"),
        ("c", "export_csv", "Export CSV"),
    ]

    def __init__(self, state: TuiState, provider: TuiDataProvider) -> None:
        super().__init__(id="assessments_tab", classes="workflow-tab")
        self.state = state
        self.provider = provider
        self.page = 1
        self.has_next = False
        self.records: list[dict[str, Any]] = []
        self.search: str | None = None
        self.structured_filter: str | None = None
        self.sort_field: str | None = None
        self.sort_desc = False
        self._restoring_view_state = False
        self._suppressed_filter_change_events = 0
        self._filter_task: asyncio.Task | None = None
        self._load_task: asyncio.Task | None = None
        self._detail_task: asyncio.Task | None = None
        self._export_task: asyncio.Task | None = None
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="split-pane"):
                with Vertical(id="assessments_list_pane", classes="list-pane"):
                    yield Static("Assessments", id="assessments_list_title", classes="pane-title")
                    yield FilterBar("assessments")
                    yield Static(
                        "Filter keys: search, name, id__in (id), tag_id, tag_ids, "
                        "execution_strategy (strategy), has_default_schedule, "
                        "use_scenario_alert_rules, version, sort, dir. "
                        "Examples: sort=name dir=asc | tag_id=<id> strategy=1",
                        id="assessments_filter_help",
                        classes="filter-help",
                    )
                    yield LoadingIndicator(id="assessments_list_loading")
                    yield LoadingIndicator(id="assessments_export_loading")
                    yield DataTable(id="assessments_table")
                    yield Static("", id="assessments_list_status")
                with Vertical(id="assessments_detail_pane", classes="detail-pane"):
                    yield Static(
                        "Assessment Detail",
                        id="assessments_detail_title",
                        classes="pane-title",
                    )
                    yield LoadingIndicator(id="assessments_detail_loading")
                    yield Static("", id="assessments_detail_status", classes="filter-help")
                    yield Static("Metadata", classes="section-title")
                    yield Static("", id="assessments_section_metadata", classes="section-body")
                    yield Static("Configuration", classes="section-title")
                    yield Static("", id="assessments_section_config", classes="section-body")
                    yield Static("Execution", classes="section-title")
                    yield Static("", id="assessments_section_execution", classes="section-body")
            yield Static(
                _tab_shortcuts_text(include_export=True),
                id="assessments_footer",
                classes="footer-bar",
            )

    async def on_mount(self) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="attackiq-assessments",
        )
        self.query_one("#assessments_list_loading", LoadingIndicator).display = False
        self.query_one("#assessments_export_loading", LoadingIndicator).display = False
        self.query_one("#assessments_detail_loading", LoadingIndicator).display = False
        self._configure_table()
        self._reset_detail()
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view assessments.")
            return
        await self._load_list(1)
        self.query_one("#assessments_filter_search", Input).focus()

    def action_refresh(self) -> None:
        if not self.state.authenticated:
            return
        self.provider.clear_assessments_cache()
        self._load_task = _replace_task(self._load_task, self._load_list(self.page))

    def action_next_page(self) -> None:
        if not self.has_next or not self.state.authenticated:
            self._update_list_status("No next page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page + 1))

    def action_prev_page(self) -> None:
        if self.page <= 1 or not self.state.authenticated:
            self._update_list_status("Already at first page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page - 1))

    def action_export_json(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("json"))

    def action_export_csv(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("csv"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id not in {"assessments_filter_search", "assessments_filter_structured"}:
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id not in {"assessments_filter_search", "assessments_filter_structured"}:
            return
        if self._suppressed_filter_change_events > 0:
            self._suppressed_filter_change_events -= 1
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "assessments_table":
            return
        item = self._selected_record()
        if item is None:
            return
        self._detail_task = _replace_task(self._detail_task, self._load_detail(item))

    async def _load_list(self, page: int) -> None:
        loading = self.query_one("#assessments_list_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Loading assessments page {page}...")
        try:
            query_params = self._build_query_params()
        except ValueError as exc:
            loading.display = False
            self._set_banner(f"Invalid assessment filter: {exc}")
            self._update_list_status("Invalid assessment filter.")
            return
        try:
            records, has_next = await self._run_blocking(
                self.provider.fetch_assessments_page,
                page=page,
                page_size=self.provider.options.page_size,
                query_params=query_params,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Assessments load failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to load assessments.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self.page = page
        self.has_next = has_next
        self.records = _sort_assessment_records(
            records,
            sort_field=self.sort_field,
            descending=self.sort_desc,
        )
        self._render_table()
        self._update_list_status(self._build_list_status(query_params))

    async def _load_detail(self, item: dict[str, Any]) -> None:
        self._set_detail_loading(True)
        self._set_detail_status("Loading assessment detail...")
        assessment_id = _extract_assessment_id(item)
        if not assessment_id:
            self._update_detail_sections(
                metadata=_build_assessment_metadata(item),
                config=_build_assessment_config(item),
                execution=_build_assessment_execution(item),
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load complete.")
            return
        try:
            detail = await self._run_blocking(
                self.provider.fetch_assessment_detail,
                assessment_id=assessment_id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Assessment detail failed: {_format_runtime_error(exc)}")
            self._update_detail_sections(
                metadata=_build_assessment_metadata(item),
                config="Failed to load configuration.",
                execution="Failed to load execution details.",
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load failed.")
            return
        self._set_banner("")
        self._update_detail_sections(
            metadata=_build_assessment_metadata(detail),
            config=_build_assessment_config(detail),
            execution=_build_assessment_execution(detail),
        )
        self._set_detail_loading(False)
        self._set_detail_status("Detail load complete.")

    def _configure_table(self) -> None:
        table = self.query_one("#assessments_table", DataTable)
        table.clear(columns=True)
        table.add_columns("Assessment ID", "Name", "Type", "Status")

    def _render_table(self) -> None:
        table = self.query_one("#assessments_table", DataTable)
        table.clear()
        for record in self.records:
            table.add_row(
                _stringify(_extract_assessment_id(record)),
                _stringify(_assessment_name(record)),
                _stringify(_assessment_type(record)),
                _stringify(record.get("status") or ""),
            )

    def _update_list_status(self, message: str) -> None:
        self.query_one("#assessments_list_status", Static).update(message)

    def _update_filters_from_inputs(self) -> None:
        self.search = _clean_filter_value(self.query_one("#assessments_filter_search", Input).value)
        self.structured_filter = _clean_filter_value(
            self.query_one("#assessments_filter_structured", Input).value
        )

    def _schedule_filter_reload(self) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view assessments.")
            return
        self._filter_task = _schedule_debounced(
            self._filter_task,
            self.provider.options.filter_debounce,
            self._reload_page_one,
        )
        self._filter_task.add_done_callback(_consume_task)

    async def _reload_page_one(self) -> None:
        await self._load_list(1)

    async def on_unmount(self) -> None:
        await _cancel_and_await_tasks(
            self._filter_task,
            self._load_task,
            self._detail_task,
            self._export_task,
        )
        self._filter_task = None
        self._load_task = None
        self._detail_task = None
        self._export_task = None
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    async def _run_blocking(
        self,
        func: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        executor = self._executor
        if executor is None:
            return func(*args, **kwargs)
        loop = asyncio.get_running_loop()
        bound = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, bound)

    def _build_query_params(self) -> dict[str, Any]:
        parsed = _parse_assessment_filter(self.structured_filter)
        self.sort_field, self.sort_desc = _resolve_assessments_sort(
            parsed.get("sort"),
            parsed.get("dir"),
        )
        search = parsed.get("search", self.search)
        filters = AssessmentFilters(
            asset_group_id=_parse_filter_list(parsed.get("asset_group_id")),
            blueprint_id=parsed.get("blueprint_id"),
            execution_strategy=_parse_filter_int(parsed.get("execution_strategy")),
            has_default_schedule=_parse_filter_bool(parsed.get("has_default_schedule")),
            id__in=_parse_filter_list(parsed.get("id__in")),
            name=parsed.get("name"),
            report_instance_type=parsed.get("report_instance_type"),
            search=search,
            tag_id=parsed.get("tag_id"),
            tag_ids=_parse_filter_list(parsed.get("tag_ids")),
            use_scenario_alert_rules=_parse_filter_bool(parsed.get("use_scenario_alert_rules")),
            version=_parse_filter_int(parsed.get("version")),
            zones_ordering=_parse_filter_list(parsed.get("zones_ordering")),
        )
        return build_assessment_query_params(filters)

    def _build_list_status(self, query_params: dict[str, Any]) -> str:
        summary = []
        if query_params.get("search"):
            summary.append(f"search={query_params['search']}")
        if query_params.get("status"):
            summary.append(f"status={query_params['status']}")
        if self.sort_field:
            direction = "desc" if self.sort_desc else "asc"
            summary.append(f"sort={self.sort_field}:{direction}")
        if self.structured_filter:
            summary.append("filter=custom")
        suffix = f" | Filters: {', '.join(summary)}" if summary else ""
        return f"Page {self.page}{suffix}"

    def _selected_record(self) -> dict[str, Any] | None:
        table = self.query_one("#assessments_table", DataTable)
        if table.row_count == 0:
            return None
        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self.records):
            return None
        return self.records[row_index]

    def _reset_detail(self) -> None:
        self._update_detail_sections(
            metadata="Select an assessment to view details.",
            config="",
            execution="",
        )
        self._set_detail_status("")

    def _update_detail_sections(self, *, metadata: str, config: str, execution: str) -> None:
        self.query_one("#assessments_section_metadata", Static).update(metadata)
        self.query_one("#assessments_section_config", Static).update(config)
        self.query_one("#assessments_section_execution", Static).update(execution)

    def _set_detail_loading(self, value: bool) -> None:
        self.query_one("#assessments_detail_loading", LoadingIndicator).display = value

    def _set_detail_status(self, message: str) -> None:
        self.query_one("#assessments_detail_status", Static).update(message)

    def _set_banner(self, message: str) -> None:
        self.app.query_one(BannerBar).set_message(message)

    async def _export_current(self, fmt: str) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to export assessments.")
            return
        records = build_assessment_summary_records(self.records)
        if not records:
            self._update_list_status("No assessments to export on this page.")
            return
        output = self._default_export_path(fmt)
        loading = self.query_one("#assessments_export_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Exporting assessments page {self.page} to {fmt.upper()}...")

        def _write_export() -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "json":
                write_json(output, records)
            else:
                write_csv_records(
                    output,
                    records,
                    preferred_fields=ASSESSMENT_FIELD_ORDER,
                    include_preferred_missing=True,
                    include_other_fields=False,
                )

        try:
            await self._run_blocking(_write_export)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Assessments export failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to export assessments.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self._update_list_status(f"Exported assessments to {output}")

    def _default_export_path(self, fmt: str) -> Path:
        name = f"assessments_page{self.page}_{_utc_timestamp()}.{fmt}"
        return Path(self.state.workspace_full) / "exports" / name

    def export_view_state(self) -> dict[str, Any]:
        table = self.query_one("#assessments_table", DataTable)
        return {
            "page": self.page,
            "search": self.search,
            "structured_filter": self.structured_filter,
            "selected_row": table.cursor_row,
        }

    def restore_view_state(self, state: dict[str, Any]) -> None:
        search_value = state.get("search")
        structured_value = state.get("structured_filter")
        _cancel_task(self._filter_task)
        self._filter_task = None
        self._restoring_view_state = True
        try:
            self.search = (
                _clean_filter_value(search_value) if isinstance(search_value, str) else None
            )
            self.structured_filter = (
                _clean_filter_value(structured_value) if isinstance(structured_value, str) else None
            )
            search_input = self.query_one("#assessments_filter_search", Input)
            structured_input = self.query_one("#assessments_filter_structured", Input)
            changed_inputs = (
                int(search_input.value != (self.search or ""))
                + int(structured_input.value != (self.structured_filter or ""))
            )
            self._suppressed_filter_change_events = max(
                self._suppressed_filter_change_events,
                changed_inputs * 4,
            )
            search_input.value = self.search or ""
            structured_input.value = self.structured_filter or ""
            selected_row = state.get("selected_row")
            page = state.get("page")
            if not isinstance(page, int) or page < 1:
                page = 1
            needs_reload = self.page != page or not self.records
            self.page = page
            if needs_reload:
                if self.state.authenticated:
                    self._load_task = _replace_task(self._load_task, self._load_list(page))
                return
            query_params = self._build_query_params()
            self._configure_table()
            self._render_table()
            self._update_list_status(self._build_list_status(query_params))
            if isinstance(selected_row, int) and selected_row >= 0:
                table = self.query_one("#assessments_table", DataTable)
                max_index = max(0, table.row_count - 1)
                table.move_cursor(row=min(selected_row, max_index), column=0)
        finally:
            self._restoring_view_state = False


class WorkflowTestsTab(Container):
    BINDINGS = [
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "refresh", "Refresh"),
        ("e", "export_json", "Export JSON"),
        ("c", "export_csv", "Export CSV"),
    ]

    def __init__(self, state: TuiState, provider: TuiDataProvider) -> None:
        super().__init__(id="tests_tab", classes="workflow-tab")
        self.state = state
        self.provider = provider
        self.page = 1
        self.has_next = False
        self.records: list[dict[str, Any]] = []
        self.search: str | None = None
        self.structured_filter: str | None = None
        self.sort_field: str | None = None
        self.sort_desc = False
        self._restoring_view_state = False
        self._suppressed_filter_change_events = 0
        self._filter_task: asyncio.Task | None = None
        self._load_task: asyncio.Task | None = None
        self._detail_task: asyncio.Task | None = None
        self._export_task: asyncio.Task | None = None
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="split-pane"):
                with Vertical(id="tests_list_pane", classes="list-pane"):
                    yield Static("Tests", id="tests_list_title", classes="pane-title")
                    yield FilterBar("tests")
                    yield Static(
                        "Filter keys: search (maps to name), name, project_template_test_id "
                        "(template), use_hosted_agent, run_in_hosted_agent_preferably "
                        "(prefer_hosted), sort, dir. Examples: name=Credential sort=name dir=asc",
                        id="tests_filter_help",
                        classes="filter-help",
                    )
                    yield LoadingIndicator(id="tests_list_loading")
                    yield LoadingIndicator(id="tests_export_loading")
                    yield DataTable(id="tests_table")
                    yield Static("", id="tests_list_status")
                with Vertical(id="tests_detail_pane", classes="detail-pane"):
                    yield Static("Test Detail", id="tests_detail_title", classes="pane-title")
                    yield LoadingIndicator(id="tests_detail_loading")
                    yield Static("", id="tests_detail_status", classes="filter-help")
                    yield Static("Metadata", classes="section-title")
                    yield Static("", id="tests_section_metadata", classes="section-body")
                    yield Static("Configuration", classes="section-title")
                    yield Static("", id="tests_section_config", classes="section-body")
                    yield Static("Execution", classes="section-title")
                    yield Static("", id="tests_section_execution", classes="section-body")
            yield Static(
                _tab_shortcuts_text(include_export=True),
                id="tests_footer",
                classes="footer-bar",
            )

    async def on_mount(self) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="attackiq-tests",
        )
        self.query_one("#tests_list_loading", LoadingIndicator).display = False
        self.query_one("#tests_export_loading", LoadingIndicator).display = False
        self.query_one("#tests_detail_loading", LoadingIndicator).display = False
        self._configure_table()
        self._reset_detail()
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view tests.")
            return
        await self._load_list(1)
        self.query_one("#tests_filter_search", Input).focus()

    def action_refresh(self) -> None:
        if not self.state.authenticated:
            return
        self.provider.clear_tests_cache()
        self._load_task = _replace_task(self._load_task, self._load_list(self.page))

    def action_next_page(self) -> None:
        if not self.has_next or not self.state.authenticated:
            self._update_list_status("No next page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page + 1))

    def action_prev_page(self) -> None:
        if self.page <= 1 or not self.state.authenticated:
            self._update_list_status("Already at first page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page - 1))

    def action_export_json(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("json"))

    def action_export_csv(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("csv"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id not in {"tests_filter_search", "tests_filter_structured"}:
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id not in {"tests_filter_search", "tests_filter_structured"}:
            return
        if self._suppressed_filter_change_events > 0:
            self._suppressed_filter_change_events -= 1
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "tests_table":
            return
        item = self._selected_record()
        if item is None:
            return
        self._detail_task = _replace_task(self._detail_task, self._load_detail(item))

    async def _load_list(self, page: int) -> None:
        loading = self.query_one("#tests_list_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Loading tests page {page}...")
        query_params = self._build_query_params()
        try:
            records, has_next = await self._run_blocking(
                self.provider.fetch_tests_page,
                page=page,
                page_size=self.provider.options.page_size,
                query_params=query_params,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Tests load failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to load tests.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self.page = page
        self.has_next = has_next
        self.records = _sort_test_records(
            records,
            sort_field=self.sort_field,
            descending=self.sort_desc,
        )
        self._render_table()
        self._update_list_status(self._build_list_status(query_params))

    async def _load_detail(self, item: dict[str, Any]) -> None:
        self._set_detail_loading(True)
        self._set_detail_status("Loading test detail...")
        test_id = _extract_test_id(item)
        if not test_id:
            self._update_detail_sections(
                metadata=_build_test_metadata(item),
                config=_build_test_config(item),
                execution=_build_test_execution(item),
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load complete.")
            return
        try:
            detail = await self._run_blocking(self.provider.fetch_test_detail, test_id=test_id)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Test detail failed: {_format_runtime_error(exc)}")
            self._update_detail_sections(
                metadata=_build_test_metadata(item),
                config="Failed to load configuration.",
                execution="Failed to load execution details.",
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load failed.")
            return
        self._set_banner("")
        self._update_detail_sections(
            metadata=_build_test_metadata(detail),
            config=_build_test_config(detail),
            execution=_build_test_execution(detail),
        )
        self._set_detail_loading(False)
        self._set_detail_status("Detail load complete.")

    def _configure_table(self) -> None:
        table = self.query_one("#tests_table", DataTable)
        table.clear(columns=True)
        table.add_columns("Test ID", "Name", "Project", "Runnable")

    def _render_table(self) -> None:
        table = self.query_one("#tests_table", DataTable)
        table.clear()
        for record in self.records:
            table.add_row(
                _stringify(_extract_test_id(record)),
                _stringify(_test_name(record)),
                _stringify(_test_project(record)),
                _stringify(record.get("runnable") or ""),
            )

    def _update_list_status(self, message: str) -> None:
        self.query_one("#tests_list_status", Static).update(message)

    def _update_filters_from_inputs(self) -> None:
        self.search = _clean_filter_value(self.query_one("#tests_filter_search", Input).value)
        self.structured_filter = _clean_filter_value(
            self.query_one("#tests_filter_structured", Input).value
        )

    def _schedule_filter_reload(self) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view tests.")
            return
        self._filter_task = _schedule_debounced(
            self._filter_task,
            self.provider.options.filter_debounce,
            self._reload_page_one,
        )
        self._filter_task.add_done_callback(_consume_task)

    async def _reload_page_one(self) -> None:
        await self._load_list(1)

    async def on_unmount(self) -> None:
        await _cancel_and_await_tasks(
            self._filter_task,
            self._load_task,
            self._detail_task,
            self._export_task,
        )
        self._filter_task = None
        self._load_task = None
        self._detail_task = None
        self._export_task = None
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    async def _run_blocking(
        self,
        func: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        executor = self._executor
        if executor is None:
            return func(*args, **kwargs)
        loop = asyncio.get_running_loop()
        bound = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, bound)

    def _build_query_params(self) -> dict[str, Any]:
        parsed = _parse_test_filter(self.structured_filter)
        self.sort_field, self.sort_desc = _resolve_tests_sort(parsed.get("sort"), parsed.get("dir"))
        query_params: dict[str, Any] = {}
        search = parsed.get("search", self.search)
        if search:
            query_params["name"] = search
        if parsed.get("name"):
            query_params["name"] = parsed["name"]
        if parsed.get("project_template_test_id"):
            query_params["project_template_test_id"] = parsed["project_template_test_id"]
        hosted = parsed.get("use_hosted_agent")
        if hosted in {"true", "false"}:
            query_params["use_hosted_agent"] = hosted
        preferred = parsed.get("run_in_hosted_agent_preferably")
        if preferred in {"true", "false"}:
            query_params["run_in_hosted_agent_preferably"] = preferred
        return query_params

    def _build_list_status(self, query_params: dict[str, Any]) -> str:
        summary = []
        if query_params.get("name"):
            summary.append(f"name={query_params['name']}")
        if query_params.get("use_hosted_agent"):
            summary.append(f"use_hosted_agent={query_params['use_hosted_agent']}")
        if self.sort_field:
            direction = "desc" if self.sort_desc else "asc"
            summary.append(f"sort={self.sort_field}:{direction}")
        if self.structured_filter:
            summary.append("filter=custom")
        suffix = f" | Filters: {', '.join(summary)}" if summary else ""
        return f"Page {self.page}{suffix}"

    def _selected_record(self) -> dict[str, Any] | None:
        table = self.query_one("#tests_table", DataTable)
        if table.row_count == 0:
            return None
        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self.records):
            return None
        return self.records[row_index]

    def _reset_detail(self) -> None:
        self._update_detail_sections(
            metadata="Select a test to view details.",
            config="",
            execution="",
        )
        self._set_detail_status("")

    def _update_detail_sections(self, *, metadata: str, config: str, execution: str) -> None:
        self.query_one("#tests_section_metadata", Static).update(metadata)
        self.query_one("#tests_section_config", Static).update(config)
        self.query_one("#tests_section_execution", Static).update(execution)

    def _set_detail_loading(self, value: bool) -> None:
        self.query_one("#tests_detail_loading", LoadingIndicator).display = value

    def _set_detail_status(self, message: str) -> None:
        self.query_one("#tests_detail_status", Static).update(message)

    def _set_banner(self, message: str) -> None:
        self.app.query_one(BannerBar).set_message(message)

    async def _export_current(self, fmt: str) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to export tests.")
            return
        records = build_test_summary_records(self.records)
        if not records:
            self._update_list_status("No tests to export on this page.")
            return
        output = self._default_export_path(fmt)
        loading = self.query_one("#tests_export_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Exporting tests page {self.page} to {fmt.upper()}...")

        def _write_export() -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "json":
                write_json(output, records)
            else:
                write_csv_records(
                    output,
                    records,
                    preferred_fields=TEST_FIELD_ORDER,
                    include_preferred_missing=True,
                    include_other_fields=False,
                )

        try:
            await self._run_blocking(_write_export)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Tests export failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to export tests.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self._update_list_status(f"Exported tests to {output}")

    def _default_export_path(self, fmt: str) -> Path:
        name = f"tests_page{self.page}_{_utc_timestamp()}.{fmt}"
        return Path(self.state.workspace_full) / "exports" / name

    def export_view_state(self) -> dict[str, Any]:
        table = self.query_one("#tests_table", DataTable)
        return {
            "page": self.page,
            "search": self.search,
            "structured_filter": self.structured_filter,
            "selected_row": table.cursor_row,
        }

    def restore_view_state(self, state: dict[str, Any]) -> None:
        search_value = state.get("search")
        structured_value = state.get("structured_filter")
        _cancel_task(self._filter_task)
        self._filter_task = None
        self._restoring_view_state = True
        try:
            self.search = (
                _clean_filter_value(search_value) if isinstance(search_value, str) else None
            )
            self.structured_filter = (
                _clean_filter_value(structured_value) if isinstance(structured_value, str) else None
            )
            search_input = self.query_one("#tests_filter_search", Input)
            structured_input = self.query_one("#tests_filter_structured", Input)
            changed_inputs = (
                int(search_input.value != (self.search or ""))
                + int(structured_input.value != (self.structured_filter or ""))
            )
            self._suppressed_filter_change_events = max(
                self._suppressed_filter_change_events,
                changed_inputs * 4,
            )
            search_input.value = self.search or ""
            structured_input.value = self.structured_filter or ""
            selected_row = state.get("selected_row")
            page = state.get("page")
            if not isinstance(page, int) or page < 1:
                page = 1
            needs_reload = self.page != page or not self.records
            self.page = page
            if needs_reload:
                if self.state.authenticated:
                    self._load_task = _replace_task(self._load_task, self._load_list(page))
                return
            query_params = self._build_query_params()
            self._configure_table()
            self._render_table()
            self._update_list_status(self._build_list_status(query_params))
            if isinstance(selected_row, int) and selected_row >= 0:
                table = self.query_one("#tests_table", DataTable)
                max_index = max(0, table.row_count - 1)
                table.move_cursor(row=min(selected_row, max_index), column=0)
        finally:
            self._restoring_view_state = False


class WorkflowAssetsTab(Container):
    BINDINGS = [
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "refresh", "Refresh"),
        ("e", "export_json", "Export JSON"),
        ("c", "export_csv", "Export CSV"),
    ]

    def __init__(self, state: TuiState, provider: TuiDataProvider) -> None:
        super().__init__(id="assets_tab", classes="workflow-tab")
        self.state = state
        self.provider = provider
        self.page = 1
        self.has_next = False
        self.records: list[dict[str, Any]] = []
        self.search: str | None = None
        self.structured_filter: str | None = None
        self.sort_field: str | None = None
        self.sort_desc = False
        self._restoring_view_state = False
        self._suppressed_filter_change_events = 0
        self._filter_task: asyncio.Task | None = None
        self._load_task: asyncio.Task | None = None
        self._detail_task: asyncio.Task | None = None
        self._export_task: asyncio.Task | None = None
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="split-pane"):
                with Vertical(id="assets_list_pane", classes="list-pane"):
                    yield Static("Assets", id="assets_list_title", classes="pane-title")
                    yield FilterBar("assets")
                    yield Static(
                        "Filter keys: search, hostname, ipv4_address (ipv4), ipv6_address (ipv6), "
                        "deployment_state_id (state), asset_group (group), activity_type (type), "
                        "ordering (order_by), deepsurface_sync_state, "
                        "deepsurface_last_seen_in_host_analysis_at, "
                        "deepsurface_sync_state_changed_at, sort, dir. "
                        "Example: search=agent state=2 sort=hostname",
                        id="assets_filter_help",
                        classes="filter-help",
                    )
                    yield LoadingIndicator(id="assets_list_loading")
                    yield LoadingIndicator(id="assets_export_loading")
                    yield DataTable(id="assets_table")
                    yield Static("", id="assets_list_status")
                with Vertical(id="assets_detail_pane", classes="detail-pane"):
                    yield Static("Asset Detail", id="assets_detail_title", classes="pane-title")
                    yield LoadingIndicator(id="assets_detail_loading")
                    yield Static("", id="assets_detail_status", classes="filter-help")
                    yield Static("Metadata", classes="section-title")
                    yield Static("", id="assets_section_metadata", classes="section-body")
                    yield Static("Network", classes="section-title")
                    yield Static("", id="assets_section_network", classes="section-body")
                    yield Static("Status", classes="section-title")
                    yield Static("", id="assets_section_status", classes="section-body")
            yield Static(
                _tab_shortcuts_text(include_export=True),
                id="assets_footer",
                classes="footer-bar",
            )

    async def on_mount(self) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="attackiq-assets",
        )
        self.query_one("#assets_list_loading", LoadingIndicator).display = False
        self.query_one("#assets_export_loading", LoadingIndicator).display = False
        self.query_one("#assets_detail_loading", LoadingIndicator).display = False
        self._configure_table()
        self._reset_detail()
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view assets.")
            return
        await self._load_list(1)
        self.query_one("#assets_filter_search", Input).focus()

    def action_refresh(self) -> None:
        if not self.state.authenticated:
            return
        self.provider.clear_assets_cache()
        self._load_task = _replace_task(self._load_task, self._load_list(self.page))

    def action_next_page(self) -> None:
        if not self.has_next or not self.state.authenticated:
            self._update_list_status("No next page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page + 1))

    def action_prev_page(self) -> None:
        if self.page <= 1 or not self.state.authenticated:
            self._update_list_status("Already at first page.")
            return
        self._load_task = _replace_task(self._load_task, self._load_list(self.page - 1))

    def action_export_json(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("json"))

    def action_export_csv(self) -> None:
        self._export_task = _replace_task(self._export_task, self._export_current("csv"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id not in {"assets_filter_search", "assets_filter_structured"}:
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id not in {"assets_filter_search", "assets_filter_structured"}:
            return
        if self._suppressed_filter_change_events > 0:
            self._suppressed_filter_change_events -= 1
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._schedule_filter_reload()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "assets_table":
            return
        item = self._selected_record()
        if item is None:
            return
        self._detail_task = _replace_task(self._detail_task, self._load_detail(item))

    async def _load_list(self, page: int) -> None:
        loading = self.query_one("#assets_list_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Loading assets page {page}...")
        query_params = self._build_query_params()
        try:
            records, has_next = await self._run_blocking(
                self.provider.fetch_assets_page,
                page=page,
                page_size=self.provider.options.page_size,
                query_params=query_params,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Assets load failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to load assets.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self.page = page
        self.has_next = has_next
        self.records = _sort_asset_records(
            records,
            sort_field=self.sort_field,
            descending=self.sort_desc,
        )
        self._render_table()
        self._update_list_status(self._build_list_status(query_params))

    async def _load_detail(self, item: dict[str, Any]) -> None:
        self._set_detail_loading(True)
        self._set_detail_status("Loading asset detail...")
        asset_id = _extract_asset_id(item)
        if not asset_id:
            self._update_detail_sections(
                metadata=_build_asset_metadata(item),
                network=_build_asset_network(item),
                status=_build_asset_status(item),
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load complete.")
            return
        try:
            detail = await self._run_blocking(self.provider.fetch_asset_detail, asset_id=asset_id)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Asset detail failed: {_format_runtime_error(exc)}")
            self._update_detail_sections(
                metadata=_build_asset_metadata(item),
                network="Failed to load network details.",
                status="Failed to load status details.",
            )
            self._set_detail_loading(False)
            self._set_detail_status("Detail load failed.")
            return
        self._set_banner("")
        self._update_detail_sections(
            metadata=_build_asset_metadata(detail),
            network=_build_asset_network(detail),
            status=_build_asset_status(detail),
        )
        self._set_detail_loading(False)
        self._set_detail_status("Detail load complete.")

    def _configure_table(self) -> None:
        table = self.query_one("#assets_table", DataTable)
        table.clear(columns=True)
        table.add_columns("Asset ID", "Hostname", "Type", "State")

    def _render_table(self) -> None:
        table = self.query_one("#assets_table", DataTable)
        table.clear()
        for record in self.records:
            table.add_row(
                _stringify(_extract_asset_id(record)),
                _stringify(_asset_hostname(record)),
                _stringify(record.get("activity_type") or ""),
                _stringify(_asset_deployment_state(record)),
            )

    def _update_list_status(self, message: str) -> None:
        self.query_one("#assets_list_status", Static).update(message)

    def _update_filters_from_inputs(self) -> None:
        self.search = _clean_filter_value(self.query_one("#assets_filter_search", Input).value)
        self.structured_filter = _clean_filter_value(
            self.query_one("#assets_filter_structured", Input).value
        )

    def _schedule_filter_reload(self) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to view assets.")
            return
        self._filter_task = _schedule_debounced(
            self._filter_task,
            self.provider.options.filter_debounce,
            self._reload_page_one,
        )
        self._filter_task.add_done_callback(_consume_task)

    async def _reload_page_one(self) -> None:
        await self._load_list(1)

    async def on_unmount(self) -> None:
        await _cancel_and_await_tasks(
            self._filter_task,
            self._load_task,
            self._detail_task,
            self._export_task,
        )
        self._filter_task = None
        self._load_task = None
        self._detail_task = None
        self._export_task = None
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    async def _run_blocking(
        self,
        func: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        executor = self._executor
        if executor is None:
            return func(*args, **kwargs)
        loop = asyncio.get_running_loop()
        bound = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, bound)

    def _build_query_params(self) -> dict[str, Any]:
        parsed = _parse_asset_filter(self.structured_filter)
        self.sort_field, self.sort_desc = _resolve_assets_sort(
            parsed.get("sort"),
            parsed.get("dir"),
        )
        query_params: dict[str, Any] = {}
        search = parsed.get("search", self.search)
        if search:
            query_params["search"] = search
        for key in (
            "hostname",
            "ipv4_address",
            "ipv6_address",
            "deployment_state_id",
            "asset_group",
            "activity_type",
            "ordering",
            "deepsurface_last_seen_in_host_analysis_at",
            "deepsurface_sync_state",
            "deepsurface_sync_state_changed_at",
        ):
            value = parsed.get(key)
            if value:
                query_params[key] = value
        return query_params

    def _build_list_status(self, query_params: dict[str, Any]) -> str:
        summary = []
        if query_params.get("search"):
            summary.append(f"search={query_params['search']}")
        if query_params.get("deployment_state_id"):
            summary.append(f"state={query_params['deployment_state_id']}")
        if self.sort_field:
            direction = "desc" if self.sort_desc else "asc"
            summary.append(f"sort={self.sort_field}:{direction}")
        if self.structured_filter:
            summary.append("filter=custom")
        suffix = f" | Filters: {', '.join(summary)}" if summary else ""
        return f"Page {self.page}{suffix}"

    def _selected_record(self) -> dict[str, Any] | None:
        table = self.query_one("#assets_table", DataTable)
        if table.row_count == 0:
            return None
        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self.records):
            return None
        return self.records[row_index]

    def _reset_detail(self) -> None:
        self._update_detail_sections(
            metadata="Select an asset to view details.",
            network="",
            status="",
        )
        self._set_detail_status("")

    def _update_detail_sections(self, *, metadata: str, network: str, status: str) -> None:
        self.query_one("#assets_section_metadata", Static).update(metadata)
        self.query_one("#assets_section_network", Static).update(network)
        self.query_one("#assets_section_status", Static).update(status)

    def _set_detail_loading(self, value: bool) -> None:
        self.query_one("#assets_detail_loading", LoadingIndicator).display = value

    def _set_detail_status(self, message: str) -> None:
        self.query_one("#assets_detail_status", Static).update(message)

    def _set_banner(self, message: str) -> None:
        self.app.query_one(BannerBar).set_message(message)

    async def _export_current(self, fmt: str) -> None:
        if not self.state.authenticated:
            self._update_list_status("Authentication required to export assets.")
            return
        records = build_asset_summary_records(self.records)
        if not records:
            self._update_list_status("No assets to export on this page.")
            return
        output = self._default_export_path(fmt)
        loading = self.query_one("#assets_export_loading", LoadingIndicator)
        loading.display = True
        self._update_list_status(f"Exporting assets page {self.page} to {fmt.upper()}...")

        def _write_export() -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "json":
                write_json(output, records)
            else:
                write_csv_records(output, records, include_other_fields=False)

        try:
            await self._run_blocking(_write_export)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Assets export failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to export assets.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self._update_list_status(f"Exported assets to {output}")

    def _default_export_path(self, fmt: str) -> Path:
        name = f"assets_page{self.page}_{_utc_timestamp()}.{fmt}"
        return Path(self.state.workspace_full) / "exports" / name

    def export_view_state(self) -> dict[str, Any]:
        table = self.query_one("#assets_table", DataTable)
        return {
            "page": self.page,
            "search": self.search,
            "structured_filter": self.structured_filter,
            "selected_row": table.cursor_row,
        }

    def restore_view_state(self, state: dict[str, Any]) -> None:
        search_value = state.get("search")
        structured_value = state.get("structured_filter")
        _cancel_task(self._filter_task)
        self._filter_task = None
        self._restoring_view_state = True
        try:
            self.search = (
                _clean_filter_value(search_value) if isinstance(search_value, str) else None
            )
            self.structured_filter = (
                _clean_filter_value(structured_value) if isinstance(structured_value, str) else None
            )
            search_input = self.query_one("#assets_filter_search", Input)
            structured_input = self.query_one("#assets_filter_structured", Input)
            changed_inputs = (
                int(search_input.value != (self.search or ""))
                + int(structured_input.value != (self.structured_filter or ""))
            )
            self._suppressed_filter_change_events = max(
                self._suppressed_filter_change_events,
                changed_inputs * 4,
            )
            search_input.value = self.search or ""
            structured_input.value = self.structured_filter or ""
            selected_row = state.get("selected_row")
            page = state.get("page")
            if not isinstance(page, int) or page < 1:
                page = 1
            needs_reload = self.page != page or not self.records
            self.page = page
            if needs_reload:
                if self.state.authenticated:
                    self._load_task = _replace_task(self._load_task, self._load_list(page))
                return
            query_params = self._build_query_params()
            self._configure_table()
            self._render_table()
            self._update_list_status(self._build_list_status(query_params))
            if isinstance(selected_row, int) and selected_row >= 0:
                table = self.query_one("#assets_table", DataTable)
                max_index = max(0, table.row_count - 1)
                table.move_cursor(row=min(selected_row, max_index), column=0)
        finally:
            self._restoring_view_state = False


class WorkflowSettingsTab(Container):
    BINDINGS = [
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "refresh", "Refresh"),
        ("e", "export_json", "Export JSON"),
        ("c", "export_csv", "Export CSV"),
    ]

    def __init__(self, state: TuiState, provider: TuiDataProvider) -> None:
        super().__init__(id="settings_tab", classes="workflow-tab")
        self.state = state
        self.provider = provider
        self.page = 1
        self.has_next = False
        self.records: list[dict[str, str]] = []
        self.search: str | None = None
        self.structured_filter: str | None = None
        self.sort_field: str | None = None
        self.sort_desc = False
        self._restoring_view_state = False
        self._suppressed_filter_change_events = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="split-pane"):
                with Vertical(id="settings_list_pane", classes="list-pane"):
                    yield Static("Settings", id="settings_list_title", classes="pane-title")
                    yield FilterBar("settings")
                    yield Static(
                        "Filter keys: search, key, value, source, category, sort, dir. "
                        "Example: category=runtime sort=key dir=asc",
                        id="settings_filter_help",
                        classes="filter-help",
                    )
                    yield DataTable(id="settings_table")
                    yield Static("", id="settings_list_status")
                with Vertical(id="settings_detail_pane", classes="detail-pane"):
                    yield Static("Setting Detail", id="settings_detail_title", classes="pane-title")
                    yield Static("", id="settings_detail_status", classes="filter-help")
                    yield Static("Metadata", classes="section-title")
                    yield Static("", id="settings_section_metadata", classes="section-body")
            yield Static(
                _tab_shortcuts_text(include_export=True),
                id="settings_footer",
                classes="footer-bar",
            )

    async def on_mount(self) -> None:
        self._configure_table()
        self._reset_detail()
        self._refresh_records()
        self.query_one("#settings_filter_search", Input).focus()

    def action_refresh(self) -> None:
        self._refresh_records()

    def action_next_page(self) -> None:
        self._update_list_status("No next page.")

    def action_prev_page(self) -> None:
        self._update_list_status("Already at first page.")

    def action_export_json(self) -> None:
        self._export_current("json")

    def action_export_csv(self) -> None:
        self._export_current("csv")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id not in {"settings_filter_search", "settings_filter_structured"}:
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._refresh_records()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id not in {"settings_filter_search", "settings_filter_structured"}:
            return
        if self._suppressed_filter_change_events > 0:
            self._suppressed_filter_change_events -= 1
            return
        if self._restoring_view_state:
            return
        self._update_filters_from_inputs()
        self._refresh_records()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "settings_table":
            return
        item = self._selected_record()
        if item is None:
            return
        self._update_detail(item)

    def _configure_table(self) -> None:
        table = self.query_one("#settings_table", DataTable)
        table.clear(columns=True)
        table.add_columns("Key", "Value", "Source", "Category")

    def _refresh_records(self) -> None:
        self.records = _sort_settings_records(
            _filter_settings_records(
                self._base_records(),
                filters=self._build_filters(),
            ),
            sort_field=self.sort_field,
            descending=self.sort_desc,
        )
        self._render_table()
        self._update_list_status(self._build_list_status())
        self._set_banner("")

    def _base_records(self) -> list[dict[str, str]]:
        cache_ttl = self.provider.cache_ttl_seconds()
        cache_ttl_display = "none" if cache_ttl is None else str(cache_ttl)
        cache_totals = _cache_domain_totals(self.provider)
        cache_total = sum(cache_totals.values())
        cache_records = [
            {
                "key": f"cache_entries_{domain}",
                "value": str(value),
                "source": "runtime",
                "category": "runtime",
            }
            for domain, value in cache_totals.items()
        ]
        return [
            {
                "key": "base_url",
                "value": self.state.base_url,
                "source": self.state.base_url_source,
                "category": "config",
            },
            {
                "key": "auth_mode",
                "value": self.state.auth_mode,
                "source": self.state.auth_source,
                "category": "config",
            },
            {
                "key": "spec_cache",
                "value": self.state.spec_cache_status,
                "source": self.state.spec_cache_dir_source,
                "category": "config",
            },
            {
                "key": "spec_cache_dir",
                "value": self.state.spec_cache_dir,
                "source": self.state.spec_cache_dir_source,
                "category": "config",
            },
            {
                "key": "spec_load_source",
                "value": self.state.spec_load_source,
                "source": "runtime",
                "category": "config",
            },
            {
                "key": "timeout",
                "value": str(self.provider.options.timeout),
                "source": self.provider.options.timeout_source,
                "category": "runtime",
            },
            {
                "key": "insecure",
                "value": "yes" if self.provider.options.insecure else "no",
                "source": self.provider.options.insecure_source,
                "category": "runtime",
            },
            {
                "key": "page_size",
                "value": str(self.provider.options.page_size),
                "source": "cli",
                "category": "runtime",
            },
            {
                "key": "cache_max",
                "value": str(self.provider.cache_max_entries()),
                "source": "env/default",
                "category": "runtime",
            },
            {
                "key": "cache_ttl",
                "value": cache_ttl_display,
                "source": "env/default",
                "category": "runtime",
            },
            {
                "key": "cache_entries_total",
                "value": str(cache_total),
                "source": "runtime",
                "category": "runtime",
            },
            *cache_records,
            {
                "key": "workspace",
                "value": self.state.workspace_full,
                "source": "runtime",
                "category": "workspace",
            },
        ]

    def _build_filters(self) -> dict[str, str | None]:
        parsed = _parse_settings_filter(self.structured_filter)
        self.sort_field, self.sort_desc = _resolve_settings_sort(
            parsed.get("sort"),
            parsed.get("dir"),
        )
        return {
            "search": parsed.get("search", self.search),
            "key": parsed.get("key"),
            "value": parsed.get("value"),
            "source": parsed.get("source"),
            "category": parsed.get("category"),
        }

    def _render_table(self) -> None:
        table = self.query_one("#settings_table", DataTable)
        if len(table.ordered_columns) == 0:
            table.add_columns("Key", "Value", "Source", "Category")
        table.clear()
        for record in self.records:
            table.add_row(
                _stringify(record.get("key")),
                _stringify(record.get("value")),
                _stringify(record.get("source")),
                _stringify(record.get("category")),
            )

    def _update_list_status(self, message: str) -> None:
        self.query_one("#settings_list_status", Static).update(message)

    def _build_list_status(self) -> str:
        summary = []
        if self.search:
            summary.append(f"search={self.search}")
        if self.structured_filter:
            summary.append("filter=custom")
        if self.sort_field:
            direction = "desc" if self.sort_desc else "asc"
            summary.append(f"sort={self.sort_field}:{direction}")
        suffix = f" | Filters: {', '.join(summary)}" if summary else ""
        return f"Page {self.page}{suffix}"

    def _selected_record(self) -> dict[str, str] | None:
        table = self.query_one("#settings_table", DataTable)
        if table.row_count == 0:
            return None
        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self.records):
            return None
        return self.records[row_index]

    def _update_filters_from_inputs(self) -> None:
        self.search = _clean_filter_value(self.query_one("#settings_filter_search", Input).value)
        self.structured_filter = _clean_filter_value(
            self.query_one("#settings_filter_structured", Input).value
        )

    def _reset_detail(self) -> None:
        self.query_one("#settings_section_metadata", Static).update(
            "Select a setting to view details."
        )
        self.query_one("#settings_detail_status", Static).update("")

    def _update_detail(self, record: dict[str, str]) -> None:
        lines = [
            f"Key: {record.get('key')}",
            f"Value: {record.get('value')}",
            f"Source: {record.get('source')}",
            f"Category: {record.get('category')}",
        ]
        self.query_one("#settings_section_metadata", Static).update("\n".join(lines))
        self.query_one("#settings_detail_status", Static).update("Detail load complete.")

    def _set_banner(self, message: str) -> None:
        self.app.query_one(BannerBar).set_message(message)

    def _export_current(self, fmt: str) -> None:
        if not self.records:
            self._update_list_status("No settings entries to export.")
            return
        output = self._default_export_path(fmt)
        output.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            write_json(output, self.records)
        else:
            write_csv_records(
                output,
                self.records,
                preferred_fields=["key", "value", "source", "category"],
                include_other_fields=False,
            )
        self._update_list_status(f"Exported settings to {output}")
        self._set_banner("")

    def _default_export_path(self, fmt: str) -> Path:
        name = f"settings_{_utc_timestamp()}.{fmt}"
        return Path(self.state.workspace_full) / "exports" / name

    def export_view_state(self) -> dict[str, Any]:
        table = self.query_one("#settings_table", DataTable)
        return {
            "search": self.search,
            "structured_filter": self.structured_filter,
            "selected_row": table.cursor_row,
        }

    def restore_view_state(self, state: dict[str, Any]) -> None:
        search_value = state.get("search")
        structured_value = state.get("structured_filter")
        self._restoring_view_state = True
        try:
            self.search = (
                _clean_filter_value(search_value) if isinstance(search_value, str) else None
            )
            self.structured_filter = (
                _clean_filter_value(structured_value) if isinstance(structured_value, str) else None
            )
            search_input = self.query_one("#settings_filter_search", Input)
            structured_input = self.query_one("#settings_filter_structured", Input)
            changed_inputs = (
                int(search_input.value != (self.search or ""))
                + int(structured_input.value != (self.structured_filter or ""))
            )
            self._suppressed_filter_change_events = max(
                self._suppressed_filter_change_events,
                changed_inputs * 2,
            )
            search_input.value = self.search or ""
            structured_input.value = self.structured_filter or ""
            self._refresh_records()
            selected_row = state.get("selected_row")
            if isinstance(selected_row, int) and selected_row >= 0:
                table = self.query_one("#settings_table", DataTable)
                max_index = max(0, table.row_count - 1)
                table.move_cursor(row=min(selected_row, max_index), column=0)
        finally:
            self._restoring_view_state = False


class AttackIQTuiApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+k", "toggle_command_palette", "Command Palette"),
        ("[", "prev_tab", "Prev Tab"),
        ("]", "next_tab", "Next Tab"),
        ("?", "toggle_help", "Help"),
        ("h", "toggle_help", "Help"),
        ("escape", "hide_help", "Close Help"),
    ]
    CSS = """
    Screen {
        layout: vertical;
    }

    #header_bar {
        layout: horizontal;
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    #header_title {
        text-style: bold;
    }

    .header-item {
        margin-right: 2;
    }

    #header_spacer {
        width: 1fr;
    }

    #banner_bar {
        height: auto;
        padding: 0 1;
        background: $error 20%;
        color: $text;
    }

    #banner_message {
        text-style: bold;
    }

    #help_overlay {
        layer: overlay;
        dock: top;
        width: 100%;
        padding: 1 2;
        background: $panel;
        border: tall $primary;
        color: $text;
    }

    #command_palette_overlay {
        layer: overlay;
        align: center middle;
        width: 80%;
        max-width: 100;
        height: 60%;
        max-height: 24;
        padding: 1;
        background: $panel;
        border: tall $accent;
    }

    #command_palette_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #command_palette_input {
        margin-bottom: 1;
    }

    #command_palette_hint {
        margin-top: 1;
        color: $text-muted;
    }

    TabbedContent {
        height: 1fr;
    }

    .workflow-tab, .status-tab {
        padding: 0 1;
    }

    .split-pane {
        height: 1fr;
    }

    .list-pane, .detail-pane {
        border: tall $surface;
        padding: 0 1;
    }

    .list-pane {
        width: 45%;
    }

    .detail-pane {
        width: 55%;
    }

    .pane-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .pane-placeholder {
        height: 1fr;
    }

    .view-selector {
        margin-bottom: 1;
    }

    .section-title {
        text-style: bold;
        margin-top: 1;
    }

    .section-body {
        margin-bottom: 1;
    }

    #status_summary {
        margin-bottom: 1;
    }

    .status-nav {
        margin-bottom: 1;
    }

    .filter_label {
        margin-right: 1;
    }

    .filter-bar Input {
        width: 1fr;
    }

    .filter-bar Input:focus {
        border: tall $primary;
    }

    .filter-help {
        color: $text-muted;
        margin-bottom: 1;
    }

    .footer-bar {
        height: 1;
        color: $text-muted;
    }

    #results_list_status {
        margin-top: 1;
    }
    """

    def __init__(self, state: TuiState, provider: TuiDataProvider) -> None:
        super().__init__()
        self.state = state
        self.provider = provider
        self._palette_entries = self._build_palette_entries()
        self._palette_filtered: list[CommandPaletteEntry] = []
        self._tab_state: dict[str, dict[str, Any]] = {}
        self._last_active_tab_id: str = "tab_status"
        self._suppress_tab_activated_handler = False

    def compose(self) -> ComposeResult:
        yield HeaderBar(self.state)
        yield BannerBar()
        yield Static(
            "\n".join(
                [
                    "Keyboard Help",
                    "q Quit | Ctrl+K Command palette | ?/h Toggle help | Esc Close help",
                    "[ Previous tab | ] Next tab",
                    "n Next page | p Previous page | r Refresh",
                    "e Export JSON | c Export CSV",
                    "Enter Apply filter | Tab Focus next",
                ]
            ),
            id="help_overlay",
        )
        with Container(id="command_palette_overlay"):
            yield Static("Command Palette", id="command_palette_title")
            yield Input(placeholder="Type to filter commands", id="command_palette_input")
            yield DataTable(id="command_palette_table")
            yield Static("Enter run selected command | Esc close", id="command_palette_hint")
        with TabbedContent(id="main_tabs"):
            with TabPane("Landing / Status", id="tab_status"):
                yield StatusTab(self.state, self.provider.options, self.provider)
            with TabPane("Scenarios", id="tab_scenarios"):
                yield ScenariosTab(self.state, self.provider)
            with TabPane("Assessments", id="tab_assessments"):
                yield AssessmentsTab(self.state, self.provider)
            with TabPane("Tests", id="tab_tests"):
                yield WorkflowTestsTab(self.state, self.provider)
            with TabPane("Assets", id="tab_assets"):
                yield WorkflowAssetsTab(self.state, self.provider)
            with TabPane("Results", id="tab_results"):
                yield ResultsTab(self.state, self.provider)
            with TabPane("Settings", id="tab_settings"):
                yield WorkflowSettingsTab(self.state, self.provider)

    async def on_mount(self) -> None:
        self.query_one("#help_overlay", Static).display = False
        self.query_one("#command_palette_overlay", Container).display = False
        palette_table = self.query_one("#command_palette_table", DataTable)
        palette_table.clear(columns=True)
        palette_table.add_columns("Group", "Command", "Keys")
        self._render_command_palette("")
        tabs = self.query_one("#main_tabs", TabbedContent)
        self._last_active_tab_id = tabs.active or "tab_status"

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tabbed_content.id != "main_tabs":
            return
        if self._suppress_tab_activated_handler:
            return
        tab_id = event.pane.id
        if not tab_id:
            return
        previous = self._last_active_tab_id
        if previous != tab_id:
            self._capture_tab_state(previous)
        self._restore_tab_state(tab_id)
        if tab_id == "tab_status":
            self._refresh_status_runtime()
        self._last_active_tab_id = tab_id

    async def action_quit(self) -> None:
        self.exit()

    def action_toggle_command_palette(self) -> None:
        overlay = self.query_one("#command_palette_overlay", Container)
        if overlay.display:
            self._hide_command_palette()
            return
        self.action_hide_help()
        overlay.display = True
        palette_input = self.query_one("#command_palette_input", Input)
        palette_input.value = ""
        self._render_command_palette("")
        palette_input.focus()

    def action_next_tab(self) -> None:
        self._switch_tab(step=1)

    def action_prev_tab(self) -> None:
        self._switch_tab(step=-1)

    def action_toggle_help(self) -> None:
        overlay = self.query_one("#help_overlay", Static)
        overlay.display = not bool(overlay.display)

    def action_hide_help(self) -> None:
        self.query_one("#help_overlay", Static).display = False
        self._hide_command_palette()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "command_palette_input":
            return
        self._render_command_palette(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command_palette_input":
            return
        entry = self._selected_palette_entry() or (
            self._palette_filtered[0] if self._palette_filtered else None
        )
        if entry is None:
            return
        self._execute_palette_command(entry.command_id)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "command_palette_table":
            return
        entry = self._selected_palette_entry()
        if entry is None:
            return
        self._execute_palette_command(entry.command_id)

    def _switch_tab(self, *, step: int) -> None:
        tabs = self.query_one("#main_tabs", TabbedContent)
        pane_ids = [pane.id for pane in tabs.query(TabPane) if pane.id]
        if not pane_ids:
            return
        current = tabs.active or pane_ids[0]
        try:
            index = pane_ids.index(current)
        except ValueError:
            index = 0
        self._set_active_tab(pane_ids[(index + step) % len(pane_ids)])

    def _hide_command_palette(self) -> None:
        self.query_one("#command_palette_overlay", Container).display = False

    def _render_command_palette(self, query: str) -> None:
        normalized = query.strip().lower()
        available = self._available_palette_entries()
        self._palette_filtered = [
            entry
            for entry in available
            if _palette_entry_matches(entry, normalized)
        ]
        table = self.query_one("#command_palette_table", DataTable)
        table.clear()
        for entry in self._palette_filtered:
            table.add_row(entry.group, entry.label, entry.shortcut or "-")
        if table.row_count > 0:
            table.move_cursor(row=0, column=0)
        hint = self.query_one("#command_palette_hint", Static)
        group_hint = _palette_group_hint(self._palette_filtered)
        hint_text = (
            f"{len(self._palette_filtered)} commands | {group_hint} | "
            "Enter run selected command | Esc close"
        )
        hint.update(
            hint_text
        )

    def _selected_palette_entry(self) -> CommandPaletteEntry | None:
        table = self.query_one("#command_palette_table", DataTable)
        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self._palette_filtered):
            return None
        return self._palette_filtered[row_index]

    def _build_palette_entries(self) -> list[CommandPaletteEntry]:
        return [
            CommandPaletteEntry(
                "switch:status",
                "Switch tab: Landing / Status",
                "Tabs",
                shortcut="[ ]",
                keywords=("switch", "go", "goto", "tab", "status", "landing"),
            ),
            CommandPaletteEntry(
                "switch:scenarios",
                "Switch tab: Scenarios",
                "Tabs",
                shortcut="[ ]",
                keywords=("switch", "go", "goto", "tab", "scenarios"),
            ),
            CommandPaletteEntry(
                "switch:assessments",
                "Switch tab: Assessments",
                "Tabs",
                shortcut="[ ]",
                keywords=("switch", "go", "goto", "tab", "assessments"),
            ),
            CommandPaletteEntry(
                "switch:tests",
                "Switch tab: Tests",
                "Tabs",
                shortcut="[ ]",
                keywords=("switch", "go", "goto", "tab", "tests"),
            ),
            CommandPaletteEntry(
                "switch:assets",
                "Switch tab: Assets",
                "Tabs",
                shortcut="[ ]",
                keywords=("switch", "go", "goto", "tab", "assets"),
            ),
            CommandPaletteEntry(
                "switch:results",
                "Switch tab: Results",
                "Tabs",
                shortcut="[ ]",
                keywords=("switch", "go", "goto", "tab", "results"),
            ),
            CommandPaletteEntry(
                "switch:settings",
                "Switch tab: Settings",
                "Tabs",
                shortcut="[ ]",
                keywords=("switch", "go", "goto", "tab", "settings"),
            ),
            CommandPaletteEntry(
                "refresh",
                "Refresh current tab",
                "Data",
                shortcut="r",
                keywords=("reload", "refresh", "sync"),
            ),
            CommandPaletteEntry(
                "cache:clear",
                "Clear all TUI caches",
                "Data",
                shortcut="-",
                keywords=("cache", "clear", "reset", "invalidate"),
            ),
            CommandPaletteEntry(
                "cache:stats",
                "Show TUI cache stats",
                "Data",
                shortcut="-",
                keywords=("cache", "stats", "status", "counts", "diagnostics"),
            ),
            CommandPaletteEntry(
                "page:next",
                "Next page",
                "Data",
                shortcut="n",
                keywords=("page", "next", "forward"),
            ),
            CommandPaletteEntry(
                "page:prev",
                "Previous page",
                "Data",
                shortcut="p",
                keywords=("page", "previous", "back"),
            ),
            CommandPaletteEntry(
                "export:json",
                "Export current view as JSON",
                "Data",
                shortcut="e",
                keywords=("export", "json", "save"),
            ),
            CommandPaletteEntry(
                "export:csv",
                "Export current view as CSV",
                "Data",
                shortcut="c",
                keywords=("export", "csv", "save"),
            ),
            CommandPaletteEntry(
                "focus:search",
                "Focus search input",
                "Focus",
                shortcut="Tab",
                keywords=("focus", "search", "find"),
            ),
            CommandPaletteEntry(
                "focus:filter",
                "Focus structured filter input",
                "Focus",
                shortcut="Tab",
                keywords=("focus", "filter", "structured"),
            ),
            CommandPaletteEntry(
                "filter-help",
                "Show filter help for current tab",
                "Help",
                shortcut="? / h",
                keywords=("help", "filter", "syntax", "examples"),
            ),
            CommandPaletteEntry(
                "help",
                "Toggle keyboard help overlay",
                "Help",
                shortcut="? / h",
                keywords=("help", "keys", "keyboard", "shortcuts"),
            ),
        ]

    def _available_palette_entries(self) -> list[CommandPaletteEntry]:
        active = self._active_tab_id()
        allowed = {
            "switch:status",
            "switch:scenarios",
            "switch:assessments",
            "switch:tests",
            "switch:assets",
            "switch:results",
            "switch:settings",
            "help",
            "cache:clear",
            "cache:stats",
        }
        if active == "tab_status":
            allowed.update({"refresh", "filter-help", "export:json", "export:csv"})
        elif active in {
            "tab_scenarios",
            "tab_results",
            "tab_assessments",
            "tab_tests",
            "tab_assets",
        }:
            allowed.update(
                {
                    "refresh",
                    "page:next",
                    "page:prev",
                    "export:json",
                    "export:csv",
                    "focus:search",
                    "focus:filter",
                    "filter-help",
                }
            )
        elif active == "tab_settings":
            allowed.update(
                {
                    "refresh",
                    "page:next",
                    "page:prev",
                    "focus:search",
                    "focus:filter",
                    "filter-help",
                    "export:json",
                    "export:csv",
                }
            )
        return [entry for entry in self._palette_entries if entry.command_id in allowed]

    def _execute_palette_command(self, command_id: str) -> None:
        available_ids = {entry.command_id for entry in self._available_palette_entries()}
        if command_id not in available_ids:
            self.query_one(BannerBar).set_message("Command is not available in this tab.")
            self._hide_command_palette()
            return
        if command_id.startswith("switch:"):
            tab = command_id.split(":", 1)[1]
            self._activate_tab(tab)
            self._set_palette_feedback(f"Switched to {tab.replace('_', ' ')} tab.")
            self._hide_command_palette()
            return
        if command_id == "refresh":
            self._refresh_active_tab()
            self._hide_command_palette()
            return
        if command_id == "cache:clear":
            self._clear_all_caches()
            self._hide_command_palette()
            return
        if command_id == "cache:stats":
            self._show_cache_stats()
            self._hide_command_palette()
            return
        if command_id == "page:next":
            self._page_active_tab(step=1)
            self._hide_command_palette()
            return
        if command_id == "page:prev":
            self._page_active_tab(step=-1)
            self._hide_command_palette()
            return
        if command_id == "export:json":
            self._export_active_tab("json")
            self._hide_command_palette()
            return
        if command_id == "export:csv":
            self._export_active_tab("csv")
            self._hide_command_palette()
            return
        if command_id == "focus:search":
            self._focus_active_input(input_name="search")
            self._hide_command_palette()
            return
        if command_id == "focus:filter":
            self._focus_active_input(input_name="filter")
            self._hide_command_palette()
            return
        if command_id == "filter-help":
            self._show_filter_help()
            self._hide_command_palette()
            return
        if command_id == "help":
            self.action_toggle_help()
            self._set_palette_feedback("Toggled keyboard help overlay.")
            self._hide_command_palette()

    def _active_tab_id(self) -> str:
        tabs = self.query_one("#main_tabs", TabbedContent)
        return tabs.active or "tab_status"

    def _activate_tab(self, short_name: str) -> None:
        tab_id = f"tab_{short_name}"
        tabs = self.query_one("#main_tabs", TabbedContent)
        pane_ids = {pane.id for pane in tabs.query(TabPane) if pane.id}
        if tab_id in pane_ids:
            self._set_active_tab(tab_id)

    def _set_active_tab(self, tab_id: str) -> None:
        tabs = self.query_one("#main_tabs", TabbedContent)
        current = tabs.active or "tab_status"
        self._capture_tab_state(current)
        self._suppress_tab_activated_handler = True
        try:
            tabs.active = tab_id
        finally:
            self._suppress_tab_activated_handler = False
        self._restore_tab_state(tab_id)
        if tab_id == "tab_status":
            self._refresh_status_runtime()
        self._last_active_tab_id = tab_id

    def _capture_tab_state(self, tab_id: str) -> None:
        if tab_id == "tab_scenarios":
            self._tab_state[tab_id] = self.query_one(ScenariosTab).export_view_state()
            return
        if tab_id == "tab_results":
            self._tab_state[tab_id] = self.query_one(ResultsTab).export_view_state()
            return
        if tab_id == "tab_assessments":
            self._tab_state[tab_id] = self.query_one(AssessmentsTab).export_view_state()
            return
        if tab_id == "tab_tests":
            self._tab_state[tab_id] = self.query_one(WorkflowTestsTab).export_view_state()
            return
        if tab_id == "tab_assets":
            self._tab_state[tab_id] = self.query_one(WorkflowAssetsTab).export_view_state()
            return
        if tab_id == "tab_settings":
            self._tab_state[tab_id] = self.query_one(WorkflowSettingsTab).export_view_state()

    def _restore_tab_state(self, tab_id: str) -> None:
        state = self._tab_state.get(tab_id)
        if state is None:
            return
        if tab_id == "tab_scenarios":
            self.query_one(ScenariosTab).restore_view_state(state)
            return
        if tab_id == "tab_results":
            self.query_one(ResultsTab).restore_view_state(state)
            return
        if tab_id == "tab_assessments":
            self.query_one(AssessmentsTab).restore_view_state(state)
            return
        if tab_id == "tab_tests":
            self.query_one(WorkflowTestsTab).restore_view_state(state)
            return
        if tab_id == "tab_assets":
            self.query_one(WorkflowAssetsTab).restore_view_state(state)
            return
        if tab_id == "tab_settings":
            self.query_one(WorkflowSettingsTab).restore_view_state(state)

    def _refresh_active_tab(self) -> None:
        active = self._active_tab_id()
        if active == "tab_status":
            self._refresh_status_runtime()
            self._set_palette_feedback("Refreshed status diagnostics.")
            return
        if active == "tab_scenarios":
            self.query_one(ScenariosTab).action_refresh()
            self._set_palette_feedback("Refresh requested for scenarios (cache cleared).")
            self._refresh_status_runtime()
            return
        if active == "tab_results":
            self.query_one(ResultsTab).action_refresh()
            self._set_palette_feedback("Refresh requested for results (cache cleared).")
            self._refresh_status_runtime()
            return
        if active == "tab_assessments":
            self.query_one(AssessmentsTab).action_refresh()
            self._set_palette_feedback("Refresh requested for assessments (cache cleared).")
            self._refresh_status_runtime()
            return
        if active == "tab_tests":
            self.query_one(WorkflowTestsTab).action_refresh()
            self._set_palette_feedback("Refresh requested for tests (cache cleared).")
            self._refresh_status_runtime()
            return
        if active == "tab_assets":
            self.query_one(WorkflowAssetsTab).action_refresh()
            self._set_palette_feedback("Refresh requested for assets (cache cleared).")
            self._refresh_status_runtime()
            return
        if active == "tab_settings":
            self.query_one(WorkflowSettingsTab).action_refresh()
            self._set_palette_feedback("Refresh requested for settings.")
            self._refresh_status_runtime()
            return
        self._set_palette_feedback("Refresh is not available in this tab.")

    def _clear_all_caches(self) -> None:
        cache_totals = _cache_domain_totals(self.provider)
        self.provider.clear_scenarios_cache()
        self.provider.clear_results_cache()
        self.provider.clear_assessments_cache()
        self.provider.clear_tests_cache()
        self.provider.clear_assets_cache()
        self.provider.clear_templates_cache()
        self._set_palette_feedback(
            "Cleared TUI caches "
            f"({_format_cache_totals_compact(cache_totals)})."
        )
        self._refresh_status_runtime()

    def _show_cache_stats(self) -> None:
        cache_totals = _cache_domain_totals(self.provider)
        self._set_palette_feedback(
            f"TUI cache stats ({_format_cache_totals_compact(cache_totals)})."
        )
        self._refresh_status_runtime()

    def _refresh_status_runtime(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one(StatusTab).refresh_runtime()

    def _page_active_tab(self, *, step: int) -> None:
        active = self._active_tab_id()
        if active == "tab_scenarios":
            scenarios_tab = self.query_one(ScenariosTab)
            if step > 0:
                scenarios_tab.action_next_page()
                self._set_palette_feedback("Next page requested for scenarios.")
            else:
                scenarios_tab.action_prev_page()
                self._set_palette_feedback("Previous page requested for scenarios.")
            return
        if active == "tab_results":
            results_tab = self.query_one(ResultsTab)
            if step > 0:
                results_tab.action_next_page()
                self._set_palette_feedback("Next page requested for results.")
            else:
                results_tab.action_prev_page()
                self._set_palette_feedback("Previous page requested for results.")
            return
        if active == "tab_assessments":
            assessments_tab = self.query_one(AssessmentsTab)
            if step > 0:
                assessments_tab.action_next_page()
                self._set_palette_feedback("Next page requested for assessments.")
            else:
                assessments_tab.action_prev_page()
                self._set_palette_feedback("Previous page requested for assessments.")
            return
        if active == "tab_tests":
            tests_tab = self.query_one(WorkflowTestsTab)
            if step > 0:
                tests_tab.action_next_page()
                self._set_palette_feedback("Next page requested for tests.")
            else:
                tests_tab.action_prev_page()
                self._set_palette_feedback("Previous page requested for tests.")
            return
        if active == "tab_assets":
            assets_tab = self.query_one(WorkflowAssetsTab)
            if step > 0:
                assets_tab.action_next_page()
                self._set_palette_feedback("Next page requested for assets.")
            else:
                assets_tab.action_prev_page()
                self._set_palette_feedback("Previous page requested for assets.")
            return
        if active == "tab_settings":
            settings_tab = self.query_one(WorkflowSettingsTab)
            if step > 0:
                settings_tab.action_next_page()
                self._set_palette_feedback("Next page requested for settings.")
            else:
                settings_tab.action_prev_page()
                self._set_palette_feedback("Previous page requested for settings.")
            return
        self._set_palette_feedback("Paging is not available in this tab.")

    def _export_active_tab(self, fmt: str) -> None:
        active = self._active_tab_id()
        if active == "tab_status":
            self._set_palette_feedback(
                f"Export {fmt.upper()} is not available on Landing / Status."
            )
            return
        if active == "tab_scenarios":
            scenarios_tab = self.query_one(ScenariosTab)
            if fmt == "json":
                scenarios_tab.action_export_json()
            else:
                scenarios_tab.action_export_csv()
            self._set_palette_feedback(f"Export {fmt.upper()} requested for scenarios.")
            return
        if active == "tab_results":
            results_tab = self.query_one(ResultsTab)
            if fmt == "json":
                results_tab.action_export_json()
            else:
                results_tab.action_export_csv()
            self._set_palette_feedback(f"Export {fmt.upper()} requested for results.")
            return
        if active == "tab_assessments":
            assessments_tab = self.query_one(AssessmentsTab)
            if fmt == "json":
                assessments_tab.action_export_json()
            else:
                assessments_tab.action_export_csv()
            self._set_palette_feedback(f"Export {fmt.upper()} requested for assessments.")
            return
        if active == "tab_tests":
            tests_tab = self.query_one(WorkflowTestsTab)
            if fmt == "json":
                tests_tab.action_export_json()
            else:
                tests_tab.action_export_csv()
            self._set_palette_feedback(f"Export {fmt.upper()} requested for tests.")
            return
        if active == "tab_assets":
            assets_tab = self.query_one(WorkflowAssetsTab)
            if fmt == "json":
                assets_tab.action_export_json()
            else:
                assets_tab.action_export_csv()
            self._set_palette_feedback(f"Export {fmt.upper()} requested for assets.")
            return
        if active == "tab_settings":
            settings_tab = self.query_one(WorkflowSettingsTab)
            if fmt == "json":
                settings_tab.action_export_json()
            else:
                settings_tab.action_export_csv()
            self._set_palette_feedback(f"Export {fmt.upper()} requested for settings.")
            return
        self._set_palette_feedback("Export is not available in this tab.")

    def _show_filter_help(self) -> None:
        active = self._active_tab_id()
        if active == "tab_status":
            self._set_palette_feedback(
                "Status tab has no list filters; use Refresh to update diagnostics and "
                "cache/runtime indicators."
            )
            return
        if active == "tab_scenarios":
            self._set_palette_feedback(
                "Scenario filters: search, tag, name, order_by, modified_after, mitre_platforms, "
                "hierarchy, object_fingerprint, parameters_description, "
                "scenario_template_instance. Example: sort=name dir=asc tag=windows"
            )
            return
        if active == "tab_results":
            self._set_palette_feedback(
                "Results filters: sort=<id|scenario|outcome|completed|key|source|count>, "
                "dir=<asc|desc>, outcome=<text>, source=<result_summary_id|scenario_job_id>, "
                "key=<text>. Example: sort=scenario dir=asc outcome=pass"
            )
            return
        if active == "tab_assessments":
            self._set_palette_feedback(
                "Assessment filters: search, name, id__in (id), tag_id, tag_ids, "
                "asset_group_id, blueprint_id, execution_strategy (strategy), "
                "has_default_schedule, use_scenario_alert_rules, version, zones_ordering, "
                "sort=<id|name|type|status|updated>, dir=<asc|desc>. "
                "Example: tag_id=<id> strategy=1 sort=name dir=asc"
            )
            return
        if active == "tab_tests":
            self._set_palette_feedback(
                "Test filters: search/name, project_template_test_id (template), "
                "use_hosted_agent, run_in_hosted_agent_preferably (prefer_hosted), "
                "sort=<id|name|project|runnable|updated>, dir=<asc|desc>. "
                "Example: name=Credential sort=name dir=asc"
            )
            return
        if active == "tab_assets":
            self._set_palette_feedback(
                "Asset filters: search, hostname, ipv4_address, ipv6_address, "
                "deployment_state_id (state), asset_group (group), activity_type (type), "
                "ordering (order_by), deepsurface_sync_state, "
                "deepsurface_last_seen_in_host_analysis_at, "
                "deepsurface_sync_state_changed_at, sort=<id|hostname|type|state|updated>, "
                "dir=<asc|desc>. "
                "Example: search=agent state=2 sort=hostname"
            )
            return
        if active == "tab_settings":
            self._set_palette_feedback(
                "Settings filters: search, key, value, source, category, "
                "sort=<key|value|source|category>, dir=<asc|desc>. "
                "Example: category=runtime sort=key dir=asc"
            )
            return
        self._set_palette_feedback("Filter help is not available in this tab.")

    def _focus_active_input(self, *, input_name: str) -> None:
        active = self._active_tab_id()
        prefix_map = {
            "tab_scenarios": "scenarios",
            "tab_results": "results",
            "tab_assessments": "assessments",
            "tab_tests": "tests",
            "tab_assets": "assets",
            "tab_settings": "settings",
        }
        prefix = prefix_map.get(active)
        if prefix is not None:
            suffix = "search" if input_name == "search" else "structured"
            self.query_one(f"#{prefix}_filter_{suffix}", Input).focus()
            self._set_palette_feedback(f"Focused {prefix} {input_name} input.")
            return
        self._set_palette_feedback("Filter inputs are not available in this tab.")

    def _set_palette_feedback(self, message: str) -> None:
        self.query_one(BannerBar).set_message(f"Command: {message}")


def _tab_shortcuts_text(*, include_export: bool) -> str:
    base = (
        "Keys: Ctrl+K=Commands [=Prev tab ]=Next tab n=Next p=Prev r=Refresh Enter=Apply filter "
        "Tab=Focus next q=Quit ?/h=Help Esc=Close help"
    )
    if include_export:
        return f"{base} e=Export JSON c=Export CSV"
    return base


def _palette_entry_matches(entry: CommandPaletteEntry, query: str) -> bool:
    if not query:
        return True
    tokens = [token for token in query.split() if token]
    searchable = " ".join(
        [
            entry.command_id.lower(),
            entry.label.lower(),
            entry.group.lower(),
            " ".join(keyword.lower() for keyword in entry.keywords),
            (entry.shortcut or "").lower(),
        ]
    )
    return all(token in searchable for token in tokens)


def _palette_group_hint(entries: list[CommandPaletteEntry]) -> str:
    if not entries:
        return "No matches"
    counts = Counter(entry.group for entry in entries)
    ordered_groups = list(dict.fromkeys(entry.group for entry in entries))
    return ", ".join(f"{group} {counts[group]}" for group in ordered_groups)


def _format_runtime_error(exc: Exception) -> str:
    if isinstance(exc, httpx.ConnectError):
        return f"network connection failed ({exc})"
    if isinstance(exc, httpx.TimeoutException):
        return f"request timed out ({exc})"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"request failed ({exc.response.status_code})"
    if isinstance(exc, httpx.RequestError):
        return f"request failed ({exc})"
    return str(exc)


def _group_by_join_key(items: list[dict[str, Any]]) -> list[ResultsGroup]:
    groups: dict[str, ResultsGroup] = {}
    for item in items:
        result_summary_id = _extract_result_summary_id(item)
        scenario_job_id = _extract_scenario_job_id(item)
        if result_summary_id:
            key = str(result_summary_id)
            source = "result_summary_id"
        elif scenario_job_id:
            key = str(scenario_job_id)
            source = "scenario_job_id"
        else:
            key = "missing"
            source = "missing"
        if key not in groups:
            groups[key] = ResultsGroup(
                key=key,
                source=source,
                result_summary_id=str(result_summary_id) if result_summary_id else None,
                scenario_job_id=str(scenario_job_id) if scenario_job_id else None,
                items=[],
            )
        groups[key].items.append(item)
    return list(groups.values())


def _extract_result_summary_id(item: dict[str, Any]) -> str | None:
    value = item.get("result_summary_id") or item.get("result_summary")
    return _extract_id(value)


def _extract_scenario_job_id(item: dict[str, Any]) -> str | None:
    value = item.get("scenario_job_id") or item.get("scenario_job")
    return _extract_id(value)


def _extract_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        extracted = str(value.get("id") or value.get("uuid") or "")
        return extracted or None
    if isinstance(value, int | float):
        return str(int(value))
    return str(value)


def _build_metadata(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    result_id = summary.get("id") or summary.get("result_summary_id") or summary.get(
        "result_summary"
    )
    if result_id:
        lines.append(f"Result Summary ID: {result_id}")
    scenario_job = summary.get("scenario_job_id") or summary.get("scenario_job")
    if scenario_job:
        lines.append(f"Scenario Job ID: {scenario_job}")
    run_id = summary.get("run_id") or summary.get("assessment_run_id")
    if run_id:
        lines.append(f"Run ID: {run_id}")
    created = summary.get("created") or summary.get("created_at")
    if created:
        lines.append(f"Created: {created}")
    modified = summary.get("modified") or summary.get("updated_at")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No metadata available."


def _build_group_metadata(group: ResultsGroup) -> str:
    lines = [
        f"Join Key: {group.key}",
        f"Source: {group.source}",
        f"Items: {group.count}",
    ]
    return "\n".join(lines)


def _build_scenario_summary(item: dict[str, Any]) -> str:
    lines: list[str] = []
    name = item.get("scenario_name") or item.get("scenario")
    if isinstance(name, dict):
        name = name.get("name") or name.get("id")
    if name:
        lines.append(f"Scenario: {name}")
    scenario_id = item.get("scenario_id")
    if scenario_id:
        lines.append(f"Scenario ID: {scenario_id}")
    scenario_type = item.get("scenario_type") or item.get("scenario_type_id")
    if scenario_type:
        lines.append(f"Scenario Type: {scenario_type}")
    return "\n".join(lines) if lines else "No scenario summary available."


def _build_outcome_summary(item: dict[str, Any]) -> str:
    outcome = item.get("outcome") or item.get("status") or item.get("result")
    if outcome:
        return f"Outcome: {outcome}"
    return "No outcome available."


def _summarize_phases(phases: list[dict[str, Any]]) -> str:
    if not phases:
        return "No phases available."
    numbers = []
    for phase in phases:
        number = phase.get("phase_number") or phase.get("phase")
        if number is not None:
            numbers.append(str(number))
    suffix = ""
    if numbers:
        preview = ", ".join(numbers[:5])
        if len(numbers) > 5:
            preview = f"{preview}, +{len(numbers) - 5} more"
        suffix = f" | Phase numbers: {preview}"
    return f"Phases loaded: {len(phases)}{suffix}"


def _summarize_logs(logs: list[dict[str, Any]]) -> str:
    if not logs:
        return "No logs available."
    return f"Logs loaded: {len(logs)}"


def _missing_join_key() -> str:
    return "Not available (missing join key)."


def _resolve_join_key(group: ResultsGroup) -> tuple[str | None, str | None] | None:
    if group.result_summary_id:
        return group.result_summary_id, None
    if group.scenario_job_id:
        return None, group.scenario_job_id
    return None


def _clean_filter_value(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _parse_structured_filter(
    value: str | None,
    *,
    keys: set[str],
    aliases: dict[str, str] | None = None,
) -> dict[str, str]:
    if not value:
        return {}
    resolved_aliases = aliases or {}
    parsed: dict[str, str] = {}
    for token in shlex.split(value):
        for part in _split_structured_filter_token(token, keys=keys, aliases=resolved_aliases):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                key, raw_value = part.split("=", 1)
            elif ":" in part:
                key, raw_value = part.split(":", 1)
            else:
                continue
            key = key.strip().lower()
            raw_value = raw_value.strip()
            if not key or not raw_value:
                continue
            key = resolved_aliases.get(key, key)
            if key not in keys:
                continue
            parsed[key] = raw_value
    return parsed


def _split_structured_filter_token(
    token: str,
    *,
    keys: set[str],
    aliases: dict[str, str],
) -> list[str]:
    parts = token.split(",")
    if len(parts) == 1:
        return parts
    split_parts: list[str] = []
    current = parts[0]
    for part in parts[1:]:
        separator = "=" if "=" in part else ":" if ":" in part else ""
        if separator:
            candidate_key = part.split(separator, 1)[0].strip().lower()
            resolved_key = aliases.get(candidate_key, candidate_key)
            if resolved_key in keys:
                split_parts.append(current)
                current = part
                continue
        current = f"{current},{part}"
    split_parts.append(current)
    return split_parts


def _parse_filter_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _parse_filter_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("integer filters must use whole-number values.") from exc


def _parse_filter_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("boolean filters must be true or false.")


_SCENARIO_FILTER_KEYS = {
    "order_by",
    "search",
    "tag",
    "name",
    "modified_after",
    "mitre_platforms",
    "hierarchy",
    "object_fingerprint",
    "parameters_description",
    "scenario_template_instance",
    "sort",
    "dir",
}

_SCENARIO_FILTER_ALIASES = {
    "order": "order_by",
    "last_updated": "modified_after",
    "updated": "modified_after",
    "mitre": "mitre_platforms",
    "fingerprint": "object_fingerprint",
    "parameters": "parameters_description",
    "template": "scenario_template_instance",
    "direction": "dir",
}


def _parse_scenario_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_SCENARIO_FILTER_KEYS,
        aliases=_SCENARIO_FILTER_ALIASES,
    )


_ASSESSMENT_FILTER_KEYS = {
    "search",
    "asset_group_id",
    "blueprint_id",
    "execution_strategy",
    "has_default_schedule",
    "name",
    "id__in",
    "report_instance_type",
    "tag_id",
    "tag_ids",
    "use_scenario_alert_rules",
    "version",
    "zones_ordering",
    "sort",
    "dir",
}

_ASSESSMENT_FILTER_ALIASES = {
    "asset_group": "asset_group_id",
    "blueprint": "blueprint_id",
    "id": "id__in",
    "id_in": "id__in",
    "report_type": "report_instance_type",
    "tag": "tag_id",
    "tags": "tag_ids",
    "schedule": "has_default_schedule",
    "strategy": "execution_strategy",
    "alert_rules": "use_scenario_alert_rules",
    "zones": "zones_ordering",
    "order": "sort",
    "direction": "dir",
}

_ASSESSMENTS_SORT_ALIASES = {
    "id": "id",
    "name": "name",
    "type": "type",
    "assessment_type": "type",
    "status": "status",
    "updated": "updated",
    "modified": "updated",
}


def _parse_assessment_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_ASSESSMENT_FILTER_KEYS,
        aliases=_ASSESSMENT_FILTER_ALIASES,
    )


_TEST_FILTER_KEYS = {
    "search",
    "name",
    "project_template_test_id",
    "use_hosted_agent",
    "run_in_hosted_agent_preferably",
    "sort",
    "dir",
}

_TEST_FILTER_ALIASES = {
    "template": "project_template_test_id",
    "prefer_hosted": "run_in_hosted_agent_preferably",
    "order": "sort",
    "direction": "dir",
}

_TESTS_SORT_ALIASES = {
    "id": "id",
    "name": "name",
    "project": "project",
    "runnable": "runnable",
    "updated": "updated",
    "modified": "updated",
}


def _parse_test_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_TEST_FILTER_KEYS,
        aliases=_TEST_FILTER_ALIASES,
    )


_ASSET_FILTER_KEYS = {
    "search",
    "hostname",
    "ipv4_address",
    "ipv6_address",
    "deployment_state_id",
    "deepsurface_last_seen_in_host_analysis_at",
    "deepsurface_sync_state",
    "deepsurface_sync_state_changed_at",
    "asset_group",
    "activity_type",
    "ordering",
    "sort",
    "dir",
}

_ASSET_FILTER_ALIASES = {
    "ipv4": "ipv4_address",
    "ipv6": "ipv6_address",
    "state": "deployment_state_id",
    "group": "asset_group",
    "type": "activity_type",
    "order_by": "ordering",
    "deepsurface_last_seen": "deepsurface_last_seen_in_host_analysis_at",
    "deepsurface_changed": "deepsurface_sync_state_changed_at",
    "deepsurface_state": "deepsurface_sync_state",
    "order": "sort",
    "direction": "dir",
}

_ASSETS_SORT_ALIASES = {
    "id": "id",
    "hostname": "hostname",
    "name": "hostname",
    "type": "type",
    "state": "state",
    "updated": "updated",
    "modified": "updated",
}


def _parse_asset_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_ASSET_FILTER_KEYS,
        aliases=_ASSET_FILTER_ALIASES,
    )


_SETTINGS_FILTER_KEYS = {
    "search",
    "key",
    "value",
    "source",
    "category",
    "sort",
    "dir",
}

_SETTINGS_FILTER_ALIASES = {
    "order": "sort",
    "direction": "dir",
}

_SETTINGS_SORT_ALIASES = {
    "key": "key",
    "value": "value",
    "source": "source",
    "category": "category",
}


def _parse_settings_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_SETTINGS_FILTER_KEYS,
        aliases=_SETTINGS_FILTER_ALIASES,
    )


_RESULTS_FILTER_KEYS = {"sort", "dir", "outcome", "source", "key"}

_RESULTS_FILTER_ALIASES = {
    "order": "sort",
    "direction": "dir",
    "status": "outcome",
    "join_key": "key",
}

_RESULTS_SUMMARY_SORT_ALIASES = {
    "id": "id",
    "result": "id",
    "result_id": "id",
    "scenario": "scenario",
    "name": "scenario",
    "outcome": "outcome",
    "status": "outcome",
    "completed": "completed",
    "updated": "completed",
    "modified": "completed",
}

_RESULTS_GROUP_SORT_ALIASES = {
    "key": "key",
    "join_key": "key",
    "source": "source",
    "count": "count",
    "items": "count",
}

_RESULTS_SOURCE_FILTER_ALIASES = {
    "summary": "result_summary_id",
    "result": "result_summary_id",
    "result_summary": "result_summary_id",
    "result_summary_id": "result_summary_id",
    "job": "scenario_job_id",
    "scenario_job": "scenario_job_id",
    "scenario_job_id": "scenario_job_id",
    "missing": "missing",
}

_SCENARIOS_SORT_ALIASES = {
    "id": "id",
    "name": "name",
    "scenario": "name",
    "type": "type",
    "scenario_type": "type",
    "updated": "updated",
    "modified": "updated",
}


def _parse_results_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_RESULTS_FILTER_KEYS,
        aliases=_RESULTS_FILTER_ALIASES,
    )


def _resolve_results_source_filter(value: str | None) -> str | None:
    if not value:
        return None
    return _RESULTS_SOURCE_FILTER_ALIASES.get(value.strip().lower())


def _normalize_sort_direction(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in {"desc", "descending", "reverse"}


def _resolve_scenarios_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _SCENARIOS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_assessments_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _ASSESSMENTS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_tests_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _TESTS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_assets_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _ASSETS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_settings_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _SETTINGS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_results_sort(
    mode: ResultsViewMode,
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    key = sort_value.strip().lower()
    aliases = _RESULTS_SUMMARY_SORT_ALIASES
    if mode != ResultsViewMode.SUMMARIES:
        aliases = _RESULTS_GROUP_SORT_ALIASES
    normalized = aliases.get(key)
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _sort_text_key(value: Any) -> tuple[bool, str]:
    if value is None:
        return True, ""
    text = str(value).strip()
    if not text:
        return True, ""
    return False, text.lower()


def _sort_scenarios_records(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(_extract_scenario_id(record))
        if sort_field == "name":
            return _sort_text_key(_scenario_name(record))
        if sort_field == "type":
            return _sort_text_key(record.get("scenario_type") or record.get("scenario_type_id"))
        return _sort_text_key(
            record.get("modified") or record.get("updated_at") or record.get("last_updated")
        )

    return sorted(records, key=_key, reverse=descending)


def _sort_assessment_records(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(_extract_assessment_id(record))
        if sort_field == "name":
            return _sort_text_key(_assessment_name(record))
        if sort_field == "type":
            return _sort_text_key(_assessment_type(record))
        if sort_field == "status":
            return _sort_text_key(record.get("status"))
        return _sort_text_key(
            record.get("modified") or record.get("updated_at") or record.get("created")
        )

    return sorted(records, key=_key, reverse=descending)


def _sort_test_records(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(_extract_test_id(record))
        if sort_field == "name":
            return _sort_text_key(_test_name(record))
        if sort_field == "project":
            return _sort_text_key(_test_project(record))
        if sort_field == "runnable":
            return _sort_text_key(record.get("runnable"))
        return _sort_text_key(
            record.get("modified") or record.get("updated_at") or record.get("created")
        )

    return sorted(records, key=_key, reverse=descending)


def _sort_asset_records(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(_extract_asset_id(record))
        if sort_field == "hostname":
            return _sort_text_key(_asset_hostname(record))
        if sort_field == "type":
            return _sort_text_key(record.get("activity_type"))
        if sort_field == "state":
            return _sort_text_key(_asset_deployment_state(record))
        return _sort_text_key(record.get("modified") or record.get("updated_at"))

    return sorted(records, key=_key, reverse=descending)


def _filter_settings_records(
    records: list[dict[str, str]],
    *,
    filters: dict[str, str | None],
) -> list[dict[str, str]]:
    search = (filters.get("search") or "").strip().lower()
    key_filter = (filters.get("key") or "").strip().lower()
    value_filter = (filters.get("value") or "").strip().lower()
    source_filter = (filters.get("source") or "").strip().lower()
    category_filter = (filters.get("category") or "").strip().lower()

    def _matches(record: dict[str, str]) -> bool:
        key = (record.get("key") or "").lower()
        value = (record.get("value") or "").lower()
        source = (record.get("source") or "").lower()
        category = (record.get("category") or "").lower()
        haystack = " ".join((key, value, source, category))
        if search and search not in haystack:
            return False
        if key_filter and key_filter not in key:
            return False
        if value_filter and value_filter not in value:
            return False
        if source_filter and source_filter not in source:
            return False
        return not category_filter or category_filter in category

    return [record for record in records if _matches(record)]


def _sort_settings_records(
    records: list[dict[str, str]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, str]]:
    if not sort_field:
        return records

    def _key(record: dict[str, str]) -> Any:
        return _sort_text_key(record.get(sort_field))

    return sorted(records, key=_key, reverse=descending)


def _sort_results_summaries(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(record.get("id") or record.get("result_summary_id"))
        if sort_field == "scenario":
            return _sort_text_key(record.get("scenario_name") or record.get("scenario"))
        if sort_field == "outcome":
            return _sort_text_key(record.get("outcome") or record.get("status"))
        return _sort_text_key(
            record.get("modified") or record.get("completed") or record.get("created")
        )

    return sorted(records, key=_key, reverse=descending)


def _filter_results_summaries(
    records: list[dict[str, Any]],
    *,
    outcome: str | None,
) -> list[dict[str, Any]]:
    if not outcome:
        return records
    normalized = outcome.strip().lower()
    if not normalized:
        return records
    return [
        record
        for record in records
        if normalized
        in str(record.get("outcome") or record.get("status") or "").strip().lower()
    ]


def _filter_results_groups(
    groups: list[ResultsGroup],
    *,
    source: str | None,
    key_query: str | None,
) -> list[ResultsGroup]:
    filtered = groups
    if source:
        filtered = [group for group in filtered if group.source == source]
    if key_query:
        normalized = key_query.strip().lower()
        if normalized:
            filtered = [group for group in filtered if normalized in group.key.lower()]
    return filtered


def _sort_results_groups(
    groups: list[ResultsGroup],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[ResultsGroup]:
    if not sort_field:
        return groups

    def _key(group: ResultsGroup) -> Any:
        if sort_field == "count":
            return group.count
        if sort_field == "source":
            return _sort_text_key(group.source)
        return _sort_text_key(group.key)

    return sorted(groups, key=_key, reverse=descending)


def _extract_assessment_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("assessment_id") or item.get("uuid")
    return _extract_id(value)


def _assessment_name(item: dict[str, Any]) -> str:
    value = item.get("name") or item.get("display_name")
    if value:
        return str(value)
    assessment_id = _extract_assessment_id(item)
    return assessment_id or "Unnamed assessment"


def _assessment_type(item: dict[str, Any]) -> str | None:
    raw = item.get("assessment_type")
    if isinstance(raw, dict):
        value = raw.get("name") or raw.get("display_name") or raw.get("id") or raw.get("uuid")
        return str(value) if value else None
    if raw is not None and str(raw).strip():
        return str(raw)
    fallback = item.get("assessment_type_name") or item.get("assessment_type_id")
    if fallback is not None and str(fallback).strip():
        return str(fallback)
    return None


def _build_assessment_metadata(item: dict[str, Any]) -> str:
    lines: list[str] = []
    assessment_id = _extract_assessment_id(item)
    if assessment_id:
        lines.append(f"Assessment ID: {assessment_id}")
    lines.append(f"Name: {_assessment_name(item)}")
    assessment_type = _assessment_type(item)
    if assessment_type:
        lines.append(f"Type: {assessment_type}")
    status = item.get("status")
    if status:
        lines.append(f"Status: {status}")
    created = item.get("created") or item.get("created_at")
    if created:
        lines.append(f"Created: {created}")
    modified = item.get("modified") or item.get("updated_at")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No metadata available."


def _build_assessment_config(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("execution_strategy") is not None:
        lines.append(f"Execution strategy: {item.get('execution_strategy')}")
    if item.get("zones_ordering") is not None:
        lines.append(f"Zones ordering: {item.get('zones_ordering')}")
    if item.get("report_instance_type"):
        lines.append(f"Report instance type: {item.get('report_instance_type')}")
    if item.get("version") is not None:
        lines.append(f"Version: {item.get('version')}")
    if item.get("has_default_schedule") is not None:
        lines.append(f"Has default schedule: {item.get('has_default_schedule')}")
    return "\n".join(lines) if lines else "No configuration details available."


def _build_assessment_execution(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("asset_group_id"):
        lines.append(f"Asset group: {item.get('asset_group_id')}")
    if item.get("blueprint_id"):
        lines.append(f"Blueprint: {item.get('blueprint_id')}")
    if item.get("use_scenario_alert_rules") is not None:
        lines.append(f"Use scenario alert rules: {item.get('use_scenario_alert_rules')}")
    last_run = item.get("last_run") or item.get("last_execution")
    if isinstance(last_run, dict):
        run_id = last_run.get("id") or last_run.get("uuid")
        if run_id:
            lines.append(f"Last run: {run_id}")
    elif last_run:
        lines.append(f"Last run: {last_run}")
    return "\n".join(lines) if lines else "No execution details available."


def _extract_asset_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("asset_id") or item.get("uuid")
    return _extract_id(value)


def _asset_hostname(item: dict[str, Any]) -> str:
    value = item.get("hostname") or item.get("name")
    if value:
        return str(value)
    asset_id = _extract_asset_id(item)
    return asset_id or "Unnamed asset"


def _asset_deployment_state(item: dict[str, Any]) -> str | None:
    value = item.get("deployment_state")
    if isinstance(value, dict):
        resolved = value.get("name") or value.get("display_name") or value.get("id")
        return str(resolved) if resolved else None
    if value is not None and str(value).strip():
        return str(value)
    fallback = item.get("deployment_state_id")
    if fallback is not None and str(fallback).strip():
        return str(fallback)
    return None


def _build_asset_metadata(item: dict[str, Any]) -> str:
    lines: list[str] = []
    asset_id = _extract_asset_id(item)
    if asset_id:
        lines.append(f"Asset ID: {asset_id}")
    lines.append(f"Hostname: {_asset_hostname(item)}")
    if item.get("activity_type"):
        lines.append(f"Activity type: {item.get('activity_type')}")
    state = _asset_deployment_state(item)
    if state:
        lines.append(f"Deployment state: {state}")
    modified = item.get("modified") or item.get("updated_at")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No metadata available."


def _build_asset_network(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("ipv4_address"):
        lines.append(f"IPv4: {item.get('ipv4_address')}")
    if item.get("ipv6_address"):
        lines.append(f"IPv6: {item.get('ipv6_address')}")
    if item.get("deepsurface_id"):
        lines.append(f"Deepsurface ID: {item.get('deepsurface_id')}")
    if item.get("testpoint_id"):
        lines.append(f"Testpoint ID: {item.get('testpoint_id')}")
    return "\n".join(lines) if lines else "No network details available."


def _build_asset_status(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("risk"):
        lines.append(f"Risk: {item.get('risk')}")
    if item.get("risk_score") is not None:
        lines.append(f"Risk score: {item.get('risk_score')}")
    if item.get("last_seen_discovery"):
        lines.append(f"Last seen discovery: {item.get('last_seen_discovery')}")
    if item.get("deepsurface_scanned") is not None:
        lines.append(f"Deepsurface scanned: {item.get('deepsurface_scanned')}")
    return "\n".join(lines) if lines else "No status details available."


def _extract_test_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("test_id") or item.get("uuid")
    return _extract_id(value)


def _test_name(item: dict[str, Any]) -> str:
    value = item.get("name") or item.get("display_name")
    if value:
        return str(value)
    test_id = _extract_test_id(item)
    return test_id or "Unnamed test"


def _test_project(item: dict[str, Any]) -> str | None:
    project = item.get("project")
    if isinstance(project, dict):
        value = project.get("name") or project.get("display_name") or project.get("id")
        return str(value) if value else None
    if project is not None and str(project).strip():
        return str(project)
    return None


def _build_test_metadata(item: dict[str, Any]) -> str:
    lines: list[str] = []
    test_id = _extract_test_id(item)
    if test_id:
        lines.append(f"Test ID: {test_id}")
    lines.append(f"Name: {_test_name(item)}")
    project = _test_project(item)
    if project:
        lines.append(f"Project: {project}")
    created = item.get("created") or item.get("created_at")
    if created:
        lines.append(f"Created: {created}")
    modified = item.get("modified") or item.get("updated_at")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No metadata available."


def _build_test_config(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("runnable") is not None:
        lines.append(f"Runnable: {item.get('runnable')}")
    if item.get("order") is not None:
        lines.append(f"Order: {item.get('order')}")
    if item.get("use_hosted_agent") is not None:
        lines.append(f"Use hosted agent: {item.get('use_hosted_agent')}")
    if item.get("use_pool_agent") is not None:
        lines.append(f"Use pool agent: {item.get('use_pool_agent')}")
    return "\n".join(lines) if lines else "No configuration details available."


def _build_test_execution(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("scheduled_count") is not None:
        lines.append(f"Scheduled count: {item.get('scheduled_count')}")
    if item.get("using_default_assets") is not None:
        lines.append(f"Using default assets: {item.get('using_default_assets')}")
    if item.get("using_default_schedule") is not None:
        lines.append(f"Using default schedule: {item.get('using_default_schedule')}")
    if item.get("has_scenario_modules") is not None:
        lines.append(f"Has scenario modules: {item.get('has_scenario_modules')}")
    return "\n".join(lines) if lines else "No execution details available."


def _extract_scenario_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("scenario_id") or item.get("uuid")
    return _extract_id(value)


def _scenario_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("scenario_name") or item.get("scenario") or "")


def _build_scenario_metadata(item: dict[str, Any]) -> str:
    lines: list[str] = []
    scenario_id = _extract_scenario_id(item)
    if scenario_id:
        lines.append(f"Scenario ID: {scenario_id}")
    name = _scenario_name(item)
    if name:
        lines.append(f"Name: {name}")
    scenario_type = item.get("scenario_type") or item.get("scenario_type_id") or item.get("type")
    if scenario_type:
        lines.append(f"Type: {scenario_type}")
    status = item.get("status") or item.get("state")
    if status:
        lines.append(f"Status: {status}")
    created = item.get("created") or item.get("created_at")
    if created:
        lines.append(f"Created: {created}")
    modified = item.get("modified") or item.get("updated_at") or item.get("last_updated")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No scenario metadata available."


def _build_scenario_description(item: dict[str, Any]) -> str:
    description = item.get("description") or item.get("summary") or item.get("details")
    if description:
        return str(description)
    return "No description available."


def _build_scenario_tags(item: dict[str, Any]) -> str:
    tags = item.get("tags") or item.get("tag") or []
    if not tags:
        return "No tags available."
    values: list[str] = []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict):
                value = tag.get("name") or tag.get("display_name") or tag.get("id")
                if value:
                    values.append(str(value))
            else:
                values.append(str(tag))
    elif isinstance(tags, dict):
        value = tags.get("name") or tags.get("display_name") or tags.get("id")
        if value:
            values.append(str(value))
    else:
        values.append(str(tags))
    if not values:
        return "No tags available."
    preview = ", ".join(values[:8])
    if len(values) > 8:
        preview = f"{preview}, +{len(values) - 8} more"
    return preview


def _build_scenario_parameters(item: dict[str, Any]) -> str:
    value = item.get("parameters_description")
    if value:
        return str(value)
    parameters = item.get("parameters")
    if isinstance(parameters, dict):
        keys = sorted(str(key) for key in parameters if str(key).strip())
        if not keys:
            return "No parameters available."
        preview = ", ".join(keys[:8])
        if len(keys) > 8:
            preview = f"{preview}, +{len(keys) - 8} more"
        return f"Keys: {preview}"
    if isinstance(parameters, list):
        if not parameters:
            return "No parameters available."
        names: list[str] = []
        for entry in parameters:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("key") or entry.get("id")
                if name:
                    names.append(str(name))
            else:
                names.append(str(entry))
        if not names:
            return "No parameters available."
        preview = ", ".join(names[:8])
        if len(names) > 8:
            preview = f"{preview}, +{len(names) - 8} more"
        return preview
    if parameters not in (None, ""):
        return str(parameters)
    return "No parameters available."


def _build_scenario_relationships(item: dict[str, Any]) -> str:
    lines: list[str] = []
    capabilities = item.get("capabilities")
    if isinstance(capabilities, list):
        names: list[str] = []
        for capability in capabilities:
            if isinstance(capability, dict):
                value = (
                    capability.get("display_name")
                    or capability.get("name")
                    or capability.get("id")
                )
                if value:
                    names.append(str(value))
            elif capability:
                names.append(str(capability))
        if names:
            preview = ", ".join(names[:6])
            if len(names) > 6:
                preview = f"{preview}, +{len(names) - 6} more"
            lines.append(f"Capabilities: {preview}")
    template_instance = item.get("scenario_template_instance")
    if template_instance:
        lines.append(f"Template Instance: {template_instance}")
    tag_sets = item.get("scenario_tags") or item.get("tags")
    if isinstance(tag_sets, list):
        lines.append(f"Tag Relations: {len(tag_sets)}")
    assessments = item.get("assessments")
    if isinstance(assessments, list):
        lines.append(f"Assessments: {len(assessments)}")
    if not lines:
        return "No relationships available."
    return "\n".join(lines)


def _build_scenario_config(item: dict[str, Any]) -> str:
    fields = [
        ("MITRE Platforms", item.get("mitre_platforms")),
        ("Hierarchy", item.get("hierarchy")),
        ("Fingerprint", item.get("object_fingerprint") or item.get("fingerprint")),
        ("Parameters", item.get("parameters_description") or item.get("parameters")),
        ("Template Instance", item.get("scenario_template_instance")),
    ]
    lines = []
    for label, value in fields:
        if value in (None, ""):
            continue
        if isinstance(value, list):
            value = ", ".join(str(entry) for entry in value)
        lines.append(f"{label}: {value}")
    return "\n".join(lines) if lines else "No configuration data available."


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _consume_task(task: asyncio.Task) -> None:
    with contextlib.suppress(asyncio.CancelledError, Exception):
        task.result()


def _cancel_task(task: asyncio.Task[Any] | None) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()


def _replace_task(
    existing: asyncio.Task[Any] | None,
    coroutine: Coroutine[Any, Any, None],
) -> asyncio.Task[None]:
    _cancel_task(existing)
    task = asyncio.create_task(coroutine)
    task.add_done_callback(_consume_task)
    return task


async def _cancel_and_await_tasks(*tasks: asyncio.Task[Any] | None) -> None:
    active = [task for task in tasks if task is not None]
    if not active:
        return
    for task in active:
        _cancel_task(task)
    await asyncio.gather(*active, return_exceptions=True)


def _schedule_debounced(
    existing: asyncio.Task | None,
    delay: float,
    action: Callable[[], Awaitable[None]],
) -> asyncio.Task:
    if existing is not None and not existing.done():
        existing.cancel()

    async def _debounced() -> None:
        try:
            await asyncio.sleep(delay)
            await action()
        except asyncio.CancelledError:
            return

    return asyncio.create_task(_debounced())


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
