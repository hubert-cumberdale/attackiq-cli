"""Network mutation executors for the deterministic DET pipeline."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any, cast

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from attackiq_cli.config import load_config
from attackiq_cli.services import (
    build_auth_context,
    build_client,
    build_det_pipeline_create_assessment_operation,
    resolve_base_url,
)


def _is_retryable_gitlab(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return bool(isinstance(exc, httpx.RequestError))


class GitLabClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = httpx.Client(timeout=30.0)

    def close(self) -> None:
        self._client.close()

    @retry(
        retry=retry_if_exception(lambda exc: _is_retryable_gitlab(exc)),
        wait=wait_exponential(multiplier=0.5, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def update_issue(
        self, *, project_id: str, iid: str, labels: Sequence[str], description: str
    ) -> dict[str, Any]:
        url = f"{self.base_url}/api/v4/projects/{project_id}/issues/{iid}"
        response = self._client.put(
            url,
            headers={"PRIVATE-TOKEN": self.token},
            data={"labels": ",".join(labels), "description": description},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


def _apply_attackiq_assessments(plan: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    config = load_config()
    base_url = resolve_base_url(config, None)
    auth = build_auth_context(config, preferred_scheme="auto")
    operation = build_det_pipeline_create_assessment_operation()
    results: list[dict[str, Any]] = []
    with build_client(
        base_url,
        config,
        auth,
        insecure=False,
        timeout=None,
    ) as client:
        for item in plan:
            try:
                payload = {
                    "name": item["assessment_name"],
                    "scenario_ids": item["scenario_ids"],
                }
                response = client.send(
                    operation,
                    path_params={},
                    query_params={},
                    headers={},
                    json_body=payload,
                ).json()
                results.append(
                    {
                        "assessment_name": item["assessment_name"],
                        "created_id": str(
                            response.get("id") or response.get("project_id") or ""
                        ),
                        "status": "success",
                    }
                )
            except Exception as exc:  # pragma: no cover - network
                results.append(
                    {
                        "assessment_name": item["assessment_name"],
                        "created_id": "",
                        "status": "failed",
                        "error": str(exc),
                    }
                )
    return results


def _apply_gitlab_updates(
    patch_plan: Sequence[dict[str, Any]], *, project_id: str
) -> list[dict[str, Any]]:
    base_url = os.getenv("GITLAB_BASE_URL", "").strip()
    token = os.getenv("GITLAB_TOKEN", "").strip()
    if not base_url or not token:
        raise ValueError("GITLAB_BASE_URL and GITLAB_TOKEN are required in apply mode.")
    client = GitLabClient(base_url, token)
    results: list[dict[str, Any]] = []
    try:
        for item in patch_plan:
            iid = str(item["iid"])
            try:
                response = client.update_issue(
                    project_id=project_id,
                    iid=iid,
                    labels=item["final_labels"],
                    description=item["description"],
                )
                results.append(
                    {
                        "iid": iid,
                        "status": "success",
                        "web_url": response.get("web_url") or "",
                    }
                )
            except Exception as exc:  # pragma: no cover - network
                results.append({"iid": iid, "status": "failed", "error": str(exc)})
    finally:
        client.close()
    return results
