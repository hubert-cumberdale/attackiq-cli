from __future__ import annotations

from typing import Any

import httpx
import pytest

from attackiq_cli.joiner import det_pipeline, det_pipeline_apply


def test_det_pipeline_preserves_apply_executor_exports() -> None:
    assert det_pipeline.GitLabClient is det_pipeline_apply.GitLabClient
    assert det_pipeline._is_retryable_gitlab is det_pipeline_apply._is_retryable_gitlab
    assert (
        det_pipeline._apply_attackiq_assessments
        is det_pipeline_apply._apply_attackiq_assessments
    )
    assert det_pipeline._apply_gitlab_updates is det_pipeline_apply._apply_gitlab_updates


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(400, False), (429, True), (500, True)],
)
def test_gitlab_retry_classification_for_http_statuses(
    status_code: int, expected: bool
) -> None:
    request = httpx.Request("PUT", "https://gitlab.example/api/v4/projects/1/issues/2")
    response = httpx.Response(status_code, request=request)
    error = httpx.HTTPStatusError("request failed", request=request, response=response)

    assert det_pipeline_apply._is_retryable_gitlab(error) is expected


def test_gitlab_retry_classification_accepts_request_errors() -> None:
    request = httpx.Request("PUT", "https://gitlab.example/api/v4/projects/1/issues/2")
    error = httpx.ConnectError("connection failed", request=request)

    assert det_pipeline_apply._is_retryable_gitlab(error) is True
    assert det_pipeline_apply._is_retryable_gitlab(ValueError("invalid")) is False


def test_apply_gitlab_updates_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_BASE_URL", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)

    with pytest.raises(
        ValueError,
        match="GITLAB_BASE_URL and GITLAB_TOKEN are required in apply mode",
    ):
        det_pipeline_apply._apply_gitlab_updates([], project_id="123")


def test_apply_gitlab_updates_closes_client_and_records_item_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class StubGitLabClient:
        closed = False

        def __init__(self, base_url: str, token: str) -> None:
            assert base_url == "https://gitlab.example"
            assert token == "secret-token"

        def update_issue(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            if kwargs["iid"] == "2":
                raise RuntimeError("update failed")
            return {"web_url": "https://gitlab.example/issues/1"}

        def close(self) -> None:
            self.closed = True

    client = StubGitLabClient("https://gitlab.example", "secret-token")
    monkeypatch.setenv("GITLAB_BASE_URL", "https://gitlab.example")
    monkeypatch.setenv("GITLAB_TOKEN", "secret-token")
    monkeypatch.setattr(det_pipeline_apply, "GitLabClient", lambda *_args: client)

    results = det_pipeline_apply._apply_gitlab_updates(
        [
            {"iid": "1", "final_labels": ["T1003"], "description": "one"},
            {"iid": "2", "final_labels": ["T1059"], "description": "two"},
        ],
        project_id="123",
    )

    assert results == [
        {
            "iid": "1",
            "status": "success",
            "web_url": "https://gitlab.example/issues/1",
        },
        {"iid": "2", "status": "failed", "error": "update failed"},
    ]
    assert calls == [
        {
            "project_id": "123",
            "iid": "1",
            "labels": ["T1003"],
            "description": "one",
        },
        {
            "project_id": "123",
            "iid": "2",
            "labels": ["T1059"],
            "description": "two",
        },
    ]
    assert client.closed is True


def test_apply_attackiq_assessments_uses_service_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = object()
    send_calls: list[dict[str, Any]] = []

    class StubResponse:
        def json(self) -> dict[str, str]:
            return {"id": "assessment-id"}

    class StubClient:
        def __enter__(self) -> StubClient:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def send(self, sent_operation: object, **kwargs: Any) -> StubResponse:
            assert sent_operation is operation
            send_calls.append(kwargs)
            return StubResponse()

    config = object()
    auth = object()
    monkeypatch.setattr(det_pipeline_apply, "load_config", lambda: config)
    monkeypatch.setattr(det_pipeline_apply, "resolve_base_url", lambda *_args: "https://api.example")
    monkeypatch.setattr(det_pipeline_apply, "build_auth_context", lambda *_args, **_kwargs: auth)
    monkeypatch.setattr(
        det_pipeline_apply,
        "build_det_pipeline_create_assessment_operation",
        lambda: operation,
    )
    monkeypatch.setattr(det_pipeline_apply, "build_client", lambda *_args, **_kwargs: StubClient())

    results = det_pipeline_apply._apply_attackiq_assessments(
        [{"assessment_name": "Assessment", "scenario_ids": ["scenario-id"]}]
    )

    assert results == [
        {
            "assessment_name": "Assessment",
            "created_id": "assessment-id",
            "status": "success",
        }
    ]
    assert send_calls == [
        {
            "path_params": {},
            "query_params": {},
            "headers": {},
            "json_body": {"name": "Assessment", "scenario_ids": ["scenario-id"]},
        }
    ]
