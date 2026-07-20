from __future__ import annotations

from typer.testing import CliRunner

from attackiq_cli import __version__
from attackiq_cli.cli import app


def test_version_option_reports_candidate_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"attackiq-cli version {__version__}"
