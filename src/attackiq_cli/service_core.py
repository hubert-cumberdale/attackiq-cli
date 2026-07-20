from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from attackiq_cli.client import AttackIQClient, AuthContext, validate_auth_for_operation
from attackiq_cli.config import (
    CliConfig,
    ConfigError,
    effective_account_token,
    effective_base_url,
    effective_jwt,
    load_config,
    normalize_base_url,
    validate_timeout,
)
from attackiq_cli.logging_utils import setup_logging
from attackiq_cli.spec import Operation, SpecIndex


@dataclass
class ServiceContext:
    config: CliConfig
    base_url: str
    auth: AuthContext
    spec: SpecIndex


def load_service_context(
    spec_path: Path,
    *,
    preferred_scheme: str = "auto",
) -> ServiceContext:
    config = load_config()
    base_url = resolve_base_url(config, None)
    auth = build_auth_context(config, preferred_scheme=preferred_scheme)
    spec = SpecIndex.from_file(spec_path)
    return ServiceContext(config=config, base_url=base_url, auth=auth, spec=spec)


def resolve_base_url(config: CliConfig, override: str | None) -> str:
    if override:
        return normalize_base_url(override)
    base_url = effective_base_url(config)
    if not base_url:
        raise ConfigError("Base URL is not set (ATTACKIQ_BASE_URL or config).")
    return base_url


def build_auth_context(config: CliConfig, *, preferred_scheme: str = "auto") -> AuthContext:
    return AuthContext(
        account_token=effective_account_token(config),
        jwt=effective_jwt(config),
        preferred_scheme=preferred_scheme,
    )


def ensure_auth(operation: Operation, auth: AuthContext) -> list[str]:
    errors, warnings = validate_auth_for_operation(operation, auth)
    if errors:
        raise ValueError("\n".join(errors))
    return warnings


def build_client(
    base_url: str,
    config: CliConfig,
    auth: AuthContext,
    *,
    insecure: bool,
    timeout: float | None,
    logger=None,
) -> AttackIQClient:
    if timeout is not None:
        timeout = validate_timeout(timeout)
    logger = logger or setup_logging(config.log_level, config.log_json)
    return AttackIQClient(
        base_url=base_url,
        auth=auth,
        verify_tls=config.verify_tls and not insecure,
        timeout=timeout or config.timeout,
        logger=logger,
    )


def warn_if_insecure_base_url(base_url: str) -> bool:
    return base_url.startswith("http://")


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _normalize_filter(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_nested_text(value: Any, key: str) -> str | None:
    if not isinstance(value, dict):
        return None
    return _optional_text(value.get(key))
