from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from attackiq_cli import __version__
from attackiq_cli.config import validate_timeout

if TYPE_CHECKING:
    from attackiq_cli.services import ServiceContext


class PlatformApiUnavailable(ValueError):
    """Raised when the optional aiq-platform-api SDK cannot be used."""


class PlatformApiUnsupported(ValueError):
    """Raised when the SDK cannot preserve this CLI's transport semantics."""


@dataclass(frozen=True)
class PlatformApiBindings:
    client_class: Any
    scenarios: Any
    assets: Any
    version: str | None


@dataclass
class PlatformApiAdapter:
    base_url: str
    platform_api_token: str
    timeout: float
    bindings: PlatformApiBindings
    user_agent: str = f"attackiq-cli/{__version__} aiq-platform-api-adapter"
    verify_tls: bool = True
    _client: Any | None = None

    async def __aenter__(self) -> PlatformApiAdapter:
        kwargs = _client_constructor_kwargs(
            self.bindings.client_class,
            timeout=self.timeout,
            user_agent=self.user_agent,
            verify_tls=self.verify_tls,
        )
        self._client = self.bindings.client_class(
            self.base_url,
            self.platform_api_token,
            **kwargs,
        )
        enter = getattr(self._client, "__aenter__", None)
        if enter is not None:
            self._client = await enter()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is None:
            return
        exit_method = getattr(self._client, "__aexit__", None)
        if exit_method is not None:
            await exit_method(exc_type, exc, tb)
            return
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()

    @property
    def client(self) -> Any:
        if self._client is None:
            raise RuntimeError("Platform API adapter must be used as an async context manager.")
        return self._client

    async def search_scenarios(
        self,
        *,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
        ordering: str | None = "-modified",
    ) -> dict[str, Any]:
        result = await self.bindings.scenarios.search_scenarios(
            self.client,
            query=query,
            limit=limit,
            offset=offset,
            ordering=ordering,
        )
        return _dict_payload(result, "Scenarios.search_scenarios")

    async def search_assets(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        ordering: str | None = "-modified",
        deployment_state: int | str | None = None,
    ) -> dict[str, Any]:
        search_assets = getattr(self.bindings.assets, "search_assets", None)
        if search_assets is not None:
            result = await search_assets(
                self.client,
                query=query,
                status=status,
                limit=limit,
                offset=offset,
                ordering=ordering,
                deployment_state=deployment_state,
            )
            return _dict_payload(result, "Assets.search_assets")

        get_assets = getattr(self.bindings.assets, "get_assets", None)
        if get_assets is None:
            raise PlatformApiUnavailable("aiq-platform-api Assets export has no search/list API.")
        params: dict[str, Any] = {}
        if query:
            params["search"] = query
        if status:
            params["status"] = status
        if deployment_state is not None:
            params["deployment_state_id"] = deployment_state
        results = [
            dict(asset)
            async for asset in get_assets(
                self.client,
                params=params,
                limit=limit,
                offset=offset,
                ordering=ordering,
            )
        ]
        return {"count": len(results), "results": results}


def load_platform_api_bindings(sdk_module: Any | None = None) -> PlatformApiBindings:
    if sdk_module is None:
        try:
            sdk_module = importlib.import_module("aiq_platform_api")
        except ImportError as exc:
            raise PlatformApiUnavailable(
                "aiq-platform-api is not installed. Install the optional extra with "
                "`pip install -e '.[platform-api]'` on Python 3.11+."
            ) from exc

    client_class = getattr(sdk_module, "AttackIQClient", None)
    scenarios = _first_export(sdk_module, ("Scenarios", "ScenarioUtils"))
    assets = _first_export(sdk_module, ("Assets", "AssetUtils"))
    missing = [
        name
        for name, value in (
            ("AttackIQClient", client_class),
            ("Scenarios", scenarios),
            ("Assets", assets),
        )
        if value is None
    ]
    if missing:
        raise PlatformApiUnavailable(
            "aiq-platform-api is missing required exports: " + ", ".join(missing)
        )

    return PlatformApiBindings(
        client_class=client_class,
        scenarios=scenarios,
        assets=assets,
        version=getattr(sdk_module, "__version__", None),
    )


def create_platform_api_adapter(
    context: ServiceContext,
    *,
    insecure: bool,
    timeout: float | None,
    bindings: PlatformApiBindings | None = None,
) -> PlatformApiAdapter:
    bindings = bindings or load_platform_api_bindings()
    verify_tls = context.config.verify_tls and not insecure
    if not verify_tls and not _client_accepts_any(bindings.client_class, ("verify", "verify_tls")):
        raise PlatformApiUnsupported(
            "aiq-platform-api 1.0.49 does not expose TLS verification control; use the "
            "native CLI client for --insecure or verify_tls=false workflows."
        )
    if not _client_accepts_any(bindings.client_class, ("timeout",)):
        raise PlatformApiUnsupported(
            "aiq-platform-api client constructor does not expose timeout control."
        )

    platform_api_token = context.auth.account_token or context.auth.jwt
    if not platform_api_token:
        raise PlatformApiUnsupported(
            "aiq-platform-api requires an Account Token or JWT-compatible API token."
        )

    return PlatformApiAdapter(
        base_url=context.base_url,
        platform_api_token=platform_api_token,
        timeout=validate_timeout(timeout if timeout is not None else context.config.timeout),
        verify_tls=verify_tls,
        bindings=bindings,
    )


def _client_constructor_kwargs(
    client_class: Any,
    *,
    timeout: float,
    user_agent: str,
    verify_tls: bool,
) -> dict[str, Any]:
    params = _signature_params(client_class)
    kwargs: dict[str, Any] = {}
    if "timeout" in params:
        kwargs["timeout"] = httpx.Timeout(timeout)
    if "user_agent" in params:
        kwargs["user_agent"] = user_agent
    if "verify" in params:
        kwargs["verify"] = verify_tls
    if "verify_tls" in params:
        kwargs["verify_tls"] = verify_tls
    return kwargs


def _client_accepts_any(client_class: Any, names: tuple[str, ...]) -> bool:
    params = _signature_params(client_class)
    return any(name in params for name in names)


def _signature_params(callable_object: Any) -> set[str]:
    try:
        return set(inspect.signature(callable_object).parameters)
    except (TypeError, ValueError):
        return set()


def _first_export(module: Any, names: tuple[str, ...]) -> Any | None:
    for name in names:
        value = getattr(module, name, None)
        if value is not None:
            return value
    return None


def _dict_payload(value: Any, source: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{source} returned {type(value).__name__}; expected dict.")
    return {str(key): payload_value for key, payload_value in value.items()}
