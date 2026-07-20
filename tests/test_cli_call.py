from __future__ import annotations

import contextlib
from typing import Any, cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_call as cli_call
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _operation() -> Operation:
    return Operation(
        operation_id="v1_example_retrieve",
        method="get",
        path="/v1/example/{id}",
        summary="",
        parameters=[
            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}},
            {"name": "X-Trace", "in": "header", "required": True, "schema": {"type": "string"}},
            {"name": "session", "in": "cookie", "required": True, "schema": {"type": "string"}},
        ],
        request_body=None,
        tags=[],
        security=[],
    )


def _patch_common(monkeypatch, operation: Operation | None = None):
    op = operation or _operation()

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return op

        def parameter_names(self, operation: Operation, location: str) -> list[str]:
            return [
                param["name"]
                for param in operation.parameters
                if param.get("in") == location
            ]

        def required_parameters(self, operation: Operation, location: str) -> list[str]:
            return [
                param["name"]
                for param in operation.parameters
                if param.get("in") == location and param.get("required")
            ]

        def parameter_schema(
            self, operation: Operation, location: str, name: str
        ) -> dict | None:
            for param in operation.parameters:
                if param.get("in") == location and param.get("name") == name:
                    return param.get("schema") or {}
            return None

        def request_body_content_types(self, _operation: Operation) -> list[str]:
            return []

        def resolve_schema(self, schema: dict) -> dict:
            return schema

    monkeypatch.setattr(cli_call, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_call, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com"
    )
    monkeypatch.setattr(cli_call, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli_call.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())


def test_call_requires_header_and_cookie(monkeypatch):
    _patch_common(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_retrieve", "--param", "id=abc"],
    )

    assert result.exit_code != 0
    assert "Missing required header parameters" in result.output
    assert "Missing required cookie parameters" in result.output


def test_call_rejects_header_param_in_param(monkeypatch):
    _patch_common(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_retrieve", "--param", "id=abc", "--param", "X-Trace=1"],
    )

    assert result.exit_code != 0
    assert "defined as a header" in result.output


def test_call_builds_cookie_header(monkeypatch):
    captured: dict[str, str] = {}

    class ClientStub:
        def send(self, _op, **kwargs):
            captured.update(kwargs["headers"])
            return type("Resp", (), {"headers": {}, "text": "", "json": lambda: {}})()

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(ClientStub())

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli_call, "build_client", _build_client)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_retrieve",
            "--param",
            "id=abc",
            "--header",
            "x-trace=123",
            "--cookie",
            "session=alpha",
            "--cookie",
            "user=beta",
        ],
    )

    assert result.exit_code == 0
    assert captured["Cookie"] == "session=alpha; user=beta"


def test_call_accepts_cookie_header_for_required_cookie(monkeypatch):
    captured: dict[str, str] = {}

    class ClientStub:
        def send(self, _op, **kwargs):
            captured.update(kwargs["headers"])
            return type("Resp", (), {"headers": {}, "text": "", "json": lambda: {}})()

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(ClientStub())

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli_call, "build_client", _build_client)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_retrieve",
            "--param",
            "id=abc",
            "--header",
            "X-Trace=123",
            "--header",
            "Cookie=session=alpha",
        ],
    )

    assert result.exit_code == 0
    assert captured["Cookie"] == "session=alpha"


def test_call_cookie_overrides_cookie_header(monkeypatch):
    captured: dict[str, str] = {}

    class ClientStub:
        def send(self, _op, **kwargs):
            captured.update(kwargs["headers"])
            return type("Resp", (), {"headers": {}, "text": "", "json": lambda: {}})()

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(ClientStub())

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli_call, "build_client", _build_client)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_retrieve",
            "--param",
            "id=abc",
            "--header",
            "X-Trace=123",
            "--header",
            "Cookie=session=alpha; theme=dark",
            "--cookie",
            "session=beta",
        ],
    )

    assert result.exit_code == 0
    assert captured["Cookie"] == "session=beta; theme=dark"


def test_call_form_fields_use_data_body(monkeypatch):
    captured: dict[str, object] = {}

    class ClientStub:
        def send(self, _op, **kwargs):
            captured["data_body"] = kwargs.get("data_body")
            captured["files"] = kwargs.get("files")
            return type("Resp", (), {"headers": {}, "text": "", "json": lambda: {}})()

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(ClientStub())

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli_call, "build_client", _build_client)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_retrieve",
            "--param",
            "id=abc",
            "--header",
            "X-Trace=123",
            "--cookie",
            "session=alpha",
            "--form",
            "name=alpha",
            "--form",
            "count=2",
        ],
    )

    assert result.exit_code == 0
    assert captured["data_body"] == {"name": "alpha", "count": "2"}
    assert captured["files"] is None


