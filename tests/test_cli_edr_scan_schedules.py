from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_edr_scan_schedules as cli_edr_scan_schedules
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation

DATA_SOURCE_ID = "11111111-1111-4111-8111-111111111111"


def _normalize_cli_output(text: str) -> str:
    no_ansi = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return " ".join(no_ansi.split())


def _list_operation() -> Operation:
    return Operation(
        operation_id="v1_emm_edr_scan_schedules_list",
        method="get",
        path="/v1/emm/edr_scan_schedules",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_edr_scan_schedules_list_outputs_summary_records(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_emm_edr_scan_schedules_list"
            return _list_operation()

    def _svc_list_edr_scan_schedules(
        _context,
        *,
        page,
        page_size,
        filters,
        insecure=False,
        timeout=None,
        check_auth=True,
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["filters"] = filters
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        captured["check_auth"] = check_auth
        return [
            {
                "id": "schedule-1",
                "name": "Daily scan",
                "data_source_id": DATA_SOURCE_ID,
                "data_source": "source-global-1",
                "schedule_type": "DAILY",
                "target_asset_ids": {"asset-1": True},
            }
        ]

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli_edr_scan_schedules, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_edr_scan_schedules, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_edr_scan_schedules.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "svc_list_edr_scan_schedules",
        _svc_list_edr_scan_schedules,
    )
    monkeypatch.setattr(cli_edr_scan_schedules, "write_json", _write_json)

    result = CliRunner().invoke(
        cli.app,
        [
            "edr-scan-schedules",
            "list",
            "--data-source",
            DATA_SOURCE_ID,
            "--enabled",
            "true",
            "--schedule-type",
            "daily",
            "--targeted",
            "false",
            "--page",
            "2",
            "--page-size",
            "50",
            "--timeout",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert captured["page"] == 2
    assert captured["page_size"] == 50
    assert captured["timeout"] == 5.0
    assert captured["check_auth"] is False
    filters = cast(cli_edr_scan_schedules.EdrScanScheduleFilters, captured["filters"])
    assert filters.data_source == DATA_SOURCE_ID
    assert filters.enabled is True
    assert filters.schedule_type == "daily"
    assert filters.targeted is False
    assert captured["payload"] == [
        {
            "id": "schedule-1",
            "name": "Daily scan",
            "data_source_id": DATA_SOURCE_ID,
            "data_source": "source-global-1",
            "schedule_type": "DAILY",
            "fire_at": None,
            "time_of_day": None,
            "days_of_week": None,
            "day_of_week": None,
            "week_interval": None,
            "enabled": None,
            "targeted": "True",
            "target_asset_count": "1",
            "last_fired_at": None,
            "created": None,
            "modified": None,
        }
    ]


def test_edr_scan_schedules_list_csv_requires_output(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_emm_edr_scan_schedules_list"
            return _list_operation()

    def _svc_list_edr_scan_schedules(*_args, **_kwargs):
        return []

    monkeypatch.setattr(cli_edr_scan_schedules, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_edr_scan_schedules, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_edr_scan_schedules.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "svc_list_edr_scan_schedules",
        _svc_list_edr_scan_schedules,
    )

    result = CliRunner().invoke(
        cli.app,
        ["edr-scan-schedules", "list", "--output-format", "csv"],
    )

    assert result.exit_code == 1
    assert "CSV output requires --output." in result.output


def test_edr_scan_schedules_list_writes_csv(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_emm_edr_scan_schedules_list"
            return _list_operation()

    def _svc_list_edr_scan_schedules(*_args, **_kwargs):
        return [{"id": "schedule-1", "name": "Daily scan"}]

    def _write_csv_records(output, records, preferred_fields=None):
        captured["output"] = output
        captured["records"] = records
        captured["preferred_fields"] = preferred_fields

    output = tmp_path / "edr-scan-schedules.csv"
    monkeypatch.setattr(cli_edr_scan_schedules, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_edr_scan_schedules, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_edr_scan_schedules.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "svc_list_edr_scan_schedules",
        _svc_list_edr_scan_schedules,
    )
    monkeypatch.setattr(cli_edr_scan_schedules, "write_csv_records", _write_csv_records)

    result = CliRunner().invoke(
        cli.app,
        [
            "edr-scan-schedules",
            "list",
            "--output-format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert captured["output"] == output
    assert captured["preferred_fields"] == cli_edr_scan_schedules.EDR_SCAN_SCHEDULE_FIELD_ORDER
    assert cast(list[dict[str, object]], captured["records"])[0]["id"] == "schedule-1"


def test_edr_scan_schedules_list_rejects_invalid_filters(monkeypatch) -> None:
    monkeypatch.setattr(cli_edr_scan_schedules, "load_config_or_exit", lambda: CliConfig())

    result = CliRunner().invoke(
        cli.app,
        ["edr-scan-schedules", "list", "--data-source", "not-a-uuid"],
    )
    assert result.exit_code != 0
    assert "--data-source must be a UUID." in _normalize_cli_output(result.output)

    result = CliRunner().invoke(
        cli.app,
        ["edr-scan-schedules", "list", "--enabled", "maybe"],
    )
    assert result.exit_code != 0
    assert "--enabled must be true or false." in _normalize_cli_output(result.output)

    result = CliRunner().invoke(
        cli.app,
        ["edr-scan-schedules", "list", "--schedule-type", "monthly"],
    )
    assert result.exit_code != 0
    assert "schedule-type must be one of" in _normalize_cli_output(result.output)


def test_edr_scan_schedules_list_reports_malformed_response(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_emm_edr_scan_schedules_list"
            return _list_operation()

    def _svc_list_edr_scan_schedules(*_args, **_kwargs):
        raise ValueError("EDR scan schedule list response results must be a list.")

    monkeypatch.setattr(cli_edr_scan_schedules, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_edr_scan_schedules, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_edr_scan_schedules.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(
        cli_edr_scan_schedules,
        "svc_list_edr_scan_schedules",
        _svc_list_edr_scan_schedules,
    )

    result = CliRunner().invoke(cli.app, ["edr-scan-schedules", "list"])

    assert result.exit_code == 1
    assert "EDR scan schedule list response results must be a list." in result.output


def test_edr_scan_schedules_list_help_has_no_apply_detail_or_runs_options() -> None:
    result = CliRunner().invoke(cli.app, ["edr-scan-schedules", "list", "--help"])

    assert result.exit_code == 0
    output = result.output
    assert "--apply" not in output
    assert "retrieve" not in output.lower()
    assert "runs" not in output.lower()
