from __future__ import annotations

from typing import cast

import attackiq_cli.services as services
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation, SpecIndex


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

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: ClientManager())
    monkeypatch.setattr(services, "paginate_results", _paginate_results)
    monkeypatch.setattr(services, "build_scenarios_query_params", _build_scenarios_query_params)

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
