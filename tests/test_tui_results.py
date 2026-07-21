from __future__ import annotations

import asyncio
import csv
import json
import threading
from types import SimpleNamespace
from typing import Any, cast

import anyio
import pytest
from textual.app import App, ComposeResult
from textual.widgets import Select, Static

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_exports, tui_results
from attackiq_cli.client import AuthContext
from attackiq_cli.config import CliConfig
from attackiq_cli.services import ServiceContext
from attackiq_cli.spec import SpecIndex
from attackiq_cli.tui import (
    BannerBar,
    ResultsTab,
    ResultsViewMode,
    TuiDataProvider,
    TuiOptions,
    TuiState,
)


def test_tui_module_reexports_results_workflow_for_compatibility() -> None:
    assert tui_module.ResultsTab is tui_results.ResultsTab
    assert tui_module.ResultsQuery is tui_results.ResultsQuery


class _FakeProvider(TuiDataProvider):
    def fetch_results_list(
        self,
        *,
        mode: Any,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        _ = (page, page_size, search)
        if mode == ResultsViewMode.SUMMARIES:
            return [
                {
                    "id": "sum-1",
                    "scenario_name": "Scenario One",
                    "outcome": "pass",
                    "completed": "2026-01-01",
                }
            ], False
        if mode == ResultsViewMode.PHASES:
            return [{"result_summary_id": "sum-1"}], False
        return [{"scenario_job_id": "job-1"}], False

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


class _SortableResultsProvider(_FakeProvider):
    def fetch_results_list(
        self,
        *,
        mode: Any,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        _ = (page, page_size, search)
        if mode == ResultsViewMode.SUMMARIES:
            return [
                {
                    "id": "sum-2",
                    "scenario_name": "Zulu",
                    "outcome": "pass",
                    "completed": "2026-01-02",
                },
                {
                    "id": "sum-1",
                    "scenario_name": "Alpha",
                    "outcome": "fail",
                    "completed": "2026-01-01",
                },
            ], False
        return [
            {"result_summary_id": "sum-1"},
            {"result_summary_id": "sum-1"},
            {"result_summary_id": "sum-2"},
            {"scenario_job_id": "job-9"},
        ], False


class _ResultsTestApp(App):
    def __init__(self, state: TuiState, provider: TuiDataProvider) -> None:
        super().__init__()
        self.state = state
        self.provider = provider

    def compose(self) -> ComposeResult:
        yield BannerBar()
        yield ResultsTab(self.state, self.provider)


def _build_state_provider(authenticated: bool) -> tuple[TuiState, _FakeProvider]:
    auth = AuthContext(account_token="token" if authenticated else None, jwt=None)
    context = ServiceContext(
        config=CliConfig(),
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
    return state, provider


def _build_state_sortable_provider(
    authenticated: bool,
) -> tuple[TuiState, _SortableResultsProvider]:
    auth = AuthContext(account_token="token" if authenticated else None, jwt=None)
    context = ServiceContext(
        config=CliConfig(),
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
    provider = _SortableResultsProvider(context, options)
    state = provider.build_state()
    return state, provider


def _disable_results_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(_self):  # noqa: ANN001
        return None

    monkeypatch.setattr(tui_module.ResultsTab, "on_mount", _noop)


@pytest.mark.anyio
async def test_results_tab_view_selector_present(monkeypatch):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_provider(authenticated=False)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.query_one("#results_view_select", Select)
        assert select.value == ResultsViewMode.SUMMARIES.value


@pytest.mark.anyio
async def test_results_tab_mode_switch_updates_title(monkeypatch):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.query_one("#results_view_select", Select)
        title = app.query_one("#results_list_title", Static)
        assert "Summaries" in str(title.renderable)
        select.value = ResultsViewMode.PHASES.value
        await pilot.pause()
        assert "Phases" in str(title.renderable)
        select.value = ResultsViewMode.LOGS.value
        await pilot.pause()
        assert "Logs" in str(title.renderable)


@pytest.mark.anyio
async def test_results_tab_mode_switch_updates_list_source_and_resets_detail(monkeypatch):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        results_tab = app.query_one(ResultsTab)
        results_tab._configure_table()
        results_tab._reset_detail()
        await results_tab._load_list(1)
        assert results_tab.records
        assert results_tab.groups == []

        results_tab._update_detail_sections(
            metadata="Custom detail",
            scenario="",
            outcome="",
            phases="",
            logs="",
        )
        select = app.query_one("#results_view_select", Select)
        select.value = ResultsViewMode.PHASES.value
        await pilot.pause()
        assert results_tab.groups
        assert results_tab.groups[0].key == "sum-1"
        metadata = app.query_one("#results_section_metadata", Static)
        assert "Select a result to view details." in str(metadata.renderable)

        select.value = ResultsViewMode.LOGS.value
        await pilot.pause()
        assert results_tab.groups
        assert results_tab.groups[0].key == "job-1"


@pytest.mark.anyio
async def test_results_tab_detail_sections_present_in_order(monkeypatch):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_provider(authenticated=False)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        titles = [
            str(cast(Static, widget).renderable)
            for widget in app.query("#results_detail_pane .section-title")
        ]
        assert app.query_one("#results_detail_status", Static) is not None
        assert titles == [
            "Metadata",
            "Scenario summary",
            "Outcome",
            "Phases",
            "Logs",
            "Export",
        ]


@pytest.mark.anyio
async def test_results_tab_banner_available(monkeypatch):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_provider(authenticated=False)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        results_tab = app.query_one(ResultsTab)
        results_tab._set_banner("Results error")
        await pilot.pause()
        banner = app.query_one("#banner_message", Static)
        assert "Results error" in str(banner.renderable)
        assert app.query_one("#banner_bar").display is True


@pytest.mark.anyio
async def test_results_tab_mode_switch_teardown_no_hang():
    state, provider = _build_state_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    with anyio.fail_after(2):
        async with app.run_test() as pilot:
            await pilot.pause()
            select = app.query_one("#results_view_select", Select)
            select.value = ResultsViewMode.PHASES.value
            await pilot.pause()
            select.value = ResultsViewMode.LOGS.value
            await pilot.pause()
            select.value = ResultsViewMode.SUMMARIES.value
            await pilot.pause()


@pytest.mark.anyio
async def test_cancel_and_await_tasks_cancels_pending_tasks():
    task = asyncio.create_task(asyncio.sleep(30))
    await tui_module._cancel_and_await_tasks(task)
    assert task.done()
    assert task.cancelled()


@pytest.mark.anyio
async def test_results_tab_export_json_writes_current_records(monkeypatch, tmp_path):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        results_tab = app.query_one(ResultsTab)
        results_tab._configure_table()
        await results_tab._load_list(1)
        monkeypatch.setattr(
            results_tab, "_default_export_path", lambda _fmt: tmp_path / "results.json"
        )
        results_tab.action_export_json()
        await pilot.pause()
        if results_tab._export_task is not None:
            await results_tab._export_task

    payload = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert payload and payload[0]["id"] == "sum-1"


@pytest.mark.anyio
async def test_results_tab_export_csv_writes_group_rows(monkeypatch, tmp_path):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        results_tab = app.query_one(ResultsTab)
        select = app.query_one("#results_view_select", Select)
        select.value = ResultsViewMode.PHASES.value
        await pilot.pause()
        monkeypatch.setattr(
            results_tab, "_default_export_path", lambda _fmt: tmp_path / "results.csv"
        )
        results_tab.action_export_csv()
        await pilot.pause()
        if results_tab._export_task is not None:
            await results_tab._export_task

    with (tmp_path / "results.csv").open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["join_key"] == "sum-1"
    assert row["source"] == "result_summary_id"


@pytest.mark.anyio
async def test_results_tab_export_shows_loading_indicator(monkeypatch, tmp_path):
    state, provider = _build_state_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    gate = threading.Event()

    def _blocking_json(_output, _payload):  # noqa: ANN001
        gate.wait(timeout=2)

    monkeypatch.setattr(tui_exports, "write_json", _blocking_json)
    async with app.run_test() as pilot:
        await pilot.pause()
        results_tab = app.query_one(ResultsTab)
        results_tab.records = [{"id": "sum-1"}]
        app.query_one("#results_export_loading").display = False
        monkeypatch.setattr(
            results_tab, "_default_export_path", lambda _fmt: tmp_path / "results.json"
        )
        results_tab.action_export_json()
        await pilot.pause()

        loading = app.query_one("#results_export_loading")
        assert loading.display is True

        gate.set()
        if results_tab._export_task is not None:
            await results_tab._export_task
        await pilot.pause()
        assert loading.display is False


@pytest.mark.anyio
async def test_results_tab_applies_structured_sort_for_summaries(monkeypatch):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_sortable_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        results_tab = app.query_one(ResultsTab)
        results_tab._configure_table()
        results_tab.structured_filter = "sort=scenario dir=asc"
        await results_tab._load_list(1)
        assert [item["scenario_name"] for item in results_tab.records] == ["Alpha", "Zulu"]
        status = str(app.query_one("#results_list_status", Static).renderable)
        assert "sort=scenario:asc" in status


@pytest.mark.anyio
async def test_results_tab_applies_structured_outcome_filter(monkeypatch):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_sortable_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        results_tab = app.query_one(ResultsTab)
        results_tab._configure_table()
        results_tab.structured_filter = "outcome=fail"
        await results_tab._load_list(1)
        assert [item["id"] for item in results_tab.records] == ["sum-1"]
        status = str(app.query_one("#results_list_status", Static).renderable)
        assert "outcome=fail" in status


@pytest.mark.anyio
async def test_results_tab_applies_group_source_filter(monkeypatch):
    _disable_results_auto_load(monkeypatch)
    state, provider = _build_state_sortable_provider(authenticated=True)
    app = _ResultsTestApp(state, provider)
    async with app.run_test() as pilot:
        await pilot.pause()
        results_tab = app.query_one(ResultsTab)
        select = app.query_one("#results_view_select", Select)
        select.value = ResultsViewMode.PHASES.value
        await pilot.pause()
        results_tab.structured_filter = "source=scenario_job_id"
        await results_tab._load_list(1)
        assert [group.key for group in results_tab.groups] == ["job-9"]
        status = str(app.query_one("#results_list_status", Static).renderable)
        assert "source=scenario_job_id" in status


def test_parse_results_filter_supports_aliases():
    parsed = tui_module._parse_results_filter("order=key direction=desc status=pass")
    assert parsed["sort"] == "key"
    assert parsed["dir"] == "desc"
    assert parsed["outcome"] == "pass"


def test_resolve_results_source_filter_supports_aliases():
    assert tui_module._resolve_results_source_filter("summary") == "result_summary_id"
    assert tui_module._resolve_results_source_filter("job") == "scenario_job_id"
