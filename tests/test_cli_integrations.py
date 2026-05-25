from __future__ import annotations

from typing import cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


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


def test_integrations_list_passes_schema_backed_filters(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_company_connectors_list"
            return _list_operation()

    def _svc_list_integration_connectors(
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
        return [{"id": "company-connector-1", "display_name": "Sentinel", "status": "ACTIVE"}]

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(
        cli, "svc_list_integration_connectors", _svc_list_integration_connectors
    )
    monkeypatch.setattr(cli, "write_json", _write_json)

    result = CliRunner().invoke(
        cli.app,
        [
            "integrations",
            "list",
            "--alert-correlation-plan",
            "plan-1",
            "--company-connector-manager-setup",
            "setup-1",
            "--company-connector-manager-setup-id",
            "setup-2",
            "--description",
            "endpoint",
            "--display-name",
            "Sentinel",
            "--implemented-mixins",
            "alerts",
            "--is-deleted",
            "false",
            "--mode",
            "automatic",
            "--mttd-timezone",
            "timezone-1",
            "--status",
            "active",
            "--ordering",
            "display_name",
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
    filters = cast(cli.IntegrationConnectorFilters, captured["filters"])
    assert filters.alert_correlation_plan == "plan-1"
    assert filters.company_connector_manager_setup == "setup-1"
    assert filters.company_connector_manager_setup_id == "setup-2"
    assert filters.description == "endpoint"
    assert filters.display_name == "Sentinel"
    assert filters.implemented_mixins == "alerts"
    assert filters.is_deleted is False
    assert filters.mode == "automatic"
    assert filters.mttd_timezone == "timezone-1"
    assert filters.status == "active"
    assert filters.ordering == "display_name"
    assert captured["payload"] == [
        {
            "id": "company-connector-1",
            "display_name": "Sentinel",
            "status": "ACTIVE",
            "enabled": None,
            "active": None,
            "pending": None,
            "mode": None,
            "connector_id": None,
            "connector_name": None,
            "connector_type_id": None,
            "connector_type_name": None,
            "vendor_product_id": None,
            "vendor_product_name": None,
            "company_id": None,
            "company_name": None,
            "source_type_count": None,
            "last_checkin": None,
            "running_version": None,
            "created": None,
            "modified": None,
        }
    ]


def test_integrations_list_csv_requires_output(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_company_connectors_list"
            return _list_operation()

    def _svc_list_integration_connectors(*_args, **_kwargs):
        return []

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_integration_connectors", _svc_list_integration_connectors)

    result = CliRunner().invoke(cli.app, ["integrations", "list", "--output-format", "csv"])

    assert result.exit_code == 1
    assert "CSV output requires --output." in result.output


def test_integrations_list_rejects_unknown_status(monkeypatch):
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())

    result = CliRunner().invoke(cli.app, ["integrations", "list", "--status", "unknown"])

    assert result.exit_code != 0
    assert "status must be one of" in result.output


def test_integrations_list_reports_malformed_response(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_company_connectors_list"
            return _list_operation()

    def _svc_list_integration_connectors(*_args, **_kwargs):
        raise ValueError("Integration connector list response results must be a list.")

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_integration_connectors", _svc_list_integration_connectors)

    result = CliRunner().invoke(cli.app, ["integrations", "list"])

    assert result.exit_code == 1
    assert "Integration connector list response results must be a list." in result.output
