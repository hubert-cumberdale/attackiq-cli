from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from attackiq_cli import __version__
from attackiq_cli.backup_artifacts import (
    REDACTED_VALUE,
    RedactionReport,
    redact_backup_payload,
    restrict_file_permissions,
    write_backup_artifact,
)
from attackiq_cli.backup_catalog import (
    BUILTIN_CONFIG_BACKUP_DOMAINS,
    DEFAULT_CONFIG_BACKUP_DOMAINS,
    BackupError,
    EndpointCatalogEntry,
    load_endpoint_catalog,
    validate_endpoint_catalog,
    validate_requested_domains,
)
from attackiq_cli.backup_fetchers import (
    SourceTypeRequest,
    build_source_type_requests,
    fetch_catalog_entry_for_backup,
    fetch_detection_rules_for_backup,
    fetch_integrations_for_backup,
    fetch_paginated_records,
    fetch_source_types_for_backup,
)
from attackiq_cli.exporter import write_json
from attackiq_cli.services import ServiceContext, build_client

__all__ = [
    "BackupError",
    "EndpointCatalogEntry",
    "REDACTED_VALUE",
    "RedactionReport",
    "SourceTypeRequest",
    "build_source_type_requests",
    "fetch_catalog_entry_for_backup",
    "fetch_detection_rules_for_backup",
    "fetch_integrations_for_backup",
    "fetch_paginated_records",
    "fetch_source_types_for_backup",
    "load_endpoint_catalog",
    "redact_backup_payload",
    "validate_endpoint_catalog",
    "write_backup_artifact",
]


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
    restrict_file_permissions(manifest_path)
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
