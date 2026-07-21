from __future__ import annotations

import contextlib
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Input, Static, TabbedContent, TabPane

from attackiq_cli.tui_assessments import AssessmentsTab
from attackiq_cli.tui_assets import WorkflowAssetsTab
from attackiq_cli.tui_display import _palette_entry_matches, _palette_group_hint
from attackiq_cli.tui_domains import (
    CommandPaletteEntry,
    allowed_command_ids_for_tab,
    build_command_palette_entries,
    filter_help_for_tab,
    focus_prefix_for_tab,
    tab_id_for_short_name,
)
from attackiq_cli.tui_preview import (
    AssessmentDefaultsPreviewScreen,
    AssessmentFromTemplatePreviewScreen,
    AssessmentRunPreviewScreen,
    NewAssessmentPreviewScreen,
    NewTestPreviewScreen,
    TestScenariosPreviewScreen,
    TestStatusPreviewScreen,
)
from attackiq_cli.tui_provider import (
    TuiDataProvider,
    TuiState,
    _cache_domain_totals,
    _format_cache_totals_compact,
)
from attackiq_cli.tui_results import ResultsTab
from attackiq_cli.tui_scenarios import ScenariosTab
from attackiq_cli.tui_settings import WorkflowSettingsTab
from attackiq_cli.tui_styles import TUI_CSS
from attackiq_cli.tui_tests import WorkflowTestsTab
from attackiq_cli.tui_widgets import BannerBar, HeaderBar, StatusTab


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
    CSS = TUI_CSS

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
                    "Read-only mode | Request previews never send requests",
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
        return build_command_palette_entries()

    def _available_palette_entries(self) -> list[CommandPaletteEntry]:
        allowed = allowed_command_ids_for_tab(self._active_tab_id())
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
        if command_id == "preview:assessment-run":
            self._hide_command_palette()
            self._open_assessment_run_preview()
            return
        if command_id == "preview:assessment-defaults":
            self._hide_command_palette()
            self._open_assessment_defaults_preview()
            return
        if command_id == "preview:assessment-from-template":
            self._hide_command_palette()
            self._open_assessment_from_template_preview()
            return
        if command_id == "preview:new-test":
            self._hide_command_palette()
            self._open_new_test_preview()
            return
        if command_id == "preview:new-assessment":
            self._hide_command_palette()
            self._open_new_assessment_preview()
            return
        if command_id == "preview:test-scenarios":
            self._hide_command_palette()
            self._open_test_scenarios_preview()
            return
        if command_id == "preview:test-status":
            self._hide_command_palette()
            self._open_test_status_preview()
            return
        if command_id == "help":
            self.action_toggle_help()
            self._set_palette_feedback("Toggled keyboard help overlay.")
            self._hide_command_palette()

    def _active_tab_id(self) -> str:
        tabs = self.query_one("#main_tabs", TabbedContent)
        return tabs.active or "tab_status"

    def _activate_tab(self, short_name: str) -> None:
        tab_id = tab_id_for_short_name(short_name) or f"tab_{short_name}"
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
        help_text = filter_help_for_tab(self._active_tab_id())
        if help_text is not None:
            self._set_palette_feedback(help_text)
            return
        self._set_palette_feedback("Filter help is not available in this tab.")

    def _open_assessment_run_preview(self) -> None:
        assessment_id = self.query_one(AssessmentsTab).selected_assessment_id()
        self.push_screen(
            AssessmentRunPreviewScreen(
                self.provider.context.spec,
                assessment_id=assessment_id,
            )
        )

    def _open_assessment_defaults_preview(self) -> None:
        assessment_id = self.query_one(AssessmentsTab).selected_assessment_id()
        self.push_screen(
            AssessmentDefaultsPreviewScreen(
                self.provider.context.spec,
                assessment_id=assessment_id,
            )
        )

    def _open_new_test_preview(self) -> None:
        assessment_id = self.query_one(AssessmentsTab).selected_assessment_id()
        self.push_screen(
            NewTestPreviewScreen(
                self.provider.context.spec,
                assessment_id=assessment_id,
            )
        )

    def _open_assessment_from_template_preview(self) -> None:
        self.push_screen(AssessmentFromTemplatePreviewScreen(self.provider.context.spec))

    def _open_new_assessment_preview(self) -> None:
        scenario_id = self.query_one(ScenariosTab).selected_scenario_id()
        self.push_screen(NewAssessmentPreviewScreen(scenario_id=scenario_id))

    def _open_test_status_preview(self) -> None:
        test_id = self.query_one(WorkflowTestsTab).selected_test_id()
        self.push_screen(
            TestStatusPreviewScreen(
                self.provider.context.spec,
                test_id=test_id,
            )
        )

    def _open_test_scenarios_preview(self) -> None:
        test_id = self.query_one(WorkflowTestsTab).selected_test_id()
        self.push_screen(
            TestScenariosPreviewScreen(
                self.provider.context.spec,
                test_id=test_id,
            )
        )

    def _focus_active_input(self, *, input_name: str) -> None:
        prefix = focus_prefix_for_tab(self._active_tab_id())
        if prefix is not None:
            suffix = "search" if input_name == "search" else "structured"
            self.query_one(f"#{prefix}_filter_{suffix}", Input).focus()
            self._set_palette_feedback(f"Focused {prefix} {input_name} input.")
            return
        self._set_palette_feedback("Filter inputs are not available in this tab.")

    def _set_palette_feedback(self, message: str) -> None:
        self.query_one(BannerBar).set_message(f"Command: {message}")
