from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from attackiq_cli import __version__
from attackiq_cli.backup_catalog import (
    BUILTIN_CONFIG_BACKUP_DOMAINS,
    DEFAULT_CONFIG_BACKUP_DOMAINS,
    BackupError,
    EndpointCatalogEntry,
    load_endpoint_catalog,
    validate_catalog_entry_read_only,
    validate_endpoint_catalog,
    validate_requested_domains,
)
from attackiq_cli.client import AttackIQClient
from attackiq_cli.exporter import write_json
from attackiq_cli.services import ServiceContext, build_client, ensure_auth
from attackiq_cli.spec import Operation

REDACTED_VALUE = "[REDACTED]"

__all__ = [
    "BackupError",
    "EndpointCatalogEntry",
    "load_endpoint_catalog",
    "validate_endpoint_catalog",
]

_KEY_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")
_SIGNED_URL_RE = re.compile(
    r"([?&](x-amz-signature|x-goog-signature|signature|sig|se)=|AWSAccessKeyId=)",
    re.IGNORECASE,
)
_AUTH_VALUE_RE = re.compile(r"^(bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{8,}$", re.IGNORECASE)
_JWT_RE = re.compile(r"^[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}$")
_PEM_PRIVATE_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*(PRIVATE KEY|ENCRYPTED|CERTIFICATE|PKCS12)[A-Z0-9 ]*-----"
)

_SENSITIVE_KEY_TOKENS = {
    "apikey",
    "api_key",
    "auth_header",
    "authorization",
    "bearer_token",
    "certificate",
    "cert",
    "client_key",
    "client_secret",
    "connection_string",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "jwt",
    "key_material",
    "password",
    "passphrase",
    "pem",
    "pfx",
    "pkcs12",
    "private_key",
    "refresh_token",
    "secret",
    "secret_key",
    "session",
    "set_cookie",
    "signed_url",
    "token",
}

_SENSITIVE_CONTAINER_KEYS = {
    "additional_configuration_options",
    "configuration",
    "connector_configuration",
    "headers",
}


@dataclass(frozen=True)
class ConfigBackupOptions:
    output_dir: Path
    domains: tuple[str, ...]
    page_size: int
    max_pages: int | None
    company_id: str | None
    endpoint_catalog: Path | None
    tenant_alias: str
    command: str
    insecure: bool
    timeout: float | None


@dataclass(frozen=True)
class SourceTypeRequest:
    company_id: str
    connector_id: str
    connector_instance_id: str | None
    connector_display_name: str | None


@dataclass
class RedactionReport:
    redacted_paths: list[str] = field(default_factory=list)

    @property
    def redacted_count(self) -> int:
        return len(self.redacted_paths)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_backup_domains(include: str | None) -> tuple[str, ...]:
    if include is None:
        return DEFAULT_CONFIG_BACKUP_DOMAINS
    domains: list[str] = []
    for part in include.split(","):
        domain = part.strip().lower()
        if domain:
            domains.append(domain)
    if not domains:
        raise BackupError("At least one backup domain must be included.")
    return tuple(dict.fromkeys(domains))


