from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.config as config_module
import attackiq_cli.spec as spec_module
import attackiq_cli.tui_provider as tui_provider
from attackiq_cli.config import (
    ENV_ACCOUNT_TOKEN,
    ENV_BASE_URL,
    ENV_CONFIG_DIR,
    ENV_JWT,
    CliConfig,
    ConfigError,
    config_dir,
    effective_account_token,
    effective_base_url,
    effective_jwt,
)
from attackiq_cli.scenario_wizard_process import subprocess_env
from attackiq_cli.scenario_wizard_runtime import (
    ENV_SCENARIO_WIZARD_CACHE_DIR,
    scenario_wizard_cache_dir,
)

ROOT = Path(__file__).resolve().parents[1]
GA_CONTRACT_PATH = ROOT / "docs" / "GA_STABLE_CONTRACT.md"
PACKAGE_ROOT = ROOT / "src" / "attackiq_cli"

ENV_OPENAPI_PATH = "ATTACKIQ_OPENAPI_PATH"
ENV_COMPLETION_SHELL = "ATTACKIQ_COMPLETION_SHELL"

GA_ENVIRONMENT_VARIABLES = frozenset(
    {
        ENV_CONFIG_DIR,
        ENV_BASE_URL,
        ENV_ACCOUNT_TOKEN,
        ENV_JWT,
        ENV_OPENAPI_PATH,
        ENV_COMPLETION_SHELL,
        spec_module.ENV_SPEC_CACHE_DISABLED,
        spec_module.ENV_SPEC_CACHE_DIR,
        tui_provider.ENV_TUI_CACHE_MAX,
        tui_provider.ENV_TUI_CACHE_TTL,
        ENV_SCENARIO_WIZARD_CACHE_DIR,
    }
)

EXCLUDED_ENVIRONMENT_VARIABLES = frozenset(
    {
        "ATTACKIQ_LIVE_SMOKE",
        "GITLAB_BASE_URL",
        "GITLAB_TOKEN",
        "AIQ_SCENARIO_WIZARD_OUTPUT_DIR",
    }
)


def _documented_environment_variables() -> frozenset[str]:
    document = GA_CONTRACT_PATH.read_text(encoding="utf-8")
    section = document.split("## Environment Variable Inventory", maxsplit=1)[1]
    section = section.split("\n## ", maxsplit=1)[0]
    return frozenset(re.findall(r"\| `(ATTACKIQ_[A-Z0-9_]+)` \|", section))


def _installed_package_attackiq_variables() -> frozenset[str]:
    references: set[str] = set()
    for path in PACKAGE_ROOT.rglob("*.py"):
        references.update(re.findall(r"\bATTACKIQ_[A-Z0-9_]+\b", path.read_text(encoding="utf-8")))
    return frozenset(references)


def _write_spec(path: Path, operation_id: str) -> None:
    path.write_text(
        "openapi: 3.0.0\n"
        "paths:\n"
        "  /items:\n"
        "    get:\n"
        f"      operationId: {operation_id}\n",
        encoding="utf-8",
    )


def test_ga_environment_inventory_matches_documentation_and_installed_package():
    assert _documented_environment_variables() == GA_ENVIRONMENT_VARIABLES
    assert _installed_package_attackiq_variables() == GA_ENVIRONMENT_VARIABLES


def test_harness_and_apply_only_environment_inputs_remain_excluded(monkeypatch):
    all_excluded_inputs = GA_ENVIRONMENT_VARIABLES | EXCLUDED_ENVIRONMENT_VARIABLES
    for name in all_excluded_inputs:
        monkeypatch.setenv(name, "environment-placeholder")

    assert _documented_environment_variables().isdisjoint(EXCLUDED_ENVIRONMENT_VARIABLES)
    assert set(subprocess_env()).isdisjoint(all_excluded_inputs)


