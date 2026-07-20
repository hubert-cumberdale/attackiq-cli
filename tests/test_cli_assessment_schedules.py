from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_assessment_schedules as cli_assessment_schedules
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _normalize_cli_output(text: str) -> str:
    no_ansi = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return " ".join(no_ansi.split())


def _list_operation() -> Operation:
    return Operation(
        operation_id="get_project_schedule_list",
        method="get",
        path="/v1/assessments/schedule_list",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_assessment_schedules_list_outputs_summary_records(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "get_project_schedule_list"
            return _list_operation()

    def _svc_list_assessment_schedules(
        _context,
        *,
        insecure=False,
        timeout=None,
        check_auth=True,
    ):
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        captured["check_auth"] = check_auth
        return [
            {
                "project": {
                    "id": "project-1",
                    "name": "Credential Assessment",
                    "project_template_name": "Credential Template",
                },
                "schedule": {
                    "schedule_version": "v3",
                    "crontab": {
                        "minute": "0",
                        "hour": "9",
                        "day_of_week": "1",
                        "day_of_month": "*",
                        "month_of_year": "*",
                        "timezone": "UTC",
                    },
                },
            }
        ]

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli_assessment_schedules, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assessment_schedules,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assessment_schedules,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assessment_schedules, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assessment_schedules.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(
        cli_assessment_schedules,
        "svc_list_assessment_schedules",
        _svc_list_assessment_schedules,
    )
    monkeypatch.setattr(cli_assessment_schedules, "write_json", _write_json)

    result = CliRunner().invoke(
        cli.app,
        [
            "assessment-schedules",
            "list",
            "--timeout",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert captured["timeout"] == 5.0
    assert captured["check_auth"] is False
    assert captured["payload"] == [
        {
            "project_id": "project-1",
            "project_name": "Credential Assessment",
            "project_template_name": "Credential Template",
            "schedule_version": "v3",
            "schedule_present": "True",
            "crontab_minute": "0",
            "crontab_hour": "9",
            "crontab_day_of_week": "1",
            "crontab_day_of_month": "*",
            "crontab_month_of_year": "*",
            "crontab_timezone": "UTC",
        }
    ]


def test_assessment_schedules_list_csv_requires_output(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "get_project_schedule_list"
            return _list_operation()

    def _svc_list_assessment_schedules(*_args, **_kwargs):
        return []

    monkeypatch.setattr(cli_assessment_schedules, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assessment_schedules,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assessment_schedules,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assessment_schedules, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assessment_schedules.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(
        cli_assessment_schedules,
        "svc_list_assessment_schedules",
        _svc_list_assessment_schedules,
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "assessment-schedules",
            "list",
            "--output-format",
            "csv",
        ],
    )

    assert result.exit_code == 1
    assert "CSV output requires --output." in result.output


def test_assessment_schedules_list_writes_csv(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "get_project_schedule_list"
            return _list_operation()

    def _svc_list_assessment_schedules(*_args, **_kwargs):
        return [
            {
                "project": {
                    "id": "project-1",
                    "name": "Credential Assessment",
                    "project_template_name": "Credential Template",
                },
                "schedule": {"schedule_version": "v3", "crontab": None},
            }
        ]

    def _write_csv_records(output, records, *, preferred_fields, **_kwargs):
        captured["output"] = output
        captured["records"] = records
        captured["preferred_fields"] = preferred_fields

    output = tmp_path / "assessment-schedules.csv"
    monkeypatch.setattr(cli_assessment_schedules, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assessment_schedules,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assessment_schedules,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assessment_schedules, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assessment_schedules.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(
        cli_assessment_schedules,
        "svc_list_assessment_schedules",
        _svc_list_assessment_schedules,
    )
    monkeypatch.setattr(cli_assessment_schedules, "write_csv_records", _write_csv_records)

    result = CliRunner().invoke(
        cli.app,
        [
            "assessment-schedules",
            "list",
            "--output-format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert captured["output"] == output
    assert (
        captured["preferred_fields"]
        == cli_assessment_schedules.ASSESSMENT_SCHEDULE_FIELD_ORDER
    )
    assert captured["records"] == [
        {
            "project_id": "project-1",
            "project_name": "Credential Assessment",
            "project_template_name": "Credential Template",
            "schedule_version": "v3",
            "schedule_present": "False",
            "crontab_minute": None,
            "crontab_hour": None,
            "crontab_day_of_week": None,
            "crontab_day_of_month": None,
            "crontab_month_of_year": None,
            "crontab_timezone": None,
        }
    ]


def test_assessment_schedules_list_reports_malformed_response(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "get_project_schedule_list"
            return _list_operation()

    def _svc_list_assessment_schedules(*_args, **_kwargs):
        raise ValueError("Assessment schedule list response must be a list.")

    monkeypatch.setattr(cli_assessment_schedules, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assessment_schedules,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assessment_schedules,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assessment_schedules, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assessment_schedules.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(
        cli_assessment_schedules,
        "svc_list_assessment_schedules",
        _svc_list_assessment_schedules,
    )

    result = CliRunner().invoke(cli.app, ["assessment-schedules", "list"])

    assert result.exit_code == 1
    assert "Assessment schedule list response must be a list." in result.output


def test_assessment_schedules_list_help_has_no_apply_or_page_option() -> None:
    result = CliRunner().invoke(cli.app, ["assessment-schedules", "list", "--help"])

    assert result.exit_code == 0
    help_text = _normalize_cli_output(result.output).lower()
    assert "output format: json or csv" in help_text
    assert "--apply" not in help_text
    assert "--page" not in help_text
