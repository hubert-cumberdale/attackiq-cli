from __future__ import annotations

import contextlib
import csv
import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.exporter import TEST_FIELD_ORDER


class DummyOperation:
    security: list[dict[str, Any]] = []


class DummySpecIndex:
    def get_operation(self, _operation_id: str) -> DummyOperation:
        return DummyOperation()


def test_export_tests_writes_json(tmp_path, monkeypatch):
    output_path = tmp_path / "tests.json"

    def _load_config() -> CliConfig:
        return CliConfig(base_url="https://api")

    def _from_file(_path: Path) -> DummySpecIndex:
        return DummySpecIndex()

    def _ensure_auth(_op, _auth):
        return []

    def _paginate_results(*_args, **_kwargs):
        return [
            {
                "id": "test-1",
                "name": "Test One",
                "description": "Example",
            }
        ]

    monkeypatch.setattr(cli, "load_config_or_exit", _load_config)
    monkeypatch.setattr(cli.SpecIndex, "from_file", _from_file)
    monkeypatch.setattr(cli, "ensure_auth", _ensure_auth)
    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(object())

    monkeypatch.setattr(cli, "build_client", _build_client)
    monkeypatch.setattr(cli, "paginate_results", _paginate_results)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "tests", "--output", str(output_path)])

    assert result.exit_code == 0
    payload = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert payload[0]["id"] == "test-1"


def test_export_tests_writes_csv(tmp_path, monkeypatch):
    output_path = tmp_path / "tests.csv"

    def _load_config() -> CliConfig:
        return CliConfig(base_url="https://api")

    def _from_file(_path: Path) -> DummySpecIndex:
        return DummySpecIndex()

    def _ensure_auth(_op, _auth):
        return []

    record = {field: f"{field}-value" for field in TEST_FIELD_ORDER}

    def _paginate_results(*_args, **_kwargs):
        return [record]

    monkeypatch.setattr(cli, "load_config_or_exit", _load_config)
    monkeypatch.setattr(cli.SpecIndex, "from_file", _from_file)
    monkeypatch.setattr(cli, "ensure_auth", _ensure_auth)
    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(object())

    monkeypatch.setattr(cli, "build_client", _build_client)
    monkeypatch.setattr(cli, "paginate_results", _paginate_results)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "tests", "--output", str(output_path)])

    assert result.exit_code == 0
    header = Path(output_path).read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[: len(TEST_FIELD_ORDER)] == TEST_FIELD_ORDER


def test_export_tests_csv_flattens_project_dict(tmp_path, monkeypatch):
    output_path = tmp_path / "tests.csv"

    def _load_config() -> CliConfig:
        return CliConfig(base_url="https://api")

    def _from_file(_path: Path) -> DummySpecIndex:
        return DummySpecIndex()

    def _ensure_auth(_op, _auth):
        return []

    def _paginate_results(*_args, **_kwargs):
        return [
            {
                "id": "test-1",
                "name": " Test One ",
                "description": " Example ",
                "project": {"id": "project-1", "name": " Core Project "},
                "runnable": True,
                "scheduled_count": 3,
            }
        ]

    monkeypatch.setattr(cli, "load_config_or_exit", _load_config)
    monkeypatch.setattr(cli.SpecIndex, "from_file", _from_file)
    monkeypatch.setattr(cli, "ensure_auth", _ensure_auth)

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(object())

    monkeypatch.setattr(cli, "build_client", _build_client)
    monkeypatch.setattr(cli, "paginate_results", _paginate_results)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "tests", "--output", str(output_path)])

    assert result.exit_code == 0
    with output_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        row = next(reader)
    assert row["id"] == "test-1"
    assert row["name"] == "Test One"
    assert row["description"] == "Example"
    assert row["project"] == "Core Project"
    assert row["runnable"] == "True"
    assert row["scheduled_count"] == "3"


def test_export_tests_rejects_invalid_page_size():
    runner = CliRunner()
    result = runner.invoke(cli.app, ["export", "tests", "--page-size", "0"])

    assert result.exit_code != 0
    assert "page-size must be >= 1." in result.output
