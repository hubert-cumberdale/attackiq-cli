from __future__ import annotations

from typing import cast

import httpx
from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_tags as cli_tags
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _operation() -> Operation:
    return Operation(
        operation_id="v1_tags_list",
        method="get",
        path="/v1/tags",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _retrieve_operation() -> Operation:
    return Operation(
        operation_id="v1_tags_retrieve",
        method="get",
        path="/v1/tags/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_tags_list_uses_paginate_results(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_tags(
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
        return [{"id": "tag-1"}]

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "svc_list_tags", _svc_list_tags)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "list", "--search", "alpha"])

    assert result.exit_code == 0
    assert captured["page_size"] == 200
    filters = cast(cli_tags.TagFilters, captured["filters"])
    assert filters.search == "alpha"


def test_tags_list_passes_filters(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_tags(
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
        return [{"id": "tag-1"}]

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "svc_list_tags", _svc_list_tags)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "tags",
            "list",
            "--name",
            "alpha",
            "--display-name",
            "Alpha",
            "--content-type",
            "scenario",
            "--exclude-tag-set",
            "11111111-1111-1111-1111-111111111111",
            "--object-fingerprint",
            "fingerprint",
            "--page-size",
            "50",
        ],
    )

    assert result.exit_code == 0
    assert captured["page_size"] == 50
    filters = cast(cli_tags.TagFilters, captured["filters"])
    assert filters.name == "alpha"
    assert filters.display_name == "Alpha"
    assert filters.content_type == "scenario"
    assert filters.exclude_tags_by_tag_set == "11111111-1111-1111-1111-111111111111"
    assert filters.object_fingerprint == "fingerprint"


def test_tags_list_page_fetches_single_page(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_tags(*_args, **_kwargs):
        return [{"id": "tag-1", "name": "alpha"}]

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "svc_list_tags", _svc_list_tags)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "list", "--page", "2", "--page-size", "50"])

    assert result.exit_code == 0
    # request path is covered by services tests; CLI only passes args to service helper.


def test_tags_list_limits_fields(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_tags(*_args, **_kwargs):
        return [
            {"id": "tag-2", "name": "alpha", "display_name": "Alpha", "extra": "ignore"},
            {"id": "tag-3", "name": "beta", "display_name": None, "foo": "bar"},
        ]

    def _write_json(_output, records):
        captured["records"] = records

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "svc_list_tags", _svc_list_tags)
    monkeypatch.setattr(cli_tags, "write_json", _write_json)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "list"])

    assert result.exit_code == 0
    assert captured["records"] == [
        {"id": "tag-2", "name": "alpha", "display_name": "Alpha"},
        {"id": "tag-3", "name": "beta", "display_name": None},
    ]


def test_tags_list_csv_requires_output(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_tags(*_args, **_kwargs):
        return []

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "svc_list_tags", _svc_list_tags)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "list", "--output-format", "csv"])

    assert result.exit_code != 0
    assert "CSV output requires --output." in result.output


def test_tags_list_rejects_invalid_exclude_tag_set(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["tags", "list", "--exclude-tag-set", "not-a-uuid"],
    )

    assert result.exit_code != 0
    assert "exclude-tag-set must be a valid UUID." in result.output


def test_tags_show_fetches_tag_detail(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tags_retrieve"
            return _retrieve_operation()

    def _fetch_tag_detail(
        _context,
        *,
        tag_id,
        insecure=False,
        timeout=None,
    ):
        captured["tag_id"] = tag_id
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        return {"id": tag_id, "name": "alpha", "display_name": "Alpha"}

    def _write_json(_output, payload):
        captured["payload"] = payload

    monkeypatch.setattr(cli_tags, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "fetch_tag_detail", _fetch_tag_detail)
    monkeypatch.setattr(cli_tags, "write_json", _write_json)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "show", "tag-1", "--timeout", "5"])

    assert result.exit_code == 0
    assert captured["tag_id"] == "tag-1"
    assert captured["timeout"] == 5.0
    assert captured["payload"] == {"id": "tag-1", "name": "alpha", "display_name": "Alpha"}


def test_tags_show_reports_malformed_detail(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tags_retrieve"
            return _retrieve_operation()

    def _fetch_tag_detail(*_args, **_kwargs):
        raise ValueError("Tag detail response must be an object.")

    monkeypatch.setattr(cli_tags, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "fetch_tag_detail", _fetch_tag_detail)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "show", "tag-1"])

    assert result.exit_code == 1
    assert "Tag detail response must be an object." in result.output


def test_tags_search_uses_search_query(monkeypatch):
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_search_tags(
        _context,
        *,
        query,
        limit,
        insecure=False,
        timeout=None,
        check_auth=True,
    ):
        captured["query"] = query
        captured["limit"] = limit
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        captured["check_auth"] = check_auth
        return [{"id": "tag-1", "name": "alpha", "display_name": "Alpha"}]

    printed: list[object] = []

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "svc_search_tags", _svc_search_tags)
    monkeypatch.setattr(cli_tags.console, "print", lambda obj: printed.append(obj))

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "search", "alpha", "--limit", "5"])

    assert result.exit_code == 0
    assert captured["limit"] == 5
    assert captured["query"] == "alpha"
    assert printed


def test_tags_search_csv_requires_output(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "search", "alpha", "--output-format", "csv"])

    assert result.exit_code != 0
    assert "CSV output requires --output." in result.output


def test_tags_list_handles_connect_error_without_traceback(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_list_tags(*_args, **_kwargs):
        request = httpx.Request("GET", "https://api.example.com/v1/tags")
        raise httpx.ConnectError("dns failure", request=request)

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "svc_list_tags", _svc_list_tags)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "list", "--page", "2"])

    assert result.exit_code == 1
    assert "Network connection failed:" in result.output
    assert "Traceback" not in result.output


def test_tags_search_handles_connect_error_without_traceback(monkeypatch):
    class DummySpecIndex:
        def get_operation(self, _operation_id: str) -> Operation:
            return _operation()

    def _svc_search_tags(*_args, **_kwargs):
        request = httpx.Request("GET", "https://api.example.com/v1/tags")
        raise httpx.ConnectError("dns failure", request=request)

    monkeypatch.setattr(cli_tags, "load_config", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tags,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tags,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tags, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tags.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tags, "svc_search_tags", _svc_search_tags)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tags", "search", "alpha"])

    assert result.exit_code == 1
    assert "Network connection failed:" in result.output
    assert "Traceback" not in result.output
