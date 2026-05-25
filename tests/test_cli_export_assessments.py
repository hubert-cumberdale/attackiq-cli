from __future__ import annotations

import contextlib
import csv
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.exporter import ASSESSMENT_FIELD_ORDER


class DummyOperation:
    security: list[dict[str, Any]] = []


class DummySpecIndex:
    def get_operation(self, _operation_id: str) -> DummyOperation:
        return DummyOperation()


def _patch_common(monkeypatch):
    def _load_config() -> CliConfig:
        return CliConfig(base_url="https://api")

    def _from_file(_path: Path) -> DummySpecIndex:
        return DummySpecIndex()

    def _ensure_auth(_op, _auth):
        return []

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(object())

    monkeypatch.setattr(cli, "load_config_or_exit", _load_config)
    monkeypatch.setattr(cli.SpecIndex, "from_file", _from_file)
    monkeypatch.setattr(cli, "ensure_auth", _ensure_auth)
    monkeypatch.setattr(cli, "build_client", _build_client)


def test_export_assessments_passes_filters(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    output_path = tmp_path / "assessments.json"
    captured: dict[str, object] = {}

    def _paginate_results(*_args, **kwargs):
        captured.update(kwargs)
        return [{"id": "assessment-1"}]

    monkeypatch.setattr(cli, "paginate_results", _paginate_results)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "export",
            "assessments",
            "--output",
            str(output_path),
            "--format",
            "json",
            "--page-size",
            "50",
            "--max-pages",
            "2",
            "--asset-group-id",
            "group-a",
            "--asset-group-id",
            "group-b,group-c",
            "--blueprint-id",
            " blueprint-1 ",
            "--execution-strategy",
            "1",
            "--has-default-schedule",
            "--name",
            " Assessment One ",
            "--report-instance-type",
            "report",
            "--search",
            " credential ",
            "--use-scenario-alert-rules",
            "--version",
            "3",
            "--zones-ordering",
            "attacker_zone",
            "--zones-ordering",
            "-target_zone",
        ],
    )

    assert result.exit_code == 0
    assert captured["page_size"] == 50
    assert captured["max_pages"] == 2
    query_params = cast(dict[str, Any], captured["query_params"])
    assert query_params["asset_group_id"] == "group-a,group-b,group-c"
    assert query_params["blueprint_id"] == "blueprint-1"
    assert query_params["execution_strategy"] == 1
    assert query_params["has_default_schedule"] is True
    assert query_params["name"] == "Assessment One"
    assert query_params["report_instance_type"] == "report"
    assert query_params["search"] == "credential"
    assert query_params["use_scenario_alert_rules"] is True
    assert query_params["version"] == 3
    assert query_params["zones_ordering"] == "attacker_zone,-target_zone"


def test_export_assessments_rejects_invalid_zones_ordering(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    output_path = tmp_path / "assessments.json"

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "export",
            "assessments",
            "--output",
            str(output_path),
            "--format",
            "json",
            "--zones-ordering",
            "invalid",
        ],
    )

    assert result.exit_code != 0
    assert "zones-ordering must be one of" in result.output


def test_export_assessments_csv_includes_preferred_fields(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    output_path = tmp_path / "assessments.csv"

    def _paginate_results(*_args, **_kwargs):
        return [{"id": "assessment-1", "name": "Assessment One"}]

    monkeypatch.setattr(cli, "paginate_results", _paginate_results)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "export",
            "assessments",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    header = output_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[: len(ASSESSMENT_FIELD_ORDER)] == ASSESSMENT_FIELD_ORDER


def test_export_assessments_csv_flattens_assessment_type_dict(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    output_path = tmp_path / "assessments.csv"

    def _paginate_results(*_args, **_kwargs):
        return [
            {
                "id": "assessment-1",
                "name": " Assessment One ",
                "assessment_type": {"id": "type-1", "name": " Purple Team "},
                "status": " complete ",
            }
        ]

    monkeypatch.setattr(cli, "paginate_results", _paginate_results)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "export",
            "assessments",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    with output_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        row = next(reader)
    assert row["id"] == "assessment-1"
    assert row["name"] == "Assessment One"
    assert row["assessment_type"] == "Purple Team"
    assert row["assessment_type_id"] == "type-1"
    assert row["assessment_type_name"] == "Purple Team"
    assert row["status"] == "complete"
