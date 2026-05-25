from __future__ import annotations

from typing import cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _list_operation() -> Operation:
    return Operation(
        operation_id="v1_asset_groups_list",
        method="get",
        path="/v1/asset_groups",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _retrieve_operation() -> Operation:
    return Operation(
        operation_id="v1_asset_groups_retrieve",
        method="get",
        path="/v1/asset_groups/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_asset_groups_list_passes_schema_backed_filters(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_asset_groups_list"
            return _list_operation()

    def _svc_list_asset_groups(
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
        return [{"id": "group-1", "name": "Linux Agents"}]

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_asset_groups", _svc_list_asset_groups)
    monkeypatch.setattr(cli, "write_json", _write_json)

    result = CliRunner().invoke(
        cli.app,
        [
            "asset-groups",
            "list",
            "--search",
            "linux",
            "--id",
            "group-1",
            "--name",
            "Linux Agents",
            "--description",
            "endpoint",
            "--company",
            "company-1",
            "--company-id",
            "company-2",
            "--user",
            "user-1",
            "--user-id",
            "user-2",
            "--created",
            "2026-05-21T00:00:00Z",
            "--created-after",
            "2026-05-20T00:00:00Z",
            "--modified",
            "2026-05-21T01:00:00Z",
            "--ordering",
            "name",
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
    filters = cast(cli.AssetGroupFilters, captured["filters"])
    assert filters.search == "linux"
    assert filters.asset_group_id == "group-1"
    assert filters.name == "Linux Agents"
    assert filters.description == "endpoint"
    assert filters.company == "company-1"
    assert filters.company_id == "company-2"
    assert filters.user == "user-1"
    assert filters.user_id == "user-2"
    assert filters.created == "2026-05-21T00:00:00Z"
    assert filters.created_after == "2026-05-20T00:00:00Z"
    assert filters.modified == "2026-05-21T01:00:00Z"
    assert filters.ordering == "name"
    assert captured["payload"] == [{"id": "group-1", "name": "Linux Agents"}]


def test_asset_groups_list_csv_requires_output(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_asset_groups_list"
            return _list_operation()

    def _svc_list_asset_groups(*_args, **_kwargs):
        return []

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_asset_groups", _svc_list_asset_groups)

    result = CliRunner().invoke(cli.app, ["asset-groups", "list", "--output-format", "csv"])

    assert result.exit_code == 1
    assert "CSV output requires --output." in result.output


def test_asset_groups_show_fetches_asset_group_detail(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_asset_groups_retrieve"
            return _retrieve_operation()

    def _fetch_asset_group_detail(
        _context,
        *,
        asset_group_id,
        insecure=False,
        timeout=None,
    ):
        captured["asset_group_id"] = asset_group_id
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        return {"id": asset_group_id, "name": "Linux Agents"}

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "fetch_asset_group_detail", _fetch_asset_group_detail)
    monkeypatch.setattr(cli, "write_json", _write_json)

    result = CliRunner().invoke(cli.app, ["asset-groups", "show", "group-1", "--timeout", "5"])

    assert result.exit_code == 0
    assert captured["asset_group_id"] == "group-1"
    assert captured["timeout"] == 5.0
    assert captured["payload"] == {"id": "group-1", "name": "Linux Agents"}


def test_asset_groups_show_reports_malformed_detail(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_asset_groups_retrieve"
            return _retrieve_operation()

    def _fetch_asset_group_detail(*_args, **_kwargs):
        raise ValueError("Asset group detail response must be an object.")

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "fetch_asset_group_detail", _fetch_asset_group_detail)

    result = CliRunner().invoke(cli.app, ["asset-groups", "show", "group-1"])

    assert result.exit_code == 1
    assert "Asset group detail response must be an object." in result.output
