from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from attackiq_cli.config import CliConfig

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "live_smoke.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("live_smoke", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
live_smoke = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = live_smoke
_SCRIPT_SPEC.loader.exec_module(live_smoke)


def test_build_commands_are_bounded_and_dry_run_by_default(tmp_path: Path):
    commands = live_smoke.build_commands(
        tmp_path,
        python="python",
        page_size=live_smoke.DEFAULT_PAGE_SIZE,
        timeout=20,
    )
    names = [command.name for command in commands]

    assert names == [
        "config validate",
        "spec list",
        "tags list",
        "scenarios list",
        "assets list",
        "assessments list",
        "tests list",
        "assessments create dry-run",
        "tests create dry-run",
        "tests add-scenarios dry-run",
        "assessments run dry-run",
    ]
    assert [command.category for command in commands] == [
        "configuration",
        "local-spec",
        "read-only",
        "read-only",
        "read-only",
        "read-only",
        "read-only",
        "fake-id-dry-run",
        "fake-id-dry-run",
        "fake-id-dry-run",
        "fake-id-dry-run",
    ]
    assert all("--apply" not in command.argv for command in commands)
    assert len(commands) == 11

    for command in commands[2:7]:
        assert command.argv[command.argv.index("--page") + 1] == "1"
        assert command.argv[command.argv.index("--page-size") + 1] == str(
            live_smoke.MAX_PAGE_SIZE
        )

    command_args = {command.name: command.argv for command in commands}
    assert live_smoke.FAKE_SCENARIO_ID in command_args["assessments create dry-run"]
    assert live_smoke.FAKE_ASSESSMENT_ID in command_args["tests create dry-run"]
    assert live_smoke.FAKE_TEST_ID in command_args["tests add-scenarios dry-run"]
    assert live_smoke.FAKE_SCENARIO_ID in command_args["tests add-scenarios dry-run"]
    assert live_smoke.FAKE_ASSESSMENT_ID in command_args["assessments run dry-run"]


