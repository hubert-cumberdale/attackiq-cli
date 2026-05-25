from __future__ import annotations

import contextlib

from typer.testing import CliRunner

from attackiq_cli import cli
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _operation() -> Operation:
    return Operation(
        operation_id="v1_example_retrieve",
        method="get",
        path="/v1/example",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


class ResponseStub:
    def __init__(self, text: str, json_payload, content_type: str) -> None:
        self.text = text
        self._json_payload = json_payload
        self.headers = {"content-type": content_type}

    def json(self):
        return self._json_payload


def _patch_common(monkeypatch, response: ResponseStub) -> None:
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

        def parameter_names(self, _operation: Operation, _location: str) -> list[str]:
            return []

        def required_parameters(self, _operation: Operation, _location: str) -> list[str]:
            return []

        def parameter_schema(self, _operation: Operation, _location: str, _name: str):
            return None

        def request_body_content_types(self, _operation: Operation) -> list[str]:
            return []

    class ClientStub:
        def send(self, _op, **_kwargs):
            return response

    def _build_client(*_args, **_kwargs):
        return contextlib.nullcontext(ClientStub())

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "build_client", _build_client)


def test_call_output_pretty_json_stdout(monkeypatch):
    response = ResponseStub('{"ok": true}', {"ok": True}, "application/json")
    _patch_common(monkeypatch, response)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_retrieve", "--output-format", "pretty-json"],
    )

    assert result.exit_code == 0
    assert result.output == '{\n  "ok": true\n}\n'


def test_call_output_pretty_json_file(monkeypatch):
    response = ResponseStub('{"ok": true}', {"ok": True}, "application/json")
    _patch_common(monkeypatch, response)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli.app,
            [
                "call",
                "v1_example_retrieve",
                "--output-format",
                "pretty-json",
                "--output",
                "out.json",
            ],
        )

        assert result.exit_code == 0
        with open("out.json", encoding="utf-8") as handle:
            assert handle.read() == '{\n  "ok": true\n}\n'


def test_call_output_raw_stdout(monkeypatch):
    response = ResponseStub("raw-body", {"ignored": True}, "text/plain")
    _patch_common(monkeypatch, response)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_retrieve", "--output-format", "raw"],
    )

    assert result.exit_code == 0
    assert result.output == "raw-body"


def test_call_output_csv_stdout(monkeypatch):
    payload = [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]
    response = ResponseStub("", payload, "application/json")
    _patch_common(monkeypatch, response)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_retrieve", "--output-format", "csv"],
    )

    assert result.exit_code == 0
    output = result.output.replace("\r\n", "\n")
    assert output == "id,name\n1,alpha\n2,beta\n"


def test_call_output_csv_requires_array_of_objects(monkeypatch):
    response = ResponseStub('{"id": 1}', {"id": 1}, "application/json")
    _patch_common(monkeypatch, response)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["call", "v1_example_retrieve", "--output-format", "csv"],
    )

    assert result.exit_code != 0
    assert "CSV output requires a JSON array of objects." in result.output
