from __future__ import annotations

import contextlib
import csv
import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_export as cli_export
from attackiq_cli.config import CliConfig
from attackiq_cli.exporter import SCENARIO_EXPORT_FIELDS


class DummyOperation:
    security: list[dict[str, Any]] = []


class DummySpecIndex:
    def get_operation(self, _operation_id: str) -> DummyOperation:
        return DummyOperation()


def test_export_scenarios_writes_json(tmp_path, monkeypatch):
    output_path = tmp_path / "scenarios.json"

    def _load_config() -> CliConfig:
        return CliConfig(base_url="https://api")

    def _from_file(_path: Path) -> DummySpecIndex:
        return DummySpecIndex()

    def _ensure_auth(_op, _auth):
        return []

    def _paginate_results(*_args, **_kwargs):
        return [
            {
                "id": "scenario-1",
                "name": "Scenario One",
                "description": "Example",
            }
        ]

    monkeypatch.setattr(cli_export, "load_config_or_exit", _load_config)
    monkeypatch.setattr(cli_export.SpecIndex, "from_file", _from_file)
    monkeypatch.setattr(cli_export, "ensure_auth", _ensure_auth)

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(object())

    monkeypatch.setattr(cli_export, "build_client", _build_client)
    monkeypatch.setattr(cli_export, "paginate_results", _paginate_results)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "scenarios", "--output", str(output_path)])

    assert result.exit_code == 0
    payload = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert payload[0]["id"] == "scenario-1"


def test_export_scenarios_writes_csv(tmp_path, monkeypatch):
    output_path = tmp_path / "scenarios.csv"

    def _load_config() -> CliConfig:
        return CliConfig(base_url="https://api")

    def _from_file(_path: Path) -> DummySpecIndex:
        return DummySpecIndex()

    def _ensure_auth(_op, _auth):
        return []

    record = {
        "id": "scenario-1",
        "name": "Scenario One",
        "scenario_type": "attack",
        "description": "Example description",
        "created": "2024-01-01",
        "modified": "2024-01-02",
        "cancellable": True,
        "capabilities": [{"display_name": "EDR/EPP"}, {"display_name": "SIEM"}],
        "last_updated": "2024-01-03",
        "description_json": {
            "failure_criteria": "fail",
            "prerequisites": "pre",
            "prevention_criteria": "prevent",
        },
        "scenario_tags": [
            {"tag": {"display_name": "Alpha"}},
            {"tag": {"display_name": "Beta"}},
        ],
        "supported_platforms": {"windows": ">=0.0"},
    }

    def _paginate_results(*_args, **_kwargs):
        return [record]

    monkeypatch.setattr(cli_export, "load_config_or_exit", _load_config)
    monkeypatch.setattr(cli_export.SpecIndex, "from_file", _from_file)
    monkeypatch.setattr(cli_export, "ensure_auth", _ensure_auth)

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(object())

    monkeypatch.setattr(cli_export, "build_client", _build_client)
    monkeypatch.setattr(cli_export, "paginate_results", _paginate_results)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "scenarios", "--output", str(output_path)])

    assert result.exit_code == 0
    with output_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        row = next(reader)
    assert header == SCENARIO_EXPORT_FIELDS
    assert row[header.index("capabilities")] == "EDR/EPP, SIEM"
    assert row[header.index("failure_criteria")] == "fail"
    assert row[header.index("prerequisites")] == "pre"
    assert row[header.index("prevention_criteria")] == "prevent"
    assert row[header.index("scenario_tags")] == "Alpha, Beta"
    assert row[header.index("supported_platform")] == "windows>=0.0"


def test_export_scenarios_rejects_invalid_page_size():
    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "scenarios", "--page-size", "0"])

    assert result.exit_code != 0
    assert "page-size must be >= 1." in result.output
