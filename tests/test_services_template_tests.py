from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
import attackiq_cli.services_templates as services_templates
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


def _context(spec: object) -> services.ServiceContext:
    return services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, spec),
    )


def _list_operation() -> Operation:
    return Operation(
        operation_id="v1_project_template_tests_list",
        method="get",
        path="/v1/project_template_tests",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_build_template_test_query_params_normalizes_filters() -> None:
    params = services.build_template_test_query_params(
        services.TemplateTestFilters(project_template_id=" template-1 ")
    )

    assert params == {"project_template_id": "template-1"}


def test_list_template_tests_autopaginates_with_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}
    op = _list_operation()

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_project_template_tests_list"
            return op

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
        return [{"id": "template-test-1", "name": "Template Test One"}]

    monkeypatch.setattr(
        services_templates,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )
    monkeypatch.setattr(services_templates, "paginate_results", _paginate_results)

    items = services.list_template_tests(
        _context(SpecStub()),
        page=None,
        page_size=100,
        filters=services.TemplateTestFilters(project_template_id=" template-1 "),
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "template-test-1", "name": "Template Test One"}]
    assert captured["operation"] is op
    assert captured["page_size"] == 100
    assert captured["query_params"] == {"project_template_id": "template-1"}


def test_list_template_tests_explicit_page_validates_results_shape(monkeypatch) -> None:
    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_project_template_tests_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return {"results": {"id": "template-test-1"}}

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_templates,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    with pytest.raises(ValueError, match="results must be a list"):
        services.list_template_tests(
            _context(SpecStub()),
            page=1,
            page_size=100,
            filters=services.TemplateTestFilters(),
            insecure=False,
            timeout=None,
            check_auth=False,
        )


def test_build_template_test_summary_records_picks_schema_fields() -> None:
    records = services.build_template_test_summary_records(
        [
            {
                "id": "template-test-1",
                "name": " Test One ",
                "description": " Scenario set ",
                "project_template": "template-1",
                "scenarios": ["scenario-1", "scenario-2"],
                "order": 3,
                "created": "2026-05-20T00:00:00Z",
                "modified": "2026-05-21T00:00:00Z",
                "meta_data": {"ignored": True},
            }
        ]
    )

    assert records == [
        {
            "id": "template-test-1",
            "name": "Test One",
            "description": "Scenario set",
            "project_template": "template-1",
            "scenario_count": "2",
            "scenarios": "scenario-1,scenario-2",
            "order": "3",
            "created": "2026-05-20T00:00:00Z",
            "modified": "2026-05-21T00:00:00Z",
        }
    ]
