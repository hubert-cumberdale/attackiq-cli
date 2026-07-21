from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict
from pathlib import Path

import pytest
from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.cli_config import mask_secret
from attackiq_cli.config import (
    CONFIG_FILENAME,
    ENV_ACCOUNT_TOKEN,
    ENV_BASE_URL,
    ENV_CONFIG_DIR,
    ENV_JWT,
    LOG_LEVELS,
    TIMEOUT_MAX,
    TIMEOUT_MIN,
    CliConfig,
    ConfigError,
    effective_account_token,
    effective_base_url,
    effective_jwt,
    load_config,
    normalize_base_url,
    save_config,
)

PERSISTED_DEFAULTS = {
    "base_url": None,
    "account_token": None,
    "jwt": None,
    "verify_tls": True,
    "timeout": 30.0,
    "log_json": False,
    "log_level": "INFO",
}


def _write_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object) -> Path:
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path))
    path = tmp_path / CONFIG_FILENAME
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_missing_file_loads_exact_persisted_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path))

    loaded = load_config()

    assert asdict(loaded) == PERSISTED_DEFAULTS


def test_save_writes_exact_persisted_keys_and_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path / "config"))

    path = save_config(CliConfig())

    assert json.loads(path.read_text(encoding="utf-8")) == PERSISTED_DEFAULTS


def test_load_ignores_unknown_keys(tmp_path, monkeypatch):
    _write_config(
        tmp_path,
        monkeypatch,
        {"timeout": 12, "future_setting": "ignored", "nested": {"also": "ignored"}},
    )

    loaded = load_config()

    assert loaded.timeout == 12.0
    assert asdict(loaded).keys() == PERSISTED_DEFAULTS.keys()


def test_load_rejects_malformed_json(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path))
    (tmp_path / CONFIG_FILENAME).write_text("{not-json}", encoding="utf-8")

    with pytest.raises(ConfigError, match="not valid JSON"):
        load_config()


@pytest.mark.parametrize("value", [None, [], "text", 1, True])
def test_load_rejects_non_object_json(tmp_path, monkeypatch, value):
    _write_config(tmp_path, monkeypatch, value)

    with pytest.raises(ConfigError, match="must contain a JSON object"):
        load_config()


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("base_url", 7, "Expected string values in config"),
        ("account_token", False, "Expected string values in config"),
        ("jwt", [], "Expected string values in config"),
        ("verify_tls", 1, "verify_tls must be true or false"),
        ("timeout", "30", "timeout must be a positive number"),
        ("log_json", 0, "log_json must be true or false"),
        ("log_level", 10, "log_level must be a string"),
    ],
)
def test_load_enforces_persisted_value_types(tmp_path, monkeypatch, key, value, message):
    _write_config(tmp_path, monkeypatch, {key: value})

    with pytest.raises(ConfigError, match=message):
        load_config()


def test_load_trims_strings_and_normalizes_log_level(tmp_path, monkeypatch):
    _write_config(
        tmp_path,
        monkeypatch,
        {
            "base_url": "  https://example.com/api/  ",
            "account_token": "  account credential  ",
            "jwt": "  jwt credential  ",
            "log_level": "  debug  ",
        },
    )

    loaded = load_config()

    assert loaded.base_url == "https://example.com/api"
    assert loaded.account_token == "account credential"
    assert loaded.jwt == "jwt credential"
    assert loaded.log_level == "DEBUG"


def test_load_normalizes_empty_optional_strings_to_none(tmp_path, monkeypatch):
    _write_config(
        tmp_path,
        monkeypatch,
        {"base_url": " \t", "account_token": "\n", "jwt": "  "},
    )

    loaded = load_config()

    assert loaded.base_url is None
    assert loaded.account_token is None
    assert loaded.jwt is None


def test_load_accepts_both_boolean_setting_values(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, {"verify_tls": False, "log_json": True})

    loaded = load_config()

    assert loaded.verify_tls is False
    assert loaded.log_json is True


@pytest.mark.parametrize("value", ["critical", " ERROR ", "warning", "Info", "DEBUG"])
def test_log_level_contract_accepts_exact_allowed_values(tmp_path, monkeypatch, value):
    _write_config(tmp_path, monkeypatch, {"log_level": value})

    loaded = load_config()

    assert loaded.log_level == value.strip().upper()
    assert loaded.log_level in LOG_LEVELS


