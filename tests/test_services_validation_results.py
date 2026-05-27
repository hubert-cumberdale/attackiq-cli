from __future__ import annotations

from typing import Any, cast

import pytest

import attackiq_cli.services as services
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


def test_build_validation_results_query_params_normalizes_filters() -> None:
    params = services.build_validation_results_query_params(
        services.ValidationResultFilters(
            days=7,
            project_ids=" project-1,project-2 ",
            scope_id=" scope-1 ",
            tag_ids=" tag-1 ",
        ),
        page=2,
        page_size=10,
    )

    assert params == {
        "page": 2,
        "page_size": 10,
        "days": 7,
        "project_ids": "project-1,project-2",
        "scope_id": "scope-1",
        "tag_ids": "tag-1",
    }


def test_fetch_validation_results_uses_selected_operation(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class ResponseStub:
        def json(self):
            return {"results": [{"asset_id": "asset-1"}], "next": "next-page"}

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

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())

    records, has_next = services.fetch_validation_results(
        _context(),
        by_asset=True,
        page=3,
        page_size=25,
        filters=services.ValidationResultFilters(days=14),
        insecure=False,
        timeout=None,
    )

    assert records == [{"asset_id": "asset-1"}]
    assert has_next is True
    assert captured == {
        "operation_id": "v1_validation_results_by_asset_retrieve",
        "query_params": {"page": 3, "page_size": 25, "days": 14},
        "path_params": {},
    }


def test_fetch_validation_result_executions_uses_path_params(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class ResponseStub:
        def json(self):
            return [{"scenario_id": "scenario-1"}]

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

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())

    records = services.fetch_validation_result_executions(
        _context(),
        asset_id="asset-1",
        filters=services.ValidationResultFilters(tag_ids="tag-1"),
        insecure=False,
        timeout=None,
    )

    assert records == [{"scenario_id": "scenario-1"}]
    assert captured == {
        "operation_id": "v1_validation_results_asset_executions_retrieve",
        "query_params": {"tag_ids": "tag-1"},
        "path_params": {"asset_id": "asset-1"},
    }


def test_fetch_validation_result_executions_uses_scenario_path_params(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class ResponseStub:
        def json(self):
            return [{"asset_id": "asset-1"}]

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

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())

    records = services.fetch_validation_result_executions(
        _context(),
        scenario_id="scenario-1",
        filters=services.ValidationResultFilters(scope_id="scope-1"),
        insecure=False,
        timeout=None,
    )

    assert records == [{"asset_id": "asset-1"}]
    assert captured == {
        "operation_id": "v1_validation_results_scenario_executions_retrieve",
        "query_params": {"scope_id": "scope-1"},
        "path_params": {"scenario_id": "scenario-1"},
    }


def test_fetch_validation_results_rejects_malformed_payload(monkeypatch) -> None:
    class ResponseStub:
        def json(self):
            return {"detail": "unexpected provider shape"}

    class ClientStub:
        def send(self, _op, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())

    with pytest.raises(ValueError, match="results list or be a list"):
        services.fetch_validation_results(
            _context(),
            by_asset=False,
            page=1,
            page_size=25,
            filters=services.ValidationResultFilters(),
            insecure=False,
            timeout=None,
        )


def test_fetch_validation_result_executions_requires_one_path_id() -> None:
    with pytest.raises(ValueError, match="Provide exactly one"):
        services.fetch_validation_result_executions(
            _context(),
            asset_id="asset-1",
            scenario_id="scenario-1",
            filters=services.ValidationResultFilters(),
            insecure=False,
            timeout=None,
        )

    with pytest.raises(ValueError, match="Provide exactly one"):
        services.fetch_validation_result_executions(
            _context(),
            filters=services.ValidationResultFilters(),
            insecure=False,
            timeout=None,
        )
