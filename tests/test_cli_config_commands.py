from __future__ import annotations

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import load_config


def test_config_and_auth_commands_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATTACKIQ_CONFIG_DIR", str(tmp_path / "config"))
    runner = CliRunner()

    set_result = runner.invoke(
        cli.app,
        [
            "config",
            "set",
            "--base-url",
            "https://tenant.example/api/",
            "--timeout",
            "12",
            "--no-verify-tls",
            "--log-json",
            "--log-level",
            "debug",
        ],
    )

    assert set_result.exit_code == 0
    assert "Config saved to" in set_result.output
    cfg = load_config()
    assert cfg.base_url == "https://tenant.example/api"
    assert cfg.timeout == 12.0
    assert cfg.verify_tls is False
    assert cfg.log_json is True
    assert cfg.log_level == "DEBUG"

    validate_result = runner.invoke(cli.app, ["config", "validate"])

    assert validate_result.exit_code == 0
    assert "TLS verification is disabled in config." in validate_result.output
    assert "No auth token configured" in validate_result.output
    assert "Config OK" in validate_result.output

    auth_result = runner.invoke(
        cli.app,
        ["auth", "set", "--account-token", "abcdef", "--jwt", "header.payload"],
    )

    assert auth_result.exit_code == 0
    assert "Credentials stored at" in auth_result.output

    show_result = runner.invoke(cli.app, ["config", "show"])

    assert show_result.exit_code == 0
    assert "https://tenant.example/api" in show_result.output
    assert "abcdef" not in show_result.output
    assert "header.payload" not in show_result.output
    assert "ab***ef" in show_result.output
    assert "he***ad" in show_result.output

    clear_result = runner.invoke(cli.app, ["auth", "clear"])

    assert clear_result.exit_code == 0
    assert "Credentials cleared from config." in clear_result.output
    cleared = load_config()
    assert cleared.account_token is None
    assert cleared.jwt is None


def test_config_set_rejects_conflicting_tls_flags(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    monkeypatch.setenv("ATTACKIQ_CONFIG_DIR", str(config_dir))
    runner = CliRunner()

    result = runner.invoke(cli.app, ["config", "set", "--verify-tls", "--no-verify-tls"])

    assert result.exit_code == 2
    assert not (config_dir / "config.json").exists()


def test_auth_set_requires_a_token_value(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    monkeypatch.setenv("ATTACKIQ_CONFIG_DIR", str(config_dir))
    runner = CliRunner()

    result = runner.invoke(cli.app, ["auth", "set"])

    assert result.exit_code == 2
    assert not (config_dir / "config.json").exists()
