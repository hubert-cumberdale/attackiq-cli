from __future__ import annotations

from typing import cast

import attackiq_cli.services as services
import attackiq_cli.services_scenarios as services_scenarios
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


def _context(spec: object) -> services.ServiceContext:
    return services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, spec),
    )


def test_list_scenarios_uses_paginate_results_and_query_builder(monkeypatch) -> None:
    captured: dict[str, object] = {}

    op = Operation(
        operation_id="v1_scenarios_list",
        method="get",
        path="/v1/scenarios",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_scenarios_list"
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
        return [{"id": "scenario-1"}]

    def _build_scenarios_query_params(*_args, **_kwargs):
        return {"search": "alpha", "tag": "tag-uuid-1"}

    monkeypatch.setattr(
        services_scenarios,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )
    monkeypatch.setattr(services_scenarios, "paginate_results", _paginate_results)
    monkeypatch.setattr(
        services_scenarios,
        "build_scenarios_query_params",
        _build_scenarios_query_params,
    )

    context = services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=services.build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, SpecStub()),
    )

    filters = services.ScenarioFilters(search="alpha", tag="beta")
    items = services.list_scenarios(
        context,
        page=None,
        page_size=200,
        filters=filters,
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "scenario-1"}]
    assert captured["page_size"] == 200
    assert captured["query_params"] == {"search": "alpha", "tag": "tag-uuid-1"}


def test_fetch_scenario_detail_uses_retrieve_path_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_scenarios_retrieve"
            return Operation(
                operation_id=operation_id,
                method="get",
                path="/v1/scenarios/{id}",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    class ResponseStub:
        def json(self):
            return {"id": "scenario-1"}

    class ClientStub:
        def send(self, operation, **kwargs):
            captured["operation_id"] = operation.operation_id
            captured["path_params"] = kwargs["path_params"]
            captured["query_params"] = kwargs["query_params"]
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_scenarios,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    detail = services.fetch_scenario_detail(
        _context(SpecStub()),
        scenario_id="scenario-1",
        insecure=False,
        timeout=None,
    )

    assert detail == {"id": "scenario-1"}
    assert captured == {
        "operation_id": "v1_scenarios_retrieve",
        "path_params": {"id": "scenario-1"},
        "query_params": {},
    }


def test_health_check_probes_scenario_list(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_scenarios_list"
            return Operation(
                operation_id=operation_id,
                method="get",
                path="/v1/scenarios",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    class ResponseStub:
        def json(self):
            return {}

    class ClientStub:
        def send(self, operation, **kwargs):
            captured["operation_id"] = operation.operation_id
            captured["path_params"] = kwargs["path_params"]
            captured["query_params"] = kwargs["query_params"]
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_scenarios,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    ok, message = services.health_check(_context(SpecStub()), insecure=False, timeout=None)

    assert ok is True
    assert message == "OK"
    assert captured == {
        "operation_id": "v1_scenarios_list",
        "path_params": {},
        "query_params": {"page": 1, "page_size": 1},
    }
