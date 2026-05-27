from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


def _context(spec: object) -> services.ServiceContext:
    return services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, spec),
    )


def test_build_template_query_params_normalizes_filters() -> None:
    params = services.build_template_query_params(
        services.TemplateFilters(
            search=" alpha ",
            template_name=" Template One ",
            project_name=" Project One ",
            category=" validation ",
            assessment_type=" baseline ",
            behavior=" endpoint ",
        )
    )

    assert params == {
        "search": "alpha",
        "template_name": "Template One",
        "project_name": "Project One",
        "category": "validation",
        "assessment_type": "baseline",
        "behavior": "endpoint",
    }


def test_list_templates_autopaginates_with_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}

    op = Operation(
        operation_id="v1_assessment_templates_list",
        method="get",
        path="/v1/assessment_templates",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessment_templates_list"
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
        return [{"id": "template-1", "template_name": "Template One"}]

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())
    monkeypatch.setattr(services, "paginate_results", _paginate_results)

    items = services.list_templates(
        _context(SpecStub()),
        page=None,
        page_size=100,
        filters=services.TemplateFilters(search=" alpha ", template_name=" Template One "),
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "template-1", "template_name": "Template One"}]
    assert captured["page_size"] == 100
    assert captured["query_params"] == {"search": "alpha", "template_name": "Template One"}


def test_list_templates_explicit_page_validates_results_shape(monkeypatch) -> None:
    op = Operation(
        operation_id="v1_assessment_templates_list",
        method="get",
        path="/v1/assessment_templates",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessment_templates_list"
            return op

    class ResponseStub:
        def json(self):
            return {"results": {"id": "template-1"}}

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())

    with pytest.raises(ValueError, match="results must be a list"):
        services.list_templates(
            _context(SpecStub()),
            page=1,
            page_size=100,
            filters=services.TemplateFilters(),
            insecure=False,
            timeout=None,
            check_auth=False,
        )


def test_fetch_template_detail_uses_retrieve_path_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    op = Operation(
        operation_id="v1_assessment_templates_retrieve",
        method="get",
        path="/v1/assessment_templates/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessment_templates_retrieve"
            return op

    class ResponseStub:
        def json(self):
            return {"id": "template-1", "template_name": "Template One"}

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

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())

    detail = services.fetch_template_detail(
        _context(SpecStub()),
        template_id="template-1",
        insecure=False,
        timeout=None,
    )

    assert detail == {"id": "template-1", "template_name": "Template One"}
    assert captured["operation"] is op
    assert captured["path_params"] == {"id": "template-1"}
    assert captured["query_params"] == {}
