from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx

from attackiq_cli.client import (
    AttackIQClient,
    paginate_results,
)
from attackiq_cli.config import ConfigError
from attackiq_cli.platform_api_adapter import create_platform_api_adapter
from attackiq_cli.service_core import (
    ServiceContext,
    _normalize_filter,
    _optional_text,
    build_client,
    ensure_auth,
)
from attackiq_cli.services_tags import resolve_tag_filter

API_BACKEND_NATIVE = "native"
API_BACKEND_PLATFORM_API = "platform-api"
VALID_API_BACKENDS = {API_BACKEND_NATIVE, API_BACKEND_PLATFORM_API}
T = TypeVar("T")


@dataclass(frozen=True)
class ScenarioFilters:
    order_by: str | None = None
    search: str | None = None
    tag: str | None = None
    name: str | None = None
    modified_after: str | None = None
    last_updated: str | None = None
    mitre_platforms: str | None = None
    hierarchy: str | None = None
    object_fingerprint: str | None = None
    parameters_description: str | None = None
    scenario_template_instance: str | None = None


def normalize_api_backend(value: str | None) -> str:
    normalized = (value or API_BACKEND_NATIVE).strip().lower()
    if normalized not in VALID_API_BACKENDS:
        raise ValueError("api-backend must be one of: native, platform-api.")
    return normalized


@dataclass(frozen=True)
class ScenarioSummary:
    scenario_id: str | None
    name: str | None
    scenario_type: str | None
    description: str | None
    created: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ScenarioSummary:
        return cls(
            scenario_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            scenario_type=_optional_text(payload.get("scenario_type")),
            description=_optional_text(payload.get("description")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.scenario_id,
            "name": self.name,
            "scenario_type": self.scenario_type,
            "description": self.description,
            "created": self.created,
            "modified": self.modified,
        }


def build_scenario_query_params(filters: ScenarioFilters) -> dict[str, str]:
    params: dict[str, str] = {}
    modified_after = _normalize_filter(filters.modified_after)
    last_updated = _normalize_filter(filters.last_updated)
    if modified_after and last_updated and modified_after != last_updated:
        raise ValueError("modified-after and last-updated cannot both be set to different values.")
    for key, value in {
        "order_by": filters.order_by,
        "search": filters.search,
        "name": filters.name,
        "mitre_platforms": filters.mitre_platforms,
        "hierarchy": filters.hierarchy,
        "object_fingerprint": filters.object_fingerprint,
        "parameters_description": filters.parameters_description,
        "scenario_template_instance": filters.scenario_template_instance,
    }.items():
        normalized = _normalize_filter(value)
        if normalized is not None:
            params[key] = normalized
    if modified_after or last_updated:
        params["modified_after"] = modified_after or last_updated or ""
    return params


def build_scenarios_query_params(
    context: ServiceContext,
    *,
    filters: ScenarioFilters,
    insecure: bool,
    timeout: float | None,
    client: AttackIQClient,
) -> dict[str, Any]:
    params = build_scenario_query_params(filters)
    normalized_tag = _normalize_filter(filters.tag)
    if normalized_tag:
        resolved_tag = resolve_tag_filter(
            context,
            tag=normalized_tag,
            insecure=insecure,
            timeout=timeout,
            client=client,
        )
        if resolved_tag:
            params["tag"] = resolved_tag
    return params


def build_scenario_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [ScenarioSummary.from_payload(item).to_record() for item in items]


def health_check(
    context: ServiceContext,
    *,
    insecure: bool,
    timeout: float | None,
) -> tuple[bool, str]:
    op = context.spec.get_operation("v1_scenarios_list")
    try:
        ensure_auth(op, context.auth)
        with build_client(
            context.base_url,
            context.config,
            context.auth,
            insecure=insecure,
            timeout=timeout,
        ) as client:
            client.send(
                op,
                path_params={},
                query_params={"page": 1, "page_size": 1},
                headers={},
            )
        return True, "OK"
    except (ConfigError, httpx.HTTPError, ValueError) as exc:
        return False, str(exc)


def fetch_scenarios_page(
    context: ServiceContext,
    *,
    page: int,
    page_size: int,
    filters: ScenarioFilters,
    insecure: bool,
    timeout: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    op = context.spec.get_operation("v1_scenarios_list")
    ensure_auth(op, context.auth)
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        resolved_params = build_scenarios_query_params(
            context,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
            client=client,
        )
        if resolved_params:
            params.update(resolved_params)
        payload = client.send(op, path_params={}, query_params=params, headers={}).json()
    items = payload.get("results", [])
    return list(items), bool(payload.get("next"))


def fetch_scenario_detail(
    context: ServiceContext,
    *,
    scenario_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_scenarios_retrieve")
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
            path_params={"id": scenario_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Scenario detail response must be an object.")
    return payload


def list_scenarios(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: ScenarioFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
    api_backend: str = API_BACKEND_NATIVE,
) -> list[dict[str, Any]]:
    api_backend = normalize_api_backend(api_backend)
    if api_backend == API_BACKEND_PLATFORM_API:
        return _run_async(
            lambda: _list_scenarios_with_platform_api(
                context,
                page=page,
                page_size=page_size,
                filters=filters,
                insecure=insecure,
                timeout=timeout,
                check_auth=check_auth,
            )
        )

    op = context.spec.get_operation("v1_scenarios_list")
    if check_auth:
        ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        query_params = build_scenarios_query_params(
            context,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
            client=client,
        )
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


async def _list_scenarios_with_platform_api(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: ScenarioFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_scenarios_list")
    if check_auth:
        ensure_auth(op, context.auth)
    _validate_platform_scenario_filters(filters)
    query = _normalize_filter(filters.search)
    ordering = _normalize_filter(filters.order_by) or "-modified"
    async with create_platform_api_adapter(
        context,
        insecure=insecure,
        timeout=timeout,
    ) as adapter:
        if page is not None:
            payload = await adapter.search_scenarios(
                query=query,
                limit=page_size,
                offset=(page - 1) * page_size,
                ordering=ordering,
            )
            return _platform_payload_results(payload)

        results: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = await adapter.search_scenarios(
                query=query,
                limit=page_size,
                offset=offset,
                ordering=ordering,
            )
            batch = _platform_payload_results(payload)
            results.extend(batch)
            total_count = _platform_payload_count(payload)
            if not batch or len(batch) < page_size:
                return results
            if total_count is not None and len(results) >= total_count:
                return results
            offset += page_size


def _validate_platform_scenario_filters(filters: ScenarioFilters) -> None:
    modified_after = _normalize_filter(filters.modified_after) or _normalize_filter(
        filters.last_updated
    )
    unsupported = [
        name
        for name, value in (
            ("tag", filters.tag),
            ("name", filters.name),
            ("modified_after", modified_after),
            ("mitre_platforms", filters.mitre_platforms),
            ("hierarchy", filters.hierarchy),
            ("object_fingerprint", filters.object_fingerprint),
            ("parameters_description", filters.parameters_description),
            ("scenario_template_instance", filters.scenario_template_instance),
        )
        if _normalize_filter(value) is not None
    ]
    if unsupported:
        raise ValueError(
            "platform-api backend currently supports only scenario search and order-by filters; "
            f"unsupported: {', '.join(unsupported)}."
        )


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
