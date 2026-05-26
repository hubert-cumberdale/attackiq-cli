from __future__ import annotations

import json

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


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


class DummySpecIndex:
    def get_operation(self, operation_id: str) -> Operation:
        return _operation(operation_id)


def _patch_common(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())


def test_platform_api_parity_compares_scenario_ids(monkeypatch) -> None:
    captured_backends: list[str] = []

    def _svc_list_scenarios(_context, *, api_backend, filters, page, page_size, **_kwargs):
        captured_backends.append(api_backend)
        assert filters.search == "alpha"
        assert page is None
        assert page_size == 2
        return [{"id": "scenario-1"}, {"id": "scenario-2"}]

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli, "svc_list_scenarios", _svc_list_scenarios)

    result = CliRunner().invoke(
        cli.app,
        ["platform-api", "parity", "scenarios", "--search", "alpha", "--page-size", "2"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert captured_backends == ["native", "platform-api"]
    assert payload["resource"] == "scenarios"
    assert payload["parity"] is True
    assert payload["native"]["ids"] == ["scenario-1", "scenario-2"]
    assert payload["comparison"]["same_order"] is True


def test_platform_api_parity_can_fail_on_mismatch(monkeypatch) -> None:
    def _svc_list_scenarios(_context, *, api_backend, **_kwargs):
        if api_backend == "native":
            return [{"id": "scenario-1"}, {"id": "scenario-2"}]
        return [{"id": "scenario-2"}, {"id": "scenario-3"}]

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli, "svc_list_scenarios", _svc_list_scenarios)

    result = CliRunner().invoke(
        cli.app,
        ["platform-api", "parity", "scenarios", "--fail-on-mismatch"],
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["parity"] is False
    assert payload["comparison"]["missing_from_platform_api"] == ["scenario-1"]
    assert payload["comparison"]["extra_from_platform_api"] == ["scenario-3"]


def test_platform_api_parity_compares_assets_with_supported_filters(monkeypatch) -> None:
    captured: list[tuple[str, dict[str, object] | None]] = []

    def _svc_list_assets(_context, *, api_backend, query_params, page, page_size, **_kwargs):
        captured.append((api_backend, query_params))
        assert page == 2
        assert page_size == 5
        return [{"id": "asset-1"}]

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli, "svc_list_assets", _svc_list_assets)

    result = CliRunner().invoke(
        cli.app,
        [
            "platform-api",
            "parity",
            "assets",
            "--search",
            "asset-host",
            "--deployment-state-id",
            "2",
            "--order-by",
            "hostname",
            "--page",
            "2",
            "--page-size",
            "5",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["resource"] == "assets"
    assert payload["query"]["deployment_state_id"] == 2
    assert captured == [
        (
            "native",
            {"search": "asset-host", "deployment_state_id": 2, "ordering": "hostname"},
        ),
        (
            "platform-api",
            {"search": "asset-host", "deployment_state_id": 2, "ordering": "hostname"},
        ),
    ]


def test_platform_api_parity_rejects_invalid_resource(monkeypatch) -> None:
    _patch_common(monkeypatch)

    result = CliRunner().invoke(cli.app, ["platform-api", "parity", "tags"])

    assert result.exit_code != 0
    assert "resource must be one of" in result.output
