from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
import attackiq_cli.services_edr_scan_schedules as services_edr_scan_schedules
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
        operation_id="v1_emm_edr_scan_schedules_list",
        method="get",
        path="/v1/emm/edr_scan_schedules",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_build_edr_scan_schedule_query_params_normalizes_filters() -> None:
    params = services.build_edr_scan_schedule_query_params(
        services.EdrScanScheduleFilters(
            data_source=" data-source-1 ",
            enabled=True,
            schedule_type=" daily ",
            targeted=False,
        )
    )

    assert params == {
        "data_source": "data-source-1",
        "enabled": True,
        "schedule_type": "DAILY",
        "targeted": False,
    }


def test_build_edr_scan_schedule_query_params_rejects_unknown_schedule_type() -> None:
    with pytest.raises(ValueError, match="schedule-type must be one of"):
        services.build_edr_scan_schedule_query_params(
            services.EdrScanScheduleFilters(schedule_type="monthly")
        )


def test_list_edr_scan_schedules_autopaginates_with_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}
    op = _list_operation()

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_emm_edr_scan_schedules_list"
            return op

    class ClientStub:
        def send(self, *_args, **_kwargs):
            raise AssertionError("send should not be used in auto-paginate mode")

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    def _paginate_results(client, operation, page_size, query_params=None, **_kwargs):
        captured["client"] = client
        captured["operation"] = operation
        captured["page_size"] = page_size
        captured["query_params"] = query_params
        return [{"id": "schedule-1", "name": "Daily scan"}]

    monkeypatch.setattr(
        services_edr_scan_schedules,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )
    monkeypatch.setattr(services_edr_scan_schedules, "paginate_results", _paginate_results)

    items = services.list_edr_scan_schedules(
        _context(SpecStub()),
        page=None,
        page_size=100,
        filters=services.EdrScanScheduleFilters(
            data_source=" data-source-1 ",
            enabled=True,
            schedule_type="weekly",
            targeted=False,
        ),
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "schedule-1", "name": "Daily scan"}]
    assert captured["operation"] is op
    assert captured["page_size"] == 100
    assert captured["query_params"] == {
        "data_source": "data-source-1",
        "enabled": True,
        "schedule_type": "WEEKLY",
        "targeted": False,
    }


def test_list_edr_scan_schedules_explicit_page_validates_results_shape(monkeypatch) -> None:
    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_emm_edr_scan_schedules_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return {"results": {"id": "schedule-1"}}

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_edr_scan_schedules,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    with pytest.raises(ValueError, match="results must be a list"):
        services.list_edr_scan_schedules(
            _context(SpecStub()),
            page=1,
            page_size=100,
            filters=services.EdrScanScheduleFilters(),
            insecure=False,
            timeout=None,
            check_auth=False,
        )


def test_build_edr_scan_schedule_summary_records_omits_raw_target_asset_ids() -> None:
    records = services.build_edr_scan_schedule_summary_records(
        [
            {
                "id": "schedule-1",
                "name": " Daily scan ",
                "data_source_id": "source-1",
                "data_source": "source-global-1",
                "schedule_type": "DAILY",
                "fire_at": "2026-06-03T01:00:00Z",
                "time_of_day": "01:00:00",
                "days_of_week": {"monday": True, "tuesday": False},
                "day_of_week": 1,
                "week_interval": 2,
                "enabled": True,
                "target_asset_ids": {"asset-1": True, "asset-2": True},
                "last_fired_at": "2026-06-02T01:00:00Z",
                "created": "2026-06-01T00:00:00Z",
                "modified": "2026-06-02T00:00:00Z",
                "recent_runs": [{"id": "run-1"}],
            },
            {
                "id": "schedule-2",
                "name": "All eligible",
                "target_asset_ids": None,
            },
        ]
    )

    assert "target_asset_ids" not in records[0]
    assert "recent_runs" not in records[0]
    assert records[0] == {
        "id": "schedule-1",
        "name": "Daily scan",
        "data_source_id": "source-1",
        "data_source": "source-global-1",
        "schedule_type": "DAILY",
        "fire_at": "2026-06-03T01:00:00Z",
        "time_of_day": "01:00:00",
        "days_of_week": {"monday": True, "tuesday": False},
        "day_of_week": "1",
        "week_interval": "2",
        "enabled": "True",
        "targeted": "True",
        "target_asset_count": "2",
        "last_fired_at": "2026-06-02T01:00:00Z",
        "created": "2026-06-01T00:00:00Z",
        "modified": "2026-06-02T00:00:00Z",
    }
    assert records[1]["targeted"] == "False"
    assert records[1]["target_asset_count"] is None
