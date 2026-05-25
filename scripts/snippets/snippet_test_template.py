from typer.testing import CliRunner

from attackiq_cli.cli import app

runner = CliRunner()


def test_items_command_requires_base_url(monkeypatch):
    monkeypatch.setenv("ATTACKIQ_BASE_URL", "")
    result = runner.invoke(app, ["items", "list-items"])
    assert result.exit_code != 0
    assert "Base URL is not set" in result.stdout
