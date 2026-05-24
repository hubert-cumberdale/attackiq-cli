from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast

import httpx
import pytest

from attackiq_cli.client import AuthContext
from attackiq_cli.config import CliConfig
from attackiq_cli.platform_api_adapter import (
    PlatformApiUnavailable,
    PlatformApiUnsupported,
    create_platform_api_adapter,
    load_platform_api_bindings,
)
from attackiq_cli.services import ServiceContext
from attackiq_cli.spec import SpecIndex


def _context(
    *,
    account_token: str | None = "account-token",
    jwt: str | None = None,
    verify_tls: bool = True,
    timeout: float = 12.0,
) -> ServiceContext:
    return ServiceContext(
        config=CliConfig(verify_tls=verify_tls, timeout=timeout),
        base_url="https://platform.example.test",
        auth=AuthContext(
            account_token=account_token,
            jwt=jwt,
            preferred_scheme="auto",
        ),
        spec=cast(SpecIndex, object()),
    )


class ClientStub:
    instances: list[ClientStub] = []

    def __init__(
        self,
        platform_url: str,
        platform_api_token: str,
        timeout: httpx.Timeout,
        user_agent: str,
    ) -> None:
        self.platform_url = platform_url
        self.platform_api_token = platform_api_token
        self.timeout = timeout
        self.user_agent = user_agent
        self.closed = False
        ClientStub.instances.append(self)

    async def __aenter__(self) -> ClientStub:
        return self

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        self.closed = True


class ScenarioSdkStub:
    @staticmethod
    async def search_scenarios(
        client: ClientStub,
        *,
        query: str | None,
        limit: int,
        offset: int,
        ordering: str | None,
    ) -> dict[str, object]:
        return {
            "count": 1,
            "results": [{"id": "scenario-1", "name": query}],
            "client_url": client.platform_url,
            "limit": limit,
            "offset": offset,
            "ordering": ordering,
        }


class AssetSdkStub:
    @staticmethod
    async def search_assets(
        client: ClientStub,
        *,
        query: str | None,
        status: str | None,
        limit: int,
        offset: int,
        ordering: str | None,
        deployment_state: int | str | None,
    ) -> dict[str, object]:
        return {
            "count": 1,
            "results": [
                {
                    "id": "asset-1",
                    "hostname": query,
                    "platform_url": client.platform_url,
                }
            ],
            "status": status,
            "limit": limit,
            "offset": offset,
            "ordering": ordering,
            "deployment_state": deployment_state,
        }


def _sdk_module():
    return SimpleNamespace(
        AttackIQClient=ClientStub,
        Scenarios=ScenarioSdkStub,
        Assets=AssetSdkStub,
        __version__="1.0.49",
    )


def test_load_platform_api_bindings_accepts_current_sdk_exports():
    bindings = load_platform_api_bindings(_sdk_module())

    assert bindings.client_class is ClientStub
    assert bindings.scenarios is ScenarioSdkStub
    assert bindings.assets is AssetSdkStub
    assert bindings.version == "1.0.49"


def test_load_platform_api_bindings_accepts_legacy_export_names():
    sdk_module = SimpleNamespace(
        AttackIQClient=ClientStub,
        ScenarioUtils=ScenarioSdkStub,
        AssetUtils=AssetSdkStub,
        __version__="1.0.0",
    )

    bindings = load_platform_api_bindings(sdk_module)

    assert bindings.scenarios is ScenarioSdkStub
    assert bindings.assets is AssetSdkStub


def test_load_platform_api_bindings_rejects_missing_exports():
    with pytest.raises(PlatformApiUnavailable, match="missing required exports"):
        load_platform_api_bindings(SimpleNamespace(AttackIQClient=ClientStub))


def test_create_platform_api_adapter_maps_context_and_timeout():
    ClientStub.instances.clear()
    bindings = load_platform_api_bindings(_sdk_module())
    adapter = create_platform_api_adapter(
        _context(timeout=9.0),
        insecure=False,
        timeout=7.5,
        bindings=bindings,
    )

    async def run() -> dict[str, object]:
        async with adapter as platform_api:
            return await platform_api.search_scenarios(query="powershell", limit=5, offset=2)

    payload = asyncio.run(run())

    assert payload["count"] == 1
    assert payload["client_url"] == "https://platform.example.test"
    assert ClientStub.instances[0].platform_api_token == "account-token"
    assert ClientStub.instances[0].timeout.connect == 7.5
    assert ClientStub.instances[0].user_agent.startswith("attackiq-cli/")
    assert ClientStub.instances[0].closed is True


def test_create_platform_api_adapter_supports_jwt_fallback():
    ClientStub.instances.clear()
    bindings = load_platform_api_bindings(_sdk_module())
    adapter = create_platform_api_adapter(
        _context(account_token=None, jwt="header.payload.signature"),
        insecure=False,
        timeout=None,
        bindings=bindings,
    )

    async def run() -> None:
        async with adapter:
            return None

    asyncio.run(run())

    assert ClientStub.instances[0].platform_api_token == "header.payload.signature"


def test_platform_api_adapter_search_assets_delegates_to_sdk():
    bindings = load_platform_api_bindings(_sdk_module())
    adapter = create_platform_api_adapter(
        _context(),
        insecure=False,
        timeout=None,
        bindings=bindings,
    )

    async def run() -> dict[str, object]:
        async with adapter as platform_api:
            return await platform_api.search_assets(
                query="asset-host",
                status="Active",
                deployment_state="Installed",
            )

    payload = asyncio.run(run())

    assert payload["count"] == 1
    assert payload["status"] == "Active"
    assert payload["deployment_state"] == "Installed"
    assert payload["results"] == [
        {
            "id": "asset-1",
            "hostname": "asset-host",
            "platform_url": "https://platform.example.test",
        }
    ]


def test_create_platform_api_adapter_rejects_insecure_when_sdk_cannot_disable_tls_verify():
    bindings = load_platform_api_bindings(_sdk_module())

    with pytest.raises(PlatformApiUnsupported, match="TLS verification control"):
        create_platform_api_adapter(
            _context(),
            insecure=True,
            timeout=None,
            bindings=bindings,
        )


def test_create_platform_api_adapter_rejects_missing_token():
    bindings = load_platform_api_bindings(_sdk_module())

    with pytest.raises(PlatformApiUnsupported, match="requires an Account Token"):
        create_platform_api_adapter(
            _context(account_token=None, jwt=None),
            insecure=False,
            timeout=None,
            bindings=bindings,
        )
