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
class BlueprintFilters:
    search: str | None = None


@dataclass(frozen=True)
class BlueprintSummary:
    blueprint_id: str | None
    name: str | None
    blueprint_template: str | None
    company: str | None
    has_modules: str | None
    modules: str | None
    created: str | None
    modified: str | None
    source_content_changed: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> BlueprintSummary:
        return cls(
            blueprint_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            blueprint_template=_optional_text(payload.get("blueprint_template")),
            company=_optional_text(payload.get("company")),
            has_modules=_optional_text(payload.get("has_modules")),
            modules=_optional_text(payload.get("modules")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
            source_content_changed=_optional_text(payload.get("source_content_changed")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.blueprint_id,
            "name": self.name,
            "blueprint_template": self.blueprint_template,
            "company": self.company,
            "has_modules": self.has_modules,
            "modules": self.modules,
            "created": self.created,
            "modified": self.modified,
            "source_content_changed": self.source_content_changed,
        }


def build_blueprint_query_params(filters: BlueprintFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    return params


def build_blueprint_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [BlueprintSummary.from_payload(item).to_record() for item in items]


def list_blueprints(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: BlueprintFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_blueprints_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_blueprint_query_params(filters)
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
        raise ValueError("Blueprint list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Blueprint list response results must be a list.")
    return list(items)
