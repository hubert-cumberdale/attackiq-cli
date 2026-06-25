from __future__ import annotations

from typing import Any, cast

import attackiq_cli.services as services
import attackiq_cli.services_results as services_results
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


def _operation(operation_id: str) -> Operation:
    return Operation(
        operation_id=operation_id,
        method="get",
        path=f"/{operation_id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


class SpecStub:
    def get_operation(self, operation_id: str) -> Operation:
        return _operation(operation_id)


def _context() -> services.ServiceContext:
    return services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, SpecStub()),
    )


def test_fetch_results_list_uses_selected_mode_query(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class ResponseStub:
        def json(self):
            return {"results": [{"id": "result-1"}], "next": "next-page"}

    class ClientStub:
        def send(self, op, **kwargs):
            captured["operation_id"] = op.operation_id
            captured["query_params"] = kwargs["query_params"]
            captured["path_params"] = kwargs["path_params"]
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_results,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    records, has_next = services.fetch_results_list(
        _context(),
        mode=services.ResultsMode.SUMMARIES,
        page=2,
        page_size=50,
        search=None,
        tag_id=" tag-1 ",
        insecure=False,
        timeout=None,
    )

    assert records == [{"id": "result-1"}]
    assert has_next is True
    assert captured == {
        "operation_id": "v1_results_list",
        "query_params": {
            "page": 2,
            "page_size": 50,
            "assessment_results": True,
            "tag_id": "tag-1",
        },
        "path_params": {},
    }


def test_fetch_phase_results_and_logs_use_join_params(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []

    class ResponseStub:
        def __init__(self, item_id: str) -> None:
            self.item_id = item_id

        def json(self):
            return {"results": [{"id": self.item_id}]}

    class ClientStub:
        def send(self, op, **kwargs):
            captured.append(
                {
                    "operation_id": op.operation_id,
                    "query_params": kwargs["query_params"],
                    "path_params": kwargs["path_params"],
                }
            )
            return ResponseStub(op.operation_id)

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_results,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    phase_results = services.fetch_phase_results(
        _context(),
        result_summary_id="summary-1",
        page=3,
        page_size=25,
        insecure=False,
        timeout=None,
    )
    phase_logs = services.fetch_phase_logs(
        _context(),
        scenario_job_id="job-1",
        insecure=False,
        timeout=None,
    )

    assert phase_results == [{"id": "v1_phase_results_list"}]
    assert phase_logs == [{"id": "v1_phase_logs_list"}]
    assert captured == [
        {
            "operation_id": "v1_phase_results_list",
            "query_params": {
                "result_summary_id": "summary-1",
                "page": 3,
                "page_size": 25,
            },
            "path_params": {},
        },
        {
            "operation_id": "v1_phase_logs_list",
            "query_params": {
                "scenario_job_id": "job-1",
                "page": 1,
                "page_size": 200,
            },
            "path_params": {},
        },
    ]


def test_fetch_phase_records_return_empty_without_join_key() -> None:
    assert (
        services.fetch_phase_results(
            _context(),
            insecure=False,
            timeout=None,
        )
        == []
    )
    assert (
        services.fetch_phase_logs(
            _context(),
            insecure=False,
            timeout=None,
        )
        == []
    )
