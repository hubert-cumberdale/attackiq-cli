from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
import attackiq_cli.services_assets as services_assets
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
        operation_id="v1_assets_list",
        method="get",
        path="/v1/assets",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _retrieve_operation() -> Operation:
    return Operation(
        operation_id="v1_assets_retrieve",
        method="get",
        path="/v1/assets/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_build_asset_query_params_normalizes_filters() -> None:
    params = services.build_asset_query_params(
        services.AssetFilters(
            search=" agent ",
            hostname=" host-1 ",
            ipv4_address=" 192.0.2.10 ",
            ipv6_address=" 2001:db8::1 ",
            deployment_state_id=2,
            deepsurface_last_seen_in_host_analysis_at=" 2026-05-21T00:00:00Z ",
            deepsurface_sync_state=" synced ",
            deepsurface_sync_state_changed_at=" 2026-05-21T01:00:00Z ",
            asset_group=" group-1 ",
            activity_type="device",
            ordering=" hostname ",
        )
    )

    assert params == {
        "search": "agent",
        "hostname": "host-1",
        "ipv4_address": "192.0.2.10",
        "ipv6_address": "2001:db8::1",
        "deployment_state_id": 2,
        "deepsurface_last_seen_in_host_analysis_at": "2026-05-21T00:00:00Z",
        "deepsurface_sync_state": "synced",
        "deepsurface_sync_state_changed_at": "2026-05-21T01:00:00Z",
        "asset_group": "group-1",
        "activity_type": "DEVICE",
        "ordering": "hostname",
    }


def test_build_asset_query_params_rejects_invalid_activity_type() -> None:
    with pytest.raises(ValueError, match="activity-type must be one of"):
        services.build_asset_query_params(services.AssetFilters(activity_type="invalid"))


def test_list_assets_autopaginates_with_query_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assets_list"
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
        return [{"id": "asset-1", "hostname": "host-1"}]

    monkeypatch.setattr(
        services_assets,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )
    monkeypatch.setattr(services_assets, "paginate_results", _paginate_results)

    items = services.list_assets(
        _context(SpecStub()),
        page=None,
        page_size=100,
        query_params={"search": "host-1"},
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "asset-1", "hostname": "host-1"}]
    assert captured["page_size"] == 100
    assert captured["query_params"] == {"search": "host-1"}


def test_list_assets_explicit_page_returns_results(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assets_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return {"results": [{"id": "asset-1", "hostname": "host-1"}]}

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
        services_assets,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    items = services.list_assets(
        _context(SpecStub()),
        page=2,
        page_size=50,
        query_params={"ordering": "hostname"},
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "asset-1", "hostname": "host-1"}]
    assert captured["query_params"] == {
        "page": 2,
        "page_size": 50,
        "ordering": "hostname",
    }


def test_fetch_assets_page_uses_page_params_and_next(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assets_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return {"results": [{"id": "asset-1"}], "next": "https://api.example.com/next"}

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
        services_assets,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    items, has_next = services.fetch_assets_page(
        _context(SpecStub()),
        page=3,
        page_size=25,
        query_params={"search": "host-1"},
        insecure=False,
        timeout=None,
    )

    assert items == [{"id": "asset-1"}]
    assert has_next is True
    assert captured["path_params"] == {}
    assert captured["query_params"] == {"page": 3, "page_size": 25, "search": "host-1"}


def test_fetch_asset_detail_uses_retrieve_path_params(monkeypatch) -> None:
    captured: dict[str, object] = {}
    op = _retrieve_operation()

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assets_retrieve"
            return op

    class ResponseStub:
        def json(self):
            return {"id": "asset-1", "hostname": "host-1"}

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
        services_assets,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    detail = services.fetch_asset_detail(
        _context(SpecStub()),
        asset_id="asset-1",
        insecure=False,
        timeout=None,
    )

    assert detail == {"id": "asset-1", "hostname": "host-1"}
    assert captured["operation"] is op
    assert captured["path_params"] == {"id": "asset-1"}
    assert captured["query_params"] == {}


def test_build_asset_summary_records_picks_schema_fields() -> None:
    records = services.build_asset_summary_records(
        [
            {
                "id": "asset-1",
                "hostname": " host-1 ",
                "activity_type": "DEVICE",
                "deployment_state": {"name": " Active "},
                "ipv4_address": "192.0.2.10",
                "ipv6_address": "2001:db8::1",
                "updated_at": "2026-05-21T00:00:00Z",
                "tags": [{"ignored": True}],
            }
        ]
    )

    assert records == [
        {
            "id": "asset-1",
            "hostname": "host-1",
            "activity_type": "DEVICE",
            "deployment_state": "Active",
            "ipv4_address": "192.0.2.10",
            "ipv6_address": "2001:db8::1",
            "modified": "2026-05-21T00:00:00Z",
        }
    ]
