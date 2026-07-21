from __future__ import annotations

from typing import cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_templates as cli_templates
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _list_operation() -> Operation:
    return Operation(
        operation_id="v1_assessment_templates_list",
        method="get",
        path="/v1/assessment_templates",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _retrieve_operation() -> Operation:
    return Operation(
        operation_id="v1_assessment_templates_retrieve",
        method="get",
        path="/v1/assessment_templates/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_templates_list_passes_schema_backed_filters(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessment_templates_list"
            return _list_operation()

    def _svc_list_templates(
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
        return [{"id": "template-1", "template_name": "Template One"}]

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli_templates, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_templates,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_templates,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_templates, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_templates.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_templates, "svc_list_templates", _svc_list_templates)
    monkeypatch.setattr(cli_templates, "write_json", _write_json)

    result = CliRunner().invoke(
        cli.app,
        [
            "templates",
            "list",
            "--search",
            "credential",
            "--template-name",
            "Template One",
            "--project-name",
            "Project One",
            "--category",
            "validation",
            "--assessment-type",
            "baseline",
            "--behavior",
            "endpoint",
            "--page",
            "2",
            "--page-size",
            "50",
        ],
    )

    assert result.exit_code == 0
    assert captured["page"] == 2
    assert captured["page_size"] == 50
    filters = cast(cli_templates.TemplateFilters, captured["filters"])
    assert filters.search == "credential"
    assert filters.template_name == "Template One"
    assert filters.project_name == "Project One"
    assert filters.category == "validation"
    assert filters.assessment_type == "baseline"
    assert filters.behavior == "endpoint"
    assert captured["payload"] == [{"id": "template-1", "template_name": "Template One"}]


def test_templates_list_csv_requires_output(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessment_templates_list"
            return _list_operation()

    def _svc_list_templates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(cli_templates, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_templates,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_templates,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_templates, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_templates.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_templates, "svc_list_templates", _svc_list_templates)

    result = CliRunner().invoke(cli.app, ["templates", "list", "--output-format", "csv"])

    assert result.exit_code == 1
    assert "CSV output requires --output." in result.output


def test_templates_show_fetches_template_detail(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessment_templates_retrieve"
            return _retrieve_operation()

    def _fetch_template_detail(
        _context,
        *,
        template_id,
        insecure=False,
        timeout=None,
    ):
        captured["template_id"] = template_id
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        return {"id": template_id, "template_name": "Template One"}

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli_templates, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_templates,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_templates,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_templates, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_templates.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_templates, "fetch_template_detail", _fetch_template_detail)
    monkeypatch.setattr(cli_templates, "write_json", _write_json)

    result = CliRunner().invoke(cli.app, ["templates", "show", "template-1", "--timeout", "5"])

    assert result.exit_code == 0
    assert captured["template_id"] == "template-1"
    assert captured["timeout"] == 5.0
    assert captured["payload"] == {"id": "template-1", "template_name": "Template One"}


def test_templates_show_reports_malformed_detail(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessment_templates_retrieve"
            return _retrieve_operation()

    def _fetch_template_detail(*_args, **_kwargs):
        raise ValueError("Template detail response must be an object.")

    monkeypatch.setattr(cli_templates, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_templates,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_templates,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_templates, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_templates.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_templates, "fetch_template_detail", _fetch_template_detail)

    result = CliRunner().invoke(cli.app, ["templates", "show", "template-1"])

    assert result.exit_code == 1
    assert "Template detail response must be an object." in result.output
