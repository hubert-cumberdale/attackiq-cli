from __future__ import annotations

import typer.main
from typer.testing import CliRunner

import attackiq_cli.cli as cli


def test_cli_help_shows_completion_options() -> None:
    command = typer.main.get_command(cli.app)
    option_names = {
        option
        for parameter in command.params
        for option in getattr(parameter, "opts", [])
    }

    assert "--install-completion" in option_names
    assert "--show-completion" in option_names


def test_cli_show_completion_uses_shell_env() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.app, ["--show-completion"], env={"SHELL": "/bin/bash"})

    assert result.exit_code == 0
    assert "complete_bash" in result.output


def test_cli_show_completion_prefers_explicit_shell_env() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["--show-completion"],
        env={"ATTACKIQ_COMPLETION_SHELL": "zsh", "SHELL": "/bin/bash"},
    )

    assert result.exit_code == 0
    assert "complete_zsh" in result.output
