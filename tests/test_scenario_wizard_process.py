from __future__ import annotations

import os

from attackiq_cli.scenario_wizard_process import safe_process_output, subprocess_env


def test_safe_process_output_redacts_credentials() -> None:
    output = (
        "Authorization: Bearer raw-token\n"
        "password=do-not-leak\n"
        "https://user:secret@example.invalid/simple\n"
    )

    redacted = safe_process_output(output)

    assert "raw-token" not in redacted
    assert "do-not-leak" not in redacted
    assert "user:secret" not in redacted
    assert "Authorization: ***" in redacted
    assert "password=***" in redacted
    assert "://***:***@" in redacted


def test_subprocess_env_does_not_inherit_package_credentials(monkeypatch) -> None:
    monkeypatch.setenv("ATTACKIQ_ACCOUNT_TOKEN", "do-not-leak")
    monkeypatch.setenv("PIP_INDEX_URL", "https://user:password@example.invalid/simple")
    monkeypatch.setenv("PATH", os.defpath)

    env = subprocess_env()

    assert "ATTACKIQ_ACCOUNT_TOKEN" not in env
    assert "PIP_INDEX_URL" not in env
    assert env["PIP_CONFIG_FILE"] == os.devnull
    assert env["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
    assert env["PIP_NO_INPUT"] == "1"
    assert env["PIP_NO_CACHE_DIR"] == "1"
    assert env["PYTHONNOUSERSITE"] == "1"
