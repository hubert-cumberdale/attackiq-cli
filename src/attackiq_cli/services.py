from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

import httpx

from attackiq_cli.client import (
    AttackIQClient,
    paginate_results,
)
from attackiq_cli.config import ConfigError
from attackiq_cli.platform_api_adapter import create_platform_api_adapter
from attackiq_cli.service_core import (
    ServiceContext as ServiceContext,
)
from attackiq_cli.service_core import (
    _normalize_filter,
    _optional_nested_text,
    _optional_text,
)
from attackiq_cli.service_core import (
    build_auth_context as build_auth_context,
)
from attackiq_cli.service_core import (
    build_client as build_client,
)
from attackiq_cli.service_core import (
    ensure_auth as ensure_auth,
)
from attackiq_cli.service_core import (
    load_service_context as load_service_context,
)
from attackiq_cli.service_core import (
    resolve_base_url as resolve_base_url,
)
from attackiq_cli.service_core import (
    warn_if_insecure_base_url as warn_if_insecure_base_url,
)
from attackiq_cli.services_source_types import (
    SourceTypeFilters as SourceTypeFilters,
)
from attackiq_cli.services_source_types import (
    SourceTypeSummary as SourceTypeSummary,
)
from attackiq_cli.services_source_types import (
    build_source_type_query_params as build_source_type_query_params,
)
from attackiq_cli.services_source_types import (
    build_source_type_summary_records as build_source_type_summary_records,
)
from attackiq_cli.services_source_types import (
    list_source_types as list_source_types,
)
from attackiq_cli.services_tags import (
    AmbiguousTagError as AmbiguousTagError,
)
from attackiq_cli.services_tags import (
    TagChoice as TagChoice,
)
from attackiq_cli.services_tags import (
    TagFilters as TagFilters,
)
from attackiq_cli.services_tags import (
    TagSummary as TagSummary,
)
from attackiq_cli.services_tags import (
    build_tag_query_params as build_tag_query_params,
)
from attackiq_cli.services_tags import (
    build_tag_summary_records as build_tag_summary_records,
)
from attackiq_cli.services_tags import (
    fetch_tag_detail as fetch_tag_detail,
)
from attackiq_cli.services_tags import (
    list_tags as list_tags,
)
from attackiq_cli.services_tags import (
    resolve_tag_filter as resolve_tag_filter,
)
from attackiq_cli.services_tags import (
    search_tags as search_tags,
)
from attackiq_cli.spec import Operation

API_BACKEND_NATIVE = "native"
API_BACKEND_PLATFORM_API = "platform-api"
VALID_API_BACKENDS = {API_BACKEND_NATIVE, API_BACKEND_PLATFORM_API}
T = TypeVar("T")


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


@dataclass(frozen=True)
class ScenarioFilters:
    order_by: str | None = None
    search: str | None = None
    tag: str | None = None
    name: str | None = None
    modified_after: str | None = None
    last_updated: str | None = None
    mitre_platforms: str | None = None
    hierarchy: str | None = None
    object_fingerprint: str | None = None
    parameters_description: str | None = None
    scenario_template_instance: str | None = None


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
class AssetFilters:
    search: str | None = None
    hostname: str | None = None
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    deployment_state_id: int | None = None
    deepsurface_last_seen_in_host_analysis_at: str | None = None
    deepsurface_sync_state: str | None = None
    deepsurface_sync_state_changed_at: str | None = None
    asset_group: str | None = None
    activity_type: str | None = None
    ordering: str | None = None


@dataclass(frozen=True)
class AssetGroupFilters:
    search: str | None = None
    asset_group_id: str | None = None
    name: str | None = None
    description: str | None = None
    company: str | None = None
    company_id: str | None = None
    user: str | None = None
    user_id: str | None = None
    created: str | None = None
    created_after: str | None = None
    modified: str | None = None
    ordering: str | None = None


@dataclass(frozen=True)
class BlueprintFilters:
    search: str | None = None


@dataclass(frozen=True)
class IntegrationConnectorFilters:
    alert_correlation_plan: str | None = None
    company_connector_manager_setup: str | None = None
    company_connector_manager_setup_id: str | None = None
    description: str | None = None
    display_name: str | None = None
    implemented_mixins: str | None = None
    is_deleted: bool | None = None
    mode: str | None = None
    mttd_timezone: str | None = None
    status: str | None = None
    ordering: str | None = None


