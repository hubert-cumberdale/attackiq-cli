from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from attackiq_cli.client import AuthContext
from attackiq_cli.config import CliConfig
from attackiq_cli.services import ScenarioFilters, ServiceContext
from attackiq_cli.spec import SpecIndex
from attackiq_cli.tui_provider import ResultsViewMode, TuiDataProvider, TuiOptions


def _build_provider() -> TuiDataProvider:
    context = ServiceContext(
        config=CliConfig(base_url="https://api.example.com", account_token="token"),
        base_url="https://api.example.com",
        auth=AuthContext(account_token="token", jwt=None),
        spec=cast(SpecIndex, SimpleNamespace(load_source="memory")),
    )
    options = TuiOptions(
        page_size=20,
        order_by=None,
        search=None,
        tag=None,
        filter_debounce=0.1,
        insecure=False,
        insecure_source="config",
        timeout=None,
        timeout_source="config",
    )
    return TuiDataProvider(context, options)


def test_provider_caches_scenarios_pages(monkeypatch):
    provider = _build_provider()
    calls = {"count": 0}

    def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return [{"id": "scenario-1", "name": "Scenario One"}], False

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_scenarios_page", _fake_fetch)
    filters = ScenarioFilters(search="alpha")

    first, first_next = provider.fetch_scenarios_page(page=1, page_size=20, filters=filters)
    first[0]["name"] = "mutated"
    second, second_next = provider.fetch_scenarios_page(page=1, page_size=20, filters=filters)

    assert calls["count"] == 1
    assert first_next is False
    assert second_next is False
    assert second[0]["name"] == "Scenario One"


def test_provider_clear_scenarios_cache_forces_refetch(monkeypatch):
    provider = _build_provider()
    calls = {"count": 0}

    def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return [{"id": "scenario-1"}], False

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_scenarios_page", _fake_fetch)
    filters = ScenarioFilters()

    provider.fetch_scenarios_page(page=1, page_size=20, filters=filters)
    provider.clear_scenarios_cache()
    provider.fetch_scenarios_page(page=1, page_size=20, filters=filters)

    assert calls["count"] == 2
    assert provider.scenarios_cache_stats() == (1, 0)


def test_provider_caches_scenario_details(monkeypatch):
    provider = _build_provider()
    calls = {"count": 0}

    def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return {"id": "scenario-1", "description": {"summary": "text"}}

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_scenario_detail", _fake_fetch)

    first = provider.fetch_scenario_detail(scenario_id="scenario-1")
    first["description"]["summary"] = "mutated"
    second = provider.fetch_scenario_detail(scenario_id="scenario-1")

    assert calls["count"] == 1
    assert second["description"]["summary"] == "text"


def test_provider_caches_results_list(monkeypatch):
    provider = _build_provider()
    calls = {"count": 0}

    def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return [{"id": "result-1", "scenario_name": "Alpha"}], False

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_results_list", _fake_fetch)

    first, _ = provider.fetch_results_list(
        mode=ResultsViewMode.SUMMARIES,
        page=1,
        page_size=20,
        search="alpha",
    )
    first[0]["scenario_name"] = "mutated"
    second, _ = provider.fetch_results_list(
        mode=ResultsViewMode.SUMMARIES,
        page=1,
        page_size=20,
        search="alpha",
    )

    assert calls["count"] == 1
    assert second[0]["scenario_name"] == "Alpha"


def test_provider_caches_phase_records(monkeypatch):
    provider = _build_provider()
    phase_calls = {"count": 0}
    log_calls = {"count": 0}

    def _fake_phase_results(*_args, **_kwargs):
        phase_calls["count"] += 1
        return [{"result_summary_id": "r-1", "phase_number": 1}]

    def _fake_phase_logs(*_args, **_kwargs):
        log_calls["count"] += 1
        return [{"result_summary_id": "r-1", "message": "ok"}]

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_phase_results", _fake_phase_results)
    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_phase_logs", _fake_phase_logs)

    first_phases = provider.fetch_phase_results(result_summary_id="r-1")
    first_logs = provider.fetch_phase_logs(result_summary_id="r-1")
    first_phases[0]["phase_number"] = 999
    first_logs[0]["message"] = "mutated"
    second_phases = provider.fetch_phase_results(result_summary_id="r-1")
    second_logs = provider.fetch_phase_logs(result_summary_id="r-1")

    assert phase_calls["count"] == 1
    assert log_calls["count"] == 1
    assert second_phases[0]["phase_number"] == 1
    assert second_logs[0]["message"] == "ok"


