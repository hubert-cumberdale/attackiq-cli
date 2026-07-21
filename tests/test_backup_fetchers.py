from __future__ import annotations

from typing import Any, cast

import pytest

from attackiq_cli import backup_fetchers
from attackiq_cli.backup_catalog import BackupError, EndpointCatalogEntry
from attackiq_cli.client import AttackIQClient
from attackiq_cli.config import CliConfig
from attackiq_cli.services import ServiceContext, build_auth_context
from attackiq_cli.spec import Operation, SpecIndex


def _operation(operation_id: str, path: str) -> Operation:
    return Operation(
        operation_id=operation_id,
        method="get",
        path=path,
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


class SpecStub:
    def get_operation(self, operation_id: str) -> Operation:
        paths = {
            "v1_source_types_list": "/v1/source_types",
            "v1_tenant_sso_get": "/v1/sso",
        }
        return _operation(operation_id, paths[operation_id])


def _context() -> ServiceContext:
    return ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, SpecStub()),
    )


class ResponseStub:
    def __init__(self, payload: Any):
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class ClientStub:
    def __init__(self, responses: dict[str, list[Any]]):
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def send(
        self,
        operation: Operation,
        *,
        query_params: dict[str, Any],
        **_kwargs: Any,
    ) -> ResponseStub:
        self.calls.append((operation.operation_id, dict(query_params)))
        payloads = self.responses[operation.operation_id]
        if not payloads:
            raise AssertionError(f"Unexpected call for {operation.operation_id}")
        return ResponseStub(payloads.pop(0))


def test_build_source_type_requests_deduplicates_company_connector_pairs() -> None:
    requests = backup_fetchers.build_source_type_requests(
        [
            {
                "id": "company-connector-1",
                "display_name": "Sentinel",
                "company": {"id": "company-1"},
                "connector": {"id": "connector-1"},
            },
            {
                "id": "company-connector-duplicate",
                "display_name": "Duplicate",
                "company_id": "company-1",
                "connector_id": "connector-1",
            },
            {
                "id": "company-connector-2",
                "display_name": "Splunk",
                "company_id": "company-2",
                "connector": {"uuid": "connector-2"},
            },
            {"id": "missing-connector", "company_id": "company-3"},
        ],
        company_id_override=None,
    )

    assert requests == [
        backup_fetchers.SourceTypeRequest(
            company_id="company-1",
            connector_id="connector-1",
            connector_instance_id="company-connector-1",
            connector_display_name="Sentinel",
        ),
        backup_fetchers.SourceTypeRequest(
            company_id="company-2",
            connector_id="connector-2",
            connector_instance_id="company-connector-2",
            connector_display_name="Splunk",
        ),
    ]


def test_fetch_paginated_records_rejects_non_object_result_items() -> None:
    client = ClientStub(
        {
            "v1_source_types_list": [
                {"results": [{"id": "source-type-1"}, "bad-item"], "next": None},
            ]
        }
    )

    with pytest.raises(BackupError, match="results must contain objects"):
        backup_fetchers.fetch_paginated_records(
            cast(AttackIQClient, client),
            _operation("v1_source_types_list", "/v1/source_types"),
            page_size=100,
            max_pages=None,
            response_label="Source type list",
        )


def test_fetch_source_types_for_backup_wraps_connector_context() -> None:
    client = ClientStub(
        {
            "v1_source_types_list": [
                {"results": [{"id": "source-type-1", "name": "Alert"}], "next": None},
            ]
        }
    )

    records = backup_fetchers.fetch_source_types_for_backup(
        _context(),
        cast(AttackIQClient, client),
        [
            backup_fetchers.SourceTypeRequest(
                company_id="company-1",
                connector_id="connector-1",
                connector_instance_id="company-connector-1",
                connector_display_name="Sentinel",
            )
        ],
        page_size=50,
        max_pages=2,
    )

    assert client.calls == [
        (
            "v1_source_types_list",
            {"page": 1, "page_size": 50, "company": "company-1", "connector": "connector-1"},
        )
    ]
    assert records == [
        {
            "company_id": "company-1",
            "connector_id": "connector-1",
            "connector_instance_id": "company-connector-1",
            "connector_display_name": "Sentinel",
            "source_type": {"id": "source-type-1", "name": "Alert"},
        }
    ]


def test_fetch_catalog_entry_for_backup_returns_object_payload() -> None:
    client = ClientStub({"v1_tenant_sso_get": [{"id": "sso-1", "enabled": True}]})
    entry = EndpointCatalogEntry(
        domain="tenant-sso",
        method="GET",
        path="/v1/sso",
        classification="backup-safe",
        operation_id="v1_tenant_sso_get",
        pagination="none",
        response_kind="object",
    )

    records = backup_fetchers.fetch_catalog_entry_for_backup(
        _context(),
        cast(AttackIQClient, client),
        entry,
        page_size=100,
        max_pages=None,
    )

    assert records == [{"id": "sso-1", "enabled": True}]
    assert client.calls == [("v1_tenant_sso_get", {})]