def test_call_rejects_invalid_header_value(monkeypatch):
    operation = Operation(
        operation_id="v1_header_validate",
        method="get",
        path="/v1/example/{id}",
        summary="",
        parameters=[
            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "X-Count", "in": "header", "required": True, "schema": {"type": "integer"}},
        ],
        request_body=None,
        tags=[],
        security=[],
    )
    _patch_common(monkeypatch, operation=operation)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_header_validate", "--param", "id=abc", "--header", "X-Count=oops"],
    )

    assert result.exit_code != 0
    assert "Invalid value for header parameter 'X-Count'" in result.output


def test_call_rejects_invalid_cookie_value(monkeypatch):
    operation = Operation(
        operation_id="v1_cookie_validate",
        method="get",
        path="/v1/example/{id}",
        summary="",
        parameters=[
            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "session", "in": "cookie", "required": True, "schema": {"type": "integer"}},
        ],
        request_body=None,
        tags=[],
        security=[],
    )
    _patch_common(monkeypatch, operation=operation)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_cookie_validate", "--param", "id=abc", "--cookie", "session=alpha"],
    )

    assert result.exit_code != 0
    assert "Invalid value for cookie parameter 'session'" in result.output


def test_call_form_file_uses_files_body(monkeypatch):
    captured: dict[str, object] = {}

    class ClientStub:
        def send(self, _op, **kwargs):
            captured["data_body"] = kwargs.get("data_body")
            captured["files"] = kwargs.get("files")
            return type("Resp", (), {"headers": {}, "text": "", "json": lambda: {}})()

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(ClientStub())

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli_call, "build_client", _build_client)

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("sample.txt", "w", encoding="utf-8") as handle:
            handle.write("hello")
        result = runner.invoke(
            cli.app,
            [
                "call",
                "v1_example_retrieve",
                "--param",
                "id=abc",
                "--header",
                "X-Trace=123",
                "--cookie",
                "session=alpha",
                "--form-file",
                "upload=sample.txt",
            ],
        )

    assert result.exit_code == 0
    assert captured["data_body"] is None
    files = captured["files"]
    assert isinstance(files, list)
    field, payload = files[0]
    filename, file_handle, content_type = payload
    assert field == "upload"
    assert filename == "sample.txt"
    assert content_type is None
    assert file_handle.closed is True


def test_call_interactive_prompts_for_required(monkeypatch):
    captured: dict[str, object] = {}

    class ClientStub:
        def send(self, _op, **kwargs):
            captured["path_params"] = kwargs.get("path_params")
            captured["query_params"] = kwargs.get("query_params")
            captured["headers"] = kwargs.get("headers")
            return type("Resp", (), {"headers": {}, "text": "", "json": lambda: {}})()

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(ClientStub())

    _patch_common(monkeypatch)
    monkeypatch.setattr(cli_call, "build_client", _build_client)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_retrieve", "--interactive"],
        input="abc\ntrace-123\nsession-1\n",
    )

    assert result.exit_code == 0
    assert captured["path_params"] == {"id": "abc"}
    assert captured["query_params"] == {}
    headers = cast(dict[str, Any], captured["headers"])
    assert headers["X-Trace"] == "trace-123"
    assert headers["Cookie"] == "session=session-1"


def test_call_dry_run_redacts_cookie_values(monkeypatch):
    _patch_common(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_retrieve",
            "--param",
            "id=abc",
            "--header",
            "X-Trace=123",
            "--cookie",
            "session=alpha",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert '"Cookie": "***"' in result.output
    assert "session=alpha" not in result.output


def test_call_dry_run_redacts_cookie_header_values(monkeypatch):
    _patch_common(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_retrieve",
            "--param",
            "id=abc",
            "--header",
            "X-Trace=123",
            "--header",
            "Cookie=session=alpha; theme=dark",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert '"Cookie": "***"' in result.output
    assert "session=alpha" not in result.output
    assert "theme=dark" not in result.output


def test_call_rejects_header_values_with_newline(monkeypatch):
    _patch_common(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_retrieve",
            "--param",
            "id=abc",
            "--header",
            "X-Trace=trace\nvalue",
            "--cookie",
            "session=alpha",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value for header 'X-Trace'" in result.output
    assert "control characters" in result.output


def test_call_rejects_cookie_header_values_with_newline(monkeypatch):
    _patch_common(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_retrieve",
            "--param",
            "id=abc",
            "--header",
            "X-Trace=123",
            "--cookie",
            "session=alpha\nbeta",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value for header 'Cookie'" in result.output
    assert "control characters" in result.output