def test_provider_clear_results_cache_forces_refetch(monkeypatch):
    provider = _build_provider()
    calls = {"results": 0, "phases": 0, "logs": 0}

    def _fake_results(*_args, **_kwargs):
        calls["results"] += 1
        return [{"id": "result-1"}], False

    def _fake_phase_results(*_args, **_kwargs):
        calls["phases"] += 1
        return [{"result_summary_id": "r-1"}]

    def _fake_phase_logs(*_args, **_kwargs):
        calls["logs"] += 1
        return [{"result_summary_id": "r-1"}]

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_results_list", _fake_results)
    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_phase_results", _fake_phase_results)
    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_phase_logs", _fake_phase_logs)

    provider.fetch_results_list(mode=ResultsViewMode.SUMMARIES, page=1, page_size=20, search=None)
    provider.fetch_phase_results(result_summary_id="r-1")
    provider.fetch_phase_logs(result_summary_id="r-1")
    provider.clear_results_cache()
    provider.fetch_results_list(mode=ResultsViewMode.SUMMARIES, page=1, page_size=20, search=None)
    provider.fetch_phase_results(result_summary_id="r-1")
    provider.fetch_phase_logs(result_summary_id="r-1")

    assert calls == {"results": 2, "phases": 2, "logs": 2}
    assert provider.results_cache_stats() == (1, 1, 1)


def test_provider_scenarios_cache_eviction_respects_max_entries(monkeypatch):
    provider = _build_provider()
    provider._cache_max_entries = 1
    calls = {"count": 0}

    def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return [{"id": f"scenario-{calls['count']}"}], False

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_scenarios_page", _fake_fetch)

    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))
    provider.fetch_scenarios_page(page=2, page_size=20, filters=ScenarioFilters(search="two"))
    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))

    assert calls["count"] == 3
    assert provider.scenarios_cache_stats() == (1, 0)


def test_provider_results_cache_eviction_respects_max_entries(monkeypatch):
    provider = _build_provider()
    provider._cache_max_entries = 1
    calls = {"count": 0}

    def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return [{"id": f"result-{calls['count']}"}], False

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_results_list", _fake_fetch)

    provider.fetch_results_list(mode=ResultsViewMode.SUMMARIES, page=1, page_size=20, search="one")
    provider.fetch_results_list(mode=ResultsViewMode.SUMMARIES, page=2, page_size=20, search="two")
    provider.fetch_results_list(mode=ResultsViewMode.SUMMARIES, page=1, page_size=20, search="one")

    assert calls["count"] == 3
    assert provider.results_cache_stats() == (1, 0, 0)


def test_provider_cache_ttl_expires_entries(monkeypatch):
    provider = _build_provider()
    provider._cache_ttl_seconds = 1.0
    calls = {"count": 0}
    now = [100.0]

    def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return [{"id": f"scenario-{calls['count']}"}], False

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_scenarios_page", _fake_fetch)
    monkeypatch.setattr("attackiq_cli.tui_provider.time.monotonic", lambda: now[0])

    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))
    now[0] = 100.5
    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))
    now[0] = 102.5
    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))

    assert calls["count"] == 2


def test_provider_cache_ttl_expires_entries_at_boundary(monkeypatch):
    provider = _build_provider()
    provider._cache_ttl_seconds = 1.0
    calls = {"count": 0}
    now = [100.0]

    def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return [{"id": f"scenario-{calls['count']}"}], False

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_scenarios_page", _fake_fetch)
    monkeypatch.setattr("attackiq_cli.tui_provider.time.monotonic", lambda: now[0])

    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))
    now[0] = 101.0
    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))

    assert calls["count"] == 2


def test_provider_cache_stats_prune_expired_entries(monkeypatch):
    provider = _build_provider()
    provider._cache_ttl_seconds = 1.0
    now = [100.0]

    monkeypatch.setattr(
        "attackiq_cli.tui_provider.fetch_scenarios_page",
        lambda *_args, **_kwargs: ([{"id": "scenario-1"}], False),
    )
    monkeypatch.setattr(
        "attackiq_cli.tui_provider.fetch_scenario_detail",
        lambda *_args, **_kwargs: {"id": "scenario-1"},
    )
    monkeypatch.setattr(
        "attackiq_cli.tui_provider.fetch_results_list",
        lambda *_args, **_kwargs: ([{"id": "result-1"}], False),
    )
    monkeypatch.setattr(
        "attackiq_cli.tui_provider.fetch_phase_results",
        lambda *_args, **_kwargs: [{"result_summary_id": "r-1"}],
    )
    monkeypatch.setattr(
        "attackiq_cli.tui_provider.fetch_phase_logs",
        lambda *_args, **_kwargs: [{"result_summary_id": "r-1"}],
    )
    monkeypatch.setattr("attackiq_cli.tui_provider.time.monotonic", lambda: now[0])

    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))
    provider.fetch_scenario_detail(scenario_id="scenario-1")
    provider.fetch_results_list(mode=ResultsViewMode.SUMMARIES, page=1, page_size=20, search=None)
    provider.fetch_phase_results(result_summary_id="r-1")
    provider.fetch_phase_logs(result_summary_id="r-1")

    assert provider.scenarios_cache_stats() == (1, 1)
    assert provider.results_cache_stats() == (1, 1, 1)

    now[0] = 102.0
    assert provider.scenarios_cache_stats() == (0, 0)
    assert provider.results_cache_stats() == (0, 0, 0)


