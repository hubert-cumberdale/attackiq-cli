from __future__ import annotations

from typer.testing import CliRunner

from attackiq_cli import cli
from attackiq_cli import tui as tui_module


def test_cli_tui_forwards_filters(monkeypatch):
    captured = {}

    def _run_tui(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(tui_module, "run_tui", _run_tui)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tui", "--search", "alpha", "--tag", "beta"])

    assert result.exit_code == 0
    assert captured["search"] == "alpha"
    assert captured["tag"] == "beta"


def test_cli_tui_strips_blank_filters(monkeypatch):
    captured = {}

    def _run_tui(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(tui_module, "run_tui", _run_tui)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tui", "--search", "   ", "--tag", "\t"])

    assert result.exit_code == 0
    assert captured["search"] is None
    assert captured["tag"] is None
