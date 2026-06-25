from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from attackiq_cli.client import paginate_results
from attackiq_cli.service_core import (
    ServiceContext,
    _normalize_filter,
    _optional_text,
    build_client,
    ensure_auth,
)


@dataclass(frozen=True)
class AssessmentFilters:
    asset_group_id: list[str] | None = None
    blueprint_id: str | None = None
    execution_strategy: int | None = None
    has_default_schedule: bool | None = None
    id__in: list[str] | None = None
    name: str | None = None
    report_instance_type: str | None = None
    search: str | None = None
    tag_id: str | None = None
    tag_ids: list[str] | None = None
    use_scenario_alert_rules: bool | None = None
    version: int | None = None
    zones_ordering: list[str] | None = None


@dataclass(frozen=True)
class TestFilters:
    name: str | None = None
    project_template_test_id: str | None = None
    run_in_hosted_agent_preferably: bool | None = None
    use_hosted_agent: bool | None = None


@dataclass(frozen=True)
class AssessmentSummary:
    assessment_id: str | None
    name: str | None
    assessment_type: str | None
    assessment_type_id: str | None
    assessment_type_name: str | None
    status: str | None
    created: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AssessmentSummary:
        assessment_type = payload.get("assessment_type")
        assessment_type_id: str | None = None
        assessment_type_name: str | None = None
        assessment_type_value = _optional_text(assessment_type)
        if isinstance(assessment_type, dict):
            assessment_type_id = _optional_text(
                assessment_type.get("id") or assessment_type.get("uuid")
            )
            assessment_type_name = _optional_text(
                assessment_type.get("name") or assessment_type.get("display_name")
            )
            if assessment_type_name:
                assessment_type_value = assessment_type_name
            elif assessment_type_id:
                assessment_type_value = assessment_type_id
            else:
                assessment_type_value = None

        return cls(
            assessment_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            assessment_type=assessment_type_value,
            assessment_type_id=assessment_type_id
            or _optional_text(payload.get("assessment_type_id")),
            assessment_type_name=assessment_type_name
            or _optional_text(payload.get("assessment_type_name")),
            status=_optional_text(payload.get("status")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.assessment_id,
            "name": self.name,
            "assessment_type": self.assessment_type,
            "assessment_type_id": self.assessment_type_id,
            "assessment_type_name": self.assessment_type_name,
            "status": self.status,
            "created": self.created,
            "modified": self.modified,
        }


@dataclass(frozen=True)
class TestSummary:
    test_id: str | None
    name: str | None
    description: str | None
    project: str | None
    runnable: str | None
    scheduled_count: str | None
    created: str | None
    modified: str | None
    use_hosted_agent: str | None
    use_pool_agent: str | None
    using_default_assets: str | None
    using_default_schedule: str | None
    order: str | None
    has_scenario_modules: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TestSummary:
        project = payload.get("project")
        project_value = _optional_text(project)
        if isinstance(project, dict):
            project_value = _optional_text(
                project.get("name")
                or project.get("display_name")
                or project.get("id")
                or project.get("uuid")
            )

        return cls(
            test_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            description=_optional_text(payload.get("description")),
            project=project_value,
            runnable=_optional_text(payload.get("runnable")),
            scheduled_count=_optional_text(payload.get("scheduled_count")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
            use_hosted_agent=_optional_text(payload.get("use_hosted_agent")),
            use_pool_agent=_optional_text(payload.get("use_pool_agent")),
            using_default_assets=_optional_text(payload.get("using_default_assets")),
            using_default_schedule=_optional_text(payload.get("using_default_schedule")),
            order=_optional_text(payload.get("order")),
            has_scenario_modules=_optional_text(payload.get("has_scenario_modules")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.test_id,
            "name": self.name,
            "description": self.description,
            "project": self.project,
            "runnable": self.runnable,
            "scheduled_count": self.scheduled_count,
            "created": self.created,
            "modified": self.modified,
            "use_hosted_agent": self.use_hosted_agent,
            "use_pool_agent": self.use_pool_agent,
            "using_default_assets": self.using_default_assets,
            "using_default_schedule": self.using_default_schedule,
            "order": self.order,
            "has_scenario_modules": self.has_scenario_modules,
        }


def _normalize_list(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    normalized: list[str] = []
    for value in values:
        if not value:
            continue
        parts = [part.strip() for part in value.split(",") if part.strip()]
        normalized.extend(parts)
    return normalized or None


def build_assessment_query_params(filters: AssessmentFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}

    asset_group_id = _normalize_list(filters.asset_group_id)
    id_in = _normalize_list(filters.id__in)
    tag_ids = _normalize_list(filters.tag_ids)
    zones_ordering = _normalize_list(filters.zones_ordering)
    if zones_ordering:
        allowed = {"attacker_zone", "-attacker_zone", "target_zone", "-target_zone"}
        invalid = [value for value in zones_ordering if value not in allowed]
        if invalid:
            raise ValueError(
                "zones-ordering must be one of: attacker_zone, -attacker_zone, "
                "target_zone, -target_zone."
            )

    if asset_group_id:
        params["asset_group_id"] = ",".join(asset_group_id)
    if (blueprint_id := _normalize_filter(filters.blueprint_id)) is not None:
        params["blueprint_id"] = blueprint_id
    if filters.execution_strategy is not None:
        if filters.execution_strategy not in {0, 1}:
            raise ValueError("execution-strategy must be 0 or 1.")
        params["execution_strategy"] = filters.execution_strategy
    if filters.has_default_schedule is not None:
        params["has_default_schedule"] = filters.has_default_schedule
    if id_in:
        params["id__in"] = ",".join(id_in)
    if (name := _normalize_filter(filters.name)) is not None:
        params["name"] = name
    if (report_instance_type := _normalize_filter(filters.report_instance_type)) is not None:
        params["report_instance_type"] = report_instance_type
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    if (tag_id := _normalize_filter(filters.tag_id)) is not None:
        params["tag_id"] = tag_id
    if tag_ids:
        params["tag_ids"] = ",".join(tag_ids)
    if filters.use_scenario_alert_rules is not None:
        params["use_scenario_alert_rules"] = filters.use_scenario_alert_rules
    if filters.version is not None:
        params["version"] = filters.version
    if zones_ordering:
        params["zones_ordering"] = ",".join(zones_ordering)
    return params


def build_test_query_params(filters: TestFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (name := _normalize_filter(filters.name)) is not None:
        params["name"] = name
    if (template_id := _normalize_filter(filters.project_template_test_id)) is not None:
        params["project_template_test_id"] = template_id
    if filters.run_in_hosted_agent_preferably is not None:
        params["run_in_hosted_agent_preferably"] = filters.run_in_hosted_agent_preferably
    if filters.use_hosted_agent is not None:
        params["use_hosted_agent"] = filters.use_hosted_agent
    return params


def build_assessment_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [AssessmentSummary.from_payload(item).to_record() for item in items]


def build_test_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [TestSummary.from_payload(item).to_record() for item in items]


def fetch_assessments_page(
    context: ServiceContext,
    *,
    page: int,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    op = context.spec.get_operation("v1_assessments_list")
    ensure_auth(op, context.auth)
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if query_params:
        params.update(query_params)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(op, path_params={}, query_params=params, headers={}).json()
    items = payload.get("results", [])
    return list(items), bool(payload.get("next"))


def fetch_assessment_detail(
    context: ServiceContext,
    *,
    assessment_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_assessments_retrieve")
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
            path_params={"id": assessment_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Assessment detail response must be an object.")
    return payload


def fetch_tests_page(
    context: ServiceContext,
    *,
    page: int,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    op = context.spec.get_operation("v1_tests_list")
    ensure_auth(op, context.auth)
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if query_params:
        params.update(query_params)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(op, path_params={}, query_params=params, headers={}).json()
    items = payload.get("results", [])
    return list(items), bool(payload.get("next"))


def fetch_test_detail(
    context: ServiceContext,
    *,
    test_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_tests_retrieve")
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
            path_params={"id": test_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Test detail response must be an object.")
    return payload


def list_assessments(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_assessments_list")
    if check_auth:
        ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        if page is None:
            return list(
                paginate_results(
                    client,
                    op,
                    page_size=page_size,
                    query_params=query_params or None,
                )
            )
        payload = client.send(
            op,
            path_params={},
            query_params={"page": page, "page_size": page_size, **(query_params or {})},
            headers={},
        ).json()
    return list(payload.get("results") or [])


def list_tests(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_tests_list")
    if check_auth:
        ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        if page is None:
            return list(
                paginate_results(
                    client,
                    op,
                    page_size=page_size,
                    query_params=query_params or None,
                )
            )
        payload = client.send(
            op,
            path_params={},
            query_params={"page": page, "page_size": page_size, **(query_params or {})},
            headers={},
        ).json()
    return list(payload.get("results") or [])
