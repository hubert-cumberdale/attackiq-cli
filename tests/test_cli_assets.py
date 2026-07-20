from __future__ import annotations

from typing import Any, cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_assets as cli_assets
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _assets_list_op() -> Operation:
    return Operation(
        operation_id="v1_assets_list",
        method="get",
        path="/v1/assets",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _assets_retrieve_op() -> Operation:
    return Operation(
        operation_id="v1_assets_retrieve",
        method="get",
        path="/v1/assets/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_assets_list_uses_services_list_helper(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assets_list"
            return _assets_list_op()

    def _svc_list_assets(
        _context,
        *,
        page,
        page_size,
        query_params=None,
        insecure=False,
        timeout=None,
        check_auth=True,
        api_backend="native",
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["query_params"] = query_params
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        captured["check_auth"] = check_auth
        captured["api_backend"] = api_backend
        return [{"id": "asset-1", "hostname": "agent-host"}]

    monkeypatch.setattr(cli_assets, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assets,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assets,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assets, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assets.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_assets, "svc_list_assets", _svc_list_assets)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assets",
            "list",
            "--search",
            " agent ",
            "--hostname",
            " agent-host ",
            "--activity-type",
            "device",
            "--deployment-state-id",
            "2",
            "--deepsurface-last-seen-in-host-analysis-at",
            " 2026-05-21T00:00:00Z ",
            "--deepsurface-sync-state",
            " synced ",
            "--deepsurface-sync-state-changed-at",
            " 2026-05-21T01:00:00Z ",
            "--asset-group",
            "00000000-0000-0000-0000-000000000000",
            "--ordering",
            "hostname",
        ],
    )

    assert result.exit_code == 0
    assert captured["page"] is None
    assert captured["page_size"] == 200
    assert captured["check_auth"] is False
    assert captured["api_backend"] == "native"
    query_params = cast(dict[str, Any], captured["query_params"])
    assert query_params == {
        "search": "agent",
        "hostname": "agent-host",
        "deployment_state_id": 2,
        "deepsurface_last_seen_in_host_analysis_at": "2026-05-21T00:00:00Z",
        "deepsurface_sync_state": "synced",
        "deepsurface_sync_state_changed_at": "2026-05-21T01:00:00Z",
        "asset_group": "00000000-0000-0000-0000-000000000000",
        "activity_type": "DEVICE",
        "ordering": "hostname",
    }


def test_assets_list_passes_platform_api_backend(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assets_list"
            return _assets_list_op()

    def _svc_list_assets(
        _context,
        *,
        page,
        page_size,
        query_params=None,
        insecure=False,
        timeout=None,
        check_auth=True,
        api_backend="native",
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        captured["check_auth"] = check_auth
        captured["api_backend"] = api_backend
        captured["query_params"] = query_params
        return [{"id": "asset-1", "hostname": "agent-host"}]

    monkeypatch.setattr(cli_assets, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assets,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assets,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assets, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assets.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_assets, "svc_list_assets", _svc_list_assets)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["assets", "list", "--api-backend", "platform-api", "--search", "asset-host"],
    )

    assert result.exit_code == 0
    assert captured["api_backend"] == "platform-api"
    assert captured["query_params"] == {"search": "asset-host"}


def test_assets_list_rejects_invalid_activity_type(monkeypatch) -> None:
    monkeypatch.setattr(cli_assets, "load_config_or_exit", lambda: CliConfig())

    runner = CliRunner()
    result = runner.invoke(cli.app, ["assets", "list", "--activity-type", "invalid"])

    assert result.exit_code != 0
    assert "activity-type must be one of" in result.output


def test_assets_show_uses_services(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assets_retrieve"
            return _assets_retrieve_op()

    monkeypatch.setattr(cli_assets, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assets,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assets,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assets, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assets.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )

    def _fetch_asset_detail(_context, *, asset_id, **_kwargs):
        captured["id"] = asset_id
        return {"id": asset_id, "hostname": "agent-host"}

    monkeypatch.setattr(cli_assets, "fetch_asset_detail", _fetch_asset_detail)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["assets", "show", "asset-9"])

    assert result.exit_code == 0
    assert captured["id"] == "asset-9"
