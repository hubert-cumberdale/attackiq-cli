from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from attackiq_cli.backup_catalog import (
    BackupError,
    EndpointCatalogEntry,
    validate_catalog_entry_read_only,
)
from attackiq_cli.client import AttackIQClient
from attackiq_cli.services import ServiceContext, ensure_auth
from attackiq_cli.spec import Operation

__all__ = [
    "SourceTypeRequest",
    "build_source_type_requests",
    "fetch_catalog_entry_for_backup",
    "fetch_detection_rules_for_backup",
    "fetch_integrations_for_backup",
    "fetch_paginated_records",
    "fetch_source_types_for_backup",
]


@dataclass(frozen=True)
class SourceTypeRequest:
    company_id: str
    connector_id: str
    connector_instance_id: str | None
    connector_display_name: str | None


def fetch_integrations_for_backup(
    context: ServiceContext,
    client: AttackIQClient,
    *,
    page_size: int,
    max_pages: int | None,
) -> list[dict[str, Any]]:
    operation = context.spec.get_operation("v1_company_connectors_list")
    ensure_auth(operation, context.auth)
    return fetch_paginated_records(
        client,
        operation,
        page_size=page_size,
        max_pages=max_pages,
        response_label="Integration connector list",
    )


def fetch_source_types_for_backup(
    context: ServiceContext,
    client: AttackIQClient,
    source_requests: list[SourceTypeRequest],
    *,
    page_size: int,
    max_pages: int | None,
) -> list[dict[str, Any]]:
    operation = context.spec.get_operation("v1_source_types_list")
    ensure_auth(operation, context.auth)
    records: list[dict[str, Any]] = []
    for request in source_requests:
        source_types = fetch_paginated_records(
            client,
            operation,
            page_size=page_size,
            max_pages=max_pages,
            query_params={"company": request.company_id, "connector": request.connector_id},
            response_label="Source type list",
        )
        for source_type in source_types:
            records.append(
                {
                    "company_id": request.company_id,
                    "connector_id": request.connector_id,
                    "connector_instance_id": request.connector_instance_id,
                    "connector_display_name": request.connector_display_name,
                    "source_type": source_type,
                }
            )
    return records


def fetch_detection_rules_for_backup(
    context: ServiceContext,
    client: AttackIQClient,
    *,
    page_size: int,
    max_pages: int | None,
) -> list[dict[str, Any]]:
    operation = context.spec.get_operation("v1_unified_mitigations_with_relations_list")
    ensure_auth(operation, context.auth)
    return fetch_paginated_records(
        client,
        operation,
        page_size=page_size,
        max_pages=max_pages,
        response_label="Detection rule list",
    )


def fetch_catalog_entry_for_backup(
    context: ServiceContext,
    client: AttackIQClient,
    entry: EndpointCatalogEntry,
    *,
    page_size: int,
    max_pages: int | None,
) -> list[Any]:
    validate_catalog_entry_read_only(entry)

    operation = _operation_for_catalog_entry(context, entry)
    ensure_auth(operation, context.auth)
    if entry.response_kind == "paginated-list":
        return fetch_paginated_records(
            client,
            operation,
            page_size=page_size,
            max_pages=max_pages,
            query_params=entry.query_params,
            response_label=f"Endpoint catalog domain '{entry.domain}'",
        )

    payload = client.send(
        operation,
        path_params={},
        query_params=entry.query_params,
        headers={},
    ).json()
    if entry.response_kind == "list":
        if not isinstance(payload, list):
            raise BackupError(f"Endpoint catalog domain '{entry.domain}' response must be a list.")
        return list(payload)
    if not isinstance(payload, dict):
        raise BackupError(f"Endpoint catalog domain '{entry.domain}' response must be an object.")
    return [payload]


def fetch_paginated_records(
    client: AttackIQClient,
    operation: Operation,
    *,
    page_size: int,
    max_pages: int | None,
    query_params: dict[str, Any] | None = None,
    response_label: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page = 1
    base_query = dict(query_params or {})
    while True:
        params = {"page": page, "page_size": page_size, **base_query}
        payload = client.send(
            operation,
            path_params={},
            query_params=params,
            headers={},
        ).json()
        if not isinstance(payload, dict):
            raise BackupError(f"{response_label} response must be an object.")
        items = payload.get("results", [])
        if not isinstance(items, list):
            raise BackupError(f"{response_label} response results must be a list.")
        for item in items:
            if not isinstance(item, dict):
                raise BackupError(f"{response_label} response results must contain objects.")
        records.extend(items)
        if not items or not payload.get("next"):
            break
        page += 1
        if max_pages is not None and page > max_pages:
            break
    return records


def build_source_type_requests(
    integrations: list[dict[str, Any]],
    *,
    company_id_override: str | None,
) -> list[SourceTypeRequest]:
    requests: list[SourceTypeRequest] = []
    seen: set[tuple[str, str]] = set()
    for integration in integrations:
        company_id = company_id_override or _extract_identifier(integration.get("company"))
        company_id = company_id or _extract_identifier(integration.get("company_id"))
        connector = integration.get("connector")
        connector_id = _extract_identifier(connector) or _extract_identifier(
            integration.get("connector_id")
        )
        if not company_id or not connector_id:
            continue
        key = (company_id, connector_id)
        if key in seen:
            continue
        seen.add(key)
        requests.append(
            SourceTypeRequest(
                company_id=company_id,
                connector_id=connector_id,
                connector_instance_id=_extract_identifier(integration.get("id")),
                connector_display_name=_optional_text(integration.get("display_name")),
            )
        )
    return requests


def _operation_for_catalog_entry(context: ServiceContext, entry: EndpointCatalogEntry) -> Operation:
    if entry.operation_id:
        operation = context.spec.get_operation(entry.operation_id)
        if operation.method.upper() != "GET":
            raise BackupError(
                f"Endpoint catalog domain '{entry.domain}' operation {entry.operation_id} is "
                f"{operation.method.upper()}; only GET is allowed."
            )
        if operation.path != entry.path:
            raise BackupError(
                f"Endpoint catalog domain '{entry.domain}' path does not match operation "
                f"{entry.operation_id}."
            )
        return operation
    return Operation(
        operation_id=f"endpoint_catalog_{entry.domain.replace('-', '_')}",
        method="get",
        path=entry.path,
        summary=f"Endpoint catalog backup domain {entry.domain}",
        parameters=[],
        request_body=None,
        tags=["endpoint-catalog"],
        security=[{"Account Token": []}, {"JSON Web Token": []}],
    )


def _extract_identifier(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("id", "uuid"):
            if identifier := _optional_text(value.get(key)):
                return identifier
        return None
    return _optional_text(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
