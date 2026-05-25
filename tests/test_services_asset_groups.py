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


def _list_operation() -> Operation:
    return Operation(
        operation_id="v1_asset_groups_list",
        method="get",
        path="/v1/asset_groups",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _retrieve_operation() -> Operation:
    return Operation(
        operation_id="v1_asset_groups_retrieve",
        method="get",
        path="/v1/asset_groups/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_build_asset_group_query_params_normalizes_filters() -> None:
    params = services.build_asset_group_query_params(
        services.AssetGroupFilters(
            search=" linux ",
            asset_group_id=" group-1 ",
            name=" Linux Agents ",
            description=" endpoint ",
            company=" company-1 ",
            company_id=" company-2 ",
            user=" user-1 ",
            user_id=" user-2 ",
            created=" 2026-05-21T00:00:00Z ",
            created_after=" 2026-05-20T00:00:00Z ",
            modified=" 2026-05-21T01:00:00Z ",
            ordering=" name ",
        )
    )

    assert params == {
        "search": "linux",
        "id": "group-1",
        "name": "Linux Agents",
        "description": "endpoint",
        "company": "company-1",
        "company_id": "company-2",
        "user": "user-1",
        "user_id": "user-2",
        "created": "2026-05-21T00:00:00Z",
        "created_after": "2026-05-20T00:00:00Z",
        "modified": "2026-05-21T01:00:00Z",
        "ordering": "name",
    }


def test_list_asset_groups_autopaginates_with_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_asset_groups_list"
            return _list_operation()

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
        return [{"id": "group-1", "name": "Linux Agents"}]

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())
    monkeypatch.setattr(services, "paginate_results", _paginate_results)

    items = services.list_asset_groups(
        _context(SpecStub()),
        page=None,
        page_size=100,
        filters=services.AssetGroupFilters(search=" linux ", name=" Linux Agents "),
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "group-1", "name": "Linux Agents"}]
    assert captured["page_size"] == 100
    assert captured["query_params"] == {"search": "linux", "name": "Linux Agents"}


def test_list_asset_groups_explicit_page_validates_results_shape(monkeypatch) -> None:
    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_asset_groups_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return {"results": {"id": "group-1"}}

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
        services.list_asset_groups(
            _context(SpecStub()),
            page=1,
            page_size=100,
            filters=services.AssetGroupFilters(),
            insecure=False,
            timeout=None,
            check_auth=False,
        )


def test_fetch_asset_group_detail_uses_retrieve_path_params(monkeypatch) -> None:
    captured: dict[str, object] = {}
    op = _retrieve_operation()

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_asset_groups_retrieve"
            return op

    class ResponseStub:
        def json(self):
            return {"id": "group-1", "name": "Linux Agents"}

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

    detail = services.fetch_asset_group_detail(
        _context(SpecStub()),
        asset_group_id="group-1",
        insecure=False,
        timeout=None,
    )

    assert detail == {"id": "group-1", "name": "Linux Agents"}
    assert captured["operation"] is op
    assert captured["path_params"] == {"id": "group-1"}
    assert captured["query_params"] == {}


def test_build_asset_group_summary_records_picks_schema_fields() -> None:
    records = services.build_asset_group_summary_records(
        [
            {
                "id": "group-1",
                "name": " Linux Agents ",
                "description": " Endpoint assets ",
                "user_id": "user-1",
                "num_assets": 12,
                "created": "2026-05-20T00:00:00Z",
                "modified": "2026-05-21T00:00:00Z",
                "created_by": "operator@example.com",
                "rules": {"ignored": True},
            }
        ]
    )

    assert records == [
        {
            "id": "group-1",
            "name": "Linux Agents",
            "description": "Endpoint assets",
            "user_id": "user-1",
            "num_assets": "12",
            "created": "2026-05-20T00:00:00Z",
            "modified": "2026-05-21T00:00:00Z",
            "created_by": "operator@example.com",
        }
    ]
