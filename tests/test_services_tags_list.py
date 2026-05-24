from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


def test_list_tags_autopaginates_with_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}

    op = Operation(
        operation_id="v1_tags_list",
        method="get",
        path="/v1/tags",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tags_list"
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
        return [{"id": "tag-1"}]

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())
    monkeypatch.setattr(services, "paginate_results", _paginate_results)

    context = services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, SpecStub()),
    )

    filters = services.TagFilters(search=" alpha ", name=" beta ")
    items = services.list_tags(
        context,
        page=None,
        page_size=200,
        filters=filters,
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "tag-1"}]
    assert captured["page_size"] == 200
    assert captured["query_params"] == {"search": "alpha", "name": "beta"}


def test_fetch_tag_detail_uses_retrieve_path_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    op = Operation(
        operation_id="v1_tags_retrieve",
        method="get",
        path="/v1/tags/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tags_retrieve"
            return op

    class ResponseStub:
        def json(self):
            return {"id": "tag-1", "name": "alpha"}

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

    context = services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, SpecStub()),
    )

    detail = services.fetch_tag_detail(
        context,
        tag_id="tag-1",
        insecure=False,
        timeout=None,
    )

    assert detail == {"id": "tag-1", "name": "alpha"}
    assert captured["operation"] is op
    assert captured["path_params"] == {"id": "tag-1"}
    assert captured["query_params"] == {}


def test_fetch_tag_detail_rejects_malformed_payload(monkeypatch) -> None:
    op = Operation(
        operation_id="v1_tags_retrieve",
        method="get",
        path="/v1/tags/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tags_retrieve"
            return op

    class ResponseStub:
        def json(self):
            return [{"id": "tag-1"}]

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())

    context = services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, SpecStub()),
    )

    with pytest.raises(ValueError, match="Tag detail response must be an object"):
        services.fetch_tag_detail(
            context,
            tag_id="tag-1",
            insecure=False,
            timeout=None,
        )


def test_search_tags_uses_single_page_search_query(monkeypatch) -> None:
    captured: dict[str, object] = {}

    op = Operation(
        operation_id="v1_tags_list",
        method="get",
        path="/v1/tags",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tags_list"
            return op

    class ClientStub:
        pass

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    def _paginate_results(
        client, operation, page_size, query_params=None, max_pages=None, **_kwargs
    ):
        captured["client"] = client
        captured["operation"] = operation
        captured["page_size"] = page_size
        captured["query_params"] = query_params
        captured["max_pages"] = max_pages
        return [
            {"id": "tag-1"},
            {"id": "tag-2"},
            {"id": "tag-3"},
        ]

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())
    monkeypatch.setattr(services, "paginate_results", _paginate_results)

    context = services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, SpecStub()),
    )

    items = services.search_tags(
        context,
        query=" alpha ",
        limit=2,
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "tag-1"}, {"id": "tag-2"}]
    assert captured["page_size"] == 2
    assert captured["query_params"] == {"search": " alpha "}
    assert captured["max_pages"] == 1
