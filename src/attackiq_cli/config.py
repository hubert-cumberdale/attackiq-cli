from __future__ import annotations

import json
import math
import os
import platform
import stat
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from urllib.parse import urlparse

CONFIG_FILENAME = "config.json"
ENV_CONFIG_DIR = "ATTACKIQ_CONFIG_DIR"
ENV_BASE_URL = "ATTACKIQ_BASE_URL"
ENV_ACCOUNT_TOKEN = "ATTACKIQ_ACCOUNT_TOKEN"
ENV_JWT = "ATTACKIQ_JWT"

VALID_SCHEMES = {"http", "https"}
TIMEOUT_MIN = 1.0
TIMEOUT_MAX = 120.0
LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


class ConfigError(ValueError):
    """Raised when configuration is invalid or cannot be loaded safely."""


@dataclass
class CliConfig:
    base_url: str | None = None
    account_token: str | None = None
    jwt: str | None = None
    verify_tls: bool = True
    timeout: float = 30.0
    log_json: bool = False
    log_level: str = "INFO"


def config_dir() -> Path:
    override = os.getenv(ENV_CONFIG_DIR)
    if override:
        return Path(override)
    if platform.system().lower().startswith("win"):
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "attackiq-cli"
    return Path.home() / ".config" / "attackiq-cli"


def config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


def load_config() -> CliConfig:
    path = config_path()
    if not path.exists():
        return CliConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a JSON object: {path}")
    normalized = _normalize_config_data(data)
    return CliConfig(**normalized)


def save_config(config: CliConfig) -> Path:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    _tighten_directory_permissions(directory)
    path = config_path()
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    _tighten_permissions(path)
    return path


def effective_base_url(config: CliConfig) -> str | None:
    raw = os.getenv(ENV_BASE_URL) or config.base_url
    if not raw:
        return None
    return normalize_base_url(raw)


def effective_account_token(config: CliConfig) -> str | None:
    return os.getenv(ENV_ACCOUNT_TOKEN) or config.account_token


def effective_jwt(config: CliConfig) -> str | None:
    return os.getenv(ENV_JWT) or config.jwt


def normalize_base_url(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ConfigError("Base URL cannot be empty.")
    parsed = urlparse(candidate)
    if parsed.scheme not in VALID_SCHEMES:
        raise ConfigError("Base URL must include http:// or https://.")
    if not parsed.netloc:
        raise ConfigError("Base URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ConfigError("Base URL must not embed credentials.")
    if parsed.query or parsed.fragment:
        raise ConfigError("Base URL must not include query strings or fragments.")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def validate_effective_config(config: CliConfig) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    base_url = os.getenv(ENV_BASE_URL) or config.base_url
    if not base_url:
        errors.append("Base URL is not set (ATTACKIQ_BASE_URL or config).")
    else:
        try:
            normalized = normalize_base_url(base_url)
            if normalized.startswith("http://"):
                warnings.append("Base URL uses http:// (TLS disabled).")
        except ConfigError as exc:
            errors.append(str(exc))

    if not effective_account_token(config) and not effective_jwt(config):
        warnings.append("No auth token configured (Account Token or JWT).")

    if not config.verify_tls:
        warnings.append("TLS verification is disabled in config.")

    return errors, warnings


def _normalize_config_data(data: dict) -> dict:
    allowed = {field.name for field in fields(CliConfig)}
    cleaned: dict = {}
    for key in allowed:
        if key not in data:
            continue
        cleaned[key] = data[key]

    cleaned["base_url"] = _clean_optional_str(cleaned.get("base_url"))
    if cleaned.get("base_url"):
        cleaned["base_url"] = normalize_base_url(cleaned["base_url"])
    cleaned["account_token"] = _clean_optional_str(cleaned.get("account_token"))
    cleaned["jwt"] = _clean_optional_str(cleaned.get("jwt"))

    verify_tls = cleaned.get("verify_tls", True)
    if not isinstance(verify_tls, bool):
        raise ConfigError("verify_tls must be true or false.")
    cleaned["verify_tls"] = verify_tls

    timeout = cleaned.get("timeout", 30.0)
    cleaned["timeout"] = validate_timeout(timeout)

    log_json = cleaned.get("log_json", False)
    if not isinstance(log_json, bool):
        raise ConfigError("log_json must be true or false.")
    cleaned["log_json"] = log_json

    log_level = cleaned.get("log_level", "INFO")
    if not isinstance(log_level, str):
        raise ConfigError("log_level must be a string.")
    log_level = log_level.strip().upper()
    if log_level not in LOG_LEVELS:
        raise ConfigError(f"log_level must be one of: {', '.join(sorted(LOG_LEVELS))}.")
    cleaned["log_level"] = log_level
    return cleaned


def _clean_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError("Expected string values in config.")
    stripped = value.strip()
    return stripped or None


def validate_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError("timeout must be a positive number of seconds.")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout < TIMEOUT_MIN or timeout > TIMEOUT_MAX:
        raise ConfigError(
            f"timeout must be between {TIMEOUT_MIN} and {TIMEOUT_MAX} seconds."
        )
    return timeout


def _tighten_directory_permissions(path: Path) -> None:
    try:
        path.chmod(stat.S_IRWXU)
    except (PermissionError, OSError):
        return


def _tighten_permissions(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except (PermissionError, OSError):
        # Best effort; continue without failing on platforms that block chmod.
        return
