from __future__ import annotations

from typer.testing import CliRunner

from attackiq_cli import cli


def test_export_templates_rejects_invalid_page_size():
    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "templates", "--page-size", "0"])

    assert result.exit_code != 0
    assert "page-size must be >= 1." in result.output


def test_export_templates_rejects_invalid_scenario_concurrency():
    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "templates", "--scenario-concurrency", "0"])

    assert result.exit_code != 0
    assert "Usage:" in result.output
    assert "export templates" in result.output
