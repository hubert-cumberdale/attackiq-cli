from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
import attackiq_cli.services_assessment_schedules as services_assessment_schedules
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


def _context(spec: object) -> services.ServiceContext:
    return services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, spec),
    )


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


def test_list_assessment_schedules_uses_read_only_schedule_operation(monkeypatch) -> None:
    captured: dict[str, object] = {}
    op = _list_operation()

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "get_project_schedule_list"
            return op

    class ResponseStub:
        def json(self):
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

    class ClientStub:
        def send(self, operation, *, path_params, query_params, headers):
            captured["operation"] = operation
            captured["path_params"] = path_params
            captured["query_params"] = query_params
            captured["headers"] = headers
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_assessment_schedules,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    items = services.list_assessment_schedules(
        _context(SpecStub()),
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items[0]["project"]["id"] == "project-1"
    assert captured["operation"] is op
    assert captured["path_params"] == {}
    assert captured["query_params"] == {}
    assert captured["headers"] == {}


def test_list_assessment_schedules_validates_response_shape(monkeypatch) -> None:
    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "get_project_schedule_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return {"results": []}

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_assessment_schedules,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    with pytest.raises(ValueError, match="response must be a list"):
        services.list_assessment_schedules(
            _context(SpecStub()),
            insecure=False,
            timeout=None,
            check_auth=False,
        )


def test_list_assessment_schedules_validates_item_shape(monkeypatch) -> None:
    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "get_project_schedule_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return ["project-1"]

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_assessment_schedules,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    with pytest.raises(ValueError, match="items must be objects"):
        services.list_assessment_schedules(
            _context(SpecStub()),
            insecure=False,
            timeout=None,
            check_auth=False,
        )


def test_build_assessment_schedule_summary_records_picks_schema_fields() -> None:
    records = services.build_assessment_schedule_summary_records(
        [
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
            },
            {
                "project": {
                    "uuid": "project-2",
                    "name": "Unscheduled Assessment",
                    "project_template_name": "Unscheduled Template",
                },
                "schedule": {"schedule_version": "v2", "crontab": None},
            },
        ]
    )

    assert records == [
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
        },
        {
            "project_id": "project-2",
            "project_name": "Unscheduled Assessment",
            "project_template_name": "Unscheduled Template",
            "schedule_version": "v2",
            "schedule_present": "False",
            "crontab_minute": None,
            "crontab_hour": None,
            "crontab_day_of_week": None,
            "crontab_day_of_month": None,
            "crontab_month_of_year": None,
            "crontab_timezone": None,
        },
    ]
