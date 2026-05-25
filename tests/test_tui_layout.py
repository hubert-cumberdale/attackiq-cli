from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import anyio
import httpx
import pytest
from textual.widgets import Input, Static, TabbedContent

from attackiq_cli import tui as tui_module
from attackiq_cli.client import AuthContext
from attackiq_cli.config import CliConfig
from attackiq_cli.services import ServiceContext
from attackiq_cli.spec import SpecIndex
from attackiq_cli.tui import (
    AssessmentsTab,
    AttackIQTuiApp,
    ResultsTab,
    ScenariosTab,
    TuiDataProvider,
    TuiOptions,
    WorkflowAssetsTab,
    WorkflowSettingsTab,
    WorkflowTestsTab,
)


def test_tui_structured_filters_accept_schema_drift_keys() -> None:
    scenario = tui_module._parse_scenario_filter(
        "last_updated=2026-05-21T00:00:00Z updated=2026-05-22T00:00:00Z"
    )
    assessment = tui_module._parse_assessment_filter("id=assessment-1 tag=tag-1 tags=tag-2")
    asset = tui_module._parse_asset_filter(
        "deepsurface_state=synced deepsurface_changed=2026-05-21T01:00:00Z"
    )

    assert scenario["modified_after"] == "2026-05-22T00:00:00Z"
    assert assessment == {
        "id__in": "assessment-1",
        "tag_id": "tag-1",
        "tag_ids": "tag-2",
    }
    assert asset == {
        "deepsurface_sync_state": "synced",
        "deepsurface_sync_state_changed_at": "2026-05-21T01:00:00Z",
    }


def test_tui_assessment_query_params_use_schema_backed_filters() -> None:
    app = _build_app(authenticated=True)
    tab = AssessmentsTab(app.state, app.provider)
    tab.search = "fallback-search"
    tab.structured_filter = (
        "search=prod id=assessment-1,assessment-2 tag=tag-1 tags=tag-2,tag-3 "
        "asset_group=group-1 blueprint=blueprint-1 strategy=1 schedule=false "
        "alert_rules=true version=3 zones=attacker_zone,-target_zone report_type=summary "
        "status=ignored type=ignored"
    )

    assert tab._build_query_params() == {
        "asset_group_id": "group-1",
        "blueprint_id": "blueprint-1",
        "execution_strategy": 1,
        "has_default_schedule": False,
        "id__in": "assessment-1,assessment-2",
        "report_instance_type": "summary",
        "search": "prod",
        "tag_id": "tag-1",
        "tag_ids": "tag-2,tag-3",
        "use_scenario_alert_rules": True,
        "version": 3,
        "zones_ordering": "attacker_zone,-target_zone",
    }


def test_tui_assessment_query_params_validate_typed_filters() -> None:
    app = _build_app(authenticated=True)
    tab = AssessmentsTab(app.state, app.provider)

    tab.structured_filter = "strategy=two"
    with pytest.raises(ValueError, match="integer filters"):
        tab._build_query_params()

    tab.structured_filter = "schedule=maybe"
    with pytest.raises(ValueError, match="boolean filters"):
        tab._build_query_params()


def _cache_entries_text(
    *,
    scenarios: int,
    results: int,
    assessments: int,
    tests: int,
    assets: int,
    templates: int,
) -> str:
    return (
        f"cache_entries=scenarios:{scenarios},"
        f"results:{results},"
        f"assessments:{assessments},"
        f"tests:{tests},"
        f"assets:{assets},"
        f"templates:{templates}"
    )


