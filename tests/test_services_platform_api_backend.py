from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


def _operation(operation_id: str) -> Operation:
    return Operation(
        operation_id=operation_id,
        method="get",
        path=f"/{operation_id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


class SpecStub:
    def get_operation(self, operation_id: str) -> Operation:
        return _operation(operation_id)


def _context() -> services.ServiceContext:
    return services.ServiceContext(
        config=CliConfig(timeout=11.0),
        base_url="https://api.example.com",
        auth=services.build_auth_context(
            CliConfig(account_token="account-token"),
            preferred_scheme="auto",
        ),
        spec=cast(SpecIndex, SpecStub()),
    )


def test_list_scenarios_can_use_platform_api_backend(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class AdapterStub:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            return None

        async def search_scenarios(self, **kwargs):
            calls.append(kwargs)
            if kwargs["offset"] == 0:
                return {
                    "count": 3,
                    "results": [{"id": "scenario-1"}, {"id": "scenario-2"}],
                }
            return {"count": 3, "results": [{"id": "scenario-3"}]}

    monkeypatch.setattr(
        services,
        "create_platform_api_adapter",
        lambda *_args, **_kwargs: AdapterStub(),
    )

    items = services.list_scenarios(
        _context(),
        page=None,
        page_size=2,
        filters=services.ScenarioFilters(search="powershell", order_by="name"),
        insecure=False,
        timeout=None,
        check_auth=False,
        api_backend="platform-api",
    )

    assert items == [{"id": "scenario-1"}, {"id": "scenario-2"}, {"id": "scenario-3"}]
    assert calls == [
        {"query": "powershell", "limit": 2, "offset": 0, "ordering": "name"},
        {"query": "powershell", "limit": 2, "offset": 2, "ordering": "name"},
    ]


def test_list_scenarios_platform_api_rejects_unmapped_filters(monkeypatch) -> None:
    monkeypatch.setattr(
        services,
        "create_platform_api_adapter",
        lambda *_args, **_kwargs: pytest.fail("adapter should not be created"),
    )

    with pytest.raises(ValueError, match="unsupported: tag"):
        services.list_scenarios(
            _context(),
            page=None,
            page_size=20,
            filters=services.ScenarioFilters(search="powershell", tag="beta"),
            insecure=False,
            timeout=None,
            check_auth=False,
            api_backend="platform-api",
        )


def test_list_assets_can_use_platform_api_backend(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class AdapterStub:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            return None

        async def search_assets(self, **kwargs):
            calls.append(kwargs)
            return {"count": 1, "results": [{"id": "asset-1", "hostname": "asset-host"}]}

    monkeypatch.setattr(
        services,
        "create_platform_api_adapter",
        lambda *_args, **_kwargs: AdapterStub(),
    )

    items = services.list_assets(
        _context(),
        page=2,
        page_size=5,
        query_params={"search": "asset-host", "deployment_state_id": 2, "ordering": "hostname"},
        insecure=False,
        timeout=9.0,
        check_auth=False,
        api_backend="platform-api",
    )

    assert items == [{"id": "asset-1", "hostname": "asset-host"}]
    assert calls == [
        {
            "query": "asset-host",
            "limit": 5,
            "offset": 5,
            "ordering": "hostname",
            "deployment_state": 2,
        }
    ]


def test_list_assets_platform_api_rejects_unmapped_filters(monkeypatch) -> None:
    monkeypatch.setattr(
        services,
        "create_platform_api_adapter",
        lambda *_args, **_kwargs: pytest.fail("adapter should not be created"),
    )

    with pytest.raises(ValueError, match="unsupported: hostname"):
        services.list_assets(
            _context(),
            page=None,
            page_size=20,
            query_params={"hostname": "agent-host"},
            insecure=False,
            timeout=None,
            check_auth=False,
            api_backend="platform-api",
        )