def test_provider_cache_stats_prune_expired_entries_at_boundary(monkeypatch):
    provider = _build_provider()
    provider._cache_ttl_seconds = 1.0
    now = [100.0]

    monkeypatch.setattr(
        "attackiq_cli.tui_provider.fetch_scenarios_page",
        lambda *_args, **_kwargs: ([{"id": "scenario-1"}], False),
    )
    monkeypatch.setattr("attackiq_cli.tui_provider.time.monotonic", lambda: now[0])

    provider.fetch_scenarios_page(page=1, page_size=20, filters=ScenarioFilters(search="one"))
    assert provider.scenarios_cache_stats() == (1, 0)

    now[0] = 101.0
    assert provider.scenarios_cache_stats() == (0, 0)


def test_provider_caches_assessments_pages_and_details(monkeypatch):
    provider = _build_provider()
    page_calls = {"count": 0}
    detail_calls = {"count": 0}

    def _fake_fetch_page(*_args, **_kwargs):
        page_calls["count"] += 1
        return [{"id": "assessment-1", "name": "Assessment One"}], False

    def _fake_fetch_detail(*_args, **_kwargs):
        detail_calls["count"] += 1
        return {"id": "assessment-1", "status": "running"}

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_assessments_page", _fake_fetch_page)
    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_assessment_detail", _fake_fetch_detail)

    first_page, first_next = provider.fetch_assessments_page(page=1, page_size=20)
    first_page[0]["name"] = "mutated"
    second_page, second_next = provider.fetch_assessments_page(page=1, page_size=20)
    first_detail = provider.fetch_assessment_detail(assessment_id="assessment-1")
    first_detail["status"] = "mutated"
    second_detail = provider.fetch_assessment_detail(assessment_id="assessment-1")

    assert page_calls["count"] == 1
    assert detail_calls["count"] == 1
    assert first_next is False and second_next is False
    assert second_page[0]["name"] == "Assessment One"
    assert second_detail["status"] == "running"
    assert provider.assessments_cache_stats() == (1, 1)


def test_provider_clear_assessments_cache_forces_refetch(monkeypatch):
    provider = _build_provider()
    calls = {"page": 0, "detail": 0}

    def _fake_fetch_page(*_args, **_kwargs):
        calls["page"] += 1
        return [{"id": "assessment-1"}], False

    def _fake_fetch_detail(*_args, **_kwargs):
        calls["detail"] += 1
        return {"id": "assessment-1"}

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_assessments_page", _fake_fetch_page)
    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_assessment_detail", _fake_fetch_detail)

    provider.fetch_assessments_page(page=1, page_size=20)
    provider.fetch_assessment_detail(assessment_id="assessment-1")
    provider.clear_assessments_cache()
    provider.fetch_assessments_page(page=1, page_size=20)
    provider.fetch_assessment_detail(assessment_id="assessment-1")

    assert calls == {"page": 2, "detail": 2}
    assert provider.assessments_cache_stats() == (1, 1)


def test_provider_caches_templates_pages_and_details(monkeypatch):
    provider = _build_provider()
    page_calls = {"count": 0}
    detail_calls = {"count": 0}

    def _fake_fetch_page(*_args, **_kwargs):
        page_calls["count"] += 1
        return [{"id": "template-1", "template_name": "Template One"}], False

    def _fake_fetch_detail(*_args, **_kwargs):
        detail_calls["count"] += 1
        return {"id": "template-1", "template_name": "Template One"}

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_templates_page", _fake_fetch_page)
    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_template_detail", _fake_fetch_detail)

    first_page, first_next = provider.fetch_templates_page(page=1, page_size=20)
    first_page[0]["template_name"] = "mutated"
    second_page, second_next = provider.fetch_templates_page(page=1, page_size=20)
    first_detail = provider.fetch_template_detail(template_id="template-1")
    first_detail["template_name"] = "mutated"
    second_detail = provider.fetch_template_detail(template_id="template-1")

    assert page_calls["count"] == 1
    assert detail_calls["count"] == 1
    assert first_next is False and second_next is False
    assert second_page[0]["template_name"] == "Template One"
    assert second_detail["template_name"] == "Template One"
    assert provider.templates_cache_stats() == (1, 1)


def test_provider_clear_templates_cache_forces_refetch(monkeypatch):
    provider = _build_provider()
    calls = {"page": 0, "detail": 0}

    def _fake_fetch_page(*_args, **_kwargs):
        calls["page"] += 1
        return [{"id": "template-1"}], False

    def _fake_fetch_detail(*_args, **_kwargs):
        calls["detail"] += 1
        return {"id": "template-1"}

    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_templates_page", _fake_fetch_page)
    monkeypatch.setattr("attackiq_cli.tui_provider.fetch_template_detail", _fake_fetch_detail)

    provider.fetch_templates_page(page=1, page_size=20)
    provider.fetch_template_detail(template_id="template-1")
    provider.clear_templates_cache()
    provider.fetch_templates_page(page=1, page_size=20)
    provider.fetch_template_detail(template_id="template-1")

    assert calls == {"page": 2, "detail": 2}
    assert provider.templates_cache_stats() == (1, 1)
