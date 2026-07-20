from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from attackiq_cli.config import ENV_ACCOUNT_TOKEN, ENV_BASE_URL, ENV_JWT, config_dir
from attackiq_cli.services import ServiceContext
from attackiq_cli.spec import ENV_SPEC_CACHE_DIR, ENV_SPEC_CACHE_DISABLED, SPEC_CACHE_DIRNAME


@dataclass
class TuiState:
    authenticated: bool
    base_url: str
    base_url_source: str
    auth_mode: str
    auth_source: str
    spec_cache_status: str
    spec_cache_dir: str
    spec_cache_dir_source: str
    spec_load_source: str
    env_display: str
    workspace_display: str
    workspace_full: str


def build_tui_state(context: ServiceContext, *, workspace_full: str) -> TuiState:
    authenticated = bool(context.auth.account_token or context.auth.jwt)
    base_url_source = _resolve_base_url_source(context.config)
    auth_mode = _resolve_auth_mode(context.auth)
    auth_source = _resolve_auth_source(context.config, auth_mode)
    spec_cache_status = "disabled" if _is_spec_cache_disabled() else "enabled"
    spec_cache_dir = _resolve_spec_cache_dir()
    spec_cache_dir_source = "env" if _has_env_value(ENV_SPEC_CACHE_DIR) else "default"
    spec_load_source = _resolve_spec_load_source(context.spec)
    return TuiState(
        authenticated=authenticated,
        base_url=context.base_url,
        base_url_source=base_url_source,
        auth_mode=auth_mode,
        auth_source=auth_source,
        spec_cache_status=spec_cache_status,
        spec_cache_dir=spec_cache_dir,
        spec_cache_dir_source=spec_cache_dir_source,
        spec_load_source=spec_load_source,
        env_display=_format_env_display(context.base_url),
        workspace_display=_shorten_path(workspace_full),
        workspace_full=workspace_full,
    )


def _shorten_path(value: str) -> str:
    path = Path(value)
    if not path.parts:
        return value
    return path.name or value


def _format_env_display(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc or base_url
    label = _infer_env_label(host)
    return f"{host} ({label})"


def _infer_env_label(host: str) -> str:
    lowered = host.lower()
    if "staging" in lowered:
        return "staging"
    if "dev" in lowered:
        return "dev"
    if "prod" in lowered or "production" in lowered:
        return "prod"
    return "custom"


def _has_env_value(name: str) -> bool:
    value = os.getenv(name)
    return isinstance(value, str) and bool(value.strip())


def _is_spec_cache_disabled() -> bool:
    raw = os.getenv(ENV_SPEC_CACHE_DISABLED, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _resolve_spec_cache_dir() -> str:
    override = os.getenv(ENV_SPEC_CACHE_DIR)
    if isinstance(override, str) and override.strip():
        return str(Path(override).expanduser())
    return str(config_dir() / SPEC_CACHE_DIRNAME)


def _resolve_spec_load_source(spec: Any) -> str:
    source = getattr(spec, "load_source", None)
    if isinstance(source, str) and source.strip():
        return source
    return "unknown"


def _resolve_base_url_source(config: Any) -> str:
    if _has_env_value(ENV_BASE_URL):
        return "env"
    configured = getattr(config, "base_url", None)
    if isinstance(configured, str) and configured.strip():
        return "config"
    return "unset"


def _resolve_auth_mode(auth: Any) -> str:
    preferred = getattr(auth, "preferred_scheme", "auto")
    if preferred in {"account-token", "jwt", "none"}:
        return preferred
    if getattr(auth, "account_token", None):
        return "account-token"
    if getattr(auth, "jwt", None):
        return "jwt"
    return "none"


def _resolve_auth_source(config: Any, auth_mode: str) -> str:
    if auth_mode == "account-token":
        if _has_env_value(ENV_ACCOUNT_TOKEN):
            return "env"
        configured = getattr(config, "account_token", None)
        if isinstance(configured, str) and configured.strip():
            return "config"
    if auth_mode == "jwt":
        if _has_env_value(ENV_JWT):
            return "env"
        configured = getattr(config, "jwt", None)
        if isinstance(configured, str) and configured.strip():
            return "config"
    return "unset"