class _FakeProvider(TuiDataProvider):
    def fetch_results_list(
        self,
        *,
        mode: Any,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        _ = (mode, page, page_size, search)
        return [], False

    def fetch_phase_results(
        self,
        *,
        result_summary_id: str | None = None,
        scenario_job_id: str | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        _ = (result_summary_id, scenario_job_id, page, page_size)
        return []

    def fetch_phase_logs(
        self,
        *,
        result_summary_id: str | None = None,
        scenario_job_id: str | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        _ = (result_summary_id, scenario_job_id, page, page_size)
        return []

    def fetch_scenarios_page(
        self, *, page: int, page_size: int, filters: Any
    ) -> tuple[list[dict[str, Any]], bool]:
        _ = (page, page_size, filters)
        return [], False

    def fetch_scenario_detail(self, *, scenario_id: str) -> dict[str, Any]:
        _ = scenario_id
        return {}

    def fetch_assessments_page(
        self,
        *,
        page: int,
        page_size: int,
        query_params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        _ = (page, page_size, query_params)
        return [], False

    def fetch_assessment_detail(self, *, assessment_id: str) -> dict[str, Any]:
        _ = assessment_id
        return {}

    def fetch_tests_page(
        self,
        *,
        page: int,
        page_size: int,
        query_params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        _ = (page, page_size, query_params)
        return [], False

    def fetch_test_detail(self, *, test_id: str) -> dict[str, Any]:
        _ = test_id
        return {}

    def fetch_assets_page(
        self,
        *,
        page: int,
        page_size: int,
        query_params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        _ = (page, page_size, query_params)
        return [], False

    def fetch_asset_detail(self, *, asset_id: str) -> dict[str, Any]:
        _ = asset_id
        return {}


class _SortableScenarioProvider(_FakeProvider):
    def fetch_scenarios_page(
        self, *, page: int, page_size: int, filters: Any
    ) -> tuple[list[dict[str, Any]], bool]:
        _ = (page, page_size, filters)
        return [
            {
                "id": "scenario-2",
                "name": "Zulu",
                "scenario_type": "atomic",
                "modified": "2026-01-02T00:00:00Z",
            },
            {
                "id": "scenario-1",
                "name": "Alpha",
                "scenario_type": "compound",
                "modified": "2026-01-01T00:00:00Z",
            },
        ], False


def _build_app(authenticated: bool) -> AttackIQTuiApp:
    auth = AuthContext(account_token="token" if authenticated else None, jwt=None)
    context = ServiceContext(
        config=CliConfig(
            base_url="https://api.example.com",
            account_token="token" if authenticated else None,
        ),
        base_url="https://api.example.com",
        auth=auth,
        spec=cast(SpecIndex, SimpleNamespace(load_source="memory")),
    )
    options = TuiOptions(
        page_size=20,
        order_by=None,
        search=None,
        tag=None,
        filter_debounce=0.4,
        insecure=False,
        insecure_source="config",
        timeout=None,
        timeout_source="config",
    )
    provider = _FakeProvider(context, options)
    state = provider.build_state()
    return AttackIQTuiApp(state, provider)


def test_format_runtime_error_connect_error():
    request = httpx.Request("GET", "https://api.example.com/v1/scenarios")
    exc = httpx.ConnectError("dns failure", request=request)
    formatted = tui_module._format_runtime_error(exc)
    assert "network connection failed" in formatted


def _mock_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tui_module, "_find_repo_root", lambda _start: Path("/repo/aiq-cli"))
    monkeypatch.setattr(
        tui_module.Path,
        "cwd",
        classmethod(lambda _cls: Path("/repo/aiq-cli/subdir")),
    )


def _disable_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(_self):  # noqa: ANN001, D401
        return None

    monkeypatch.setattr(tui_module.ScenariosTab, "on_mount", _noop)
    monkeypatch.setattr(tui_module.ResultsTab, "on_mount", _noop)
    monkeypatch.setattr(tui_module.AssessmentsTab, "on_mount", _noop)
    monkeypatch.setattr(tui_module.WorkflowTestsTab, "on_mount", _noop)
    monkeypatch.setattr(tui_module.WorkflowAssetsTab, "on_mount", _noop)
    monkeypatch.setattr(tui_module.WorkflowSettingsTab, "on_mount", _noop)


def _build_sortable_scenarios_app() -> AttackIQTuiApp:
    auth = AuthContext(account_token="token", jwt=None)
    context = ServiceContext(
        config=CliConfig(base_url="https://api.example.com", account_token="token"),
        base_url="https://api.example.com",
        auth=auth,
        spec=cast(SpecIndex, SimpleNamespace(load_source="memory")),
    )
    options = TuiOptions(
        page_size=20,
        order_by=None,
        search=None,
        tag=None,
        filter_debounce=0.4,
        insecure=False,
        insecure_source="config",
        timeout=None,
        timeout_source="config",
    )
    provider = _SortableScenarioProvider(context, options)
    state = provider.build_state()
    return AttackIQTuiApp(state, provider)


@pytest.mark.anyio
async def test_tui_tabs_present():
    app = _build_app(authenticated=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        for tab_id in (
            "#tab_status",
            "#tab_scenarios",
            "#tab_assessments",
            "#tab_tests",
            "#tab_assets",
            "#tab_results",
            "#tab_settings",
        ):
            assert app.query_one(tab_id) is not None


@pytest.mark.anyio
async def test_tui_workflow_tab_layout_present():
    app = _build_app(authenticated=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#scenarios_list_pane") is not None
        assert app.query_one("#scenarios_detail_pane") is not None
        assert app.query_one("#scenarios_filter_search") is not None
        assert app.query_one("#scenarios_filter_structured") is not None


@pytest.mark.anyio
async def test_tui_filter_help_examples_visible():
    app = _build_app(authenticated=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        scenarios_help = str(app.query_one("#scenarios_filter_help", Static).renderable)
        results_help = str(app.query_one("#results_filter_help", Static).renderable)
        assert "Examples:" in scenarios_help
        assert "sort=name dir=asc" in scenarios_help
        assert "Examples:" in results_help
        assert "sort=scenario dir=asc outcome=pass" in results_help


@pytest.mark.anyio
async def test_tui_scenarios_detail_sections_present_in_order():
    app = _build_app(authenticated=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#scenarios_detail_status", Static) is not None
        titles = [
            str(cast(Static, widget).renderable)
            for widget in app.query("#scenarios_detail_pane .section-title")
        ]
        assert titles == [
            "Metadata",
            "Description",
            "Tags",
            "Parameters",
            "Relationships",
            "Configuration",
        ]


@pytest.mark.anyio
async def test_tui_placeholder_workflow_footer_shortcuts(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = app.query_one("#assessments_footer", Static)
        text = str(footer.renderable)
        assert "?/h=Help" in text
        assert "e=Export JSON" in text
        assert "c=Export CSV" in text


@pytest.mark.anyio
async def test_tui_status_tab_summary_usage(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        summary = app.query_one("#status_summary", Static)
        text = str(summary.renderable)
        assert "Auth Status: Authenticated" in text
        assert "API Env: https://api.example.com" in text
        assert "Workspace: " in text
        assert "Use the tabs to browse data" in text
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert "page_size=20" in runtime
        assert "timeout=default" in runtime
        assert "insecure=no (config)" in runtime
        assert "cache_max=" in runtime
        assert "cache_ttl=" in runtime
        assert _cache_entries_text(
            scenarios=0,
            results=0,
            assessments=0,
            tests=0,
            assets=0,
            templates=0,
        ) in runtime
        diagnostics = str(app.query_one("#status_diagnostics", Static).renderable)
        assert "auth_mode=account-token" in diagnostics
        assert "auth_source=config" in diagnostics
        assert "Base URL source: config" in diagnostics
        assert "Spec cache: enabled (default)" in diagnostics
        assert "Spec load source: memory" in diagnostics
        usage_help = str(app.query_one("#status_usage_help", Static).renderable)
        assert "?/h=Help" in usage_help


@pytest.mark.anyio
async def test_tui_status_tab_diagnostics_env_precedence(monkeypatch):
    monkeypatch.setenv("ATTACKIQ_BASE_URL", "https://env.example.com")
    monkeypatch.setenv("ATTACKIQ_ACCOUNT_TOKEN", "env-token")
    monkeypatch.setenv("ATTACKIQ_SPEC_CACHE_DISABLE", "1")
    monkeypatch.setenv("ATTACKIQ_SPEC_CACHE_DIR", "/tmp/spec-cache-test")
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        diagnostics = str(app.query_one("#status_diagnostics", Static).renderable)
        assert "auth_source=env" in diagnostics
        assert "Base URL source: env" in diagnostics
        assert "Spec cache: disabled (env) /tmp/spec-cache-test" in diagnostics


@pytest.mark.anyio
async def test_tui_banner_bar_hidden_by_default():
    app = _build_app(authenticated=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        banner = app.query_one("#banner_bar")
        assert banner.display is False


@pytest.mark.anyio
async def test_tui_help_overlay_hidden_by_default(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        overlay = app.query_one("#help_overlay", Static)
        assert overlay.display is False


@pytest.mark.anyio
async def test_tui_command_palette_hidden_by_default(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        overlay = app.query_one("#command_palette_overlay")
        assert overlay.display is False


@pytest.mark.anyio
async def test_tui_help_overlay_toggle_actions(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        overlay = app.query_one("#help_overlay", Static)
        assert overlay.display is False
        app.action_toggle_help()
        await pilot.pause()
        assert overlay.display is True
        assert "Keyboard Help" in str(overlay.renderable)
        assert "] Next tab" in str(overlay.renderable)
        app.action_hide_help()
        await pilot.pause()
        assert overlay.display is False


@pytest.mark.anyio
async def test_tui_command_palette_switch_tab_command(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        app.action_toggle_command_palette()
        await pilot.pause()
        assert app.query_one("#command_palette_overlay").display is True
        app._execute_palette_command("switch:results")
        await pilot.pause()
        assert tabs.active == "tab_results"
        assert app.query_one("#command_palette_overlay").display is False


@pytest.mark.anyio
async def test_tui_command_palette_routes_refresh_export_and_filter_help(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_scenarios"
        scenarios_tab = app.query_one(ScenariosTab)
        calls = {"refresh": 0, "json": 0, "csv": 0, "next": 0, "prev": 0}

        def _mark(name: str) -> None:
            calls[name] += 1

        monkeypatch.setattr(scenarios_tab, "action_refresh", lambda: _mark("refresh"))
        monkeypatch.setattr(scenarios_tab, "action_export_json", lambda: _mark("json"))
        monkeypatch.setattr(scenarios_tab, "action_export_csv", lambda: _mark("csv"))
        monkeypatch.setattr(scenarios_tab, "action_next_page", lambda: _mark("next"))
        monkeypatch.setattr(scenarios_tab, "action_prev_page", lambda: _mark("prev"))
        app._execute_palette_command("refresh")
        app._execute_palette_command("page:next")
        app._execute_palette_command("page:prev")
        app._execute_palette_command("export:json")
        app._execute_palette_command("export:csv")
        app._execute_palette_command("focus:search")
        app._execute_palette_command("focus:filter")
        app._execute_palette_command("filter-help")
        await pilot.pause()

        assert calls == {"refresh": 1, "json": 1, "csv": 1, "next": 1, "prev": 1}
        assert app.focused is app.query_one("#scenarios_filter_structured")
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert banner_text.startswith("Command: ")
        assert "Scenario filters:" in banner_text


@pytest.mark.anyio
async def test_scenarios_refresh_clears_provider_cache(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_scenarios"
        scenarios_tab = app.query_one(ScenariosTab)
        calls = {"clear": 0}

        async def _fake_load(_page: int) -> None:
            return None

        def _clear_cache() -> None:
            calls["clear"] += 1

        monkeypatch.setattr(scenarios_tab.provider, "clear_scenarios_cache", _clear_cache)
        monkeypatch.setattr(scenarios_tab, "_load_list", _fake_load)
        scenarios_tab.action_refresh()
        await pilot.pause()
        assert calls["clear"] == 1


@pytest.mark.anyio
async def test_palette_clear_all_caches_command(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        calls = {
            "scenarios": 0,
            "results": 0,
            "assessments": 0,
            "tests": 0,
            "assets": 0,
            "templates": 0,
        }

        def _clear_scenarios() -> None:
            calls["scenarios"] += 1

        def _clear_results() -> None:
            calls["results"] += 1

        def _clear_assessments() -> None:
            calls["assessments"] += 1

        def _clear_tests() -> None:
            calls["tests"] += 1

        def _clear_assets() -> None:
            calls["assets"] += 1

        def _clear_templates() -> None:
            calls["templates"] += 1

        monkeypatch.setattr(app.provider, "scenarios_cache_stats", lambda: (2, 1))
        monkeypatch.setattr(app.provider, "results_cache_stats", lambda: (3, 1, 1))
        monkeypatch.setattr(app.provider, "assessments_cache_stats", lambda: (1, 2))
        monkeypatch.setattr(app.provider, "tests_cache_stats", lambda: (2, 2))
        monkeypatch.setattr(app.provider, "assets_cache_stats", lambda: (1, 1))
        monkeypatch.setattr(app.provider, "templates_cache_stats", lambda: (2, 3))
        monkeypatch.setattr(app.provider, "clear_scenarios_cache", _clear_scenarios)
        monkeypatch.setattr(app.provider, "clear_results_cache", _clear_results)
        monkeypatch.setattr(app.provider, "clear_assessments_cache", _clear_assessments)
        monkeypatch.setattr(app.provider, "clear_tests_cache", _clear_tests)
        monkeypatch.setattr(app.provider, "clear_assets_cache", _clear_assets)
        monkeypatch.setattr(app.provider, "clear_templates_cache", _clear_templates)
        app.action_toggle_command_palette()
        await pilot.pause()
        app._execute_palette_command("cache:clear")
        await pilot.pause()

        assert calls == {
            "scenarios": 1,
            "results": 1,
            "assessments": 1,
            "tests": 1,
            "assets": 1,
            "templates": 1,
        }
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert (
            "Cleared TUI caches (scenarios=3, results=5, assessments=3, "
            "tests=4, assets=2, templates=5)."
            in banner_text
        )
        assert app.query_one("#command_palette_overlay").display is False


@pytest.mark.anyio
async def test_palette_show_cache_stats_command(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_status"

        monkeypatch.setattr(app.provider, "scenarios_cache_stats", lambda: (1, 2))
        monkeypatch.setattr(app.provider, "results_cache_stats", lambda: (2, 1, 2))
        monkeypatch.setattr(app.provider, "assessments_cache_stats", lambda: (2, 1))
        monkeypatch.setattr(app.provider, "tests_cache_stats", lambda: (2, 2))
        monkeypatch.setattr(app.provider, "assets_cache_stats", lambda: (1, 1))
        monkeypatch.setattr(app.provider, "templates_cache_stats", lambda: (3, 2))

        app.action_toggle_command_palette()
        await pilot.pause()
        rows = [entry.label for entry in app._palette_filtered]
        assert "Show TUI cache stats" in rows

        app._execute_palette_command("cache:stats")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert (
            "TUI cache stats (scenarios=3, results=5, assessments=3, "
            "tests=4, assets=2, templates=5)."
            in banner_text
        )
        assert app.query_one("#command_palette_overlay").display is False


@pytest.mark.anyio
async def test_status_runtime_cache_entries_update_after_cache_clear(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    counts = {
        "scenarios": 3,
        "results": 5,
        "assessments": 3,
        "tests": 4,
        "assets": 2,
        "templates": 5,
    }

    monkeypatch.setattr(app.provider, "scenarios_cache_stats", lambda: (counts["scenarios"], 0))
    monkeypatch.setattr(app.provider, "results_cache_stats", lambda: (counts["results"], 0, 0))
    monkeypatch.setattr(
        app.provider, "assessments_cache_stats", lambda: (counts["assessments"], 0)
    )
    monkeypatch.setattr(app.provider, "tests_cache_stats", lambda: (counts["tests"], 0))
    monkeypatch.setattr(app.provider, "assets_cache_stats", lambda: (counts["assets"], 0))
    monkeypatch.setattr(app.provider, "templates_cache_stats", lambda: (counts["templates"], 0))

    def _clear_scenarios() -> None:
        counts["scenarios"] = 0

    def _clear_results() -> None:
        counts["results"] = 0

    def _clear_assessments() -> None:
        counts["assessments"] = 0

    def _clear_tests() -> None:
        counts["tests"] = 0

    def _clear_assets() -> None:
        counts["assets"] = 0

    def _clear_templates() -> None:
        counts["templates"] = 0

    monkeypatch.setattr(app.provider, "clear_scenarios_cache", _clear_scenarios)
    monkeypatch.setattr(app.provider, "clear_results_cache", _clear_results)
    monkeypatch.setattr(app.provider, "clear_assessments_cache", _clear_assessments)
    monkeypatch.setattr(app.provider, "clear_tests_cache", _clear_tests)
    monkeypatch.setattr(app.provider, "clear_assets_cache", _clear_assets)
    monkeypatch.setattr(app.provider, "clear_templates_cache", _clear_templates)

    async with app.run_test() as pilot:
        await pilot.pause()
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=3,
            results=5,
            assessments=3,
            tests=4,
            assets=2,
            templates=5,
        ) in runtime

        app._execute_palette_command("cache:clear")
        await pilot.pause()
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=0,
            results=0,
            assessments=0,
            tests=0,
            assets=0,
            templates=0,
        ) in runtime


@pytest.mark.anyio
async def test_status_runtime_cache_entries_refresh_on_status_tab_activation(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    counts = {
        "scenarios": 1,
        "results": 1,
        "assessments": 1,
        "tests": 1,
        "assets": 1,
        "templates": 1,
    }
    monkeypatch.setattr(app.provider, "scenarios_cache_stats", lambda: (counts["scenarios"], 0))
    monkeypatch.setattr(app.provider, "results_cache_stats", lambda: (counts["results"], 0, 0))
    monkeypatch.setattr(
        app.provider, "assessments_cache_stats", lambda: (counts["assessments"], 0)
    )
    monkeypatch.setattr(app.provider, "tests_cache_stats", lambda: (counts["tests"], 0))
    monkeypatch.setattr(app.provider, "assets_cache_stats", lambda: (counts["assets"], 0))
    monkeypatch.setattr(app.provider, "templates_cache_stats", lambda: (counts["templates"], 0))

    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=1,
            results=1,
            assessments=1,
            tests=1,
            assets=1,
            templates=1,
        ) in runtime

        counts["scenarios"] = 4
        counts["results"] = 3
        counts["assessments"] = 2
        counts["tests"] = 6
        counts["assets"] = 7
        counts["templates"] = 5

        app._activate_tab("results")
        await pilot.pause()
        app._activate_tab("status")
        await pilot.pause()

        assert tabs.active == "tab_status"
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=4,
            results=3,
            assessments=2,
            tests=6,
            assets=7,
            templates=5,
        ) in runtime


@pytest.mark.anyio
async def test_tui_results_state_restores_on_direct_tab_activation(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        results_tab = app.query_one(ResultsTab)
        app._tab_state["tab_results"] = {
            "page": 2,
            "search": "credential",
            "structured_filter": "status=pass",
            "view_mode": "Summaries",
            "selected_row": 0,
        }
        tabs.active = "tab_results"
        await pilot.pause()
        assert results_tab.page == 2
        assert results_tab.search == "credential"
        assert results_tab.structured_filter == "status=pass"


@pytest.mark.anyio
async def test_results_refresh_clears_provider_cache(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_results"
        results_tab = app.query_one(ResultsTab)
        calls = {"clear": 0}

        async def _fake_load(_page: int) -> None:
            return None

        def _clear_cache() -> None:
            calls["clear"] += 1

        monkeypatch.setattr(results_tab.provider, "clear_results_cache", _clear_cache)
        monkeypatch.setattr(results_tab, "_load_list", _fake_load)
        results_tab.action_refresh()
        await pilot.pause()
        assert calls["clear"] == 1


@pytest.mark.anyio
async def test_assessments_refresh_clears_assessment_cache(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assessments"
        clear_calls = {"assessments": 0}

        def _clear_assessments() -> None:
            clear_calls["assessments"] += 1

        monkeypatch.setattr(app.provider, "clear_assessments_cache", _clear_assessments)

        app.action_toggle_command_palette()
        await pilot.pause()
        rows = [entry.label for entry in app._palette_filtered]
        assert "Refresh current tab" in rows
        assert "Focus search input" in rows
        assert "Focus structured filter input" in rows
        assert "Show filter help for current tab" in rows
        assert "Next page" in rows
        assert "Previous page" in rows
        assert "Export current view as JSON" in rows

        app._execute_palette_command("refresh")
        await pilot.pause()
        assert clear_calls["assessments"] == 1


@pytest.mark.anyio
async def test_settings_tab_allows_focus_and_filter_palette_commands(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_settings"
        app.action_toggle_command_palette()
        await pilot.pause()
        rows = [entry.label for entry in app._palette_filtered]
        assert "Focus search input" in rows
        assert "Focus structured filter input" in rows
        assert "Show filter help for current tab" in rows
        assert "Refresh current tab" in rows
        assert "Next page" in rows
        assert "Previous page" in rows
        assert "Export current view as JSON" in rows
        app._execute_palette_command("focus:filter")
        await pilot.pause()
        assert app.focused is app.query_one("#settings_filter_structured")
        app._execute_palette_command("page:next")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Next page requested for settings." in banner_text
        status_text = str(app.query_one("#settings_list_status", Static).renderable)
        assert "No next page." in status_text
        app._execute_palette_command("filter-help")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Settings filters:" in banner_text


@pytest.mark.anyio
async def test_settings_tab_refresh_palette_command(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_settings"
        app.action_toggle_command_palette()
        await pilot.pause()
        rows = [entry.label for entry in app._palette_filtered]
        assert "Refresh current tab" in rows
        assert "Next page" in rows
        assert "Previous page" in rows
        app._execute_palette_command("refresh")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Refresh requested for settings." in banner_text


@pytest.mark.anyio
async def test_assessments_tab_key_actions(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assessments"
        assessments_tab = app.query_one("#assessments_tab", AssessmentsTab)

        clear_calls = {"assessments": 0}

        def _clear_assessments() -> None:
            clear_calls["assessments"] += 1

        monkeypatch.setattr(assessments_tab.provider, "clear_assessments_cache", _clear_assessments)

        async def _fake_load(_page: int) -> None:
            return None

        monkeypatch.setattr(assessments_tab, "_load_list", _fake_load)

        assessments_tab.action_refresh()
        await pilot.pause()
        assert clear_calls["assessments"] == 1

        assessments_tab.page = 1
        assessments_tab.has_next = False
        assessments_tab.action_next_page()
        await pilot.pause()
        status_text = str(app.query_one("#assessments_list_status", Static).renderable)
        assert "No next page." in status_text

        assessments_tab.action_prev_page()
        await pilot.pause()
        status_text = str(app.query_one("#assessments_list_status", Static).renderable)
        assert "Already at first page." in status_text

        assessments_tab.action_export_json()
        await pilot.pause()
        status_text = str(app.query_one("#assessments_list_status", Static).renderable)
        assert "No assessments to export on this page." in status_text

        assessments_tab.action_export_csv()
        await pilot.pause()
        status_text = str(app.query_one("#assessments_list_status", Static).renderable)
        assert "No assessments to export on this page." in status_text


@pytest.mark.anyio
async def test_tests_tab_key_actions(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_tests"
        tests_tab = app.query_one("#tests_tab", WorkflowTestsTab)

        clear_calls = {"tests": 0}

        def _clear_tests() -> None:
            clear_calls["tests"] += 1

        monkeypatch.setattr(tests_tab.provider, "clear_tests_cache", _clear_tests)

        async def _fake_load(_page: int) -> None:
            return None

        monkeypatch.setattr(tests_tab, "_load_list", _fake_load)

        tests_tab.action_refresh()
        await pilot.pause()
        assert clear_calls["tests"] == 1

        tests_tab.page = 1
        tests_tab.has_next = False
        tests_tab.action_next_page()
        await pilot.pause()
        status_text = str(app.query_one("#tests_list_status", Static).renderable)
        assert "No next page." in status_text

        tests_tab.action_prev_page()
        await pilot.pause()
        status_text = str(app.query_one("#tests_list_status", Static).renderable)
        assert "Already at first page." in status_text

        tests_tab.action_export_json()
        await pilot.pause()
        status_text = str(app.query_one("#tests_list_status", Static).renderable)
        assert "No tests to export on this page." in status_text

        tests_tab.action_export_csv()
        await pilot.pause()
        status_text = str(app.query_one("#tests_list_status", Static).renderable)
        assert "No tests to export on this page." in status_text


@pytest.mark.anyio
async def test_assets_tab_key_actions(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assets"
        assets_tab = app.query_one("#assets_tab", WorkflowAssetsTab)

        clear_calls = {"assets": 0}

        def _clear_assets() -> None:
            clear_calls["assets"] += 1

        monkeypatch.setattr(assets_tab.provider, "clear_assets_cache", _clear_assets)

        async def _fake_load(_page: int) -> None:
            return None

        monkeypatch.setattr(assets_tab, "_load_list", _fake_load)

        assets_tab.action_refresh()
        await pilot.pause()
        assert clear_calls["assets"] == 1

        assets_tab.page = 1
        assets_tab.has_next = False
        assets_tab.action_next_page()
        await pilot.pause()
        status_text = str(app.query_one("#assets_list_status", Static).renderable)
        assert "No next page." in status_text

        assets_tab.action_prev_page()
        await pilot.pause()
        status_text = str(app.query_one("#assets_list_status", Static).renderable)
        assert "Already at first page." in status_text

        assets_tab.action_export_json()
        await pilot.pause()
        status_text = str(app.query_one("#assets_list_status", Static).renderable)
        assert "No assets to export on this page." in status_text

        assets_tab.action_export_csv()
        await pilot.pause()
        status_text = str(app.query_one("#assets_list_status", Static).renderable)
        assert "No assets to export on this page." in status_text


@pytest.mark.anyio
async def test_settings_tab_key_actions(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_settings"
        settings_tab = app.query_one("#settings_tab", WorkflowSettingsTab)

        settings_tab.action_refresh()
        await pilot.pause()

        settings_tab.action_next_page()
        await pilot.pause()
        status_text = str(app.query_one("#settings_list_status", Static).renderable)
        assert "No next page." in status_text

        settings_tab.action_prev_page()
        await pilot.pause()
        status_text = str(app.query_one("#settings_list_status", Static).renderable)
        assert "Already at first page." in status_text

        settings_tab.records = []
        settings_tab.action_export_json()
        await pilot.pause()
        status_text = str(app.query_one("#settings_list_status", Static).renderable)
        assert "No settings entries to export." in status_text

        settings_tab.action_export_csv()
        await pilot.pause()
        status_text = str(app.query_one("#settings_list_status", Static).renderable)
        assert "No settings entries to export." in status_text


@pytest.mark.anyio
async def test_settings_tab_includes_cache_entry_diagnostics(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    monkeypatch.setattr(app.provider, "scenarios_cache_stats", lambda: (1, 2))
    monkeypatch.setattr(app.provider, "results_cache_stats", lambda: (2, 1, 2))
    monkeypatch.setattr(app.provider, "assessments_cache_stats", lambda: (2, 1))
    monkeypatch.setattr(app.provider, "tests_cache_stats", lambda: (3, 1))
    monkeypatch.setattr(app.provider, "assets_cache_stats", lambda: (1, 4))
    monkeypatch.setattr(app.provider, "templates_cache_stats", lambda: (3, 2))
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_settings"
        settings_tab = app.query_one("#settings_tab", WorkflowSettingsTab)
        settings_tab._refresh_records()

        records = {item["key"]: item["value"] for item in settings_tab.records}
        assert records["cache_entries_scenarios"] == "3"
        assert records["cache_entries_results"] == "5"
        assert records["cache_entries_assessments"] == "3"
        assert records["cache_entries_tests"] == "4"
        assert records["cache_entries_assets"] == "5"
        assert records["cache_entries_templates"] == "5"
        assert records["cache_entries_total"] == "25"


@pytest.mark.anyio
async def test_settings_tab_export_palette_command(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_settings"
        app._execute_palette_command("export:json")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Export JSON requested for settings." in banner_text


@pytest.mark.anyio
async def test_tui_command_palette_context_hides_unsupported_actions(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_status"
        app.action_toggle_command_palette()
        await pilot.pause()
        rows = [entry.label for entry in app._palette_filtered]
        assert "Refresh current tab" in rows
        assert "Next page" not in rows
        assert "Previous page" not in rows
        assert "Export current view as JSON" in rows
        assert "Export current view as CSV" in rows
        assert "Focus search input" not in rows
        assert "Focus structured filter input" not in rows
        assert "Show filter help for current tab" in rows


@pytest.mark.anyio
async def test_status_palette_export_commands_show_guidance(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_status"
        app._execute_palette_command("export:json")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Export JSON is not available on Landing / Status." in banner_text
        app._execute_palette_command("export:csv")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Export CSV is not available on Landing / Status." in banner_text


@pytest.mark.anyio
async def test_status_filter_help_command_shows_guidance(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_status"
        app._execute_palette_command("filter-help")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Status tab has no list filters" in banner_text


@pytest.mark.anyio
async def test_assessments_filter_help_command_shows_guidance(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assessments"
        app._execute_palette_command("filter-help")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Assessment filters:" in banner_text


@pytest.mark.anyio
async def test_tests_filter_help_command_shows_guidance(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_tests"
        app._execute_palette_command("filter-help")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Test filters:" in banner_text


@pytest.mark.anyio
async def test_assets_filter_help_command_shows_guidance(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assets"
        app._execute_palette_command("filter-help")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Asset filters:" in banner_text


@pytest.mark.anyio
async def test_settings_filter_help_command_shows_guidance(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_settings"
        app._execute_palette_command("filter-help")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Settings filters:" in banner_text


@pytest.mark.anyio
async def test_status_refresh_updates_runtime_diagnostics(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    counts = {
        "scenarios": 1,
        "results": 1,
        "assessments": 1,
        "tests": 1,
        "assets": 1,
        "templates": 1,
    }
    monkeypatch.setattr(app.provider, "scenarios_cache_stats", lambda: (counts["scenarios"], 0))
    monkeypatch.setattr(app.provider, "results_cache_stats", lambda: (counts["results"], 0, 0))
    monkeypatch.setattr(
        app.provider, "assessments_cache_stats", lambda: (counts["assessments"], 0)
    )
    monkeypatch.setattr(app.provider, "tests_cache_stats", lambda: (counts["tests"], 0))
    monkeypatch.setattr(app.provider, "assets_cache_stats", lambda: (counts["assets"], 0))
    monkeypatch.setattr(app.provider, "templates_cache_stats", lambda: (counts["templates"], 0))
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_status"
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=1,
            results=1,
            assessments=1,
            tests=1,
            assets=1,
            templates=1,
        ) in runtime

        counts["scenarios"] = 4
        counts["results"] = 3
        counts["assessments"] = 2
        counts["tests"] = 6
        counts["assets"] = 7
        counts["templates"] = 5
        app._execute_palette_command("refresh")
        await pilot.pause()
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=4,
            results=3,
            assessments=2,
            tests=6,
            assets=7,
            templates=5,
        ) in runtime
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Refreshed status diagnostics." in banner_text


@pytest.mark.anyio
async def test_status_tab_refresh_key_action_updates_runtime(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    counts = {
        "scenarios": 1,
        "results": 1,
        "assessments": 1,
        "tests": 1,
        "assets": 1,
        "templates": 1,
    }
    monkeypatch.setattr(app.provider, "scenarios_cache_stats", lambda: (counts["scenarios"], 0))
    monkeypatch.setattr(app.provider, "results_cache_stats", lambda: (counts["results"], 0, 0))
    monkeypatch.setattr(
        app.provider, "assessments_cache_stats", lambda: (counts["assessments"], 0)
    )
    monkeypatch.setattr(app.provider, "tests_cache_stats", lambda: (counts["tests"], 0))
    monkeypatch.setattr(app.provider, "assets_cache_stats", lambda: (counts["assets"], 0))
    monkeypatch.setattr(app.provider, "templates_cache_stats", lambda: (counts["templates"], 0))
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_status"
        status_tab = app.query_one("#status_tab", tui_module.StatusTab)
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=1,
            results=1,
            assessments=1,
            tests=1,
            assets=1,
            templates=1,
        ) in runtime

        counts["scenarios"] = 2
        counts["results"] = 3
        counts["assessments"] = 4
        counts["tests"] = 5
        counts["assets"] = 6
        counts["templates"] = 5
        status_tab.action_refresh()
        await pilot.pause()
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=2,
            results=3,
            assessments=4,
            tests=5,
            assets=6,
            templates=5,
        ) in runtime
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Refreshed status diagnostics." in banner_text


@pytest.mark.anyio
async def test_status_tab_export_key_actions_show_guidance(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_status"
        status_tab = app.query_one("#status_tab", tui_module.StatusTab)
        status_tab.action_export_json()
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Export JSON is not available on Landing / Status." in banner_text
        status_tab.action_export_csv()
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Export CSV is not available on Landing / Status." in banner_text


@pytest.mark.anyio
async def test_tui_command_palette_filters_commands(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_results"
        app.action_toggle_command_palette()
        await pilot.pause()
        palette_input = app.query_one("#command_palette_input", Input)
        palette_input.value = "export"
        await pilot.pause()
        rows = [entry.label for entry in app._palette_filtered]
        assert rows == ["Export current view as JSON", "Export current view as CSV"]


@pytest.mark.anyio
async def test_tui_command_palette_group_hint_and_alias_search(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_results"
        app.action_toggle_command_palette()
        await pilot.pause()

        hint_text = str(app.query_one("#command_palette_hint", Static).renderable)
        assert "Tabs" in hint_text
        assert "Data" in hint_text
        assert "Focus" in hint_text
        assert "Help" in hint_text

        palette_input = app.query_one("#command_palette_input", Input)
        palette_input.value = "goto results"
        await pilot.pause()
        rows = [entry.label for entry in app._palette_filtered]
        assert rows == ["Switch tab: Results"]


@pytest.mark.anyio
async def test_tui_command_palette_unsupported_execute_shows_banner(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_status"
        app.action_toggle_command_palette()
        await pilot.pause()
        app._execute_palette_command("export:json")
        await pilot.pause()
        banner_text = str(app.query_one("#banner_message", Static).renderable)
        assert "Export JSON is not available on Landing / Status." in banner_text
        assert app.query_one("#command_palette_overlay").display is False


@pytest.mark.anyio
async def test_tui_tab_navigation_actions(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        assert tabs.active == "tab_status"
        app.action_next_tab()
        await pilot.pause()
        assert tabs.active == "tab_scenarios"
        app.action_prev_tab()
        await pilot.pause()
        assert tabs.active == "tab_status"


@pytest.mark.anyio
async def test_tui_scenarios_state_restores_on_tab_switch(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_scenarios"
        scenarios_tab = app.query_one(ScenariosTab)
        scenarios_tab.search = "alpha"
        scenarios_tab.structured_filter = "tag=purple"
        scenarios_tab.page = 3
        scenarios_tab.records = [{"id": "scenario-1", "name": "Scenario One"}]
        app._capture_tab_state("tab_scenarios")

        app._activate_tab("results")
        await pilot.pause()
        app._activate_tab("scenarios")
        await pilot.pause()

        assert tabs.active == "tab_scenarios"
        assert scenarios_tab.search == "alpha"
        assert scenarios_tab.structured_filter == "tag=purple"
        assert scenarios_tab.page == 3


@pytest.mark.anyio
async def test_tui_results_state_restores_on_palette_switch(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_results"
        results_tab = app.query_one(ResultsTab)
        results_tab.search = "credential"
        results_tab.structured_filter = "status=pass"
        results_tab.page = 2
        results_tab.records = [{"id": "result-1", "scenario_name": "Scenario One"}]
        app._capture_tab_state("tab_results")

        app._execute_palette_command("switch:status")
        await pilot.pause()
        app._execute_palette_command("switch:results")
        await pilot.pause()

        assert tabs.active == "tab_results"
        assert results_tab.search == "credential"
        assert results_tab.structured_filter == "status=pass"
        assert app._tab_state["tab_results"]["page"] == 2


@pytest.mark.anyio
async def test_tui_assessments_state_restores_on_palette_switch(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assessments"
        assessments_tab = app.query_one(AssessmentsTab)
        assessments_tab.search = "prod"
        assessments_tab.structured_filter = "status=active"
        assessments_tab.page = 2
        assessments_tab.records = [{"id": "assessment-1", "name": "Assessment One"}]
        app._capture_tab_state("tab_assessments")

        app._execute_palette_command("switch:status")
        await pilot.pause()
        app._execute_palette_command("switch:assessments")
        await pilot.pause()

        assert tabs.active == "tab_assessments"
        assert assessments_tab.search == "prod"
        assert assessments_tab.structured_filter == "status=active"
        assert app._tab_state["tab_assessments"]["page"] == 2


@pytest.mark.anyio
async def test_tui_tests_state_restores_on_palette_switch(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_tests"
        tests_tab = app.query_one(WorkflowTestsTab)
        tests_tab.search = "credential"
        tests_tab.structured_filter = "use_hosted_agent=true"
        tests_tab.page = 3
        tests_tab.records = [{"id": "test-1", "name": "Test One"}]
        app._capture_tab_state("tab_tests")

        app._execute_palette_command("switch:status")
        await pilot.pause()
        app._execute_palette_command("switch:tests")
        await pilot.pause()

        assert tabs.active == "tab_tests"
        assert tests_tab.search == "credential"
        assert tests_tab.structured_filter == "use_hosted_agent=true"
        assert app._tab_state["tab_tests"]["page"] == 3


@pytest.mark.anyio
async def test_tui_assets_state_restores_on_palette_switch(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assets"
        assets_tab = app.query_one(WorkflowAssetsTab)
        assets_tab.search = "agent"
        assets_tab.structured_filter = "state=2"
        assets_tab.page = 4
        assets_tab.records = [{"id": "asset-1", "hostname": "host-one"}]
        app._capture_tab_state("tab_assets")

        app._execute_palette_command("switch:status")
        await pilot.pause()
        app._execute_palette_command("switch:assets")
        await pilot.pause()

        assert tabs.active == "tab_assets"
        assert assets_tab.search == "agent"
        assert assets_tab.structured_filter == "state=2"
        assert app._tab_state["tab_assets"]["page"] == 4


@pytest.mark.anyio
async def test_tui_settings_state_restores_on_palette_switch(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_settings"
        settings_tab = app.query_one(WorkflowSettingsTab)
        settings_tab.search = "auth"
        settings_tab.structured_filter = "category=config"
        settings_tab.records = [{"key": "base_url", "value": "https://api.example.com"}]
        app._capture_tab_state("tab_settings")

        app._execute_palette_command("switch:status")
        await pilot.pause()
        app._execute_palette_command("switch:settings")
        await pilot.pause()

        assert tabs.active == "tab_settings"
        assert settings_tab.search == "auth"
        assert settings_tab.structured_filter == "category=config"


@pytest.mark.anyio
async def test_tui_scenarios_restore_ignores_programmatic_filter_events(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    app.provider.options.filter_debounce = 0
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_scenarios"
        scenarios_tab = app.query_one(ScenariosTab)
        scenarios_tab.page = 5
        scenarios_tab.records = [{"id": "scenario-1", "name": "Scenario One"}]
        app._tab_state["tab_scenarios"] = {
            "page": 5,
            "search": "alpha",
            "structured_filter": "tag=purple",
            "selected_row": 0,
        }

        app._restore_tab_state("tab_scenarios")
        await anyio.sleep(0.01)
        await pilot.pause()

        assert scenarios_tab.page == 5


@pytest.mark.anyio
async def test_tui_results_restore_ignores_programmatic_filter_events(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    app.provider.options.filter_debounce = 0
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_results"
        results_tab = app.query_one(ResultsTab)
        results_tab.page = 4
        results_tab.records = [{"id": "result-1", "scenario_name": "Scenario One"}]
        app._tab_state["tab_results"] = {
            "page": 4,
            "search": "credential",
            "structured_filter": "status=pass",
            "view_mode": "Summaries",
            "selected_row": 0,
        }

        app._restore_tab_state("tab_results")
        await anyio.sleep(0.01)
        await pilot.pause()

        assert results_tab.page == 4


@pytest.mark.anyio
async def test_tui_header_env_and_workspace_display(monkeypatch):
    _mock_workspace(monkeypatch)
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        env_text = str(app.query_one("#header_env", Static).renderable)
        workspace_text = str(app.query_one("#header_workspace", Static).renderable)
        assert env_text == "Env: api.example.com (custom)"
        assert workspace_text == "Workspace: aiq-cli"


@pytest.mark.anyio
async def test_tui_status_runtime_includes_cache_entry_totals(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    monkeypatch.setattr(app.provider, "scenarios_cache_stats", lambda: (1, 2))
    monkeypatch.setattr(app.provider, "results_cache_stats", lambda: (2, 1, 2))
    monkeypatch.setattr(app.provider, "assessments_cache_stats", lambda: (2, 1))
    monkeypatch.setattr(app.provider, "tests_cache_stats", lambda: (2, 2))
    monkeypatch.setattr(app.provider, "assets_cache_stats", lambda: (1, 1))
    monkeypatch.setattr(app.provider, "templates_cache_stats", lambda: (3, 2))
    async with app.run_test() as pilot:
        await pilot.pause()
        runtime = str(app.query_one("#status_runtime", Static).renderable)
        assert _cache_entries_text(
            scenarios=3,
            results=5,
            assessments=3,
            tests=4,
            assets=2,
            templates=5,
        ) in runtime


@pytest.mark.anyio
async def test_scenarios_tab_export_csv_shortcut(monkeypatch, tmp_path):
    _disable_auto_load(monkeypatch)
    app = _build_app(authenticated=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        scenarios_tab = app.query_one(ScenariosTab)
        scenarios_tab.records = [
            {
                "id": "scenario-1",
                "name": "Scenario One",
                "scenario_type": "atomic",
                "description": "Example",
                "created": "2026-01-01T00:00:00Z",
                "modified": "2026-01-02T00:00:00Z",
            }
        ]
        monkeypatch.setattr(
            scenarios_tab, "_default_export_path", lambda _fmt: tmp_path / "scenarios.csv"
        )
        scenarios_tab.action_export_csv()
        await pilot.pause()
        if scenarios_tab._export_task is not None:
            await scenarios_tab._export_task

    with (tmp_path / "scenarios.csv").open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["id"] == "scenario-1"
    assert row["name"] == "Scenario One"


@pytest.mark.anyio
async def test_scenarios_tab_applies_structured_sort(monkeypatch):
    _disable_auto_load(monkeypatch)
    app = _build_sortable_scenarios_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        scenarios_tab = app.query_one(ScenariosTab)
        scenarios_tab._configure_table()
        scenarios_tab.structured_filter = "sort=name dir=asc"
        await scenarios_tab._load_list(1)
        assert [record["name"] for record in scenarios_tab.records] == ["Alpha", "Zulu"]
        status = str(app.query_one("#scenarios_list_status", Static).renderable)
        assert "sort=name:asc" in status


def test_scenario_detail_builders_parameters_and_relationships():
    scenario = {
        "parameters": {"credential": "required", "timeout": 30},
        "capabilities": [{"display_name": "Credential Access"}],
        "scenario_tags": [{"tag": {"name": "Windows"}}],
        "assessments": ["a1", "a2"],
        "scenario_template_instance": "tmpl-1",
    }
    parameters = tui_module._build_scenario_parameters(scenario)
    relationships = tui_module._build_scenario_relationships(scenario)
    assert "credential" in parameters
    assert "timeout" in parameters
    assert "Capabilities: Credential Access" in relationships
    assert "Tag Relations: 1" in relationships
    assert "Assessments: 2" in relationships