def normalize_api_backend(value: str | None) -> str:
    normalized = (value or API_BACKEND_NATIVE).strip().lower()
    if normalized not in VALID_API_BACKENDS:
        raise ValueError("api-backend must be one of: native, platform-api.")
    return normalized


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


@dataclass(frozen=True)
class ScenarioSummary:
    scenario_id: str | None
    name: str | None
    scenario_type: str | None
    description: str | None
    created: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ScenarioSummary:
        return cls(
            scenario_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            scenario_type=_optional_text(payload.get("scenario_type")),
            description=_optional_text(payload.get("description")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.scenario_id,
            "name": self.name,
            "scenario_type": self.scenario_type,
            "description": self.description,
            "created": self.created,
            "modified": self.modified,
        }


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


@dataclass(frozen=True)
class AssetSummary:
    asset_id: str | None
    hostname: str | None
    activity_type: str | None
    deployment_state: str | None
    ipv4_address: str | None
    ipv6_address: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AssetSummary:
        deployment = payload.get("deployment_state")
        deployment_state = _optional_text(deployment)
        if isinstance(deployment, dict):
            deployment_state = _optional_text(
                deployment.get("name")
                or deployment.get("display_name")
                or deployment.get("id")
                or deployment.get("state")
            )

        return cls(
            asset_id=_optional_text(payload.get("id")),
            hostname=_optional_text(payload.get("hostname") or payload.get("name")),
            activity_type=_optional_text(payload.get("activity_type")),
            deployment_state=deployment_state,
            ipv4_address=_optional_text(payload.get("ipv4_address")),
            ipv6_address=_optional_text(payload.get("ipv6_address")),
            modified=_optional_text(payload.get("modified") or payload.get("updated_at")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.asset_id,
            "hostname": self.hostname,
            "activity_type": self.activity_type,
            "deployment_state": self.deployment_state,
            "ipv4_address": self.ipv4_address,
            "ipv6_address": self.ipv6_address,
            "modified": self.modified,
        }


@dataclass(frozen=True)
class AssetGroupSummary:
    asset_group_id: str | None
    name: str | None
    description: str | None
    user_id: str | None
    num_assets: str | None
    created: str | None
    modified: str | None
    created_by: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AssetGroupSummary:
        return cls(
            asset_group_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            description=_optional_text(payload.get("description")),
            user_id=_optional_text(payload.get("user_id")),
            num_assets=_optional_text(payload.get("num_assets")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
            created_by=_optional_text(payload.get("created_by")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.asset_group_id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "num_assets": self.num_assets,
            "created": self.created,
            "modified": self.modified,
            "created_by": self.created_by,
        }


@dataclass(frozen=True)
class BlueprintSummary:
    blueprint_id: str | None
    name: str | None
    blueprint_template: str | None
    company: str | None
    has_modules: str | None
    modules: str | None
    created: str | None
    modified: str | None
    source_content_changed: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> BlueprintSummary:
        return cls(
            blueprint_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            blueprint_template=_optional_text(payload.get("blueprint_template")),
            company=_optional_text(payload.get("company")),
            has_modules=_optional_text(payload.get("has_modules")),
            modules=_optional_text(payload.get("modules")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
            source_content_changed=_optional_text(payload.get("source_content_changed")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.blueprint_id,
            "name": self.name,
            "blueprint_template": self.blueprint_template,
            "company": self.company,
            "has_modules": self.has_modules,
            "modules": self.modules,
            "created": self.created,
            "modified": self.modified,
            "source_content_changed": self.source_content_changed,
        }


@dataclass(frozen=True)
class IntegrationConnectorSummary:
    connector_instance_id: str | None
    display_name: str | None
    status: str | None
    enabled: str | None
    active: str | None
    pending: str | None
    mode: str | None
    connector_id: str | None
    connector_name: str | None
    connector_type_id: str | None
    connector_type_name: str | None
    vendor_product_id: str | None
    vendor_product_name: str | None
    company_id: str | None
    company_name: str | None
    source_type_count: str | None
    last_checkin: str | None
    running_version: str | None
    created: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> IntegrationConnectorSummary:
        connector = payload.get("connector")
        vendor_product: Any = None
        connector_type: Any = None
        if isinstance(connector, dict):
            vendor_product = connector.get("vendor_product")
            connector_type = connector.get("connector_type")

        company = payload.get("company")
        source_types = payload.get("source_types")
        source_type_count = str(len(source_types)) if isinstance(source_types, list) else None

        return cls(
            connector_instance_id=_optional_text(payload.get("id")),
            display_name=_optional_text(payload.get("display_name")),
            status=_optional_text(payload.get("status")),
            enabled=_optional_text(payload.get("enabled")),
            active=_optional_text(payload.get("active")),
            pending=_optional_text(payload.get("pending")),
            mode=_optional_text(payload.get("mode")),
            connector_id=_optional_nested_text(connector, "id"),
            connector_name=_optional_nested_text(connector, "name"),
            connector_type_id=_optional_nested_text(connector_type, "id"),
            connector_type_name=_optional_nested_text(connector_type, "name"),
            vendor_product_id=_optional_nested_text(vendor_product, "id"),
            vendor_product_name=_optional_nested_text(vendor_product, "name"),
            company_id=_optional_nested_text(company, "id"),
            company_name=_optional_nested_text(company, "display_name")
            or _optional_nested_text(company, "name"),
            source_type_count=source_type_count,
            last_checkin=_optional_text(payload.get("last_checkin")),
            running_version=_optional_text(payload.get("running_version")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "id": self.connector_instance_id,
            "display_name": self.display_name,
            "status": self.status,
            "enabled": self.enabled,
            "active": self.active,
            "pending": self.pending,
            "mode": self.mode,
            "connector_id": self.connector_id,
            "connector_name": self.connector_name,
            "connector_type_id": self.connector_type_id,
            "connector_type_name": self.connector_type_name,
            "vendor_product_id": self.vendor_product_id,
            "vendor_product_name": self.vendor_product_name,
            "company_id": self.company_id,
            "company_name": self.company_name,
            "source_type_count": self.source_type_count,
            "last_checkin": self.last_checkin,
            "running_version": self.running_version,
            "created": self.created,
            "modified": self.modified,
        }


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


def build_scenario_query_params(filters: ScenarioFilters) -> dict[str, str]:
    params: dict[str, str] = {}
    modified_after = _normalize_filter(filters.modified_after)
    last_updated = _normalize_filter(filters.last_updated)
    if modified_after and last_updated and modified_after != last_updated:
        raise ValueError("modified-after and last-updated cannot both be set to different values.")
    for key, value in {
        "order_by": filters.order_by,
        "search": filters.search,
        "name": filters.name,
        "mitre_platforms": filters.mitre_platforms,
        "hierarchy": filters.hierarchy,
        "object_fingerprint": filters.object_fingerprint,
        "parameters_description": filters.parameters_description,
        "scenario_template_instance": filters.scenario_template_instance,
    }.items():
        normalized = _normalize_filter(value)
        if normalized is not None:
            params[key] = normalized
    if modified_after or last_updated:
        params["modified_after"] = modified_after or last_updated or ""
    return params


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


def build_asset_query_params(filters: AssetFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    if (hostname := _normalize_filter(filters.hostname)) is not None:
        params["hostname"] = hostname
    if (ipv4_address := _normalize_filter(filters.ipv4_address)) is not None:
        params["ipv4_address"] = ipv4_address
    if (ipv6_address := _normalize_filter(filters.ipv6_address)) is not None:
        params["ipv6_address"] = ipv6_address
    if filters.deployment_state_id is not None:
        params["deployment_state_id"] = filters.deployment_state_id
    if (
        deepsurface_last_seen := _normalize_filter(
            filters.deepsurface_last_seen_in_host_analysis_at
        )
    ) is not None:
        params["deepsurface_last_seen_in_host_analysis_at"] = deepsurface_last_seen
    if (deepsurface_sync_state := _normalize_filter(filters.deepsurface_sync_state)) is not None:
        params["deepsurface_sync_state"] = deepsurface_sync_state
    if (
        deepsurface_sync_state_changed := _normalize_filter(
            filters.deepsurface_sync_state_changed_at
        )
    ) is not None:
        params["deepsurface_sync_state_changed_at"] = deepsurface_sync_state_changed
    if (asset_group := _normalize_filter(filters.asset_group)) is not None:
        params["asset_group"] = asset_group
    if (activity_type := _normalize_filter(filters.activity_type)) is not None:
        normalized_type = activity_type.upper()
        allowed = {"DEVICE", "DOMAIN", "TESTPOINT"}
        if normalized_type not in allowed:
            raise ValueError("activity-type must be one of: DEVICE, DOMAIN, TESTPOINT.")
        params["activity_type"] = normalized_type
    if (ordering := _normalize_filter(filters.ordering)) is not None:
        params["ordering"] = ordering
    return params


def build_asset_group_query_params(filters: AssetGroupFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    if (asset_group_id := _normalize_filter(filters.asset_group_id)) is not None:
        params["id"] = asset_group_id
    if (name := _normalize_filter(filters.name)) is not None:
        params["name"] = name
    if (description := _normalize_filter(filters.description)) is not None:
        params["description"] = description
    if (company := _normalize_filter(filters.company)) is not None:
        params["company"] = company
    if (company_id := _normalize_filter(filters.company_id)) is not None:
        params["company_id"] = company_id
    if (user := _normalize_filter(filters.user)) is not None:
        params["user"] = user
    if (user_id := _normalize_filter(filters.user_id)) is not None:
        params["user_id"] = user_id
    if (created := _normalize_filter(filters.created)) is not None:
        params["created"] = created
    if (created_after := _normalize_filter(filters.created_after)) is not None:
        params["created_after"] = created_after
    if (modified := _normalize_filter(filters.modified)) is not None:
        params["modified"] = modified
    if (ordering := _normalize_filter(filters.ordering)) is not None:
        params["ordering"] = ordering
    return params


def build_blueprint_query_params(filters: BlueprintFilters) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (search := _normalize_filter(filters.search)) is not None:
        params["search"] = search
    return params


def build_integration_connector_query_params(
    filters: IntegrationConnectorFilters,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (plan := _normalize_filter(filters.alert_correlation_plan)) is not None:
        params["alert_correlation_plan"] = plan
    if (setup := _normalize_filter(filters.company_connector_manager_setup)) is not None:
        params["company_connector_manager_setup"] = setup
    if (setup_id := _normalize_filter(filters.company_connector_manager_setup_id)) is not None:
        params["company_connector_manager_setup_id"] = setup_id
    if (description := _normalize_filter(filters.description)) is not None:
        params["description"] = description
    if (display_name := _normalize_filter(filters.display_name)) is not None:
        params["display_name"] = display_name
    if (implemented_mixins := _normalize_filter(filters.implemented_mixins)) is not None:
        params["implemented_mixins"] = implemented_mixins
    if filters.is_deleted is not None:
        params["is_deleted"] = filters.is_deleted
    if (mode := _normalize_filter(filters.mode)) is not None:
        allowed_modes = {"Ad Hoc": "Ad Hoc", "Automatic": "Automatic"}
        normalized_mode = allowed_modes.get(mode) or allowed_modes.get(mode.title())
        if normalized_mode is None:
            raise ValueError("mode must be one of: Ad Hoc, Automatic.")
        params["mode"] = normalized_mode
    if (mttd_timezone := _normalize_filter(filters.mttd_timezone)) is not None:
        params["mttd_timezone"] = mttd_timezone
    if (status := _normalize_filter(filters.status)) is not None:
        normalized_status = status.upper()
        allowed_statuses = {
            "ACTIVE",
            "DISABLED",
            "ERROR",
            "PENDING",
            "TESTING",
            "TEST_FAILED",
            "TRANSIENT",
        }
        if normalized_status not in allowed_statuses:
            raise ValueError(
                "status must be one of: ACTIVE, DISABLED, ERROR, PENDING, TESTING, "
                "TEST_FAILED, TRANSIENT."
            )
        params["status"] = normalized_status
    if (ordering := _normalize_filter(filters.ordering)) is not None:
        params["ordering"] = ordering
    return params


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


def build_scenarios_query_params(
    context: ServiceContext,
    *,
    filters: ScenarioFilters,
    insecure: bool,
    timeout: float | None,
    client: AttackIQClient,
) -> dict[str, Any]:
    params = build_scenario_query_params(filters)
    normalized_tag = _normalize_filter(filters.tag)
    if normalized_tag:
        resolved_tag = resolve_tag_filter(
            context,
            tag=normalized_tag,
            insecure=insecure,
            timeout=timeout,
            client=client,
        )
        if resolved_tag:
            params["tag"] = resolved_tag
    return params


def build_det_pipeline_create_assessment_operation() -> Operation:
    # This endpoint is used by the joiner det-pipeline apply mode but is not currently
    # represented in the bundled OpenAPI schema.
    return Operation(
        operation_id="det_pipeline_create_assessment",
        method="post",
        path="/v1/assessments",
        summary="Create assessment",
        parameters=[],
        request_body=None,
        tags=["assessments"],
        security=[{"Account Token": []}, {"JSON Web Token": []}],
    )


def build_scenario_template_upload_operation() -> Operation:
    # Captured from the Scenario Development UI because this endpoint is not currently
    # represented in the bundled OpenAPI schema. The UI posts multipart form-data with
    # the uploaded Scenario Wizard package under the `zip_file` field.
    return Operation(
        operation_id="scenario_template_upload",
        method="post",
        path="/v1/scenario_templates",
        summary="Upload custom scenario template package",
        parameters=[],
        request_body=None,
        tags=["scenarios"],
        security=[{"Account Token": []}, {"JSON Web Token": []}],
    )


def build_template_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [TemplateSummary.from_payload(item).to_record() for item in items]


def build_template_test_summary_records(
    items: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    return [TemplateTestSummary.from_payload(item).to_record() for item in items]


def build_scenario_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [ScenarioSummary.from_payload(item).to_record() for item in items]


def build_assessment_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [AssessmentSummary.from_payload(item).to_record() for item in items]


def build_test_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [TestSummary.from_payload(item).to_record() for item in items]


def build_asset_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [AssetSummary.from_payload(item).to_record() for item in items]


def build_asset_group_summary_records(
    items: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    return [AssetGroupSummary.from_payload(item).to_record() for item in items]


def build_blueprint_summary_records(items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [BlueprintSummary.from_payload(item).to_record() for item in items]


def build_integration_connector_summary_records(
    items: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    return [IntegrationConnectorSummary.from_payload(item).to_record() for item in items]


def health_check(
    context: ServiceContext,
    *,
    insecure: bool,
    timeout: float | None,
) -> tuple[bool, str]:
    op = context.spec.get_operation("v1_scenarios_list")
    try:
        ensure_auth(op, context.auth)
        with build_client(
            context.base_url,
            context.config,
            context.auth,
            insecure=insecure,
            timeout=timeout,
        ) as client:
            client.send(
                op,
                path_params={},
                query_params={"page": 1, "page_size": 1},
                headers={},
            )
        return True, "OK"
    except (ConfigError, httpx.HTTPError, ValueError) as exc:
        return False, str(exc)


def fetch_scenarios_page(
    context: ServiceContext,
    *,
    page: int,
    page_size: int,
    filters: ScenarioFilters,
    insecure: bool,
    timeout: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    op = context.spec.get_operation("v1_scenarios_list")
    ensure_auth(op, context.auth)
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        resolved_params = build_scenarios_query_params(
            context,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
            client=client,
        )
        if resolved_params:
            params.update(resolved_params)
        payload = client.send(op, path_params={}, query_params=params, headers={}).json()
    items = payload.get("results", [])
    return list(items), bool(payload.get("next"))


def fetch_scenario_detail(
    context: ServiceContext,
    *,
    scenario_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_scenarios_retrieve")
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
            path_params={"id": scenario_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Scenario detail response must be an object.")
    return payload


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


def fetch_assets_page(
    context: ServiceContext,
    *,
    page: int,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    op = context.spec.get_operation("v1_assets_list")
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


def fetch_asset_detail(
    context: ServiceContext,
    *,
    asset_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_assets_retrieve")
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
            path_params={"id": asset_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Asset detail response must be an object.")
    return payload


def list_asset_groups(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: AssetGroupFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_asset_groups_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_asset_group_query_params(filters)
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
        raise ValueError("Asset group list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Asset group list response results must be a list.")
    return list(items)


def fetch_asset_group_detail(
    context: ServiceContext,
    *,
    asset_group_id: str,
    insecure: bool,
    timeout: float | None,
) -> dict[str, Any]:
    op = context.spec.get_operation("v1_asset_groups_retrieve")
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
            path_params={"id": asset_group_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Asset group detail response must be an object.")
    return payload


def list_blueprints(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: BlueprintFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_blueprints_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_blueprint_query_params(filters)
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
        raise ValueError("Blueprint list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Blueprint list response results must be a list.")
    return list(items)


def list_integration_connectors(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: IntegrationConnectorFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_company_connectors_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_integration_connector_query_params(filters)
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
        raise ValueError("Integration connector list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("Integration connector list response results must be a list.")
    return list(items)


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


def list_assets(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
    api_backend: str = API_BACKEND_NATIVE,
) -> list[dict[str, Any]]:
    api_backend = normalize_api_backend(api_backend)
    if api_backend == API_BACKEND_PLATFORM_API:
        return _run_async(
            lambda: _list_assets_with_platform_api(
                context,
                page=page,
                page_size=page_size,
                query_params=query_params,
                insecure=insecure,
                timeout=timeout,
                check_auth=check_auth,
            )
        )

    op = context.spec.get_operation("v1_assets_list")
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


def list_scenarios(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: ScenarioFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
    api_backend: str = API_BACKEND_NATIVE,
) -> list[dict[str, Any]]:
    api_backend = normalize_api_backend(api_backend)
    if api_backend == API_BACKEND_PLATFORM_API:
        return _run_async(
            lambda: _list_scenarios_with_platform_api(
                context,
                page=page,
                page_size=page_size,
                filters=filters,
                insecure=insecure,
                timeout=timeout,
                check_auth=check_auth,
            )
        )

    op = context.spec.get_operation("v1_scenarios_list")
    if check_auth:
        ensure_auth(op, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        query_params = build_scenarios_query_params(
            context,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
            client=client,
        )
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


def _run_async(factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    coroutine = factory()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    coroutine.close()
    raise ValueError("platform-api backend cannot run from an active asyncio event loop.")


async def _list_scenarios_with_platform_api(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: ScenarioFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_scenarios_list")
    if check_auth:
        ensure_auth(op, context.auth)
    _validate_platform_scenario_filters(filters)
    query = _normalize_filter(filters.search)
    ordering = _normalize_filter(filters.order_by) or "-modified"
    async with create_platform_api_adapter(
        context,
        insecure=insecure,
        timeout=timeout,
    ) as adapter:
        if page is not None:
            payload = await adapter.search_scenarios(
                query=query,
                limit=page_size,
                offset=(page - 1) * page_size,
                ordering=ordering,
            )
            return _platform_payload_results(payload)

        results: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = await adapter.search_scenarios(
                query=query,
                limit=page_size,
                offset=offset,
                ordering=ordering,
            )
            batch = _platform_payload_results(payload)
            results.extend(batch)
            total_count = _platform_payload_count(payload)
            if not batch or len(batch) < page_size:
                return results
            if total_count is not None and len(results) >= total_count:
                return results
            offset += page_size


async def _list_assets_with_platform_api(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    query_params: dict[str, Any] | None,
    insecure: bool,
    timeout: float | None,
    check_auth: bool,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_assets_list")
    if check_auth:
        ensure_auth(op, context.auth)
    search, deployment_state, ordering = _platform_asset_filters(query_params)
    async with create_platform_api_adapter(
        context,
        insecure=insecure,
        timeout=timeout,
    ) as adapter:
        if page is not None:
            payload = await adapter.search_assets(
                query=search,
                limit=page_size,
                offset=(page - 1) * page_size,
                ordering=ordering,
                deployment_state=deployment_state,
            )
            return _platform_payload_results(payload)

        results: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = await adapter.search_assets(
                query=search,
                limit=page_size,
                offset=offset,
                ordering=ordering,
                deployment_state=deployment_state,
            )
            batch = _platform_payload_results(payload)
            results.extend(batch)
            total_count = _platform_payload_count(payload)
            if not batch or len(batch) < page_size:
                return results
            if total_count is not None and len(results) >= total_count:
                return results
            offset += page_size


def _validate_platform_scenario_filters(filters: ScenarioFilters) -> None:
    modified_after = _normalize_filter(filters.modified_after) or _normalize_filter(
        filters.last_updated
    )
    unsupported = [
        name
        for name, value in (
            ("tag", filters.tag),
            ("name", filters.name),
            ("modified_after", modified_after),
            ("mitre_platforms", filters.mitre_platforms),
            ("hierarchy", filters.hierarchy),
            ("object_fingerprint", filters.object_fingerprint),
            ("parameters_description", filters.parameters_description),
            ("scenario_template_instance", filters.scenario_template_instance),
        )
        if _normalize_filter(value) is not None
    ]
    if unsupported:
        raise ValueError(
            "platform-api backend currently supports only scenario search and order-by filters; "
            f"unsupported: {', '.join(unsupported)}."
        )


def _platform_asset_filters(
    query_params: dict[str, Any] | None,
) -> tuple[str | None, int | str | None, str | None]:
    query_params = query_params or {}
    supported = {"search", "deployment_state_id", "ordering"}
    unsupported = sorted(set(query_params) - supported)
    if unsupported:
        raise ValueError(
            "platform-api backend currently supports only asset search, deployment-state-id, "
            f"and ordering filters; unsupported: {', '.join(unsupported)}."
        )
    search = _normalize_filter(str(query_params["search"])) if "search" in query_params else None
    ordering = (
        _normalize_filter(str(query_params["ordering"])) if "ordering" in query_params else None
    )
    deployment_state = query_params.get("deployment_state_id")
    return search, deployment_state, ordering


def _platform_payload_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_results = payload.get("results") or []
    if not isinstance(raw_results, list):
        raise ValueError("platform-api payload results must be a list.")
    results: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            raise ValueError("platform-api payload results must contain objects.")
        results.append(item)
    return results


def _platform_payload_count(payload: dict[str, Any]) -> int | None:
    count = payload.get("count")
    if isinstance(count, int) and count >= 0:
        return count
    return None


def create_assessment_from_scenarios(
    context: ServiceContext,
    *,
    name: str,
    scenario_ids: list[str],
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> dict[str, Any]:
    """Create an assessment by name + scenario_ids.

    This endpoint is used by det-pipeline apply mode and is intentionally represented
    in code (not the bundled OpenAPI).
    """
    operation = build_det_pipeline_create_assessment_operation()
    if check_auth:
        ensure_auth(operation, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            operation,
            path_params={},
            query_params={},
            headers={},
            json_body={"name": name, "scenario_ids": scenario_ids},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Create assessment response must be an object.")
    return payload


def create_assessment_from_template(
    context: ServiceContext,
    *,
    template_id: str,
    project_name: str,
    blueprint_id: str | None,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> dict[str, Any]:
    operation = context.spec.get_operation("v1_assessments_project_from_template_create")
    if check_auth:
        ensure_auth(operation, context.auth)
    body: dict[str, Any] = {
        "template": template_id,
        "project_name": project_name,
    }
    if blueprint_id is not None:
        body["blueprint"] = blueprint_id
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            operation,
            path_params={},
            query_params={},
            headers={},
            json_body=body,
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Create assessment from template response must be an object.")
    return payload


def run_assessment(
    context: ServiceContext,
    *,
    assessment_id: str,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> dict[str, Any]:
    operation = context.spec.get_operation("v1_assessments_run_all_create")
    if check_auth:
        ensure_auth(operation, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            operation,
            path_params={"id": assessment_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Run assessment response must be an object.")
    return payload


def update_assessment_defaults(
    context: ServiceContext,
    *,
    assessment_id: str,
    assets: str | None,
    asset_groups: str | None,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> dict[str, Any]:
    operation = context.spec.get_operation("v1_assessments_update_defaults_create")
    if check_auth:
        ensure_auth(operation, context.auth)
    body: dict[str, str] = {}
    if assets:
        body["assets"] = assets
    if asset_groups:
        body["asset_groups"] = asset_groups
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            operation,
            path_params={"id": assessment_id},
            query_params={},
            headers={},
            json_body=body,
        ).json()
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return {"message": payload}
    return {"result": payload}


def create_test(
    context: ServiceContext,
    *,
    assessment_id: str,
    name: str,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> dict[str, Any]:
    operation = context.spec.get_operation("v1_tests_create")
    if check_auth:
        ensure_auth(operation, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            operation,
            path_params={},
            query_params={},
            headers={},
            json_body={"project": assessment_id, "name": name},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Create test response must be an object.")
    return payload


def add_scenarios_to_test(
    context: ServiceContext,
    *,
    test_id: str,
    scenario_ids: list[str],
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> dict[str, Any]:
    operation = context.spec.get_operation("v1_tests_bulk_add_scenarios_create")
    if check_auth:
        ensure_auth(operation, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            operation,
            path_params={"id": test_id},
            query_params={},
            headers={},
            json_body={"include": scenario_ids},
        ).json()
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return {"message": payload}
    return {"result": payload}


def get_test_status(
    context: ServiceContext,
    *,
    test_id: str,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> dict[str, Any]:
    operation = context.spec.get_operation("v1_tests_get_status_retrieve")
    if check_auth:
        ensure_auth(operation, context.auth)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            operation,
            path_params={"id": test_id},
            query_params={},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("Test status response must be an object.")
    return payload
