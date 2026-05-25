from __future__ import annotations

import contextlib
import json
from typing import cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _operation() -> Operation:
    return Operation(
        operation_id="v1_scenarios_list",
        method="get",
        path="/v1/scenarios",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_scenarios_list_uses_paginate_results(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_scenarios(
        _context,
        *,
        page,
        page_size,
        filters,
        api_backend="native",
        **_kwargs,
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["filters"] = filters
        captured["api_backend"] = api_backend
        return [{"id": "scenario-1"}]

    monkeypatch.setattr(cli, "load_config", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_scenarios", _svc_list_scenarios)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "scenarios",
            "list",
            "--search",
            "alpha",
            "--tag",
            "beta",
            "--modified-after",
            "2026-05-21T00:00:00Z",
        ],
    )

    assert result.exit_code == 0
    assert captured["page_size"] == 200
    assert captured["page"] is None
    assert captured["api_backend"] == "native"
    filters = cast(cli.ScenarioFilters, captured["filters"])
    assert filters.search == "alpha"
    assert filters.tag == "beta"
    assert filters.modified_after == "2026-05-21T00:00:00Z"
    assert filters.last_updated is None


def test_scenarios_list_accepts_last_updated_alias(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_scenarios(
        _context,
        *,
        page,
        page_size,
        filters,
        api_backend="native",
        **_kwargs,
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["filters"] = filters
        captured["api_backend"] = api_backend
        return [{"id": "scenario-1"}]

    monkeypatch.setattr(cli, "load_config", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_scenarios", _svc_list_scenarios)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["scenarios", "list", "--last-updated", "2026-05-20T00:00:00Z"],
    )

    assert result.exit_code == 0
    filters = cast(cli.ScenarioFilters, captured["filters"])
    assert filters.modified_after is None
    assert filters.last_updated == "2026-05-20T00:00:00Z"


def test_scenarios_list_passes_platform_api_backend(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_scenarios(
        _context,
        *,
        page,
        page_size,
        filters,
        api_backend="native",
        **_kwargs,
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["api_backend"] = api_backend
        captured["filters"] = filters
        return [{"id": "scenario-1"}]

    monkeypatch.setattr(cli, "load_config", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_scenarios", _svc_list_scenarios)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["scenarios", "list", "--api-backend", "platform-api", "--search", "alpha"],
    )

    assert result.exit_code == 0
    assert captured["api_backend"] == "platform-api"
    filters = cast(cli.ScenarioFilters, captured["filters"])
    assert filters.search == "alpha"


def test_scenarios_list_single_page(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_scenarios(
        _context,
        *,
        page,
        page_size,
        filters,
        **_kwargs,
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["filters"] = filters
        return [{"id": "scenario-2"}]

    monkeypatch.setattr(cli, "load_config", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_scenarios", _svc_list_scenarios)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["scenarios", "list", "--page", "2", "--page-size", "5", "--order-by", "name"],
    )

    assert result.exit_code == 0
    assert captured["page"] == 2
    assert captured["page_size"] == 5
    filters = cast(cli.ScenarioFilters, captured["filters"])
    assert filters.order_by == "name"


def test_scenarios_list_csv_requires_output(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_scenarios(*_args, **_kwargs):
        return [{"id": "scenario-1"}]

    monkeypatch.setattr(cli, "load_config", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_scenarios", _svc_list_scenarios)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["scenarios", "list", "--output-format", "csv"])

    assert result.exit_code != 0
    assert "CSV output requires --output." in result.output


def test_scenarios_list_csv_writes_file(tmp_path, monkeypatch):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_scenarios(*_args, **_kwargs):
        return [
            {
                "id": "scenario-1",
                "name": "Scenario One",
                "scenario_type": "atomic",
                "description": "Example scenario",
                "created": "2025-01-01T00:00:00Z",
                "modified": "2025-01-02T00:00:00Z",
            }
        ]

    monkeypatch.setattr(cli, "load_config", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_scenarios", _svc_list_scenarios)

    output_path = tmp_path / "scenarios.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["scenarios", "list", "--output-format", "csv", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    header = output_path.read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",")[:6] == [
        "id",
        "name",
        "scenario_type",
        "description",
        "created",
        "modified",
    ]


def test_scenarios_show(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return Operation(
                operation_id="v1_scenarios_retrieve",
                method="get",
                path="/v1/scenarios/{id}",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli, "load_config", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    def _fetch_scenario_detail(_context, *, scenario_id, **_kwargs):
        captured.update({"id": scenario_id})
        return {"id": scenario_id}

    monkeypatch.setattr(cli, "fetch_scenario_detail", _fetch_scenario_detail)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["scenarios", "show", "scenario-9"])

    assert result.exit_code == 0
    assert captured["id"] == "scenario-9"


def test_scenarios_upload_dry_run_redacts_auth(tmp_path, monkeypatch):
    package = tmp_path / "scenario.zip"
    package.write_bytes(b"PK\x03\x04example")

    monkeypatch.setattr(
        cli,
        "load_config_or_exit",
        lambda: CliConfig(base_url="https://api.example.com", account_token="secret-token"),
    )
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])

    runner = CliRunner()
    result = runner.invoke(cli.app, ["scenarios", "upload", str(package)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["method"] == "POST"
    assert payload["url"] == "https://api.example.com/v1/scenario_templates"
    assert payload["multipart_file_field"] == "zip_file"
    assert payload["headers"]["Authorization"] == "***"
    assert payload["packages"][0]["filename"] == "scenario.zip"
    assert "secret-token" not in result.output


def test_scenarios_upload_apply_posts_zip_file(tmp_path, monkeypatch):
    package = tmp_path / "scenario.zip"
    package.write_bytes(b"PK\x03\x04example")
    captured: dict[str, object] = {}

    class Response:
        status_code = 201
        headers = {"content-type": "application/json"}
        text = '{"id": "uploaded"}'

        def json(self):
            return {"id": "uploaded"}

    class ClientStub:
        def send(self, op, **kwargs):
            captured["operation_id"] = op.operation_id
            captured["path"] = op.path
            captured["files"] = kwargs["files"]
            return Response()

    monkeypatch.setattr(
        cli,
        "load_config_or_exit",
        lambda: CliConfig(base_url="https://api.example.com", account_token="secret-token"),
    )
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: contextlib.nullcontext(ClientStub()),
    )

    runner = CliRunner()
    result = runner.invoke(cli.app, ["scenarios", "upload", str(package), "--apply"])

    assert result.exit_code == 0
    assert captured["operation_id"] == "scenario_template_upload"
    assert captured["path"] == "/v1/scenario_templates"
    files = cast(list, captured["files"])
    assert files[0][0] == "zip_file"
    assert files[0][1][0] == "scenario.zip"
    payload = json.loads(result.output)
    assert payload[0]["status_code"] == 201
    assert payload[0]["response"] == {"id": "uploaded"}


def test_scenarios_upload_apply_redacts_response_urls_and_secrets(tmp_path, monkeypatch):
    package = tmp_path / "scenario.zip"
    package.write_bytes(b"PK\x03\x04example")

    class Response:
        status_code = 201
        headers = {"content-type": "application/json"}
        text = "{}"

        def json(self):
            return {
                "id": "uploaded",
                "package_url": (
                    "https://static.attackiq.example/package.zip"
                    "?X-Amz-Signature=signed-value"
                ),
                "metadata": {
                    "downloadUrl": "https://files.example.com/package.zip",
                    "api_token": "tenant-token-value",
                    "notes": "safe value",
                },
                "links": ["https://files.example.com/secondary.zip"],
            }

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(
        cli,
        "load_config_or_exit",
        lambda: CliConfig(base_url="https://api.example.com", account_token="secret-token"),
    )
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: contextlib.nullcontext(ClientStub()),
    )

    output_path = tmp_path / "upload-response.json"
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["scenarios", "upload", str(package), "--apply", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    output_text = output_path.read_text(encoding="utf-8")
    assert "https://static.attackiq.example" not in output_text
    assert "signed-value" not in output_text
    assert "tenant-token-value" not in output_text
    payload = json.loads(output_text)
    response = payload[0]["response"]
    assert response["id"] == "uploaded"
    assert response["package_url"] == "***"
    assert response["metadata"]["downloadUrl"] == "***"
    assert response["metadata"]["api_token"] == "***"
    assert response["metadata"]["notes"] == "safe value"
    assert response["links"] == ["***"]


def test_scenarios_upload_apply_raw_response_preserves_response_body(tmp_path, monkeypatch):
    package = tmp_path / "scenario.zip"
    package.write_bytes(b"PK\x03\x04example")

    class Response:
        status_code = 201
        headers = {"content-type": "application/json"}
        text = "{}"

        def json(self):
            return {
                "id": "uploaded",
                "package_url": "https://static.attackiq.example/package.zip?signature=raw-value",
            }

    class ClientStub:
        def send(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(
        cli,
        "load_config_or_exit",
        lambda: CliConfig(base_url="https://api.example.com", account_token="secret-token"),
    )
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: contextlib.nullcontext(ClientStub()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["scenarios", "upload", str(package), "--apply", "--raw-response"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["response"] == {
        "id": "uploaded",
        "package_url": "https://static.attackiq.example/package.zip?signature=raw-value",
    }


def test_scenarios_upload_rejects_non_zip(tmp_path, monkeypatch):
    package = tmp_path / "scenario.txt"
    package.write_text("not a zip", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "load_config_or_exit",
        lambda: CliConfig(base_url="https://api.example.com", account_token="secret-token"),
    )

    runner = CliRunner()
    result = runner.invoke(cli.app, ["scenarios", "upload", str(package)])

    assert result.exit_code != 0
    assert "Scenario package must be a .zip file." in result.output