def run_configuration_backup(
    context: ServiceContext,
    options: ConfigBackupOptions,
) -> dict[str, Any]:
    if options.page_size < 1:
        raise BackupError("page-size must be >= 1.")
    if options.max_pages is not None and options.max_pages < 1:
        raise BackupError("max-pages must be >= 1.")

    catalog = load_endpoint_catalog(options.endpoint_catalog)
    domains = options.domains
    validate_requested_domains(domains, catalog)
    output_dir = prepare_backup_output_dir(options.output_dir)
    generated_at = utc_timestamp()

    artifacts: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    integrations: list[dict[str, Any]] | None = None

    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=options.insecure,
        timeout=options.timeout,
    ) as client:
        if "integrations" in domains or "source-types" in domains:
            integrations = fetch_integrations_for_backup(
                context,
                client,
                page_size=options.page_size,
                max_pages=options.max_pages,
            )

        if "integrations" in domains:
            artifacts.append(
                write_backup_artifact(
                    output_dir=output_dir,
                    domain="integrations",
                    operation_id="v1_company_connectors_list",
                    source="openapi",
                    classification="needs-redaction",
                    records=integrations or [],
                )
            )

        if "source-types" in domains:
            source_requests = build_source_type_requests(
                integrations or [],
                company_id_override=options.company_id,
            )
            if not source_requests:
                skipped.append(
                    {
                        "domain": "source-types",
                        "reason": "no integrations with company and connector IDs were found",
                    }
                )
            else:
                source_type_records = fetch_source_types_for_backup(
                    context,
                    client,
                    source_requests,
                    page_size=options.page_size,
                    max_pages=options.max_pages,
                )
                artifacts.append(
                    write_backup_artifact(
                        output_dir=output_dir,
                        domain="source-types",
                        operation_id="v1_source_types_list",
                        source="openapi",
                        classification="needs-redaction",
                        records=source_type_records,
                    )
                )

        if "detection-rules" in domains:
            detection_rules = fetch_detection_rules_for_backup(
                context,
                client,
                page_size=options.page_size,
                max_pages=options.max_pages,
            )
            artifacts.append(
                write_backup_artifact(
                    output_dir=output_dir,
                    domain="detection-rules",
                    operation_id="v1_unified_mitigations_with_relations_list",
                    source="openapi",
                    classification="needs-redaction",
                    records=detection_rules,
                )
            )

        for domain in domains:
            if domain in BUILTIN_CONFIG_BACKUP_DOMAINS:
                continue
            entry = catalog[domain]
            catalog_records = fetch_catalog_entry_for_backup(
                context,
                client,
                entry,
                page_size=options.page_size,
                max_pages=options.max_pages,
            )
            artifacts.append(
                write_backup_artifact(
                    output_dir=output_dir,
                    domain=entry.domain,
                    operation_id=entry.operation_id or f"endpoint-catalog:{entry.path}",
                    source="endpoint-catalog",
                    classification=entry.classification,
                    records=catalog_records,
                    sensitive_fields=entry.sensitive_fields,
                    fail_on_unclassified=True,
                )
            )

    manifest = {
        "backup_type": "configuration",
        "generated_at": generated_at,
        "cli_version": __version__,
        "command": options.command,
        "tenant_alias": options.tenant_alias,
        "domains_requested": list(domains),
        "artifacts": artifacts,
        "skipped_domains": skipped,
        "redaction_policy": {
            "status": "enabled",
            "raw_response_output": False,
            "redacted_value": REDACTED_VALUE,
        },
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    _restrict_file(manifest_path)
    return manifest


def prepare_backup_output_dir(output_dir: Path) -> Path:
    resolved = output_dir.expanduser().resolve()
    git_root = _find_git_root(Path.cwd())
    if git_root is not None and _is_relative_to(resolved, git_root):
        raise BackupError("Backup output directory must be outside the git worktree.")
    if resolved.exists() and any(resolved.iterdir()):
        raise BackupError("Backup output directory must be empty or not exist.")
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    with suppress(OSError):
        resolved.chmod(0o700)
    return resolved


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


def redact_backup_payload(payload: Any) -> tuple[Any, RedactionReport]:
    report = RedactionReport()
    return _redact_value(payload, path=(), report=report), report


def write_backup_artifact(
    *,
    output_dir: Path,
    domain: str,
    operation_id: str,
    source: str,
    classification: str,
    records: list[Any],
    sensitive_fields: tuple[str, ...] = (),
    fail_on_unclassified: bool = False,
) -> dict[str, Any]:
    artifact_payload = {
        "domain": domain,
        "operation_id": operation_id,
        "source": source,
        "classification": classification,
        "records": records,
    }
    redacted_payload, report = redact_backup_payload(artifact_payload)
    if fail_on_unclassified:
        _validate_catalog_redactions(
            domain=domain,
            classification=classification,
            report=report,
            sensitive_fields=sensitive_fields,
        )

    artifact_name = f"{_safe_artifact_name(domain)}.json"
    artifact_path = output_dir / artifact_name
    write_json(artifact_path, redacted_payload)
    _restrict_file(artifact_path)
    return {
        "domain": domain,
        "operation_id": operation_id,
        "source": source,
        "classification": classification,
        "artifact": artifact_name,
        "record_count": len(records),
        "redaction_status": "redacted" if report.redacted_count else "no-redactions-needed",
        "redacted_field_count": report.redacted_count,
        "redacted_paths": report.redacted_paths,
    }


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


def _validate_catalog_redactions(
    *,
    domain: str,
    classification: str,
    report: RedactionReport,
    sensitive_fields: tuple[str, ...],
) -> None:
    if classification == "backup-safe" and report.redacted_paths:
        raise BackupError(
            f"Endpoint catalog domain '{domain}' is backup-safe but sensitive fields were found."
        )
    if classification != "needs-redaction":
        return

    unclassified = [
        path
        for path in report.redacted_paths
        if not _redaction_path_is_classified(path, sensitive_fields)
    ]
    if unclassified:
        raise BackupError(
            f"Endpoint catalog domain '{domain}' returned unclassified sensitive fields: "
            f"{', '.join(unclassified)}."
        )


def _redaction_path_is_classified(path: str, sensitive_fields: tuple[str, ...]) -> bool:
    if "*" in sensitive_fields:
        return True
    normalized_path = re.sub(r"\[\d+\]", "[]", path)
    normalized_key = _normalize_key(path.rsplit(".", 1)[-1].replace("[]", ""))
    for sensitive_field in sensitive_fields:
        normalized_field = sensitive_field.strip()
        if not normalized_field:
            continue
        if normalized_field in (path, normalized_path):
            return True
        if _normalize_key(normalized_field) == normalized_key:
            return True
    return False


def _redact_value(value: Any, *, path: tuple[str, ...], report: RedactionReport) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            next_path = (*path, key_text)
            if _is_sensitive_key(key_text):
                report.redacted_paths.append(_format_path(next_path))
                redacted[key_text] = REDACTED_VALUE
                continue
            redacted[key_text] = _redact_value(item, path=next_path, report=report)
        return redacted
    if isinstance(value, list):
        return [
            _redact_value(item, path=(*path, f"[{index}]"), report=report)
            for index, item in enumerate(value)
        ]
    if isinstance(value, str) and _is_sensitive_string(value):
        report.redacted_paths.append(_format_path(path))
        return REDACTED_VALUE
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalize_key(key)
    if normalized in _SENSITIVE_CONTAINER_KEYS:
        return True
    if normalized in _SENSITIVE_KEY_TOKENS:
        return True
    parts = [part for part in normalized.split("_") if part]
    if any(part in {"token", "secret", "password", "credential", "credentials"} for part in parts):
        return True
    joined = "".join(parts)
    if joined in _SENSITIVE_KEY_TOKENS:
        return True
    key_pairs = {
        ("api", "key"),
        ("access", "key"),
        ("auth", "key"),
        ("client", "secret"),
        ("private", "key"),
        ("secret", "key"),
        ("signed", "url"),
    }
    return any(first in parts and second in parts for first, second in key_pairs)


def _is_sensitive_string(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if _SIGNED_URL_RE.search(stripped):
        return True
    if _AUTH_VALUE_RE.match(stripped):
        return True
    if _JWT_RE.match(stripped):
        return True
    return bool(_PEM_PRIVATE_RE.search(stripped))


def _normalize_key(key: str) -> str:
    return _KEY_SEPARATOR_RE.sub("_", key.strip().lower()).strip("_")


def _format_path(path: tuple[str, ...]) -> str:
    if not path:
        return "$"
    output = "$"
    for part in path:
        if part.startswith("["):
            output += part
        else:
            output += f".{part}"
    return output


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


def _safe_artifact_name(domain: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", domain.strip().lower()).strip("-")
    return cleaned or "backup-domain"


def _restrict_file(path: Path) -> None:
    with suppress(OSError):
        path.chmod(0o600)


def _find_git_root(start: Path) -> Path | None:
    current = start.expanduser().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
