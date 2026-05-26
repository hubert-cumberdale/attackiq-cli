from __future__ import annotations

from typing import cast

import pytest

from attackiq_cli.client import AttackIQClient, AuthContext
from attackiq_cli.config import CliConfig
from attackiq_cli.services import (
    AmbiguousTagError,
    AssessmentFilters,
    AssetFilters,
    ResultsMode,
    ScenarioFilters,
    ServiceContext,
    build_assessment_query_params,
    build_assessment_summary_records,
    build_asset_query_params,
    build_results_list_query,
    build_scenario_query_params,
    build_scenario_summary_records,
    build_tag_summary_records,
    build_test_summary_records,
    fetch_scenarios_page,
    resolve_tag_filter,
)
from attackiq_cli.spec import Operation, SpecIndex


def test_fetch_scenarios_page_includes_search_and_tag(monkeypatch):
    scenario_operation = Operation(
        operation_id="v1_scenarios_list",
        method="get",
        path="/scenarios",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )
    tags_operation = Operation(
        operation_id="v1_tags_list",
        method="get",
        path="/v1/tags",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            if _operation_id == "v1_tags_list":
                return tags_operation
            return scenario_operation

    context = ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=AuthContext(account_token=None, jwt=None, preferred_scheme="auto"),
        spec=cast(SpecIndex, DummySpecIndex()),
    )

    captured: dict[str, object] = {}

    class TagsResponseStub:
        def json(self):
            return {"results": [{"id": "tag-uuid-1", "name": "beta"}]}

    class ScenariosResponseStub:
        def json(self):
            return {"results": [], "next": None}

    class ClientStub:
        def send(self, _op, **kwargs):
            if _op.operation_id == "v1_tags_list":
                return TagsResponseStub()
            captured.update(kwargs["query_params"])
            return ScenariosResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "attackiq_cli.services.build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    fetch_scenarios_page(
        context,
        page=1,
        page_size=25,
        filters=ScenarioFilters(search="alpha", tag="beta"),
        insecure=False,
        timeout=None,
    )

    assert captured["search"] == "alpha"
    assert captured["tag"] == "tag-uuid-1"


def test_build_scenario_query_params_uses_modified_after() -> None:
    params = build_scenario_query_params(
        ScenarioFilters(
            search=" alpha ",
            modified_after=" 2026-05-21T00:00:00Z ",
            last_updated="",
        )
    )

    assert params == {
        "search": "alpha",
        "modified_after": "2026-05-21T00:00:00Z",
    }


def test_build_scenario_query_params_maps_last_updated_alias() -> None:
    params = build_scenario_query_params(
        ScenarioFilters(last_updated="2026-05-21T00:00:00Z")
    )

    assert params == {"modified_after": "2026-05-21T00:00:00Z"}


def test_build_scenario_query_params_rejects_conflicting_modified_filters() -> None:
    with pytest.raises(ValueError, match="modified-after and last-updated"):
        build_scenario_query_params(
            ScenarioFilters(
                modified_after="2026-05-21T00:00:00Z",
                last_updated="2026-05-20T00:00:00Z",
            )
        )


def test_build_assessment_query_params_includes_schema_filters() -> None:
    params = build_assessment_query_params(
        AssessmentFilters(
            id__in=["assessment-1, assessment-2", "assessment-3"],
            tag_id=" tag-1 ",
            tag_ids=["tag-2, tag-3"],
            search=" alpha ",
        )
    )

    assert params == {
        "id__in": "assessment-1,assessment-2,assessment-3",
        "search": "alpha",
        "tag_id": "tag-1",
        "tag_ids": "tag-2,tag-3",
    }


def test_build_asset_query_params_includes_deepsurface_filters() -> None:
    params = build_asset_query_params(
        AssetFilters(
            deepsurface_last_seen_in_host_analysis_at=" 2026-05-21T00:00:00Z ",
            deepsurface_sync_state=" synced ",
            deepsurface_sync_state_changed_at=" 2026-05-21T01:00:00Z ",
        )
    )

    assert params == {
        "deepsurface_last_seen_in_host_analysis_at": "2026-05-21T00:00:00Z",
        "deepsurface_sync_state": "synced",
        "deepsurface_sync_state_changed_at": "2026-05-21T01:00:00Z",
    }


