from __future__ import annotations

from typing import Any

from attackiq_cli.service_core import ServiceContext, build_client, ensure_auth
from attackiq_cli.spec import Operation


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
