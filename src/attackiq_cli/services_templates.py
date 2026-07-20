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
class TemplateFilters:
    search: str | None = None
    template_name: str | None = None
    project_name: str | None = None
    category: str | None = None
    assessment_type: str | None = None
    behavior: str | None = None


@dataclass(frozen=True)
class TemplateTestFilters:
    project_template_id: str | None = None


@dataclass(frozen=True)
class TemplateSummary:
    template_id: str | None
    template_name: str | None
    project_name: str | None
    project_template_type: str | None
    project_template_type_id: str | None
    project_template_type_name: str | None
    num_tests: str | None
    num_scenarios: str | None
    is_av2_compatible: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TemplateSummary:
        template_type = payload.get("project_template_type")
        template_type_id = _optional_text(payload.get("project_template_type_id"))
        template_type_name = _optional_text(payload.get("project_template_type_name"))
        template_type_value = _optional_text(template_type)
        if isinstance(template_type, dict):
            template_type_id = template_type_id or _optional_text(
                template_type.get("id") or template_type.get("uuid")
            )
            template_type_name = template_type_name or _optional_text(
                template_type.get("name") or template_type.get("display_name")
            )
            template_type_value = template_type_name or template_type_id

        return cls(
            template_id=_optional_text(payload.get("id")),
            template_name=_optional_text(payload.get("template_name")),
            project_name=_optional_text(payload.get("project_name")),
            project_template_type=template_type_value,
            project_template_type_id=template_type_id,
            project_template_type_name=template_type_name,
            num_tests=_optional_text(payload.get("num_tests")),
            num_scenarios=_optional_text(payload.get("num_scenarios")),
            is_av2_compatible=_optional_text(payload.get("is_av2_compatible")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.template_id,
            "template_name": self.template_name,
            "project_name": self.project_name,
            "project_template_type": self.project_template_type,
            "project_template_type_id": self.project_template_type_id,
            "project_template_type_name": self.project_template_type_name,
            "num_tests": self.num_tests,
            "num_scenarios": self.num_scenarios,
            "is_av2_compatible": self.is_av2_compatible,
            "modified": self.modified,
        }


@dataclass(frozen=True)
class TemplateTestSummary:
    template_test_id: str | None
    name: str | None
    description: str | None
    project_template: str | None
    scenario_count: str | None
    scenarios: str | None
    order: str | None
    created: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TemplateTestSummary:
        scenarios = payload.get("scenarios")
        scenario_count: str | None = None
        scenario_ids: str | None = _optional_text(scenarios)
        if isinstance(scenarios, list):
            scenario_count = str(len(scenarios))
            scenario_ids = ",".join(str(item).strip() for item in scenarios if str(item).strip())

        return cls(
            template_test_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            description=_optional_text(payload.get("description")),
            project_template=_optional_text(payload.get("project_template")),
            scenario_count=scenario_count,
            scenarios=scenario_ids,
            order=_optional_text(payload.get("order")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.template_test_id,
            "name": self.name,
            "description": self.description,
            "project_template": self.project_template,
            "scenario_count": self.scenario_count,
            "scenarios": self.scenarios,
            "order": self.order,
            "created": self.created,
            "modified": self.modified,
        }


def build_template_query_params(filters: TemplateFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    if (template_name := _normalize_filter(filters.template_name)) is not None:
        params["template_name"] = template_name
    if (project_name := _normalize_filter(filters.project_name)) is not None:
        params["project_name"] = project_name
    if (category := _normalize_filter(filters.category)) is not None:
        params["category"] = category
    if (assessment_type := _normalize_filter(filters.assessment_type)) is not None:
        params["assessment_type"] = assessment_type
    if (behavior := _normalize_filter(filters.behavior)) is not None:
        params["behavior"] = behavior
    return params


def build_template_test_query_params(filters: TemplateTestFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (project_template_id := _normalize_filter(filters.project_template_id)) is not None:
        params["project_template_id"] = project_template_id
    return params


def build_template_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [TemplateSummary.from_payload(item).to_record() for item in items]


def build_template_test_summary_records(
    items: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    return [TemplateTestSummary.from_payload(item).to_record() for item in items]


def fetch_templates_page(
    context: ServiceContext,
    *,
    page: int,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    op = context.spec.get_operation("v1_assessment_templates_list")
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
    if not isinstance(payload, dict):
        raise ValueError("Template list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Template list response results must be a list.")
    return list(items), bool(payload.get("next"))


def list_templates(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: TemplateFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_assessment_templates_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_template_query_params(filters)
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
    if not isinstance(payload, dict):
        raise ValueError("Template list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Template list response results must be a list.")
    return list(items)


def fetch_template_detail(
    context: ServiceContext,
    *,
    template_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_assessment_templates_retrieve")
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
            path_params={"id": template_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Template detail response must be an object.")
    return payload


def list_template_tests(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: TemplateTestFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_project_template_tests_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_template_test_query_params(filters)
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
    if not isinstance(payload, dict):
        raise ValueError("Template test list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Template test list response results must be a list.")
    return list(items)
