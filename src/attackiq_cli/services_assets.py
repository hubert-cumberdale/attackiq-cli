from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

from attackiq_cli.client import paginate_results
from attackiq_cli.platform_api_adapter import create_platform_api_adapter
from attackiq_cli.service_core import (
    ServiceContext,
    _normalize_filter,
    _optional_text,
    build_client,
    ensure_auth,
)

API_BACKEND_NATIVE = "native"
API_BACKEND_PLATFORM_API = "platform-api"
VALID_API_BACKENDS = {API_BACKEND_NATIVE, API_BACKEND_PLATFORM_API}
T = TypeVar("T")


@dataclass(frozen=True)
class AssetFilters:
    search: str | None = None
    hostname: str | None = None
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    deployment_state_id: int | None = None
    deepsurface_last_seen_in_host_analysis_at: str | None = None
    deepsurface_sync_state: str | None = None
    deepsurface_sync_state_changed_at: str | None = None
    asset_group: str | None = None
    activity_type: str | None = None
    ordering: str | None = None


@dataclass(frozen=True)
class AssetSummary:
    asset_id: str | None
    hostname: str | None
    activity_type: str | None
    deployment_state: str | None
    ipv4_address: str | None
    ipv6_address: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AssetSummary:
        deployment = payload.get("deployment_state")
        deployment_state = _optional_text(deployment)
        if isinstance(deployment, dict):
            deployment_state = _optional_text(
                deployment.get("name")
                or deployment.get("display_name")
                or deployment.get("id")
                or deployment.get("state")
            )

        return cls(
            asset_id=_optional_text(payload.get("id")),
            hostname=_optional_text(payload.get("hostname") or payload.get("name")),
            activity_type=_optional_text(payload.get("activity_type")),
            deployment_state=deployment_state,
            ipv4_address=_optional_text(payload.get("ipv4_address")),
            ipv6_address=_optional_text(payload.get("ipv6_address")),
            modified=_optional_text(payload.get("modified") or payload.get("updated_at")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.asset_id,
            "hostname": self.hostname,
            "activity_type": self.activity_type,
            "deployment_state": self.deployment_state,
            "ipv4_address": self.ipv4_address,
            "ipv6_address": self.ipv6_address,
            "modified": self.modified,
        }


def normalize_api_backend(value: str | None) -> str:
    normalized = (value or API_BACKEND_NATIVE).strip().lower()
    if normalized not in VALID_API_BACKENDS:
        raise ValueError("api-backend must be one of: native, platform-api.")
    return normalized


def build_asset_query_params(filters: AssetFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    if (hostname := _normalize_filter(filters.hostname)) is not None:
        params["hostname"] = hostname
    if (ipv4_address := _normalize_filter(filters.ipv4_address)) is not None:
        params["ipv4_address"] = ipv4_address
    if (ipv6_address := _normalize_filter(filters.ipv6_address)) is not None:
        params["ipv6_address"] = ipv6_address
    if filters.deployment_state_id is not None:
        params["deployment_state_id"] = filters.deployment_state_id
    if (
        deepsurface_last_seen := _normalize_filter(
            filters.deepsurface_last_seen_in_host_analysis_at
        )
    ) is not None:
        params["deepsurface_last_seen_in_host_analysis_at"] = deepsurface_last_seen
    if (deepsurface_sync_state := _normalize_filter(filters.deepsurface_sync_state)) is not None:
        params["deepsurface_sync_state"] = deepsurface_sync_state
    if (
        deepsurface_sync_state_changed := _normalize_filter(
            filters.deepsurface_sync_state_changed_at
        )
    ) is not None:
        params["deepsurface_sync_state_changed_at"] = deepsurface_sync_state_changed
    if (asset_group := _normalize_filter(filters.asset_group)) is not None:
        params["asset_group"] = asset_group
    if (activity_type := _normalize_filter(filters.activity_type)) is not None:
        normalized_type = activity_type.upper()
        allowed = {"DEVICE", "DOMAIN", "TESTPOINT"}
        if normalized_type not in allowed:
            raise ValueError("activity-type must be one of: DEVICE, DOMAIN, TESTPOINT.")
        params["activity_type"] = normalized_type
    if (ordering := _normalize_filter(filters.ordering)) is not None:
        params["ordering"] = ordering
    return params


def build_asset_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [AssetSummary.from_payload(item).to_record() for item in items]


def fetch_assets_page(
    context: ServiceContext,
    *,
    page: int,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    op = context.spec.get_operation("v1_assets_list")
    ensure_auth(op, context.auth)
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if query_params:
        params.update(query_params)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(op, path_params={}, query_params=params, headers={}).json()
    items = payload.get("results", [])
    return list(items), bool(payload.get("next"))


def fetch_asset_detail(
    context: ServiceContext,
    *,
    asset_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_assets_retrieve")
    ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            op,
            path_params={"id": asset_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Asset detail response must be an object.")
    return payload


def list_assets(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
    api_backend: str = API_BACKEND_NATIVE,
) -> list[dict[str, Any]]:
    api_backend = normalize_api_backend(api_backend)
    if api_backend == API_BACKEND_PLATFORM_API:
        return _run_async(
            lambda: _list_assets_with_platform_api(
                context,
                page=page,
                page_size=page_size,
                query_params=query_params,
                insecure=insecure,
                timeout=timeout,
                check_auth=check_auth,
            )
        )

    op = context.spec.get_operation("v1_assets_list")
    if check_auth:
        ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        if page is None:
            return list(
                paginate_results(
                    client,
                    op,
                    page_size=page_size,
                    query_params=query_params or None,
                )
            )
        payload = client.send(
            op,
            path_params={},
            query_params={"page": page, "page_size": page_size, **(query_params or {})},
            headers={},
        ).json()
    return list(payload.get("results") or [])


def _run_async(factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    coroutine = factory()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    coroutine.close()
    raise ValueError("platform-api backend cannot run from an active asyncio event loop.")


async def _list_assets_with_platform_api(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
    check_auth: bool,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_assets_list")
    if check_auth:
        ensure_auth(op, context.auth)
    search, deployment_state, ordering = _platform_asset_filters(query_params)
    async with create_platform_api_adapter(
        context,
        insecure=insecure,
        timeout=timeout,
    ) as adapter:
        if page is not None:
            payload = await adapter.search_assets(
                query=search,
                limit=page_size,
                offset=(page - 1) * page_size,
                ordering=ordering,
                deployment_state=deployment_state,
            )
            return _platform_payload_results(payload)

        results: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = await adapter.search_assets(
                query=search,
                limit=page_size,
                offset=offset,
                ordering=ordering,
                deployment_state=deployment_state,
            )
            batch = _platform_payload_results(payload)
            results.extend(batch)
            total_count = _platform_payload_count(payload)
            if not batch or len(batch) < page_size:
                return results
            if total_count is not None and len(results) >= total_count:
                return results
            offset += page_size


def _platform_asset_filters(
    query_params: dict[str, Any] | None,
) -> tuple[str | None, int | str | None, str | None]:
    query_params = query_params or {}
    supported = {"search", "deployment_state_id", "ordering"}
    unsupported = sorted(set(query_params) - supported)
    if unsupported:
        raise ValueError(
            "platform-api backend currently supports only asset search, deployment-state-id, "
            f"and ordering filters; unsupported: {', '.join(unsupported)}."
        )
    search = _normalize_filter(str(query_params["search"])) if "search" in query_params else None
    ordering = (
        _normalize_filter(str(query_params["ordering"])) if "ordering" in query_params else None
    )
    deployment_state = query_params.get("deployment_state_id")
    return search, deployment_state, ordering


def _platform_payload_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_results = payload.get("results") or []
    if not isinstance(raw_results, list):
        raise ValueError("platform-api payload results must be a list.")
    results: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            raise ValueError("platform-api payload results must contain objects.")
        results.append(item)
    return results


def _platform_payload_count(payload: dict[str, Any]) -> int | None:
    count = payload.get("count")
    if isinstance(count, int) and count >= 0:
        return count
    return None