def test_config_directory_environment_override_and_empty_fallback(tmp_path, monkeypatch):
    override = tmp_path / "config-override"
    monkeypatch.setenv(ENV_CONFIG_DIR, str(override))

    assert config_dir() == override

    monkeypatch.setenv(ENV_CONFIG_DIR, "")
    monkeypatch.setattr(config_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(config_module.Path, "home", classmethod(lambda _cls: tmp_path))

    assert config_dir() == tmp_path / ".config" / "attackiq-cli"


def test_base_url_and_auth_environment_precedence_and_empty_fallback(monkeypatch):
    config = CliConfig(
        base_url="https://persisted.example/api",
        account_token="persisted-account-placeholder",
        jwt="persisted-jwt-placeholder",
    )
    monkeypatch.setenv(ENV_BASE_URL, "  https://environment.example/v1/  ")
    monkeypatch.setenv(ENV_ACCOUNT_TOKEN, "environment-account-placeholder")
    monkeypatch.setenv(ENV_JWT, "environment-jwt-placeholder")

    assert effective_base_url(config) == "https://environment.example/v1"
    assert effective_account_token(config) == "environment-account-placeholder"
    assert effective_jwt(config) == "environment-jwt-placeholder"

    monkeypatch.setenv(ENV_BASE_URL, "")
    monkeypatch.setenv(ENV_ACCOUNT_TOKEN, "")
    monkeypatch.setenv(ENV_JWT, "")

    assert effective_base_url(config) == "https://persisted.example/api"
    assert effective_account_token(config) == "persisted-account-placeholder"
    assert effective_jwt(config) == "persisted-jwt-placeholder"


def test_invalid_environment_base_url_fails_closed(monkeypatch):
    monkeypatch.setenv(ENV_BASE_URL, "file:///tmp/provider")

    with pytest.raises(ConfigError, match="http:// or https://"):
        effective_base_url(CliConfig(base_url="https://persisted.example/api"))


def test_openapi_path_environment_override_loads_local_spec(tmp_path):
    environment_spec = tmp_path / "environment.yaml"
    _write_spec(environment_spec, "from_environment")

    result = CliRunner().invoke(
        cli.app,
        ["spec", "list"],
        env={
            ENV_OPENAPI_PATH: str(environment_spec),
            spec_module.ENV_SPEC_CACHE_DISABLED: "1",
        },
    )

    assert result.exit_code == 0
    assert "from_environment" in result.output


def test_openapi_cli_option_takes_precedence_over_environment(tmp_path):
    environment_spec = tmp_path / "environment.yaml"
    option_spec = tmp_path / "option.yaml"
    _write_spec(environment_spec, "from_environment")
    _write_spec(option_spec, "from_option")

    result = CliRunner().invoke(
        cli.app,
        ["--spec-path", str(option_spec), "spec", "list"],
        env={
            ENV_OPENAPI_PATH: str(environment_spec),
            spec_module.ENV_SPEC_CACHE_DISABLED: "1",
        },
    )

    assert result.exit_code == 0
    assert "from_option" in result.output
    assert "from_environment" not in result.output


def test_openapi_path_environment_rejects_missing_path(tmp_path):
    result = CliRunner().invoke(
        cli.app,
        ["spec", "list"],
        env={ENV_OPENAPI_PATH: str(tmp_path / "missing.yaml")},
    )

    assert result.exit_code == 2
    assert "does not exist" in result.output


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("bash", "bash"),
        ("/bin/ZSH", "zsh"),
        ("fish", "fish"),
        ("powershell.exe", "powershell"),
        ("pwsh.exe", "pwsh"),
    ],
)
def test_completion_shell_environment_accepts_supported_aliases(monkeypatch, value, expected):
    monkeypatch.setenv(ENV_COMPLETION_SHELL, value)
    monkeypatch.setenv("SHELL", "/bin/bash")

    assert cli._completion_shell_from_env() == expected


def test_completion_shell_environment_invalid_and_empty_behavior(monkeypatch):
    monkeypatch.setenv(ENV_COMPLETION_SHELL, "unsupported")
    monkeypatch.setenv("SHELL", "/bin/bash")

    assert cli._completion_shell_from_env() is None

    monkeypatch.setenv(ENV_COMPLETION_SHELL, "")

    assert cli._completion_shell_from_env() == "bash"


@pytest.mark.parametrize("value", ["1", " true ", "YES", "On"])
def test_spec_cache_disable_environment_accepts_exact_truthy_values(monkeypatch, value):
    monkeypatch.setenv(spec_module.ENV_SPEC_CACHE_DISABLED, value)

    assert spec_module._cache_enabled() is False


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "2", "invalid"])
def test_spec_cache_disable_environment_ignores_other_values(monkeypatch, value):
    monkeypatch.setenv(spec_module.ENV_SPEC_CACHE_DISABLED, value)

    assert spec_module._cache_enabled() is True


def test_spec_cache_directory_environment_override_and_empty_fallback(tmp_path, monkeypatch):
    override = tmp_path / "spec-cache"
    config_override = tmp_path / "config"
    monkeypatch.setenv(spec_module.ENV_SPEC_CACHE_DIR, str(override))

    assert spec_module._cache_directory() == override

    monkeypatch.setenv(spec_module.ENV_SPEC_CACHE_DIR, "")
    monkeypatch.setenv(ENV_CONFIG_DIR, str(config_override))

    assert spec_module._cache_directory() == config_override / spec_module.SPEC_CACHE_DIRNAME


@pytest.mark.parametrize(("value", "expected"), [("1", 1), (" 64 ", 64), ("+3", 3)])
def test_tui_cache_max_environment_accepts_positive_integers(monkeypatch, value, expected):
    monkeypatch.setenv(tui_provider.ENV_TUI_CACHE_MAX, value)

    assert tui_provider._resolve_tui_cache_max_entries() == expected


@pytest.mark.parametrize("value", ["", "0", "-1", "1.5", "1e3", "invalid"])
def test_tui_cache_max_environment_uses_default_for_invalid_values(monkeypatch, value):
    monkeypatch.setenv(tui_provider.ENV_TUI_CACHE_MAX, value)

    assert tui_provider._resolve_tui_cache_max_entries() == tui_provider.DEFAULT_TUI_CACHE_MAX


@pytest.mark.parametrize(("value", "expected"), [("0.1", 0.1), (" 30 ", 30.0)])
def test_tui_cache_ttl_environment_accepts_positive_finite_numbers(monkeypatch, value, expected):
    monkeypatch.setenv(tui_provider.ENV_TUI_CACHE_TTL, value)

    assert tui_provider._resolve_tui_cache_ttl_seconds() == expected


@pytest.mark.parametrize(
    "value",
    ["", "0", "-1", "nan", "inf", "-inf", "infinity", "invalid"],
)
def test_tui_cache_ttl_environment_disables_invalid_values(monkeypatch, value):
    monkeypatch.setenv(tui_provider.ENV_TUI_CACHE_TTL, value)

    assert tui_provider._resolve_tui_cache_ttl_seconds() is None


def test_scenario_wizard_cache_directory_environment_override_and_empty_fallback(
    tmp_path, monkeypatch
):
    override = tmp_path / "scenario-wizard-cache"
    monkeypatch.setenv(ENV_SCENARIO_WIZARD_CACHE_DIR, str(override))

    assert scenario_wizard_cache_dir() == override

    monkeypatch.setenv(ENV_SCENARIO_WIZARD_CACHE_DIR, "")
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    assert scenario_wizard_cache_dir() == tmp_path / ".cache" / "attackiq-cli" / "scenario-wizard"
