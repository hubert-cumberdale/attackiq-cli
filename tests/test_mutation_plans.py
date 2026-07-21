from __future__ import annotations

from attackiq_cli.mutation_plans import (
    build_add_scenarios_to_test_plan,
    build_create_assessment_from_scenarios_plan,
    build_create_assessment_from_template_plan,
    build_create_test_plan,
    build_get_test_status_plan,
    build_run_assessment_plan,
    build_update_assessment_defaults_plan,
)
from attackiq_cli.spec import Operation


class _Resolver:
    def get_operation(self, operation_id: str) -> Operation:
        return Operation(
            operation_id=operation_id,
            method="post",
            path=f"/fixture/{operation_id}",
            summary="",
            parameters=[],
            request_body=None,
            tags=[],
            security=[],
        )


def test_create_assessment_from_scenarios_plan_uses_synthetic_operation() -> None:
    plan = build_create_assessment_from_scenarios_plan(
        name="My Assessment",
        scenario_ids=["scenario-1", "scenario-2"],
    )

    assert plan.operation.operation_id == "det_pipeline_create_assessment"
    assert plan.path_params == {}
    assert plan.query_params == {}
    assert plan.json_body == {
        "name": "My Assessment",
        "scenario_ids": ["scenario-1", "scenario-2"],
    }


def test_create_assessment_from_template_plan_omits_empty_blueprint() -> None:
    plan = build_create_assessment_from_template_plan(
        _Resolver(),
        template_id="template-1",
        project_name="Template Assessment",
    )

    assert plan.operation.operation_id == "v1_assessments_project_from_template_create"
    assert plan.json_body == {
        "template": "template-1",
        "project_name": "Template Assessment",
    }


def test_update_assessment_defaults_plan_joins_targets() -> None:
    plan = build_update_assessment_defaults_plan(
        _Resolver(),
        assessment_id="assessment-1",
        asset_ids=["asset-1", "asset-2"],
        asset_group_ids=["group-1"],
    )

    assert plan.operation.operation_id == "v1_assessments_update_defaults_create"
    assert plan.path_params == {"id": "assessment-1"}
    assert plan.json_body == {
        "assets": "asset-1,asset-2",
        "asset_groups": "group-1",
    }


def test_run_assessment_and_get_test_status_plans_do_not_add_body() -> None:
    assessment_plan = build_run_assessment_plan(_Resolver(), assessment_id="assessment-1")
    status_plan = build_get_test_status_plan(_Resolver(), test_id="test-1")

    assert assessment_plan.operation.operation_id == "v1_assessments_run_all_create"
    assert assessment_plan.path_params == {"id": "assessment-1"}
    assert assessment_plan.json_body is None
    assert status_plan.operation.operation_id == "v1_tests_get_status_retrieve"
    assert status_plan.path_params == {"id": "test-1"}
    assert status_plan.json_body is None


def test_create_test_and_add_scenarios_plans_copy_input_lists() -> None:
    scenario_ids = ["scenario-1"]
    create_plan = build_create_test_plan(
        _Resolver(),
        assessment_id="assessment-1",
        name="API Test",
    )
    add_plan = build_add_scenarios_to_test_plan(
        _Resolver(),
        test_id="test-1",
        scenario_ids=scenario_ids,
    )
    scenario_ids.append("scenario-2")

    assert create_plan.operation.operation_id == "v1_tests_create"
    assert create_plan.json_body == {"project": "assessment-1", "name": "API Test"}
    assert add_plan.operation.operation_id == "v1_tests_bulk_add_scenarios_create"
    assert add_plan.path_params == {"id": "test-1"}
    assert add_plan.json_body == {"include": ["scenario-1"]}
