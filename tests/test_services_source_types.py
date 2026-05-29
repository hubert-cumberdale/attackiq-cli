from __future__ import annotations

from typing import cast

import pytest

import attackiq_cli.services as services
import attackiq_cli.services_source_types as services_source_types
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
        operation_id="v1_source_types_list",
        method="get",
        path="/v1/source_types",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_build_source_type_query_params_requires_company_and_connector() -> None:
    with pytest.raises(ValueError, match="company_id is required"):
        services.build_source_type_query_params(
            services.SourceTypeFilters(company_id=" ", connector_id="connector-1")
        )

    with pytest.raises(ValueError, match="connector_id is required"):
        services.build_source_type_query_params(
            services.SourceTypeFilters(company_id="company-1", connector_id=" ")
        )


def test_build_source_type_query_params_normalizes_filters() -> None:
    params = services.build_source_type_query_params(
        services.SourceTypeFilters(
            company_id=" company-1 ",
            connector_id=" connector-1 ",
            object_fingerprint=" fingerprint-1 ",
            unassigned_for=" assessment-1 ",
        )
    )

    assert params == {
        "company": "company-1",
        "connector": "connector-1",
        "object_fingerprint": "fingerprint-1",
        "unassigned_for": "assessment-1",
    }


def test_list_source_types_autopaginates_with_required_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}
    op = _list_operation()

    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_source_types_list"
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
        return [{"id": "source-type-1", "source_type_string": "alerts"}]

    monkeypatch.setattr(
        services_source_types,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )
    monkeypatch.setattr(services_source_types, "paginate_results", _paginate_results)

    items = services.list_source_types(
        _context(SpecStub()),
        page=None,
        page_size=100,
        filters=services.SourceTypeFilters(
            company_id=" company-1 ",
            connector_id=" connector-1 ",
        ),
        insecure=False,
        timeout=None,
        check_auth=False,
    )

    assert items == [{"id": "source-type-1", "source_type_string": "alerts"}]
    assert captured["operation"] is op
    assert captured["page_size"] == 100
    assert captured["query_params"] == {"company": "company-1", "connector": "connector-1"}


def test_list_source_types_explicit_page_validates_results_shape(monkeypatch) -> None:
    class SpecStub:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_source_types_list"
            return _list_operation()

    class ResponseStub:
        def json(self):
            return {"results": {"id": "source-type-1"}}

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return ResponseStub()

    class ClientManager:
        def __enter__(self):
            return ClientStub()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        services_source_types,
        "build_client",
        lambda *_args, **_kwargs: ClientManager(),
    )

    with pytest.raises(ValueError, match="results must be a list"):
        services.list_source_types(
            _context(SpecStub()),
            page=1,
            page_size=100,
            filters=services.SourceTypeFilters(
                company_id="company-1",
                connector_id="connector-1",
            ),
            insecure=False,
            timeout=None,
            check_auth=False,
        )


def test_build_source_type_summary_records_picks_schema_fields() -> None:
    records = services.build_source_type_summary_records(
        [
            {
                "id": "source-type-1",
                "source_type_string": " alerts ",
                "connector": {"id": "connector-1", "name": "Connector One"},
                "vendor_product": {"id": "vendor-product-1", "name": "Sentinel"},
                "company": "company-1",
                "user": "user-1",
                "ignore": False,
                "object_fingerprint": "fingerprint-1",
                "syncd_on": "2026-05-21T00:00:00Z",
                "created": "2026-05-20T00:00:00Z",
                "modified": "2026-05-21T00:00:00Z",
            }
        ]
    )

    assert records == [
        {
            "id": "source-type-1",
            "source_type_string": "alerts",
            "connector_id": "connector-1",
            "connector_name": "Connector One",
            "vendor_product_id": "vendor-product-1",
            "vendor_product_name": "Sentinel",
            "company_id": "company-1",
            "user_id": "user-1",
            "ignore": "False",
            "object_fingerprint": "fingerprint-1",
            "syncd_on": "2026-05-21T00:00:00Z",
            "created": "2026-05-20T00:00:00Z",
            "modified": "2026-05-21T00:00:00Z",
        }
    ]
