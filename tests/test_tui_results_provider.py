from __future__ import annotations

from attackiq_cli.services import ResultsMode, build_results_list_query


def test_results_query_summaries_requires_assessment_results():
    operation_id, params = build_results_list_query(
        mode=ResultsMode.SUMMARIES,
        page=2,
        page_size=50,
    )
    assert operation_id == "v1_results_list"
    assert params["assessment_results"] is True
    assert params["page"] == 2
    assert params["page_size"] == 50


def test_results_query_phases_uses_phase_results_endpoint():
    operation_id, params = build_results_list_query(
        mode=ResultsMode.PHASES,
        page=1,
        page_size=20,
    )
    assert operation_id == "v1_phase_results_list"
    assert "assessment_results" not in params
    assert params["page"] == 1
    assert params["page_size"] == 20


def test_results_query_logs_uses_phase_logs_endpoint():
    operation_id, params = build_results_list_query(
        mode=ResultsMode.LOGS,
        page=3,
        page_size=15,
    )
    assert operation_id == "v1_phase_logs_list"
    assert "assessment_results" not in params
    assert params["page"] == 3
    assert params["page_size"] == 15
