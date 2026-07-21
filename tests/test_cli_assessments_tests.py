from __future__ import annotations

from typing import Any, cast

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_assessments as cli_assessments
import attackiq_cli.cli_tests as cli_tests
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


def _assessments_list_op() -> Operation:
    return Operation(
        operation_id="v1_assessments_list",
        method="get",
        path="/v1/assessments",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _assessments_retrieve_op() -> Operation:
    return Operation(
        operation_id="v1_assessments_retrieve",
        method="get",
        path="/v1/assessments/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _tests_list_op() -> Operation:
    return Operation(
        operation_id="v1_tests_list",
        method="get",
        path="/v1/tests",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def _tests_retrieve_op() -> Operation:
    return Operation(
        operation_id="v1_tests_retrieve",
        method="get",
        path="/v1/tests/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_assessments_list_uses_services_list_helper(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_list"
            return _assessments_list_op()

    def _svc_list_assessments(
        _context,
        *,
        page,
        page_size,
        query_params=None,
        insecure=False,
        timeout=None,
        check_auth=True,
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["query_params"] = query_params
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        captured["check_auth"] = check_auth
        return [{"id": "assessment-1"}]

    monkeypatch.setattr(cli_assessments, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assessments,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assessments,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assessments, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assessments.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_assessments, "svc_list_assessments", _svc_list_assessments)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "list",
            "--search",
            " alpha ",
            "--id",
            "assessment-1,assessment-2",
            "--id-in",
            "assessment-3",
            "--tag-id",
            " tag-1 ",
            "--tag-ids",
            "tag-2,tag-3",
        ],
    )

    assert result.exit_code == 0
    assert captured["page_size"] == 200
    query_params = cast(dict[str, Any], captured["query_params"])
    assert query_params == {
        "id__in": "assessment-1,assessment-2,assessment-3",
        "search": "alpha",
        "tag_id": "tag-1",
        "tag_ids": "tag-2,tag-3",
    }


def test_assessments_show_uses_services(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_retrieve"
            return _assessments_retrieve_op()

    monkeypatch.setattr(cli_assessments, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_assessments,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_assessments,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_assessments, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_assessments.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )

    def _fetch_assessment_detail(_context, *, assessment_id, **_kwargs):
        captured["id"] = assessment_id
        return {"id": assessment_id}

    monkeypatch.setattr(cli_assessments, "fetch_assessment_detail", _fetch_assessment_detail)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["assessments", "show", "assessment-9"])

    assert result.exit_code == 0
    assert captured["id"] == "assessment-9"


def test_tests_list_uses_services_list_helper(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_list"
            return _tests_list_op()

    def _svc_list_tests(
        _context,
        *,
        page,
        page_size,
        query_params=None,
        insecure=False,
        timeout=None,
        check_auth=True,
    ):
        captured["page"] = page
        captured["page_size"] = page_size
        captured["query_params"] = query_params
        captured["insecure"] = insecure
        captured["timeout"] = timeout
        captured["check_auth"] = check_auth
        return [{"id": "test-1"}]

    monkeypatch.setattr(cli_tests, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tests,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tests,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tests, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tests.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )
    monkeypatch.setattr(cli_tests, "svc_list_tests", _svc_list_tests)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tests", "list", "--name", " API Test "])

    assert result.exit_code == 0
    assert captured["page_size"] == 200
    query_params = cast(dict[str, Any], captured["query_params"])
    assert query_params["name"] == "API Test"


def test_tests_show_uses_services(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_retrieve"
            return _tests_retrieve_op()

    monkeypatch.setattr(cli_tests, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_tests,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_tests,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(cli_tests, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_tests.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )

    def _fetch_test_detail(_context, *, test_id, **_kwargs):
        captured["id"] = test_id
        return {"id": test_id}

    monkeypatch.setattr(cli_tests, "fetch_test_detail", _fetch_test_detail)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tests", "show", "test-9"])

    assert result.exit_code == 0
    assert captured["id"] == "test-9"
