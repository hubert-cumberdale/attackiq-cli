from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from attackiq_cli.client import paginate_results
from attackiq_cli.service_core import (
    ServiceContext,
    _normalize_filter,
    _optional_nested_text,
    _optional_text,
    build_client,
    ensure_auth,
)


@dataclass(frozen=True)
class SourceTypeFilters:
    company_id: str
    connector_id: str
    object_fingerprint: str | None = None
    unassigned_for: str | None = None


@dataclass(frozen=True)
class SourceTypeSummary:
    source_type_id: str | None
    source_type_string: str | None
    connector_id: str | None
    connector_name: str | None
    vendor_product_id: str | None
    vendor_product_name: str | None
    company_id: str | None
    user_id: str | None
    ignore: str | None
    object_fingerprint: str | None
    syncd_on: str | None
    created: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SourceTypeSummary:
        connector = payload.get("connector")
        vendor_product = payload.get("vendor_product")
        return cls(
            source_type_id=_optional_text(payload.get("id")),
            source_type_string=_optional_text(payload.get("source_type_string")),
            connector_id=_optional_nested_text(connector, "id"),
            connector_name=_optional_nested_text(connector, "name"),
            vendor_product_id=_optional_nested_text(vendor_product, "id"),
            vendor_product_name=_optional_nested_text(vendor_product, "name"),
            company_id=_optional_text(payload.get("company")),
            user_id=_optional_text(payload.get("user")),
            ignore=_optional_text(payload.get("ignore")),
            object_fingerprint=_optional_text(payload.get("object_fingerprint")),
            syncd_on=_optional_text(payload.get("syncd_on")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.source_type_id,
            "source_type_string": self.source_type_string,
            "connector_id": self.connector_id,
            "connector_name": self.connector_name,
            "vendor_product_id": self.vendor_product_id,
            "vendor_product_name": self.vendor_product_name,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "ignore": self.ignore,
            "object_fingerprint": self.object_fingerprint,
            "syncd_on": self.syncd_on,
            "created": self.created,
            "modified": self.modified,
        }


def build_source_type_query_params(filters: SourceTypeFilters) -> dict[str, Any]:
    company_id = _normalize_filter(filters.company_id)
    connector_id = _normalize_filter(filters.connector_id)
    if company_id is None:
        raise ValueError("company_id is required.")
    if connector_id is None:
        raise ValueError("connector_id is required.")

    params: dict[str, Any] = {
        "company": company_id,
        "connector": connector_id,
    }
    if (fingerprint := _normalize_filter(filters.object_fingerprint)) is not None:
        params["object_fingerprint"] = fingerprint
    if (unassigned_for := _normalize_filter(filters.unassigned_for)) is not None:
        params["unassigned_for"] = unassigned_for
    return params


def build_source_type_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [SourceTypeSummary.from_payload(item).to_record() for item in items]


def list_source_types(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: SourceTypeFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_source_types_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_source_type_query_params(filters)
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
                    query_params=query_params,
                )
            )
        payload = client.send(
            op,
            path_params={},
            query_params={"page": page, "page_size": page_size, **query_params},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Source type list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Source type list response results must be a list.")
    return list(items)
