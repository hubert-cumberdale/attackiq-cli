from __future__ import annotations

import contextlib
from typing import Any, cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _operation(schema: dict, tags: list[str] | None = None) -> Operation:
    return Operation(
        operation_id="v1_example_create",
        method="post",
        path="/v1/example/{id}",
        summary="",
        parameters=[
            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        request_body={
            "required": True,
            "content": {"application/json": {"schema": schema}},
        },
        tags=tags or [],
        security=[],
    )


def _patch_common(monkeypatch, schema: dict, tags: list[str] | None = None):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation(schema, tags)

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

        def request_body_schema(self, operation: Operation) -> dict | None:
            if operation.request_body is None:
                return None
            content = cast(dict[str, Any], operation.request_body.get("content"))
            media = cast(dict[str, Any], content.get("application/json"))
            return cast(dict[str, Any] | None, media.get("schema"))

        def resolve_schema(self, schema: dict) -> dict:
            return schema

        def request_body_content_types(self, _operation: Operation) -> list[str]:
            return ["application/json"]

    class ClientStub:
        def send(self, _op, **_kwargs):
            return type("Resp", (), {"headers": {}, "text": "", "json": lambda: {}})()

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(ClientStub())

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "build_client", _build_client)


def test_call_body_missing_required_property(monkeypatch):
    schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
    _patch_common(monkeypatch, schema)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_create", "--param", "id=abc", "--body", "{}"],
    )

    assert result.exit_code != 0
    assert "missing required property" in result.output


def test_call_body_type_mismatch(monkeypatch):
    schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}},
        "required": ["count"],
    }
    _patch_common(monkeypatch, schema)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_create", "--param", "id=abc", "--body", '{"count":"nope"}'],
    )

    assert result.exit_code != 0
    assert "expected integer" in result.output


def test_call_body_additional_properties_false(monkeypatch):
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
    }
    _patch_common(monkeypatch, schema)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_create", "--param", "id=abc", "--body", '{"name":"x","extra":1}'],
    )

    assert result.exit_code != 0
    assert "unexpected property" in result.output


def test_call_body_format_validation(monkeypatch):
    schema = {
        "type": "object",
        "required": ["id", "email", "ip", "when"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "email": {"type": "string", "format": "email"},
            "ip": {"type": "string", "format": "ipv4"},
            "when": {"type": "string", "format": "date-time"},
        },
    }
    _patch_common(monkeypatch, schema)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "call",
            "v1_example_create",
            "--param",
            "id=abc",
            "--body",
            '{"id":"not-a-uuid","email":"bad","ip":"nope","when":"yesterday"}',
        ],
    )

    assert result.exit_code != 0
    assert "expected uuid format" in result.output


def test_call_skips_validation_for_public_tags(monkeypatch):
    schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
    _patch_common(monkeypatch, schema, tags=["public"])

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_create", "--param", "id=abc", "--body", "{}"],
    )

    assert result.exit_code == 0


def test_call_interactive_prompts_for_body(monkeypatch):
    schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
    _patch_common(monkeypatch, schema)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_create", "--param", "id=abc", "--interactive"],
        input="json\n{\"name\":\"alpha\"}\n",
    )

    assert result.exit_code == 0


def test_call_body_enforces_min_length_and_pattern(monkeypatch):
    schema = {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string", "minLength": 5, "pattern": "^[A-Z]{5,}$"},
        },
    }
    _patch_common(monkeypatch, schema)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_create", "--param", "id=abc", "--body", '{"name":"a"}'],
    )

    assert result.exit_code != 0
    assert "expected length >= 5" in result.output
    assert "expected string matching pattern" in result.output


def test_call_body_enforces_numeric_bounds(monkeypatch):
    schema = {
        "type": "object",
        "required": ["count"],
        "properties": {
            "count": {"type": "integer", "minimum": 10, "maximum": 20},
        },
    }
    _patch_common(monkeypatch, schema)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_create", "--param", "id=abc", "--body", '{"count":1}'],
    )

    assert result.exit_code != 0
    assert "expected >= 10" in result.output
