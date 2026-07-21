from __future__ import annotations

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Input, LoadingIndicator, Static

from attackiq_cli.services import build_asset_summary_records
from attackiq_cli.tui_display import _format_runtime_error, _tab_shortcuts_text
from attackiq_cli.tui_exports import build_tui_export_path, write_tui_export
from attackiq_cli.tui_filters import (
    _clean_filter_value,
    _parse_asset_filter,
    _resolve_assets_sort,
)
from attackiq_cli.tui_provider import TuiDataProvider, TuiState
from attackiq_cli.tui_record_lists import _sort_asset_records
from attackiq_cli.tui_record_text import (
    _asset_deployment_state,
    _asset_hostname,
    _build_asset_metadata,
    _build_asset_network,
    _build_asset_status,
    _extract_asset_id,
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
            records, has_next = await _run_blocking(self._executor,
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
            detail = await _run_blocking(
                self._executor,
                self.provider.fetch_asset_detail,
                asset_id=asset_id,
            )
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

        try:
            await _run_blocking(self._executor,
                write_tui_export,
                output,
                fmt,
                records,
                include_other_fields=False,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._set_banner(f"Assets export failed: {_format_runtime_error(exc)}")
            self._update_list_status("Failed to export assets.")
            return
        finally:
            loading.display = False
        self._set_banner("")
        self._update_list_status(f"Exported assets to {output}")

    def _default_export_path(self, fmt: str) -> Path:
        return build_tui_export_path(self.state.workspace_full, "assets", fmt, page=self.page)

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
