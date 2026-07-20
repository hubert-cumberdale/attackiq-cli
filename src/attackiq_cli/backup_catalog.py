from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_BACKUP_DOMAINS = ("integrations", "source-types", "detection-rules")
BUILTIN_CONFIG_BACKUP_DOMAINS = set(DEFAULT_CONFIG_BACKUP_DOMAINS)

CATALOG_CLASSIFICATIONS = {"backup-safe", "needs-redaction", "write-like", "unsupported"}
CATALOG_PAGINATION_MODES = {"page", "none"}
CATALOG_RESPONSE_KINDS = {"paginated-list", "list", "object"}


class BackupError(ValueError):
    """Raised when a backup operation must fail closed."""


@dataclass(frozen=True)
class EndpointCatalogEntry:
    domain: str
    method: str
    path: str
    classification: str
    operation_id: str | None = None
    query_params: dict[str, Any] = field(default_factory=dict)
    required_params: tuple[str, ...] = ()
    pagination: str = "page"
    response_kind: str = "paginated-list"
    sensitive_fields: tuple[str, ...] = ()


def load_endpoint_catalog(path: Path | None) -> dict[str, EndpointCatalogEntry]:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupError(f"Endpoint catalog is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise BackupError(f"Endpoint catalog could not be read: {exc}") from exc
    entries = validate_endpoint_catalog(data)
    return {entry.domain: entry for entry in entries}


def validate_endpoint_catalog(data: Any) -> list[EndpointCatalogEntry]:
    if not isinstance(data, dict):
        raise BackupError("Endpoint catalog root must be an object.")
    if data.get("version") != 1:
        raise BackupError("Endpoint catalog version must be 1.")
    raw_entries = data.get("endpoints")
    if not isinstance(raw_entries, list):
        raise BackupError("Endpoint catalog endpoints must be a list.")

    entries: list[EndpointCatalogEntry] = []
    seen_domains: set[str] = set()
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            raise BackupError(f"Endpoint catalog entry {index} must be an object.")
        domain = _required_catalog_text(raw_entry, "domain", index).lower()
        if domain in seen_domains:
            raise BackupError(f"Endpoint catalog domain '{domain}' is duplicated.")
        seen_domains.add(domain)

        method = _required_catalog_text(raw_entry, "method", index).upper()
        path = _required_catalog_text(raw_entry, "path", index)
        if not path.startswith("/") or "://" in path:
            raise BackupError(f"Endpoint catalog domain '{domain}' must use a relative path.")

        classification = _required_catalog_text(raw_entry, "classification", index)
        if classification not in CATALOG_CLASSIFICATIONS:
            raise BackupError(
                f"Endpoint catalog domain '{domain}' classification must be one of: "
                f"{', '.join(sorted(CATALOG_CLASSIFICATIONS))}."
            )

        pagination = _optional_catalog_text(raw_entry, "pagination", "page")
        if pagination not in CATALOG_PAGINATION_MODES:
            raise BackupError(
                f"Endpoint catalog domain '{domain}' pagination must be page or none."
            )

        default_response_kind = "paginated-list" if pagination == "page" else "object"
        response_kind = _optional_catalog_text(raw_entry, "response_kind", default_response_kind)
        if response_kind not in CATALOG_RESPONSE_KINDS:
            raise BackupError(
                f"Endpoint catalog domain '{domain}' response_kind must be one of: "
                f"{', '.join(sorted(CATALOG_RESPONSE_KINDS))}."
            )
        if pagination == "page" and response_kind != "paginated-list":
            raise BackupError(
                f"Endpoint catalog domain '{domain}' with page pagination must use "
                "response_kind paginated-list."
            )

        query_params = raw_entry.get("query_params", {})
        if not isinstance(query_params, dict):
            raise BackupError(f"Endpoint catalog domain '{domain}' query_params must be an object.")
        required_params = _catalog_string_tuple(raw_entry.get("required_params", ()), domain)
        missing_params = [param for param in required_params if param not in query_params]
        if missing_params:
            raise BackupError(
                f"Endpoint catalog domain '{domain}' is missing required query_params: "
                f"{', '.join(missing_params)}."
            )

        sensitive_fields = _catalog_string_tuple(raw_entry.get("sensitive_fields", ()), domain)
        if classification == "needs-redaction" and not sensitive_fields:
            raise BackupError(
                f"Endpoint catalog domain '{domain}' needs-redaction entries must declare "
                "sensitive_fields."
            )

        operation_id = raw_entry.get("operation_id")
        if operation_id is not None and not isinstance(operation_id, str):
            raise BackupError(f"Endpoint catalog domain '{domain}' operation_id must be a string.")

        entries.append(
            EndpointCatalogEntry(
                domain=domain,
                method=method,
                path=path,
                classification=classification,
                operation_id=operation_id.strip() if operation_id else None,
                query_params=dict(query_params),
                required_params=required_params,
                pagination=pagination,
                response_kind=response_kind,
                sensitive_fields=sensitive_fields,
            )
        )
    return entries


def validate_requested_domains(
    domains: tuple[str, ...],
    catalog: dict[str, EndpointCatalogEntry],
) -> None:
    for domain in domains:
        if domain in BUILTIN_CONFIG_BACKUP_DOMAINS:
            continue
        if domain not in catalog:
            known = sorted(BUILTIN_CONFIG_BACKUP_DOMAINS | set(catalog))
            raise BackupError(
                f"Unknown backup domain '{domain}'. Known domains: {', '.join(known)}."
            )
        validate_catalog_entry_read_only(catalog[domain])


def validate_catalog_entry_read_only(entry: EndpointCatalogEntry) -> None:
    if entry.classification in {"write-like", "unsupported"}:
        raise BackupError(
            f"Endpoint catalog domain '{entry.domain}' is {entry.classification} and cannot be "
            "used by backup commands."
        )
    if entry.method != "GET":
        raise BackupError(
            f"Endpoint catalog domain '{entry.domain}' uses method {entry.method}; only GET is "
            "allowed for backup commands."
        )


def _required_catalog_text(entry: dict[str, Any], field_name: str, index: int) -> str:
    value = entry.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise BackupError(f"Endpoint catalog entry {index} field '{field_name}' is required.")
    return value.strip()


def _optional_catalog_text(entry: dict[str, Any], field_name: str, default: str) -> str:
    value = entry.get(field_name, default)
    if not isinstance(value, str) or not value.strip():
        return default
    return value.strip()


def _catalog_string_tuple(value: Any, domain: str) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise BackupError(f"Endpoint catalog domain '{domain}' field list must be a list.")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise BackupError(
                f"Endpoint catalog domain '{domain}' field list values must be strings."
            )
        items.append(item.strip())
    return tuple(items)
