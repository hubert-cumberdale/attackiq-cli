import json

import pytest

from attackiq_cli.config import (
    ENV_CONFIG_DIR,
    TIMEOUT_MAX,
    TIMEOUT_MIN,
    CliConfig,
    ConfigError,
    load_config,
    normalize_base_url,
    save_config,
    validate_effective_config,
)


def test_normalize_base_url_accepts_https_and_strips_trailing_slash():
    assert normalize_base_url("https://example.com/api/") == "https://example.com/api"


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("example.com", "http:// or https://"),
        ("ftp://example.com", "http:// or https://"),
        ("https://user:pass@example.com", "must not embed credentials"),
        ("https://example.com?query=1", "must not include query strings"),
        ("https://example.com#frag", "must not include query strings"),
    ],
)
def test_normalize_base_url_rejects_invalid_values(value, message):
    with pytest.raises(ConfigError) as exc:
        normalize_base_url(value)
    assert message in str(exc.value)


def test_load_config_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path))
    (tmp_path / "config.json").write_text("{not-json}")
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_invalid_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"timeout": -1}))
    with pytest.raises(ConfigError):
        load_config()


@pytest.mark.parametrize("value", [TIMEOUT_MIN - 0.1, TIMEOUT_MAX + 1])
def test_load_config_timeout_out_of_range(tmp_path, monkeypatch, value):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"timeout": value}))
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_invalid_log_level(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"log_level": "invalid"}))
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path))
    config = CliConfig(base_url="https://example.com/api", timeout=15.0, log_json=True)
    save_config(config)
    loaded = load_config()
    assert loaded.base_url == "https://example.com/api"
    assert loaded.timeout == 15.0
    assert loaded.log_json is True


def test_validate_effective_config_missing_base_url():
    errors, warnings = validate_effective_config(CliConfig())
    assert errors
    assert "Base URL is not set" in errors[0]
    assert any("No auth token configured" in warning for warning in warnings)


def test_validate_effective_config_http_warning():
    config = CliConfig(base_url="http://example.com")
    errors, warnings = validate_effective_config(config)
    assert not errors
    assert any("http://" in warning for warning in warnings)
