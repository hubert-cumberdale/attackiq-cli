from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from attackiq_cli.client import paginate_results
from attackiq_cli.service_core import (
    ServiceContext,
    _normalize_filter,
    _optional_text,
    build_client,
    ensure_auth,
)


@dataclass(frozen=True)
class AssetGroupFilters:
    search: str | None = None
    asset_group_id: str | None = None
    name: str | None = None
    description: str | None = None
    company: str | None = None
    company_id: str | None = None
    user: str | None = None
    user_id: str | None = None
    created: str | None = None
    created_after: str | None = None
    modified: str | None = None
    ordering: str | None = None


@dataclass(frozen=True)
class AssetGroupSummary:
    asset_group_id: str | None
    name: str | None
    description: str | None
    user_id: str | None
    num_assets: str | None
    created: str | None
    modified: str | None
    created_by: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AssetGroupSummary:
        return cls(
            asset_group_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            description=_optional_text(payload.get("description")),
            user_id=_optional_text(payload.get("user_id")),
            num_assets=_optional_text(payload.get("num_assets")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
            created_by=_optional_text(payload.get("created_by")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.asset_group_id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "num_assets": self.num_assets,
            "created": self.created,
            "modified": self.modified,
            "created_by": self.created_by,
        }


def build_asset_group_query_params(filters: AssetGroupFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    if (asset_group_id := _normalize_filter(filters.asset_group_id)) is not None:
        params["id"] = asset_group_id
    if (name := _normalize_filter(filters.name)) is not None:
        params["name"] = name
    if (description := _normalize_filter(filters.description)) is not None:
        params["description"] = description
    if (company := _normalize_filter(filters.company)) is not None:
        params["company"] = company
    if (company_id := _normalize_filter(filters.company_id)) is not None:
        params["company_id"] = company_id
    if (user := _normalize_filter(filters.user)) is not None:
        params["user"] = user
    if (user_id := _normalize_filter(filters.user_id)) is not None:
        params["user_id"] = user_id
    if (created := _normalize_filter(filters.created)) is not None:
        params["created"] = created
    if (created_after := _normalize_filter(filters.created_after)) is not None:
        params["created_after"] = created_after
    if (modified := _normalize_filter(filters.modified)) is not None:
        params["modified"] = modified
    if (ordering := _normalize_filter(filters.ordering)) is not None:
        params["ordering"] = ordering
    return params


def build_asset_group_summary_records(
    items: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    return [AssetGroupSummary.from_payload(item).to_record() for item in items]


def list_asset_groups(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: AssetGroupFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_asset_groups_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_asset_group_query_params(filters)
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
    if not isinstance(payload, dict):
        raise ValueError("Asset group list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Asset group list response results must be a list.")
    return list(items)


def fetch_asset_group_detail(
    context: ServiceContext,
    *,
    asset_group_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_asset_groups_retrieve")
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
            path_params={"id": asset_group_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Asset group detail response must be an object.")
    return payload
