from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_widgets


class _WidgetTestApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.state = SimpleNamespace(
            authenticated=True,
            env_display="api.example.com",
            workspace_display="/repo",
        )

    def compose(self) -> ComposeResult:
        yield tui_widgets.HeaderBar(self.state)  # type: ignore[arg-type]
        yield tui_widgets.BannerBar()
        yield tui_widgets.FilterBar("demo")


@pytest.mark.anyio
async def test_header_banner_and_filter_widgets_mount() -> None:
    app = _WidgetTestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        banner = app.query_one(tui_widgets.BannerBar)
        banner.set_message("Ready")

        assert str(app.query_one("#header_env", Static).renderable) == "Env: api.example.com"
        assert app.query_one("#demo_filter_search") is not None
        assert str(app.query_one("#banner_message", Static).renderable) == "Ready"
        assert banner.display is True


def test_status_tab_runtime_line_uses_provider_cache_counts() -> None:
    state = SimpleNamespace()
    options = SimpleNamespace(
        page_size=20,
        timeout=None,
        timeout_source="config",
        insecure=False,
        insecure_source="config",
    )
    provider = SimpleNamespace(
        scenarios_cache_stats=lambda: (1, 2),
        results_cache_stats=lambda: (3, 4, 5),
        assessments_cache_stats=lambda: (6, 7),
        tests_cache_stats=lambda: (8, 9),
        assets_cache_stats=lambda: (10, 11),
        templates_cache_stats=lambda: (12, 13),
    )

    tab = tui_widgets.StatusTab(state, options, provider)  # type: ignore[arg-type]

    runtime = tab._build_runtime_line()
    assert "page_size=20" in runtime
    assert "timeout=default (config)" in runtime
    assert "insecure=no (config)" in runtime
    assert "cache_entries=scenarios:3,results:12" in runtime


def test_tui_module_reexports_widgets_for_compatibility() -> None:
    assert tui_module.HeaderBar is tui_widgets.HeaderBar
    assert tui_module.BannerBar is tui_widgets.BannerBar
    assert tui_module.FilterBar is tui_widgets.FilterBar
    assert tui_module.StatusTab is tui_widgets.StatusTab
    assert tui_module.WorkflowTab is tui_widgets.WorkflowTab