def test_build_results_list_query_supports_summary_tag_id_only() -> None:
    operation_id, params = build_results_list_query(
        mode=ResultsMode.SUMMARIES,
        page=1,
        page_size=20,
        tag_id=" tag-1 ",
    )

    assert operation_id == "v1_results_list"
    assert params["tag_id"] == "tag-1"

    with pytest.raises(ValueError, match="tag_id is only supported"):
        build_results_list_query(
            mode=ResultsMode.PHASES,
            page=1,
            page_size=20,
            tag_id="tag-1",
        )


def test_resolve_tag_filter_multiple_matches():
    tags_operation = Operation(
        operation_id="v1_tags_list",
        method="get",
        path="/v1/tags",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return tags_operation

    context = ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=AuthContext(account_token=None, jwt=None, preferred_scheme="auto"),
        spec=cast(SpecIndex, DummySpecIndex()),
    )

    class ResponseStub:
        def json(self):
            return {
                "results": [
                    {"id": "tag-1", "name": "alpha"},
                    {"id": "tag-2", "name": "alpha"},
                ]
            }

    class ClientStub:
        def send(self, _op, **_kwargs):
            return ResponseStub()

    with pytest.raises(AmbiguousTagError, match="Multiple tags found") as exc_info:
        resolve_tag_filter(
            context,
            tag="alpha",
            insecure=False,
            timeout=None,
            client=cast(AttackIQClient, ClientStub()),
        )

    error = exc_info.value
    assert error.tag == "alpha"
    assert len(error.choices) == 2
    assert error.choices[0].tag_id == "tag-1"


def test_build_tag_summary_records_normalizes_values():
    records = build_tag_summary_records(
        [
            {"id": "tag-1", "name": "alpha", "display_name": "Alpha", "ignored": "x"},
            {"id": 2, "name": " beta ", "display_name": None},
        ]
    )

    assert records == [
        {"id": "tag-1", "name": "alpha", "display_name": "Alpha"},
        {"id": "2", "name": "beta", "display_name": None},
    ]


def test_build_scenario_summary_records_picks_common_fields():
    records = build_scenario_summary_records(
        [
            {
                "id": "scenario-1",
                "name": "Scenario One",
                "scenario_type": "atomic",
                "description": "Example",
                "created": "2026-01-01T00:00:00Z",
                "modified": "2026-01-02T00:00:00Z",
                "extra": "ignore",
            }
        ]
    )

    assert records == [
        {
            "id": "scenario-1",
            "name": "Scenario One",
            "scenario_type": "atomic",
            "description": "Example",
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-02T00:00:00Z",
        }
    ]


def test_build_assessment_summary_records_normalizes_nested_type():
    records = build_assessment_summary_records(
        [
            {
                "id": 7,
                "name": "  Assessment One  ",
                "assessment_type": {"id": "type-1", "name": " Purple Team "},
                "status": " complete ",
                "created": "2026-01-01T00:00:00Z",
                "modified": "2026-01-02T00:00:00Z",
                "extra": "ignored",
            }
        ]
    )

    assert records == [
        {
            "id": "7",
            "name": "Assessment One",
            "assessment_type": "Purple Team",
            "assessment_type_id": "type-1",
            "assessment_type_name": "Purple Team",
            "status": "complete",
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-02T00:00:00Z",
        }
    ]


def test_build_test_summary_records_normalizes_project_and_flags():
    records = build_test_summary_records(
        [
            {
                "id": 9,
                "name": " Test One ",
                "description": " Example ",
                "project": {"id": "project-1", "name": " Core Project "},
                "runnable": True,
                "scheduled_count": 2,
                "created": "2026-01-01T00:00:00Z",
                "modified": "2026-01-02T00:00:00Z",
                "use_hosted_agent": False,
                "use_pool_agent": True,
                "using_default_assets": False,
                "using_default_schedule": True,
                "order": 5,
                "has_scenario_modules": False,
            }
        ]
    )

    assert records == [
        {
            "id": "9",
            "name": "Test One",
            "description": "Example",
            "project": "Core Project",
            "runnable": "True",
            "scheduled_count": "2",
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-02T00:00:00Z",
            "use_hosted_agent": "False",
            "use_pool_agent": "True",
            "using_default_assets": "False",
            "using_default_schedule": "True",
            "order": "5",
            "has_scenario_modules": "False",
        }
    ]
