from __future__ import annotations

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_record_lists


def test_group_by_join_key_groups_summary_job_and_missing_items() -> None:
    groups = tui_record_lists._group_by_join_key(
        [
            {"result_summary_id": "sum-1", "outcome": "pass"},
            {"result_summary": {"id": "sum-1"}, "outcome": "fail"},
            {"scenario_job_id": "job-1"},
            {"id": "unjoined"},
        ]
    )

    by_key = {group.key: group for group in groups}
    assert by_key["sum-1"].source == "result_summary_id"
    assert by_key["sum-1"].count == 2
    assert by_key["job-1"].source == "scenario_job_id"
    assert by_key["missing"].source == "missing"


def test_results_summary_filter_and_sort_helpers() -> None:
    records = [
        {"id": "sum-2", "scenario_name": "Zulu", "outcome": "pass"},
        {"id": "sum-1", "scenario_name": "Alpha", "outcome": "fail"},
    ]

    filtered = tui_record_lists._filter_results_summaries(records, outcome="pa")
    sorted_records = tui_record_lists._sort_results_summaries(
        records,
        sort_field="scenario",
        descending=False,
    )

    assert filtered == [records[0]]
    assert [record["id"] for record in sorted_records] == ["sum-1", "sum-2"]


def test_results_group_filter_and_sort_helpers() -> None:
    groups = [
        tui_record_lists.ResultsGroup(
            key="sum-1",
            source="result_summary_id",
            result_summary_id="sum-1",
            scenario_job_id=None,
            items=[{}, {}],
        ),
        tui_record_lists.ResultsGroup(
            key="job-1",
            source="scenario_job_id",
            result_summary_id=None,
            scenario_job_id="job-1",
            items=[{}],
        ),
    ]

    filtered = tui_record_lists._filter_results_groups(
        groups,
        source="scenario_job_id",
        key_query="job",
    )
    sorted_groups = tui_record_lists._sort_results_groups(
        groups,
        sort_field="count",
        descending=True,
    )

    assert filtered == [groups[1]]
    assert [group.key for group in sorted_groups] == ["sum-1", "job-1"]


def test_tui_module_reexports_record_list_helpers_for_compatibility() -> None:
    assert tui_module.ResultsGroup is tui_record_lists.ResultsGroup
    assert tui_module._group_by_join_key is tui_record_lists._group_by_join_key
    assert tui_module._sort_results_summaries is tui_record_lists._sort_results_summaries
