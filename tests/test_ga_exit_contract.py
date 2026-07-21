from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_platform_api as cli_platform_api
from attackiq_cli.config import (
    CONFIG_FILENAME,
    ENV_ACCOUNT_TOKEN,
    ENV_BASE_URL,
    ENV_CONFIG_DIR,
    ENV_JWT,
    CliConfig,
    save_config,
)
from attackiq_cli.spec import Operation

ROOT = Path(__file__).resolve().parents[1]
GA_CONTRACT_PATH = ROOT / "docs" / "GA_STABLE_CONTRACT.md"
LIVE_SMOKE_PATH = ROOT / "scripts" / "live_smoke.py"

_LIVE_SMOKE_SPEC = importlib.util.spec_from_file_location(
    "ga_exit_contract_live_smoke", LIVE_SMOKE_PATH
)
assert _LIVE_SMOKE_SPEC is not None
assert _LIVE_SMOKE_SPEC.loader is not None
live_smoke = importlib.util.module_from_spec(_LIVE_SMOKE_SPEC)
sys.modules[_LIVE_SMOKE_SPEC.name] = live_smoke
_LIVE_SMOKE_SPEC.loader.exec_module(live_smoke)


class _DummySpecIndex:
    def get_operation(self, operation_id: str) -> Operation:
        return Operation(
            operation_id=operation_id,
            method="get",
            path=f"/{operation_id}",
            summary="",
            parameters=[],
            request_body=None,
            tags=[],
            security=[],
        )


def _use_temporary_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path / "config"))
    for name in (ENV_ACCOUNT_TOKEN, ENV_BASE_URL, ENV_JWT):
        monkeypatch.delenv(name, raising=False)


def test_successful_local_invocation_returns_zero(tmp_path: Path, monkeypatch) -> None:
    _use_temporary_config(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["spec", "list", "--limit", "1"])

    assert result.exit_code == 0


def test_warning_only_config_validation_returns_zero(tmp_path: Path, monkeypatch) -> None:
    _use_temporary_config(tmp_path, monkeypatch)
    save_config(
        CliConfig(
            base_url="http://warning-only.example.test",
            verify_tls=False,
        )
    )

    result = CliRunner().invoke(cli.app, ["config", "validate"])

    assert result.exit_code == 0
    assert "Warnings:" in result.output
    assert "Config OK" in result.output
    assert "Errors:" not in result.output


def test_malformed_config_is_a_handled_failure_with_exit_one(tmp_path: Path, monkeypatch) -> None:
    _use_temporary_config(tmp_path, monkeypatch)
    config_path = tmp_path / "config" / CONFIG_FILENAME
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{malformed", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["config", "validate"])

    assert result.exit_code == 1
    assert "not valid JSON" in result.output
    assert "Traceback" not in result.output


def test_click_usage_validation_returns_two(tmp_path: Path, monkeypatch) -> None:
    _use_temporary_config(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["spec", "show"])

    assert result.exit_code == 2
    assert "Missing argument" in result.output


def test_experimental_parity_mismatch_deliberately_returns_two(
    tmp_path: Path, monkeypatch
) -> None:
    _use_temporary_config(tmp_path, monkeypatch)
    context = SimpleNamespace(auth=None, spec=_DummySpecIndex())
    monkeypatch.setattr(
        cli_platform_api,
        "_prepare_read_only_context",
        lambda *_args, **_kwargs: (context, None),
    )
    monkeypatch.setattr(cli_platform_api, "ensure_auth", lambda *_args, **_kwargs: [])

    def fake_list_scenarios(_context, *, api_backend, **_kwargs):
        if api_backend == "native":
            return [{"id": "native-record"}]
        return [{"id": "platform-record"}]

    monkeypatch.setattr(cli_platform_api, "svc_list_scenarios", fake_list_scenarios)

    result = CliRunner().invoke(
        cli.app,
        ["platform-api", "parity", "scenarios", "--fail-on-mismatch"],
    )

    assert result.exit_code == 2
    assert json.loads(result.output)["parity"] is False


def test_live_smoke_timeout_returns_124_and_redacts_sensitive_values(
    tmp_path: Path, capsys
) -> None:
    account_token = "placeholder-account-token"
    jwt = "placeholder-jwt-token"
    tenant_url = "https://tenant.example.test"
    env = {
        "ATTACKIQ_ACCOUNT_TOKEN": account_token,
        "ATTACKIQ_JWT": jwt,
        "ATTACKIQ_BASE_URL": tenant_url,
    }
    command = live_smoke.SmokeCommand(
        "simulated timeout",
        ["attackiq", "offline-placeholder"],
        category="offline-test",
    )

    def timeout_runner(argv, **kwargs):
        raise subprocess.TimeoutExpired(
            argv,
            kwargs["timeout"],
            output=f"stdout token={account_token} jwt={jwt}",
            stderr=f"stderr GET {tenant_url}/v1/records",
        )

    result = live_smoke.run_smoke(
        [command],
        output_dir=tmp_path,
        runner=timeout_runner,
        env=env,
    )

    captured = capsys.readouterr()
    assert result == 124
    assert "timed out" in captured.err
    assert account_token not in captured.err
    assert jwt not in captured.err
    assert "tenant.example.test" not in captured.err
    assert "<redacted-url>" in captured.err


def test_documented_stable_exit_inventory_is_exact_and_excludes_harness_values() -> None:
    contract = GA_CONTRACT_PATH.read_text(encoding="utf-8")
    exit_section = contract.split("## Exit Behavior Inventory", maxsplit=1)[1].split(
        "\n## ", maxsplit=1
    )[0]
    stable_exits = {
        int(match.group(1))
        for match in re.finditer(r"^\| `(\d+)` \|", exit_section, flags=re.MULTILINE)
    }

    assert stable_exits == {0, 1, 2}
    assert "Experimental parity mismatch" in exit_section
    assert "outside the stable contract" in exit_section
    assert "live-smoke harness additionally returns `124`" in exit_section
    assert 124 not in stable_exits
    assert "the experimental `attackiq platform-api parity` command" in contract

