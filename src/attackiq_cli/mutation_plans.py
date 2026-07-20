from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from attackiq_cli.services_mutations import build_det_pipeline_create_assessment_operation
from attackiq_cli.spec import Operation


class OperationResolver(Protocol):
    def get_operation(self, operation_id: str) -> Operation: ...


@dataclass(frozen=True)
class MutationCallPlan:
    operation: Operation
    path_params: dict[str, Any] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None


def build_create_assessment_from_scenarios_plan(
    *,
    name: str,
    scenario_ids: list[str],
) -> MutationCallPlan:
    return MutationCallPlan(
        operation=build_det_pipeline_create_assessment_operation(),
        json_body={"name": name, "scenario_ids": list(scenario_ids)},
    )


def build_create_assessment_from_template_plan(
    resolver: OperationResolver,
    *,
    template_id: str,
    project_name: str,
    blueprint_id: str | None = None,
) -> MutationCallPlan:
    body: dict[str, Any] = {
        "template": template_id,
        "project_name": project_name,
    }
    if blueprint_id is not None:
        body["blueprint"] = blueprint_id
    return MutationCallPlan(
        operation=resolver.get_operation("v1_assessments_project_from_template_create"),
        json_body=body,
    )


def build_update_assessment_defaults_plan(
    resolver: OperationResolver,
    *,
    assessment_id: str,
    asset_ids: list[str],
    asset_group_ids: list[str],
) -> MutationCallPlan:
    body: dict[str, str] = {}
    if asset_ids:
        body["assets"] = ",".join(asset_ids)
    if asset_group_ids:
        body["asset_groups"] = ",".join(asset_group_ids)
    return MutationCallPlan(
        operation=resolver.get_operation("v1_assessments_update_defaults_create"),
        path_params={"id": assessment_id},
        json_body=body,
    )


def build_run_assessment_plan(
    resolver: OperationResolver,
    *,
    assessment_id: str,
) -> MutationCallPlan:
    return MutationCallPlan(
        operation=resolver.get_operation("v1_assessments_run_all_create"),
        path_params={"id": assessment_id},
    )


def build_create_test_plan(
    resolver: OperationResolver,
    *,
    assessment_id: str,
    name: str,
) -> MutationCallPlan:
    return MutationCallPlan(
        operation=resolver.get_operation("v1_tests_create"),
        json_body={"project": assessment_id, "name": name},
    )


def build_add_scenarios_to_test_plan(
    resolver: OperationResolver,
    *,
    test_id: str,
    scenario_ids: list[str],
) -> MutationCallPlan:
    return MutationCallPlan(
        operation=resolver.get_operation("v1_tests_bulk_add_scenarios_create"),
        path_params={"id": test_id},
        json_body={"include": list(scenario_ids)},
    )


def build_get_test_status_plan(
    resolver: OperationResolver,
    *,
    test_id: str,
) -> MutationCallPlan:
    return MutationCallPlan(
        operation=resolver.get_operation("v1_tests_get_status_retrieve"),
        path_params={"id": test_id},
    )
