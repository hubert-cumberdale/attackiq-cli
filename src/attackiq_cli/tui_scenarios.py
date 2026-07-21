from __future__ import annotations

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Input, LoadingIndicator, Static

from attackiq_cli.exporter import SCENARIO_FIELD_ORDER
from attackiq_cli.services import ScenarioFilters, build_scenario_summary_records
from attackiq_cli.tui_display import _format_runtime_error, _tab_shortcuts_text
from attackiq_cli.tui_exports import build_tui_export_path, write_tui_export
from attackiq_cli.tui_filters import (
    _clean_filter_value,
    _parse_scenario_filter,
    _resolve_scenarios_sort,
)
from attackiq_cli.tui_provider import TuiDataProvider, TuiState
from attackiq_cli.tui_record_lists import _sort_scenarios_records
from attackiq_cli.tui_record_text import (
    _build_scenario_config,
    _build_scenario_description,
    _build_scenario_metadata,
    _build_scenario_parameters,
    _build_scenario_relationships,
    _build_scenario_tags,
    _extract_scenario_id,
    _scenario_name,
    _stringify,
)
from attackiq_cli.tui_tasks import (
    _cancel_and_await_tasks,
    _cancel_task,
    _consume_task,
    _replace_task,
    _run_blocking,
    _schedule_debounced,
)
from attackiq_cli.tui_widgets import BannerBar, FilterBar


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
            records, has_next = await _run_blocking(self._executor,
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
            detail = await _run_blocking(self._executor,
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

    def selected_scenario_id(self) -> str | None:
        item = self._selected_record()
        return _extract_scenario_id(item) if item is not None else None

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

        try:
            await _run_blocking(self._executor,
                write_tui_export,
                output,
                fmt,
                records,
                preferred_fields=SCENARIO_FIELD_ORDER,
                include_preferred_missing=True,
                include_other_fields=False,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Scenarios export failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to export scenarios.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self._update_list_status(f"Exported scenarios to {output}")

    def _default_export_path(self, fmt: str) -> Path:
        return build_tui_export_path(self.state.workspace_full, "scenarios", fmt, page=self.page)

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
