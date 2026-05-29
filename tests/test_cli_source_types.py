from __future__ import annotations

import re
from typing import cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation

COMPANY_ID = "11111111-1111-4111-8111-111111111111"
CONNECTOR_ID = "22222222-2222-4222-8222-222222222222"
UNASSIGNED_FOR_ID = "33333333-3333-4333-8333-333333333333"


def _normalize_cli_output(text: str) -> str:
    no_ansi = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return " ".join(no_ansi.split())


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


def test_source_types_list_passes_required_filters(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_source_types_list"
            return _list_operation()

    def _svc_list_source_types(
        _context,
        *,
        page,
        page_size,
        filters,
        insecure=False,
        timeout=None,
        check_auth=True,
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["filters"] = filters
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        captured["check_auth"] = check_auth
        return [
            {
                "id": "source-type-1",
                "source_type_string": "alerts",
                "connector": {"id": CONNECTOR_ID, "name": "Connector One"},
                "vendor_product": {"id": "vendor-product-1", "name": "Sentinel"},
                "company": COMPANY_ID,
            }
        ]

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_source_types", _svc_list_source_types)
    monkeypatch.setattr(cli, "write_json", _write_json)

    result = CliRunner().invoke(
        cli.app,
        [
            "source-types",
            "list",
            "--company-id",
            COMPANY_ID,
            "--connector-id",
            CONNECTOR_ID,
            "--object-fingerprint",
            "fingerprint-1",
            "--unassigned-for",
            UNASSIGNED_FOR_ID,
            "--page",
            "2",
            "--page-size",
            "50",
            "--timeout",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert captured["page"] == 2
    assert captured["page_size"] == 50
    assert captured["timeout"] == 5.0
    assert captured["check_auth"] is False
    filters = cast(cli.SourceTypeFilters, captured["filters"])
    assert filters.company_id == COMPANY_ID
    assert filters.connector_id == CONNECTOR_ID
    assert filters.object_fingerprint == "fingerprint-1"
    assert filters.unassigned_for == UNASSIGNED_FOR_ID
    assert captured["payload"] == [
        {
            "id": "source-type-1",
            "source_type_string": "alerts",
            "connector_id": CONNECTOR_ID,
            "connector_name": "Connector One",
            "vendor_product_id": "vendor-product-1",
            "vendor_product_name": "Sentinel",
            "company_id": COMPANY_ID,
            "user_id": None,
            "ignore": None,
            "object_fingerprint": None,
            "syncd_on": None,
            "created": None,
            "modified": None,
        }
    ]


def test_source_types_list_csv_requires_output(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_source_types_list"
            return _list_operation()

    def _svc_list_source_types(*_args, **_kwargs):
        return []

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_source_types", _svc_list_source_types)

    result = CliRunner().invoke(
        cli.app,
        [
            "source-types",
            "list",
            "--company-id",
            COMPANY_ID,
            "--connector-id",
            CONNECTOR_ID,
            "--output-format",
            "csv",
        ],
    )

    assert result.exit_code == 1
    assert "CSV output requires --output." in result.output


def test_source_types_list_rejects_invalid_uuid() -> None:
    result = CliRunner().invoke(
        cli.app,
        [
            "source-types",
            "list",
            "--company-id",
            "not-a-uuid",
            "--connector-id",
            CONNECTOR_ID,
        ],
    )

    assert result.exit_code != 0
    assert "--company-id must be a UUID." in _normalize_cli_output(result.output)


def test_source_types_list_reports_malformed_response(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_source_types_list"
            return _list_operation()

    def _svc_list_source_types(*_args, **_kwargs):
        raise ValueError("Source type list response results must be a list.")

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_source_types", _svc_list_source_types)

    result = CliRunner().invoke(
        cli.app,
        [
            "source-types",
            "list",
            "--company-id",
            COMPANY_ID,
            "--connector-id",
            CONNECTOR_ID,
        ],
    )

    assert result.exit_code == 1
    assert "Source type list response results must be a list." in result.output
