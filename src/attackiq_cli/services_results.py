from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from attackiq_cli.service_core import (
    ServiceContext,
    _normalize_filter,
    build_client,
    ensure_auth,
)


class ResultsMode(Enum):
    SUMMARIES = "summaries"
    PHASES = "phases"
    LOGS = "logs"


@dataclass(frozen=True)
class ValidationResultFilters:
    days: int | None = None
    project_ids: str | None = None
    scope_id: str | None = None
    tag_ids: str | None = None


def build_results_list_query(
    *,
    mode: ResultsMode,
    page: int,
    page_size: int,
    search: str | None = None,
    tag_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    normalized_tag_id = _normalize_filter(tag_id)
    if mode == ResultsMode.SUMMARIES:
        params["assessment_results"] = True
        if normalized_tag_id is not None:
            params["tag_id"] = normalized_tag_id
        operation_id = "v1_results_list"
    elif mode == ResultsMode.PHASES:
        if normalized_tag_id is not None:
            raise ValueError("tag_id is only supported for results summaries.")
        operation_id = "v1_phase_results_list"
    else:
        if normalized_tag_id is not None:
            raise ValueError("tag_id is only supported for results summaries.")
        operation_id = "v1_phase_logs_list"
    if search and mode != ResultsMode.SUMMARIES:
        params["search"] = search
    return operation_id, params


def build_validation_results_query_params(
    filters: ValidationResultFilters,
    *,
    page: int | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["page_size"] = page_size
    if filters.days is not None:
        params["days"] = filters.days
    for key, value in {
        "project_ids": filters.project_ids,
        "scope_id": filters.scope_id,
        "tag_ids": filters.tag_ids,
    }.items():
        normalized = _normalize_filter(value)
        if normalized is not None:
            params[key] = normalized
    return params


def _build_join_query_params(
    result_summary_id: str | None,
    scenario_job_id: str | None,
) -> dict[str, Any]:
    if result_summary_id:
        return {"result_summary_id": result_summary_id}
    if scenario_job_id:
        return {"scenario_job_id": scenario_job_id}
    return {}


def _records_from_validation_payload(payload: Any) -> tuple[list[dict[str, Any]], bool]:
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)], bool(payload.get("next"))
        raise ValueError("Validation results response must contain a results list or be a list.")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], False
    raise ValueError("Validation results response must contain a results list or be a list.")


def fetch_results_list(
    context: ServiceContext,
    *,
    mode: ResultsMode,
    page: int,
    page_size: int,
    search: str | None,
    insecure: bool,
    timeout: float | None,
    tag_id: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    operation_id, params = build_results_list_query(
        mode=mode,
        page=page,
        page_size=page_size,
        search=search,
        tag_id=tag_id,
    )
    op = context.spec.get_operation(operation_id)
    ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            op,
            path_params={},
            query_params=params,
            headers={},
        ).json()
    return list(payload.get("results") or []), bool(payload.get("next"))


def fetch_validation_results(
    context: ServiceContext,
    *,
    by_asset: bool,
    page: int,
    page_size: int,
    filters: ValidationResultFilters,
    insecure: bool,
    timeout: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    operation_id = (
        "v1_validation_results_by_asset_retrieve"
        if by_asset
        else "v1_validation_results_retrieve"
    )
    op = context.spec.get_operation(operation_id)
    ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            op,
            path_params={},
            query_params=build_validation_results_query_params(
                filters,
                page=page,
                page_size=page_size,
            ),
            headers={},
        ).json()
    return _records_from_validation_payload(payload)


def fetch_validation_result_executions(
    context: ServiceContext,
    *,
    asset_id: str | None = None,
    scenario_id: str | None = None,
    filters: ValidationResultFilters,
    insecure: bool,
    timeout: float | None,
) -> list[dict[str, Any]]:
    if bool(asset_id) == bool(scenario_id):
        raise ValueError("Provide exactly one of asset_id or scenario_id.")
    if asset_id is not None:
        operation_id = "v1_validation_results_asset_executions_retrieve"
        path_params: dict[str, str] = {"asset_id": asset_id}
    else:
        assert scenario_id is not None
        operation_id = "v1_validation_results_scenario_executions_retrieve"
        path_params = {"scenario_id": scenario_id}
    op = context.spec.get_operation(operation_id)
    ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            op,
            path_params=path_params,
            query_params=build_validation_results_query_params(filters),
            headers={},
        ).json()
    records, _has_next = _records_from_validation_payload(payload)
    return records


def fetch_phase_results(
    context: ServiceContext,
    *,
    result_summary_id: str | None = None,
    scenario_job_id: str | None = None,
    page: int = 1,
    page_size: int | None = None,
    insecure: bool,
    timeout: float | None,
) -> list[dict[str, Any]]:
    params = _build_join_query_params(result_summary_id, scenario_job_id)
    if not params:
        return []
    params["page"] = page
    params["page_size"] = page_size or 200
    op = context.spec.get_operation("v1_phase_results_list")
    ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            op,
            path_params={},
            query_params=params,
            headers={},
        ).json()
    return list(payload.get("results") or [])


def fetch_phase_logs(
    context: ServiceContext,
    *,
    result_summary_id: str | None = None,
    scenario_job_id: str | None = None,
    page: int = 1,
    page_size: int | None = None,
    insecure: bool,
    timeout: float | None,
) -> list[dict[str, Any]]:
    params = _build_join_query_params(result_summary_id, scenario_job_id)
    if not params:
        return []
    params["page"] = page
    params["page_size"] = page_size or 200
    op = context.spec.get_operation("v1_phase_logs_list")
    ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            op,
            path_params={},
            query_params=params,
            headers={},
        ).json()
    return list(payload.get("results") or [])
