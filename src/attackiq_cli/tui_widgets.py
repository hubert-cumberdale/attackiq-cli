from __future__ import annotations

import contextlib

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Input, Static

from attackiq_cli.tui_display import _tab_shortcuts_text
from attackiq_cli.tui_provider import (
    TuiDataProvider,
    TuiOptions,
    TuiState,
    _cache_domain_totals,
    _format_cache_entries_runtime,
    _resolve_tui_cache_max_entries,
    _resolve_tui_cache_ttl_seconds,
)


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
                    "Browse data and inspect local request previews in read-only mode.",
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
        yield Static(
            "Read-only mode. Request previews never send requests.",
            id="status_hint",
            classes="status-hint",
        )
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
