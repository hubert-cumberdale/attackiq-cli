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
class IntegrationConnectorFilters:
    alert_correlation_plan: str | None = None
    company_connector_manager_setup: str | None = None
    company_connector_manager_setup_id: str | None = None
    description: str | None = None
    display_name: str | None = None
    implemented_mixins: str | None = None
    is_deleted: bool | None = None
    mode: str | None = None
    mttd_timezone: str | None = None
    status: str | None = None
    ordering: str | None = None


@dataclass(frozen=True)
class IntegrationConnectorSummary:
    connector_instance_id: str | None
    display_name: str | None
    status: str | None
    enabled: str | None
    active: str | None
    pending: str | None
    mode: str | None
    connector_id: str | None
    connector_name: str | None
    connector_type_id: str | None
    connector_type_name: str | None
    vendor_product_id: str | None
    vendor_product_name: str | None
    company_id: str | None
    company_name: str | None
    source_type_count: str | None
    last_checkin: str | None
    running_version: str | None
    created: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> IntegrationConnectorSummary:
        connector = payload.get("connector")
        vendor_product: Any = None
        connector_type: Any = None
        if isinstance(connector, dict):
            vendor_product = connector.get("vendor_product")
            connector_type = connector.get("connector_type")

        company = payload.get("company")
        source_types = payload.get("source_types")
        source_type_count = str(len(source_types)) if isinstance(source_types, list) else None

        return cls(
            connector_instance_id=_optional_text(payload.get("id")),
            display_name=_optional_text(payload.get("display_name")),
            status=_optional_text(payload.get("status")),
            enabled=_optional_text(payload.get("enabled")),
            active=_optional_text(payload.get("active")),
            pending=_optional_text(payload.get("pending")),
            mode=_optional_text(payload.get("mode")),
            connector_id=_optional_nested_text(connector, "id"),
            connector_name=_optional_nested_text(connector, "name"),
            connector_type_id=_optional_nested_text(connector_type, "id"),
            connector_type_name=_optional_nested_text(connector_type, "name"),
            vendor_product_id=_optional_nested_text(vendor_product, "id"),
            vendor_product_name=_optional_nested_text(vendor_product, "name"),
            company_id=_optional_nested_text(company, "id"),
            company_name=_optional_nested_text(company, "display_name")
            or _optional_nested_text(company, "name"),
            source_type_count=source_type_count,
            last_checkin=_optional_text(payload.get("last_checkin")),
            running_version=_optional_text(payload.get("running_version")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.connector_instance_id,
            "display_name": self.display_name,
            "status": self.status,
            "enabled": self.enabled,
            "active": self.active,
            "pending": self.pending,
            "mode": self.mode,
            "connector_id": self.connector_id,
            "connector_name": self.connector_name,
            "connector_type_id": self.connector_type_id,
            "connector_type_name": self.connector_type_name,
            "vendor_product_id": self.vendor_product_id,
            "vendor_product_name": self.vendor_product_name,
            "company_id": self.company_id,
            "company_name": self.company_name,
            "source_type_count": self.source_type_count,
            "last_checkin": self.last_checkin,
            "running_version": self.running_version,
            "created": self.created,
            "modified": self.modified,
        }


def build_integration_connector_query_params(
    filters: IntegrationConnectorFilters,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (plan := _normalize_filter(filters.alert_correlation_plan)) is not None:
        params["alert_correlation_plan"] = plan
    if (setup := _normalize_filter(filters.company_connector_manager_setup)) is not None:
        params["company_connector_manager_setup"] = setup
    if (setup_id := _normalize_filter(filters.company_connector_manager_setup_id)) is not None:
        params["company_connector_manager_setup_id"] = setup_id
    if (description := _normalize_filter(filters.description)) is not None:
        params["description"] = description
    if (display_name := _normalize_filter(filters.display_name)) is not None:
        params["display_name"] = display_name
    if (implemented_mixins := _normalize_filter(filters.implemented_mixins)) is not None:
        params["implemented_mixins"] = implemented_mixins
    if filters.is_deleted is not None:
        params["is_deleted"] = filters.is_deleted
    if (mode := _normalize_filter(filters.mode)) is not None:
        allowed_modes = {"Ad Hoc": "Ad Hoc", "Automatic": "Automatic"}
        normalized_mode = allowed_modes.get(mode) or allowed_modes.get(mode.title())
        if normalized_mode is None:
            raise ValueError("mode must be one of: Ad Hoc, Automatic.")
        params["mode"] = normalized_mode
    if (mttd_timezone := _normalize_filter(filters.mttd_timezone)) is not None:
        params["mttd_timezone"] = mttd_timezone
    if (status := _normalize_filter(filters.status)) is not None:
        normalized_status = status.upper()
        allowed_statuses = {
            "ACTIVE",
            "DISABLED",
            "ERROR",
            "PENDING",
            "TESTING",
            "TEST_FAILED",
            "TRANSIENT",
        }
        if normalized_status not in allowed_statuses:
            raise ValueError(
                "status must be one of: ACTIVE, DISABLED, ERROR, PENDING, TESTING, "
                "TEST_FAILED, TRANSIENT."
            )
        params["status"] = normalized_status
    if (ordering := _normalize_filter(filters.ordering)) is not None:
        params["ordering"] = ordering
    return params


def build_integration_connector_summary_records(
    items: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    return [IntegrationConnectorSummary.from_payload(item).to_record() for item in items]


def list_integration_connectors(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: IntegrationConnectorFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_company_connectors_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_integration_connector_query_params(filters)
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
        raise ValueError("Integration connector list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Integration connector list response results must be a list.")
    return list(items)
