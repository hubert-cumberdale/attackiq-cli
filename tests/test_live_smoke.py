from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "live_smoke.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("live_smoke", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
live_smoke = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = live_smoke
_SCRIPT_SPEC.loader.exec_module(live_smoke)


def test_build_commands_are_bounded_and_dry_run_by_default(tmp_path: Path):
    commands = live_smoke.build_commands(tmp_path, python="python", page_size=5, timeout=20)
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
    assert all("--apply" not in command.argv for command in commands)
    assert commands[2].argv[-2:] == ["--output", str(tmp_path / "tags.json")]
    assert commands[2].argv[commands[2].argv.index("--page-size") + 1] == "5"


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
    command = live_smoke.SmokeCommand("failing command", ["attackiq", "bad"])

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
    command = live_smoke.SmokeCommand("timeout command", ["attackiq", "slow"])

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
