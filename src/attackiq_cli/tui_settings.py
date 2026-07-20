from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Input, Static

from attackiq_cli.tui_display import _tab_shortcuts_text
from attackiq_cli.tui_exports import build_tui_export_path, write_tui_export
from attackiq_cli.tui_filters import (
    _clean_filter_value,
    _parse_settings_filter,
    _resolve_settings_sort,
)
from attackiq_cli.tui_provider import TuiDataProvider, TuiState, _cache_domain_totals
from attackiq_cli.tui_record_lists import (
    _filter_settings_records,
    _sort_settings_records,
)
from attackiq_cli.tui_record_text import _stringify
from attackiq_cli.tui_widgets import BannerBar, FilterBar


def build_settings_records(state: TuiState, provider: Any) -> list[dict[str, str]]:
    cache_ttl = provider.cache_ttl_seconds()
    cache_ttl_display = "none" if cache_ttl is None else str(cache_ttl)
    cache_totals = _cache_domain_totals(provider)
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
            "value": state.base_url,
            "source": state.base_url_source,
            "category": "config",
        },
        {
            "key": "auth_mode",
            "value": state.auth_mode,
            "source": state.auth_source,
            "category": "config",
        },
        {
            "key": "spec_cache",
            "value": state.spec_cache_status,
            "source": state.spec_cache_dir_source,
            "category": "config",
        },
        {
            "key": "spec_cache_dir",
            "value": state.spec_cache_dir,
            "source": state.spec_cache_dir_source,
            "category": "config",
        },
        {
            "key": "spec_load_source",
            "value": state.spec_load_source,
            "source": "runtime",
            "category": "config",
        },
        {
            "key": "timeout",
            "value": str(provider.options.timeout),
            "source": provider.options.timeout_source,
            "category": "runtime",
        },
        {
            "key": "insecure",
            "value": "yes" if provider.options.insecure else "no",
            "source": provider.options.insecure_source,
            "category": "runtime",
        },
        {
            "key": "page_size",
            "value": str(provider.options.page_size),
            "source": "cli",
            "category": "runtime",
        },
        {
            "key": "cache_max",
            "value": str(provider.cache_max_entries()),
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
            "value": state.workspace_full,
            "source": "runtime",
            "category": "workspace",
        },
    ]


def build_settings_detail(record: dict[str, str]) -> str:
    lines = [
        f"Key: {record.get('key')}",
        f"Value: {record.get('value')}",
        f"Source: {record.get('source')}",
        f"Category: {record.get('category')}",
    ]
    return "\n".join(lines)


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
                build_settings_records(self.state, self.provider),
                filters=self._build_filters(),
            ),
            sort_field=self.sort_field,
            descending=self.sort_desc,
        )
        self._render_table()
        self._update_list_status(self._build_list_status())
        self._set_banner("")

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
        self.query_one("#settings_section_metadata", Static).update(
            build_settings_detail(record)
        )
        self.query_one("#settings_detail_status", Static).update("Detail load complete.")

    def _set_banner(self, message: str) -> None:
        self.app.query_one(BannerBar).set_message(message)

    def _export_current(self, fmt: str) -> None:
        if not self.records:
            self._update_list_status("No settings entries to export.")
            return
        output = self._default_export_path(fmt)
        write_tui_export(
            output,
            fmt,
            self.records,
            preferred_fields=["key", "value", "source", "category"],
            include_other_fields=False,
        )
        self._update_list_status(f"Exported settings to {output}")
        self._set_banner("")

    def _default_export_path(self, fmt: str) -> Path:
        return build_tui_export_path(self.state.workspace_full, "settings", fmt)

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
            changed_inputs = int(search_input.value != (self.search or "")) + int(
                structured_input.value != (self.structured_filter or "")
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
