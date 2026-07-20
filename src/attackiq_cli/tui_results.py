from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Input, LoadingIndicator, Select, Static

from attackiq_cli.tui_display import _format_runtime_error, _tab_shortcuts_text
from attackiq_cli.tui_exports import build_tui_export_path, write_tui_export
from attackiq_cli.tui_filters import (
    _clean_filter_value,
    _parse_results_filter,
    _resolve_results_sort,
    _resolve_results_source_filter,
)
from attackiq_cli.tui_provider import ResultsViewMode, TuiDataProvider, TuiState
from attackiq_cli.tui_record_lists import (
    ResultsGroup,
    _build_group_metadata,
    _build_metadata,
    _build_outcome_summary,
    _build_scenario_summary,
    _filter_results_groups,
    _filter_results_summaries,
    _group_by_join_key,
    _missing_join_key,
    _resolve_join_key,
    _sort_results_groups,
    _sort_results_summaries,
    _summarize_logs,
    _summarize_phases,
)
from attackiq_cli.tui_record_text import _stringify
from attackiq_cli.tui_tasks import (
    _cancel_and_await_tasks,
    _cancel_task,
    _consume_task,
    _replace_task,
    _run_blocking,
    _schedule_debounced,
)
from attackiq_cli.tui_widgets import BannerBar, FilterBar


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
            records, has_next = await _run_blocking(self._executor,
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
            phases = await _run_blocking(self._executor,
                self.provider.fetch_phase_results,
                result_summary_id=str(result_summary_id),
            )
            self._set_detail_status("Loading logs (2/2)...")
            logs = await _run_blocking(self._executor,
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
                phases = await _run_blocking(self._executor,
                    self.provider.fetch_phase_results,
                    result_summary_id=result_summary_id,
                    scenario_job_id=scenario_job_id,
                )
                phases_text = _summarize_phases(phases)
                step += 1
            if self.view_mode == ResultsViewMode.PHASES:
                self._set_detail_status(f"Loading logs ({step}/2)...")
                logs = await _run_blocking(self._executor,
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

        try:
            await _run_blocking(self._executor, write_tui_export, output, fmt, records)
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
        return build_tui_export_path(
            self.state.workspace_full,
            f"results_{mode}",
            fmt,
            page=self.page,
        )

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