def test_main_refuses_live_smoke_without_opt_in(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv(live_smoke.OPT_IN_ENV, raising=False)

    result = live_smoke.main(["--output-dir", str(tmp_path)])

    assert result == 2
    assert live_smoke.OPT_IN_ENV in capsys.readouterr().err


def test_dry_run_prints_plan_without_opt_in(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv(live_smoke.OPT_IN_ENV, raising=False)

    result = live_smoke.main(["--dry-run", "--output-dir", str(tmp_path)])

    assert result == 0
    output = capsys.readouterr().out
    assert "Planned live smoke commands" in output
    assert "--apply" not in output


def test_main_rejects_page_size_above_ga_bound(tmp_path: Path, capsys):
    result = live_smoke.main(
        [
            "--dry-run",
            "--page-size",
            str(live_smoke.MAX_PAGE_SIZE + 1),
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 2
    assert f"--page-size must be <= {live_smoke.MAX_PAGE_SIZE}" in capsys.readouterr().err


def test_main_refuses_live_smoke_when_tls_verification_is_disabled(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setenv(live_smoke.OPT_IN_ENV, "1")
    monkeypatch.delenv("ATTACKIQ_BASE_URL", raising=False)
    monkeypatch.setattr(
        live_smoke,
        "load_config",
        lambda: CliConfig(
            base_url="https://tenant.example.test",
            verify_tls=False,
        ),
    )
    monkeypatch.setattr(
        live_smoke,
        "run_smoke",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("commands were launched")),
    )

    result = live_smoke.main(["--output-dir", str(tmp_path)])

    assert result == 2
    error = capsys.readouterr().err
    assert "TLS verification is disabled" in error
    assert "tenant.example.test" not in error


def test_main_refuses_live_smoke_when_effective_base_url_is_not_https(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setenv(live_smoke.OPT_IN_ENV, "1")
    monkeypatch.setenv("ATTACKIQ_BASE_URL", "http://tenant.example.test")
    monkeypatch.setattr(
        live_smoke,
        "load_config",
        lambda: CliConfig(
            base_url="https://persisted.example.test",
            verify_tls=True,
        ),
    )
    monkeypatch.setattr(
        live_smoke,
        "run_smoke",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("commands were launched")),
    )

    result = live_smoke.main(["--output-dir", str(tmp_path)])

    assert result == 2
    error = capsys.readouterr().err
    assert "effective base URL does not use https://" in error
    assert "tenant.example.test" not in error


def test_main_runs_live_smoke_after_verified_tls_preflight(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(live_smoke.OPT_IN_ENV, "1")
    monkeypatch.delenv("ATTACKIQ_BASE_URL", raising=False)
    monkeypatch.setattr(
        live_smoke,
        "load_config",
        lambda: CliConfig(
            base_url="https://tenant.example.test",
            verify_tls=True,
        ),
    )
    launched: list[list[object]] = []

    def fake_run_smoke(commands, **_kwargs):
        launched.append(list(commands))
        return 0

    monkeypatch.setattr(live_smoke, "run_smoke", fake_run_smoke)

    result = live_smoke.main(["--output-dir", str(tmp_path)])

    assert result == 0
    assert len(launched) == 1
    assert len(launched[0]) == 11


def test_redact_text_masks_tokens_and_urls():
    env = {
        "ATTACKIQ_ACCOUNT_TOKEN": "acct-token-value",
        "ATTACKIQ_JWT": "jwt-value",
        "ATTACKIQ_BASE_URL": "https://tenant.example.test",
    }
    text = (
        "GET https://tenant.example.test/v1/assets "
        "Authorization: Bearer acct-token-value jwt=jwt-value"
    )

    redacted = live_smoke.redact_text(text, env=env)

    assert "acct-token-value" not in redacted
    assert "jwt-value" not in redacted
    assert "tenant.example.test" not in redacted
    assert "<redacted-url>" in redacted


def test_run_smoke_writes_summaries_without_raw_output(tmp_path: Path, capsys):
    env = {live_smoke.OPT_IN_ENV: "1", "ATTACKIQ_ACCOUNT_TOKEN": "secret-token"}
    commands = live_smoke.build_commands(tmp_path, python="python", page_size=5, timeout=20)
    seen: list[list[str]] = []

    def fake_runner(argv, cwd, env, capture_output, text, timeout, check):
        _ = (cwd, env, capture_output, text, timeout, check)
        argv = list(argv)
        seen.append(argv)
        if "--output" in argv:
            output = Path(argv[argv.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            if "list" in argv:
                output.write_text('[{"id": "one"}]\n', encoding="utf-8")
            else:
                output.write_text('{"operation_id": "planned_operation"}\n', encoding="utf-8")
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="raw stdout with secret-token",
            stderr="raw stderr with secret-token",
        )

    result = live_smoke.run_smoke(commands, output_dir=tmp_path, runner=fake_runner, env=env)

    output = capsys.readouterr().out
    assert result == 0
    assert len(seen) == len(commands)
    assert "PASS tags list: records=1" in output
    assert "PASS assessments run dry-run: operation_id=planned_operation" in output
    assert "secret-token" not in output


def test_run_smoke_redacts_failed_command_output(tmp_path: Path, capsys):
    env = {
        live_smoke.OPT_IN_ENV: "1",
        "ATTACKIQ_ACCOUNT_TOKEN": "secret-token",
        "ATTACKIQ_BASE_URL": "https://tenant.example.test",
    }
    command = live_smoke.SmokeCommand(
        "failing command", ["attackiq", "bad"], category="test"
    )

    def fake_runner(argv, cwd, env, capture_output, text, timeout, check):
        _ = (cwd, env, capture_output, text, timeout, check)
        argv = list(argv)
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout="stdout token=secret-token",
            stderr="stderr https://tenant.example.test/v1 Authorization: Bearer secret-token",
        )

    result = live_smoke.run_smoke([command], output_dir=tmp_path, runner=fake_runner, env=env)

    captured = capsys.readouterr()
    assert result == 1
    assert "FAIL failing command" in captured.err
    assert "secret-token" not in captured.err
    assert "tenant.example.test" not in captured.err
    assert "<redacted-url>" in captured.err


def test_run_smoke_redacts_timeout_output(tmp_path: Path, capsys):
    env = {
        live_smoke.OPT_IN_ENV: "1",
        "ATTACKIQ_ACCOUNT_TOKEN": "secret-token",
        "ATTACKIQ_BASE_URL": "https://tenant.example.test",
    }
    command = live_smoke.SmokeCommand(
        "timeout command", ["attackiq", "slow"], category="test"
    )

    def fake_runner(argv, cwd, env, capture_output, text, timeout, check):
        _ = (cwd, env, capture_output, text, check)
        raise subprocess.TimeoutExpired(
            argv,
            timeout,
            output="stdout token=secret-token",
            stderr="stderr https://tenant.example.test/v1",
        )

    result = live_smoke.run_smoke([command], output_dir=tmp_path, runner=fake_runner, env=env)

    captured = capsys.readouterr()
    assert result == 124
    assert "FAIL timeout command" in captured.err
    assert "secret-token" not in captured.err
    assert "tenant.example.test" not in captured.err


def test_run_smoke_fails_when_expected_output_is_missing(tmp_path: Path, capsys):
    command = live_smoke.SmokeCommand(
        "tags list",
        ["attackiq", "tags", "list"],
        category="test",
        output=tmp_path / "tags.json",
        expected_kind="records",
    )

    def fake_runner(argv, cwd, env, capture_output, text, timeout, check):
        _ = (cwd, env, capture_output, text, timeout, check)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    result = live_smoke.run_smoke(
        [command],
        output_dir=tmp_path,
        runner=fake_runner,
        env={live_smoke.OPT_IN_ENV: "1"},
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "expected output missing" in captured.err
