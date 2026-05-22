from __future__ import annotations

from typing import cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _list_operation() -> Operation:
    return Operation(
        operation_id="v1_project_template_tests_list",
        method="get",
        path="/v1/project_template_tests",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_templates_tests_passes_template_filter(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_project_template_tests_list"
            return _list_operation()

    def _svc_list_template_tests(
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
        return [{"id": "template-test-1", "name": "Template Test One"}]

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_template_tests", _svc_list_template_tests)
    monkeypatch.setattr(cli, "write_json", _write_json)

    result = CliRunner().invoke(
        cli.app,
        [
            "templates",
            "tests",
            "--template-id",
            "template-1",
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
    filters = cast(cli.TemplateTestFilters, captured["filters"])
    assert filters.project_template_id == "template-1"
    assert captured["payload"] == [{"id": "template-test-1", "name": "Template Test One"}]


def test_templates_tests_csv_requires_output(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_project_template_tests_list"
            return _list_operation()

    def _svc_list_template_tests(*_args, **_kwargs):
        return []

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_template_tests", _svc_list_template_tests)

    result = CliRunner().invoke(cli.app, ["templates", "tests", "--output-format", "csv"])

    assert result.exit_code == 1
    assert "CSV output requires --output." in result.output


def test_templates_tests_reports_malformed_response(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_project_template_tests_list"
            return _list_operation()

    def _svc_list_template_tests(*_args, **_kwargs):
        raise ValueError("Template test list response results must be a list.")

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "svc_list_template_tests", _svc_list_template_tests)

    result = CliRunner().invoke(cli.app, ["templates", "tests"])

    assert result.exit_code == 1
    assert "Template test list response results must be a list." in result.output