@pytest.mark.parametrize("value", ["", "TRACE", "INFO DEBUG"])
def test_log_level_contract_rejects_values_outside_allowlist(tmp_path, monkeypatch, value):
    _write_config(tmp_path, monkeypatch, {"log_level": value})

    with pytest.raises(ConfigError, match="log_level must be one of"):
        load_config()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://example.com/", "http://example.com"),
        ("https://example.com/api///", "https://example.com/api"),
        ("  https://example.com:8443/api/  ", "https://example.com:8443/api"),
    ],
)
def test_base_url_contract_accepts_and_normalizes_http_and_https(value, expected):
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "cannot be empty"),
        ("example.com", "must include http:// or https://"),
        ("ftp://example.com", "must include http:// or https://"),
        ("https:///api", "must include a hostname"),
        ("https://user@example.com", "must not embed credentials"),
        ("https://user:password@example.com", "must not embed credentials"),
        ("https://example.com/api?mode=test", "must not include query strings or fragments"),
        ("https://example.com/api#section", "must not include query strings or fragments"),
    ],
)
def test_base_url_contract_rejects_invalid_values(value, message):
    with pytest.raises(ConfigError, match=message):
        normalize_base_url(value)


@pytest.mark.parametrize("value", [TIMEOUT_MIN, TIMEOUT_MAX, 30])
def test_timeout_contract_accepts_inclusive_bounds(tmp_path, monkeypatch, value):
    _write_config(tmp_path, monkeypatch, {"timeout": value})

    assert load_config().timeout == float(value)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (True, "timeout must be a positive number"),
        (False, "timeout must be a positive number"),
        ("30", "timeout must be a positive number"),
        (float("nan"), "timeout must be between"),
        (float("inf"), "timeout must be between"),
        (float("-inf"), "timeout must be between"),
        (TIMEOUT_MIN - 0.01, "timeout must be between"),
        (TIMEOUT_MAX + 0.01, "timeout must be between"),
    ],
)
def test_timeout_contract_rejects_invalid_values(tmp_path, monkeypatch, value, message):
    _write_config(tmp_path, monkeypatch, {"timeout": value})

    with pytest.raises(ConfigError, match=message):
        load_config()


def test_environment_credentials_and_base_url_override_persisted_values(monkeypatch):
    config = CliConfig(
        base_url="https://persisted.example/api",
        account_token="persisted account credential",
        jwt="persisted jwt credential",
    )
    monkeypatch.setenv(ENV_BASE_URL, "  https://environment.example/v1/  ")
    monkeypatch.setenv(ENV_ACCOUNT_TOKEN, "environment account credential")
    monkeypatch.setenv(ENV_JWT, "environment jwt credential")

    assert effective_base_url(config) == "https://environment.example/v1"
    assert effective_account_token(config) == "environment account credential"
    assert effective_jwt(config) == "environment jwt credential"


@pytest.mark.parametrize(
    ("secret", "masked"),
    [(None, ""), ("", ""), ("abcd", "***"), ("abcdef", "ab***ef")],
)
def test_secret_mask_contract(secret, masked):
    assert mask_secret(secret) == masked


def test_config_show_masks_complete_persisted_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path / "config"))
    account_token = "persisted-account-placeholder"
    jwt = "persisted-jwt-placeholder"
    save_config(CliConfig(account_token=account_token, jwt=jwt))

    result = CliRunner().invoke(cli.app, ["config", "show"])

    assert result.exit_code == 0
    assert account_token not in result.output
    assert jwt not in result.output
    assert mask_secret(account_token) in result.output
    assert mask_secret(jwt) in result.output


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits are not portable")
def test_save_config_sets_final_posix_directory_and_file_modes(tmp_path, monkeypatch):
    directory = tmp_path / "config"
    directory.mkdir(mode=0o777)
    path = directory / CONFIG_FILENAME
    path.write_text("{}", encoding="utf-8")
    directory.chmod(0o777)
    path.chmod(0o666)
    monkeypatch.setenv(ENV_CONFIG_DIR, str(directory))

    saved_path = save_config(CliConfig())

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(saved_path.stat().st_mode) == 0o600


def test_save_config_permission_hardening_is_best_effort(tmp_path, monkeypatch):
    directory = tmp_path / "config"
    monkeypatch.setenv(ENV_CONFIG_DIR, str(directory))

    def unsupported_chmod(_path: Path, _mode: int) -> None:
        raise OSError("chmod unsupported")

    monkeypatch.setattr(Path, "chmod", unsupported_chmod)

    path = save_config(CliConfig())

    assert path.exists()
    assert load_config() == CliConfig()
