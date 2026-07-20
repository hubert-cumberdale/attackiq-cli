from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
import attackiq_cli.services_integrations as services_integrations
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
        operation_id="v1_company_connectors_list",
        method="get",
        path="/v1/company_connectors",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_build_integration_connector_query_params_normalizes_filters() -> None:
    params = services.build_integration_connector_query_params(
        services.IntegrationConnectorFilters(
            alert_correlation_plan=" plan-1 ",
            company_connector_manager_setup=" setup-1 ",
            company_connector_manager_setup_id=" setup-2 ",
            description=" endpoint ",
            display_name=" Sentinel ",
            implemented_mixins=" alerts ",
            is_deleted=False,
            mode="automatic",
            mttd_timezone=" timezone-1 ",
            status="active",
            ordering=" display_name ",
        )
    )

    assert params == {
        "alert_correlation_plan": "plan-1",
        "company_connector_manager_setup": "setup-1",
        "company_connector_manager_setup_id": "setup-2",
        "description": "endpoint",
        "display_name": "Sentinel",
        "implemented_mixins": "alerts",
        "is_deleted": False,
        "mode": "Automatic",
        "mttd_timezone": "timezone-1",
        "status": "ACTIVE",
        "ordering": "display_name",
    }


def test_build_integration_connector_query_params_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="status must be one of"):
        services.build_integration_connector_query_params(
            services.IntegrationConnectorFilters(status="unknown")
        )


def test_list_integration_connectors_autopaginates_with_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}
    op = _list_operation()

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_company_connectors_list"
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
        return [{"id": "company-connector-1", "display_name": "Sentinel", "status": "ACTIVE"}]

    monkeypatch.setattr(
        services_integrations,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )
    monkeypatch.setattr(services_integrations, "paginate_results", _paginate_results)

    items = services.list_integration_connectors(
        _context(SpecStub()),
        page=None,
        page_size=100,
        filters=services.IntegrationConnectorFilters(status=" active "),
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "company-connector-1", "display_name": "Sentinel", "status": "ACTIVE"}]
    assert captured["operation"] is op
    assert captured["page_size"] == 100
    assert captured["query_params"] == {"status": "ACTIVE"}


def test_list_integration_connectors_explicit_page_validates_results_shape(monkeypatch) -> None:
    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_company_connectors_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return {"results": {"id": "connector-1"}}

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_integrations,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    with pytest.raises(ValueError, match="results must be a list"):
        services.list_integration_connectors(
            _context(SpecStub()),
            page=1,
            page_size=100,
            filters=services.IntegrationConnectorFilters(),
            insecure=False,
            timeout=None,
            check_auth=False,
        )


def test_build_integration_connector_summary_records_omits_configuration() -> None:
    records = services.build_integration_connector_summary_records(
        [
            {
                "id": "company-connector-1",
                "display_name": " Sentinel ",
                "status": " ACTIVE ",
                "enabled": True,
                "active": True,
                "pending": False,
                "mode": "Automatic",
                "connector": {
                    "id": "connector-1",
                    "name": "Connector One",
                    "connector_type": {"id": "type-1", "name": "SIEM"},
                    "vendor_product": {"id": "vendor-product-1", "name": "Sentinel"},
                },
                "company": {"id": "company-1", "name": "Tenant", "display_name": "Tenant One"},
                "source_types": [{"id": "source-type-1"}, {"id": "source-type-2"}],
                "last_checkin": "2026-05-21T00:00:00Z",
                "running_version": "1.2.3",
                "created": "2026-05-20T00:00:00Z",
                "modified": "2026-05-21T00:00:00Z",
                "configuration": "secret-config",
                "additional_configuration_options": {"secret": "value"},
            }
        ]
    )

    assert records == [
        {
            "id": "company-connector-1",
            "display_name": "Sentinel",
            "status": "ACTIVE",
            "enabled": "True",
            "active": "True",
            "pending": "False",
            "mode": "Automatic",
            "connector_id": "connector-1",
            "connector_name": "Connector One",
            "connector_type_id": "type-1",
            "connector_type_name": "SIEM",
            "vendor_product_id": "vendor-product-1",
            "vendor_product_name": "Sentinel",
            "company_id": "company-1",
            "company_name": "Tenant One",
            "source_type_count": "2",
            "last_checkin": "2026-05-21T00:00:00Z",
            "running_version": "1.2.3",
            "created": "2026-05-20T00:00:00Z",
            "modified": "2026-05-21T00:00:00Z",
        }
    ]
    assert "configuration" not in records[0]
    assert "additional_configuration_options" not in records[0]
