from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from attackiq_cli.client import AttackIQClient, paginate_results
from attackiq_cli.service_core import (
    ServiceContext,
    _is_uuid,
    _normalize_filter,
    _optional_text,
    build_client,
    ensure_auth,
)


@dataclass(frozen=True)
class TagChoice:
    name: str
    display_name: str | None
    tag_id: str

    def label(self) -> str:
        label = self.name
        if self.display_name and self.display_name != self.name:
            label = f"{self.name} ({self.display_name})"
        return f"{label} [{self.tag_id}]"


class AmbiguousTagError(ValueError):
    def __init__(self, tag: str, choices: list[TagChoice], message: str) -> None:
        super().__init__(message)
        self.tag = tag
        self.choices = choices


@dataclass(frozen=True)
class TagFilters:
    search: str | None = None
    name: str | None = None
    display_name: str | None = None
    content_type: str | None = None
    exclude_tags_by_tag_set: str | None = None
    object_fingerprint: str | None = None


@dataclass(frozen=True)
class TagSummary:
    tag_id: str | None
    name: str | None
    display_name: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TagSummary:
        return cls(
            tag_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            display_name=_optional_text(payload.get("display_name")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.tag_id,
            "name": self.name,
            "display_name": self.display_name,
        }


def build_tag_query_params(filters: TagFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    if (name := _normalize_filter(filters.name)) is not None:
        params["name"] = name
    if (display_name := _normalize_filter(filters.display_name)) is not None:
        params["display_name"] = display_name
    if (content_type := _normalize_filter(filters.content_type)) is not None:
        params["content_type"] = content_type
    if (exclude := _normalize_filter(filters.exclude_tags_by_tag_set)) is not None:
        # CLI validates UUID; we keep this builder simple.
        params["exclude_tags_by_tag_set"] = exclude
    if (fingerprint := _normalize_filter(filters.object_fingerprint)) is not None:
        params["object_fingerprint"] = fingerprint
    return params


def resolve_tag_filter(
    context: ServiceContext,
    *,
    tag: str | None,
    insecure: bool,
    timeout: float | None,
    client: AttackIQClient | None = None,
) -> str | None:
    if not tag:
        return None
    if _is_uuid(tag):
        return tag
    op = context.spec.get_operation("v1_tags_list")
    ensure_auth(op, context.auth)

    def _build_tag_choices(results: list[dict[str, Any]]) -> list[TagChoice]:
        choices: list[TagChoice] = []
        for record in results:
            name = str(record.get("name") or "")
            display_name = record.get("display_name")
            tag_id = str(record.get("id") or "unknown-id")
            choices.append(TagChoice(name=name, display_name=display_name, tag_id=tag_id))
        return choices

    def _resolve_tag_id(active_client: AttackIQClient) -> str:
        payload = active_client.send(
            op,
            path_params={},
            query_params={"name": tag, "page": 1, "page_size": 200},
            headers={},
        ).json()
        results = list(payload.get("results") or [])
        matches = [record for record in results if record.get("name") == tag]
        if matches:
            results = matches
        if not results:
            raise ValueError(f"No tag found with name '{tag}'.")
        tag_ids = [record.get("id") for record in results if record.get("id")]
        if len(tag_ids) == 1:
            return str(tag_ids[0])
        choices = _build_tag_choices(results)
        preview = ", ".join(choice.label() for choice in choices[:5])
        if len(choices) > 5:
            preview = f"{preview}, +{len(choices) - 5} more"
        message = f"Multiple tags found for '{tag}': {preview}. Use a tag UUID instead."
        raise AmbiguousTagError(tag, choices, message)

    if client is None:
        with build_client(
            context.base_url,
            context.config,
            context.auth,
            insecure=insecure,
            timeout=timeout,
        ) as active_client:
            return _resolve_tag_id(active_client)
    return _resolve_tag_id(client)


def build_tag_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [TagSummary.from_payload(item).to_record() for item in items]


def list_tags(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: TagFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_tags_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_tag_query_params(filters)
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


def fetch_tag_detail(
    context: ServiceContext,
    *,
    tag_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_tags_retrieve")
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
            path_params={"id": tag_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Tag detail response must be an object.")
    return payload


def search_tags(
    context: ServiceContext,
    *,
    query: str,
    limit: int,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_tags_list")
    if check_auth:
        ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        results = list(
            paginate_results(
                client,
                op,
                page_size=limit,
                query_params={"search": query},
                max_pages=1,
            )
        )
    if len(results) > limit:
        return results[:limit]
    return results
