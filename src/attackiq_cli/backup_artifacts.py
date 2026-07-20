from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from attackiq_cli.backup_catalog import BackupError
from attackiq_cli.exporter import write_json

REDACTED_VALUE = "[REDACTED]"

__all__ = [
    "REDACTED_VALUE",
    "RedactionReport",
    "redact_backup_payload",
    "restrict_file_permissions",
    "write_backup_artifact",
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


@dataclass
class RedactionReport:
    redacted_paths: list[str] = field(default_factory=list)

    @property
    def redacted_count(self) -> int:
        return len(self.redacted_paths)


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
    restrict_file_permissions(artifact_path)
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


def restrict_file_permissions(path: Path) -> None:
    with suppress(OSError):
        path.chmod(0o600)


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


def _safe_artifact_name(domain: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", domain.strip().lower()).strip("-")
    return cleaned or "backup-domain"
