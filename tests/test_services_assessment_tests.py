from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
import attackiq_cli.services_assessment_tests as services_assessment_tests
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


def _context(spec: object) -> services.ServiceContext:
    return services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, spec),
    )


def _operation(operation_id: str) -> Operation:
    path = f"/v1/{operation_id.removeprefix('v1_').removesuffix('_list').removesuffix('_retrieve')}"
    return Operation(
        operation_id=operation_id,
        method="get",
        path=path,
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_build_assessment_query_params_validates_schema_filters() -> None:
    params = services.build_assessment_query_params(
        services.AssessmentFilters(
            asset_group_id=[" group-1, group-2 "],
            blueprint_id=" blueprint-1 ",
            execution_strategy=1,
            has_default_schedule=False,
            id__in=[" assessment-1 ", "assessment-2, assessment-3"],
            name=" Campaign ",
            report_instance_type=" summary ",
            search=" alpha ",
            tag_id=" tag-1 ",
            tag_ids=[" tag-2, tag-3 "],
            use_scenario_alert_rules=True,
            version=2,
            zones_ordering=[" attacker_zone ", "-target_zone"],
        )
    )

    assert params == {
        "asset_group_id": "group-1,group-2",
        "blueprint_id": "blueprint-1",
        "execution_strategy": 1,
        "has_default_schedule": False,
        "id__in": "assessment-1,assessment-2,assessment-3",
        "name": "Campaign",
        "report_instance_type": "summary",
        "search": "alpha",
        "tag_id": "tag-1",
        "tag_ids": "tag-2,tag-3",
        "use_scenario_alert_rules": True,
        "version": 2,
        "zones_ordering": "attacker_zone,-target_zone",
    }


def test_build_assessment_query_params_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="execution-strategy must be 0 or 1"):
        services.build_assessment_query_params(services.AssessmentFilters(execution_strategy=3))

    with pytest.raises(ValueError, match="zones-ordering must be one of"):
        services.build_assessment_query_params(
            services.AssessmentFilters(zones_ordering=["invalid"])
        )


def test_build_test_query_params_normalizes_filters() -> None:
    params = services.build_test_query_params(
        services.TestFilters(
            name=" API Test ",
            project_template_test_id=" template-test-1 ",
            run_in_hosted_agent_preferably=True,
            use_hosted_agent=False,
        )
    )

    assert params == {
        "name": "API Test",
        "project_template_test_id": "template-test-1",
        "run_in_hosted_agent_preferably": True,
        "use_hosted_agent": False,
    }


def test_list_assessments_autopaginates_with_query_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_list"
            return _operation(operation_id)

    class ClientStub:
        def send(self, *_args, **_kwargs):
            raise AssertionError("send should not be used in auto-paginate mode")

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    def _paginate_results(client, operation, page_size, query_params=None, **_kwargs):
        captured["client"] = client
        captured["operation"] = operation
        captured["page_size"] = page_size
        captured["query_params"] = query_params
        return [{"id": "assessment-1"}]

    monkeypatch.setattr(
        services_assessment_tests,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )
    monkeypatch.setattr(services_assessment_tests, "paginate_results", _paginate_results)

    items = services.list_assessments(
        _context(SpecStub()),
        page=None,
        page_size=100,
        query_params={"search": "alpha"},
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "assessment-1"}]
    assert captured["page_size"] == 100
    assert captured["query_params"] == {"search": "alpha"}


def test_list_tests_explicit_page_returns_results(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_list"
            return _operation(operation_id)

    class ResponseStub:
        def json(self):
            return {"results": [{"id": "test-1"}]}

    class ClientStub:
        def send(self, _operation, **kwargs):
            captured["query_params"] = kwargs["query_params"]
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_assessment_tests,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    items = services.list_tests(
        _context(SpecStub()),
        page=2,
        page_size=50,
        query_params={"name": "API Test"},
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "test-1"}]
    assert captured["query_params"] == {"page": 2, "page_size": 50, "name": "API Test"}


def test_fetch_assessments_page_uses_page_params_and_next(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_list"
            return _operation(operation_id)

    class ResponseStub:
        def json(self):
            return {"results": [{"id": "assessment-1"}], "next": "https://api.example.com/next"}

    class ClientStub:
        def send(self, operation, **kwargs):
            captured["operation"] = operation
            captured["path_params"] = kwargs["path_params"]
            captured["query_params"] = kwargs["query_params"]
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_assessment_tests,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    items, has_next = services.fetch_assessments_page(
        _context(SpecStub()),
        page=3,
        page_size=25,
        query_params={"search": "alpha"},
        insecure=False,
        timeout=None,
    )

    assert items == [{"id": "assessment-1"}]
    assert has_next is True
    assert captured["path_params"] == {}
    assert captured["query_params"] == {"page": 3, "page_size": 25, "search": "alpha"}


def test_fetch_tests_page_uses_page_params_and_next(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_list"
            return _operation(operation_id)

    class ResponseStub:
        def json(self):
            return {"results": [{"id": "test-1"}], "next": None}

    class ClientStub:
        def send(self, operation, **kwargs):
            captured["operation"] = operation
            captured["path_params"] = kwargs["path_params"]
            captured["query_params"] = kwargs["query_params"]
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_assessment_tests,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    items, has_next = services.fetch_tests_page(
        _context(SpecStub()),
        page=1,
        page_size=25,
        query_params={"name": "API Test"},
        insecure=False,
        timeout=None,
    )

    assert items == [{"id": "test-1"}]
    assert has_next is False
    assert captured["path_params"] == {}
    assert captured["query_params"] == {"page": 1, "page_size": 25, "name": "API Test"}


def test_fetch_assessment_and_test_detail_use_retrieve_path_params(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            return _operation(operation_id)

    class ResponseStub:
        def __init__(self, item_id: str) -> None:
            self.item_id = item_id

        def json(self):
            return {"id": self.item_id}

    class ClientStub:
        def send(self, operation, **kwargs):
            captured.append(
                {
                    "operation": operation.operation_id,
                    "path_params": kwargs["path_params"],
                    "query_params": kwargs["query_params"],
                }
            )
            return ResponseStub(str(kwargs["path_params"]["id"]))

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_assessment_tests,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    assessment = services.fetch_assessment_detail(
        _context(SpecStub()),
        assessment_id="assessment-1",
        insecure=False,
        timeout=None,
    )
    test = services.fetch_test_detail(
        _context(SpecStub()),
        test_id="test-1",
        insecure=False,
        timeout=None,
    )

    assert assessment == {"id": "assessment-1"}
    assert test == {"id": "test-1"}
    assert captured == [
        {
            "operation": "v1_assessments_retrieve",
            "path_params": {"id": "assessment-1"},
            "query_params": {},
        },
        {
            "operation": "v1_tests_retrieve",
            "path_params": {"id": "test-1"},
            "query_params": {},
        },
    ]
