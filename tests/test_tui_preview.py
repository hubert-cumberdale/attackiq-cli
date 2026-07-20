from __future__ import annotations

import inspect
from typing import Any, cast

import pytest
from textual.widgets import DataTable, Input, Static, TabbedContent

import attackiq_cli.services_mutations as services_mutations
from attackiq_cli.client import AuthContext
from attackiq_cli.config import CliConfig
from attackiq_cli.services import ServiceContext
from attackiq_cli.spec import Operation, SpecIndex
from attackiq_cli.tui import (
    AssessmentsTab,
    AttackIQTuiApp,
    ResultsTab,
    ScenariosTab,
    TuiDataProvider,
    TuiOptions,
    WorkflowAssetsTab,
    WorkflowSettingsTab,
    WorkflowTestsTab,
)
from attackiq_cli.tui_domains import allowed_command_ids_for_tab
from attackiq_cli.tui_preview import (
    AssessmentDefaultsPreviewScreen,
    AssessmentFromTemplatePreviewScreen,
    AssessmentRunPreviewScreen,
    NewAssessmentPreviewScreen,
    NewTestPreviewScreen,
    build_assessment_defaults_preview,
    build_assessment_from_template_preview,
    build_assessment_run_preview,
    build_new_assessment_preview,
    build_new_test_preview,
    build_test_scenarios_preview,
    build_test_status_preview,
    render_mutation_preview,
)
from attackiq_cli.tui_preview import (
    TestScenariosPreviewScreen as ScenariosPreviewScreen,
)
from attackiq_cli.tui_preview import (
    TestStatusPreviewScreen as StatusPreviewScreen,
)

ASSESSMENT_ID = "00000000-0000-4000-8000-000000000001"
TEST_ID = "00000000-0000-4000-8000-000000000002"
SCENARIO_ID = "00000000-0000-4000-8000-000000000003"
SECOND_SCENARIO_ID = "00000000-0000-4000-8000-000000000004"
ASSET_ID = "00000000-0000-4000-8000-000000000005"
SECOND_ASSET_ID = "00000000-0000-4000-8000-000000000006"
ASSET_GROUP_ID = "00000000-0000-4000-8000-000000000007"
TEMPLATE_ID = "00000000-0000-4000-8000-000000000008"
BLUEPRINT_ID = "00000000-0000-4000-8000-000000000009"


class _Resolver:
    load_source = "memory"

    def get_operation(self, operation_id: str) -> Operation:
        operations = {
            "v1_assessments_run_all_create": (
                "post",
                "/v1/assessments/{id}/run_all",
            ),
            "v1_assessments_update_defaults_create": (
                "post",
                "/v1/assessments/{id}/update_defaults",
            ),
            "v1_assessments_project_from_template_create": (
                "post",
                "/v1/assessments/project_from_template",
            ),
            "v1_tests_create": ("post", "/v1/tests"),
            "v1_tests_bulk_add_scenarios_create": (
                "post",
                "/v1/tests/{id}/bulk_add_scenarios",
            ),
            "v1_tests_get_status_retrieve": ("get", "/v1/tests/{id}/get_status"),
        }
        try:
            method, path = operations[operation_id]
        except KeyError:
            raise KeyError(operation_id) from None
        return Operation(
            operation_id=operation_id,
            method=method,
            path=path,
            summary="",
            parameters=[],
            request_body=None,
            tags=[],
            security=[],
        )


def _disable_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(_self: object) -> None:
        return None

    monkeypatch.setattr(ScenariosTab, "on_mount", _noop)
    monkeypatch.setattr(ResultsTab, "on_mount", _noop)
    monkeypatch.setattr(AssessmentsTab, "on_mount", _noop)
    monkeypatch.setattr(WorkflowTestsTab, "on_mount", _noop)
    monkeypatch.setattr(WorkflowAssetsTab, "on_mount", _noop)
    monkeypatch.setattr(WorkflowSettingsTab, "on_mount", _noop)


def _build_app() -> AttackIQTuiApp:
    context = ServiceContext(
        config=CliConfig(base_url="https://api.example.com", account_token="token"),
        base_url="https://api.example.com",
        auth=AuthContext(account_token="token", jwt=None),
        spec=cast(SpecIndex, _Resolver()),
    )
    options = TuiOptions(
        page_size=20,
        order_by=None,
        search=None,
        tag=None,
        filter_debounce=0.4,
        insecure=False,
        insecure_source="config",
        timeout=None,
        timeout_source="config",
    )
    provider = TuiDataProvider(context, options)
    return AttackIQTuiApp(provider.build_state(), provider)


def test_build_assessment_run_preview_matches_cli_plan_shape() -> None:
    preview = build_assessment_run_preview(_Resolver(), assessment_id=ASSESSMENT_ID)

    assert preview.as_dict() == {
        "operation_id": "v1_assessments_run_all_create",
        "method": "POST",
        "path": "/v1/assessments/{id}/run_all",
        "path_params": {"id": ASSESSMENT_ID},
        "query_params": {},
        "request_status": "No request sent",
    }


def test_build_test_status_preview_matches_cli_plan_shape() -> None:
    preview = build_test_status_preview(_Resolver(), test_id=TEST_ID)

    assert preview.as_dict() == {
        "operation_id": "v1_tests_get_status_retrieve",
        "method": "GET",
        "path": "/v1/tests/{id}/get_status",
        "path_params": {"id": TEST_ID},
        "query_params": {},
        "request_status": "No request sent",
    }


def test_build_new_test_preview_matches_cli_plan_shape() -> None:
    preview = build_new_test_preview(
        _Resolver(),
        assessment_id=ASSESSMENT_ID,
        name="  Preview regression  ",
    )

    assert preview.as_dict() == {
        "operation_id": "v1_tests_create",
        "method": "POST",
        "path": "/v1/tests",
        "path_params": {},
        "query_params": {},
        "json_body_summary": {
            "project": ASSESSMENT_ID,
            "name": "Preview regression",
        },
        "request_status": "No request sent",
    }


def test_build_test_scenarios_preview_matches_cli_plan_shape() -> None:
    preview = build_test_scenarios_preview(
        _Resolver(),
        test_id=TEST_ID,
        scenario_ids=f" {SCENARIO_ID}, {SECOND_SCENARIO_ID}, {SCENARIO_ID} ",
    )

    assert preview.as_dict() == {
        "operation_id": "v1_tests_bulk_add_scenarios_create",
        "method": "POST",
        "path": "/v1/tests/{id}/bulk_add_scenarios",
        "path_params": {"id": TEST_ID},
        "query_params": {},
        "json_body_summary": {"include": [SCENARIO_ID, SECOND_SCENARIO_ID]},
        "request_status": "No request sent",
    }


def test_build_test_scenarios_preview_bounds_scenario_list() -> None:
    scenario_ids = [f"00000000-0000-4000-8000-{index:012d}" for index in range(22)]
    preview = build_test_scenarios_preview(
        _Resolver(),
        test_id=TEST_ID,
        scenario_ids=",".join(scenario_ids),
    )

    assert isinstance(preview.json_body_summary, dict)
    assert preview.json_body_summary["include"][-1] == "<2 more items>"
    assert len(preview.json_body_summary["include"]) == 21


def test_build_assessment_defaults_preview_matches_cli_plan_shape() -> None:
    preview = build_assessment_defaults_preview(
        _Resolver(),
        assessment_id=ASSESSMENT_ID,
        asset_ids=f" {ASSET_ID}, {SECOND_ASSET_ID}, {ASSET_ID} ",
        asset_group_ids=ASSET_GROUP_ID,
    )

    assert preview.as_dict() == {
        "operation_id": "v1_assessments_update_defaults_create",
        "method": "POST",
        "path": "/v1/assessments/{id}/update_defaults",
        "path_params": {"id": ASSESSMENT_ID},
        "query_params": {},
        "json_body_summary": {
            "assets": f"{ASSET_ID},{SECOND_ASSET_ID}",
            "asset_groups": ASSET_GROUP_ID,
        },
        "request_status": "No request sent",
    }


def test_build_assessment_defaults_preview_omits_empty_target_type() -> None:
    preview = build_assessment_defaults_preview(
        _Resolver(),
        assessment_id=ASSESSMENT_ID,
        asset_ids="",
        asset_group_ids=ASSET_GROUP_ID,
    )

    assert preview.json_body_summary == {"asset_groups": ASSET_GROUP_ID}


def test_build_new_assessment_preview_matches_cli_plan_shape() -> None:
    preview = build_new_assessment_preview(
        scenario_ids=f" {SCENARIO_ID}, {SECOND_SCENARIO_ID}, {SCENARIO_ID} ",
        name="  Preview assessment  ",
    )

    assert preview.as_dict() == {
        "operation_id": "det_pipeline_create_assessment",
        "method": "POST",
        "path": "/v1/assessments",
        "path_params": {},
        "query_params": {},
        "json_body_summary": {
            "name": "Preview assessment",
            "scenario_ids": [SCENARIO_ID, SECOND_SCENARIO_ID],
        },
        "request_status": "No request sent",
    }


def test_build_assessment_from_template_preview_matches_cli_plan_shape() -> None:
    preview = build_assessment_from_template_preview(
        _Resolver(),
        template_id=f" {TEMPLATE_ID} ",
        name="  Template assessment  ",
        blueprint_id=f" {BLUEPRINT_ID} ",
    )
    without_blueprint = build_assessment_from_template_preview(
        _Resolver(),
        template_id=TEMPLATE_ID,
        name="Template assessment",
        blueprint_id="  ",
    )

    assert preview.as_dict() == {
        "operation_id": "v1_assessments_project_from_template_create",
        "method": "POST",
        "path": "/v1/assessments/project_from_template",
        "path_params": {},
        "query_params": {},
        "json_body_summary": {
            "template": TEMPLATE_ID,
            "project_name": "Template assessment",
            "blueprint": BLUEPRINT_ID,
        },
        "request_status": "No request sent",
    }
    assert without_blueprint.json_body_summary == {
        "template": TEMPLATE_ID,
        "project_name": "Template assessment",
    }


@pytest.mark.parametrize(
    ("assessment_id", "message"),
    [("", "Assessment ID is required"), ("not-a-uuid", "Assessment ID must be a UUID")],
)
def test_build_assessment_run_preview_rejects_invalid_ids(
    assessment_id: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_assessment_run_preview(_Resolver(), assessment_id=assessment_id)


@pytest.mark.parametrize(
    ("test_id", "message"),
    [("", "Test ID is required"), ("not-a-uuid", "Test ID must be a UUID")],
)
def test_build_test_status_preview_rejects_invalid_ids(test_id: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_test_status_preview(_Resolver(), test_id=test_id)


@pytest.mark.parametrize(
    ("assessment_id", "name", "message"),
    [
        ("", "Preview regression", "Assessment ID is required"),
        ("not-a-uuid", "Preview regression", "Assessment ID must be a UUID"),
        (ASSESSMENT_ID, "  ", "Test name is required"),
    ],
)
def test_build_new_test_preview_rejects_invalid_inputs(
    assessment_id: str,
    name: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_new_test_preview(
            _Resolver(),
            assessment_id=assessment_id,
            name=name,
        )


@pytest.mark.parametrize(
    ("test_id", "scenario_ids", "message"),
    [
        ("", SCENARIO_ID, "Test ID is required"),
        ("not-a-uuid", SCENARIO_ID, "Test ID must be a UUID"),
        (TEST_ID, "  ", "At least one Scenario ID is required"),
        (TEST_ID, "not-a-uuid", "Scenario ID must be a UUID"),
    ],
)
def test_build_test_scenarios_preview_rejects_invalid_inputs(
    test_id: str,
    scenario_ids: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_test_scenarios_preview(
            _Resolver(),
            test_id=test_id,
            scenario_ids=scenario_ids,
        )


@pytest.mark.parametrize(
    ("assessment_id", "asset_ids", "asset_group_ids", "message"),
    [
        ("", ASSET_ID, "", "Assessment ID is required"),
        ("not-a-uuid", ASSET_ID, "", "Assessment ID must be a UUID"),
        (ASSESSMENT_ID, "not-a-uuid", "", "Asset ID must be a UUID"),
        (ASSESSMENT_ID, "", "not-a-uuid", "Asset group ID must be a UUID"),
        (ASSESSMENT_ID, "", "", "At least one Asset ID or Asset group ID is required"),
    ],
)
def test_build_assessment_defaults_preview_rejects_invalid_inputs(
    assessment_id: str,
    asset_ids: str,
    asset_group_ids: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_assessment_defaults_preview(
            _Resolver(),
            assessment_id=assessment_id,
            asset_ids=asset_ids,
            asset_group_ids=asset_group_ids,
        )


@pytest.mark.parametrize(
    ("scenario_ids", "name", "message"),
    [
        ("", "Preview assessment", "At least one Scenario ID is required"),
        ("not-a-uuid", "Preview assessment", "Scenario ID must be a UUID"),
        (SCENARIO_ID, "  ", "Assessment name is required"),
    ],
)
def test_build_new_assessment_preview_rejects_invalid_inputs(
    scenario_ids: str,
    name: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_new_assessment_preview(scenario_ids=scenario_ids, name=name)


@pytest.mark.parametrize(
    ("template_id", "name", "blueprint_id", "message"),
    [
        ("", "Template assessment", "", "Template ID is required"),
        ("not-a-uuid", "Template assessment", "", "Template ID must be a UUID"),
        (TEMPLATE_ID, "  ", "", "Assessment name is required"),
        (TEMPLATE_ID, "Template assessment", "not-a-uuid", "Blueprint ID must be a UUID"),
    ],
)
def test_build_assessment_from_template_preview_rejects_invalid_inputs(
    template_id: str,
    name: str,
    blueprint_id: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_assessment_from_template_preview(
            _Resolver(),
            template_id=template_id,
            name=name,
            blueprint_id=blueprint_id,
        )


def test_render_assessment_run_preview_is_bounded_to_call_plan_fields() -> None:
    preview = build_assessment_run_preview(_Resolver(), assessment_id=ASSESSMENT_ID)
    rendered = render_mutation_preview(preview)

    assert "Request status: No request sent" in rendered
    assert "Operation: v1_assessments_run_all_create" in rendered
    assert "Method: POST" in rendered
    assert "Path: /v1/assessments/{id}/run_all" in rendered
    assert f'"id": "{ASSESSMENT_ID}"' in rendered
    assert "api.example.com" not in rendered


def test_preview_module_has_no_apply_or_client_boundary() -> None:
    from attackiq_cli import tui_preview

    assert "apply" not in inspect.signature(build_assessment_defaults_preview).parameters
    assert "apply" not in inspect.signature(build_assessment_run_preview).parameters
    assert "apply" not in inspect.signature(build_new_test_preview).parameters
    assert "apply" not in inspect.signature(build_new_assessment_preview).parameters
    assert "apply" not in inspect.signature(build_assessment_from_template_preview).parameters
    assert "apply" not in inspect.signature(build_test_scenarios_preview).parameters
    assert "apply" not in inspect.signature(build_test_status_preview).parameters
    assert not {
        "AttackIQClient",
        "apply_request",
        "build_client",
        "prepare_context",
        "run_assessment",
    } & set(vars(tui_preview))


@pytest.mark.anyio
async def test_assessment_preview_palette_flow_is_contextual_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_auto_load(monkeypatch)
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )
    app = _build_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "preview:assessment-run" not in allowed_command_ids_for_tab("tab_status")
        assert "preview:assessment-run" in allowed_command_ids_for_tab("tab_assessments")
        assert "preview:assessment-run" not in allowed_command_ids_for_tab("tab_tests")

        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assessments"
        assessment_tab = app.query_one(AssessmentsTab)
        assessment_tab.records = [
            {
                "id": ASSESSMENT_ID,
                "name": "Preview target",
                "assessment_type": "Validation",
                "status": "ready",
            }
        ]
        assessment_tab._configure_table()
        assessment_tab._render_table()
        assessment_tab.query_one("#assessments_table", DataTable).move_cursor(row=0, column=0)

        app._execute_palette_command("preview:assessment-run")
        await pilot.pause()

        assert isinstance(app.screen, AssessmentRunPreviewScreen)
        assessment_input = app.screen.query_one("#assessment_run_preview_id", Input)
        assert assessment_input.value == ASSESSMENT_ID

        await pilot.press("enter")
        await pilot.pause()

        output = str(
            app.screen.query_one("#assessment_run_preview_output", Static).renderable
        )
        assert "Request status: No request sent" in output
        assert "Operation: v1_assessments_run_all_create" in output
        assert "Method: POST" in output
        assert f'"id": "{ASSESSMENT_ID}"' in output
        assert not hasattr(app.screen, "apply")

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, AssessmentRunPreviewScreen)


@pytest.mark.anyio
async def test_assessment_defaults_preview_palette_flow_is_contextual_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_auto_load(monkeypatch)
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )
    app = _build_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "preview:assessment-defaults" not in allowed_command_ids_for_tab("tab_status")
        assert "preview:assessment-defaults" in allowed_command_ids_for_tab("tab_assessments")
        assert "preview:assessment-defaults" not in allowed_command_ids_for_tab("tab_tests")

        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assessments"
        assessment_tab = app.query_one(AssessmentsTab)
        assessment_tab.records = [
            {
                "id": ASSESSMENT_ID,
                "name": "Default targets",
                "assessment_type": "Validation",
                "status": "ready",
            }
        ]
        assessment_tab._configure_table()
        assessment_tab._render_table()
        assessment_tab.query_one("#assessments_table", DataTable).move_cursor(row=0, column=0)

        app._execute_palette_command("preview:assessment-defaults")
        await pilot.pause()

        assert isinstance(app.screen, AssessmentDefaultsPreviewScreen)
        assessment_input = app.screen.query_one(
            "#assessment_defaults_preview_assessment_id",
            Input,
        )
        asset_input = app.screen.query_one("#assessment_defaults_preview_asset_ids", Input)
        assert assessment_input.value == ASSESSMENT_ID

        asset_input.value = f"{ASSET_ID},{SECOND_ASSET_ID}"
        await pilot.press("enter")
        await pilot.pause()

        output = str(
            app.screen.query_one("#assessment_defaults_preview_output", Static).renderable
        )
        assert "Request status: No request sent" in output
        assert "Operation: v1_assessments_update_defaults_create" in output
        assert "Method: POST" in output
        assert f'"id": "{ASSESSMENT_ID}"' in output
        assert f'"assets": "{ASSET_ID},{SECOND_ASSET_ID}"' in output
        assert not hasattr(app.screen, "apply")

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, AssessmentDefaultsPreviewScreen)


@pytest.mark.anyio
async def test_new_assessment_preview_palette_flow_is_contextual_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_auto_load(monkeypatch)
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )
    app = _build_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "preview:new-assessment" not in allowed_command_ids_for_tab("tab_status")
        assert "preview:new-assessment" in allowed_command_ids_for_tab("tab_scenarios")
        assert "preview:new-assessment" not in allowed_command_ids_for_tab("tab_assessments")

        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_scenarios"
        scenario_tab = app.query_one(ScenariosTab)
        scenario_tab.records = [
            {
                "id": SCENARIO_ID,
                "name": "Assessment seed",
                "scenario_type": "Attack",
                "last_updated": "2026-07-18T00:00:00Z",
            }
        ]
        scenario_tab._configure_table()
        scenario_tab._render_table()
        scenario_tab.query_one("#scenarios_table", DataTable).move_cursor(row=0, column=0)

        app._execute_palette_command("preview:new-assessment")
        await pilot.pause()

        assert isinstance(app.screen, NewAssessmentPreviewScreen)
        scenario_input = app.screen.query_one("#new_assessment_preview_scenario_ids", Input)
        name_input = app.screen.query_one("#new_assessment_preview_name", Input)
        assert scenario_input.value == SCENARIO_ID

        name_input.value = "Preview assessment"
        await pilot.press("enter")
        await pilot.pause()

        output = str(app.screen.query_one("#new_assessment_preview_output", Static).renderable)
        assert "Request status: No request sent" in output
        assert "Operation: det_pipeline_create_assessment" in output
        assert "Method: POST" in output
        assert '"name": "Preview assessment"' in output
        assert f'"{SCENARIO_ID}"' in output
        assert not hasattr(app.screen, "apply")

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, NewAssessmentPreviewScreen)


@pytest.mark.anyio
async def test_assessment_from_template_preview_palette_flow_is_contextual_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_auto_load(monkeypatch)
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )
    app = _build_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        command_id = "preview:assessment-from-template"
        assert command_id not in allowed_command_ids_for_tab("tab_status")
        assert command_id not in allowed_command_ids_for_tab("tab_scenarios")
        assert command_id in allowed_command_ids_for_tab("tab_assessments")
        assert command_id not in allowed_command_ids_for_tab("tab_tests")

        app.query_one("#main_tabs", TabbedContent).active = "tab_assessments"
        app._execute_palette_command(command_id)
        await pilot.pause()

        assert isinstance(app.screen, AssessmentFromTemplatePreviewScreen)
        template_input = app.screen.query_one(
            "#assessment_from_template_preview_template_id",
            Input,
        )
        name_input = app.screen.query_one("#assessment_from_template_preview_name", Input)
        blueprint_input = app.screen.query_one(
            "#assessment_from_template_preview_blueprint_id",
            Input,
        )
        template_input.value = TEMPLATE_ID
        await pilot.press("enter")
        name_input.value = "Template assessment"
        await pilot.press("enter")
        blueprint_input.value = BLUEPRINT_ID
        await pilot.press("enter")
        await pilot.pause()

        output = str(
            app.screen.query_one(
                "#assessment_from_template_preview_output",
                Static,
            ).renderable
        )
        assert "Request status: No request sent" in output
        assert "Operation: v1_assessments_project_from_template_create" in output
        assert "Method: POST" in output
        assert f'"template": "{TEMPLATE_ID}"' in output
        assert '"project_name": "Template assessment"' in output
        assert f'"blueprint": "{BLUEPRINT_ID}"' in output
        assert not hasattr(app.screen, "apply")

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, AssessmentFromTemplatePreviewScreen)


@pytest.mark.anyio
async def test_new_test_preview_palette_flow_is_contextual_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_auto_load(monkeypatch)
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )
    app = _build_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "preview:new-test" not in allowed_command_ids_for_tab("tab_status")
        assert "preview:new-test" in allowed_command_ids_for_tab("tab_assessments")
        assert "preview:new-test" not in allowed_command_ids_for_tab("tab_tests")

        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_assessments"
        assessment_tab = app.query_one(AssessmentsTab)
        assessment_tab.records = [
            {
                "id": ASSESSMENT_ID,
                "name": "New test target",
                "assessment_type": "Validation",
                "status": "ready",
            }
        ]
        assessment_tab._configure_table()
        assessment_tab._render_table()
        assessment_tab.query_one("#assessments_table", DataTable).move_cursor(row=0, column=0)

        app._execute_palette_command("preview:new-test")
        await pilot.pause()

        assert isinstance(app.screen, NewTestPreviewScreen)
        assessment_input = app.screen.query_one("#new_test_preview_assessment_id", Input)
        name_input = app.screen.query_one("#new_test_preview_name", Input)
        assert assessment_input.value == ASSESSMENT_ID

        name_input.value = "Preview regression"
        await pilot.press("enter")
        await pilot.pause()

        output = str(app.screen.query_one("#new_test_preview_output", Static).renderable)
        assert "Request status: No request sent" in output
        assert "Operation: v1_tests_create" in output
        assert "Method: POST" in output
        assert f'"project": "{ASSESSMENT_ID}"' in output
        assert '"name": "Preview regression"' in output
        assert not hasattr(app.screen, "apply")

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, NewTestPreviewScreen)


@pytest.mark.anyio
async def test_test_scenarios_preview_palette_flow_is_contextual_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_auto_load(monkeypatch)
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )
    app = _build_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "preview:test-scenarios" not in allowed_command_ids_for_tab("tab_status")
        assert "preview:test-scenarios" not in allowed_command_ids_for_tab("tab_assessments")
        assert "preview:test-scenarios" in allowed_command_ids_for_tab("tab_tests")

        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_tests"
        tests_tab = app.query_one(WorkflowTestsTab)
        tests_tab.records = [
            {
                "id": TEST_ID,
                "name": "Scenario target",
                "project": "Preview assessment",
                "runnable": True,
            }
        ]
        tests_tab._configure_table()
        tests_tab._render_table()
        tests_tab.query_one("#tests_table", DataTable).move_cursor(row=0, column=0)

        app._execute_palette_command("preview:test-scenarios")
        await pilot.pause()

        assert isinstance(app.screen, ScenariosPreviewScreen)
        test_input = app.screen.query_one("#test_scenarios_preview_test_id", Input)
        scenario_input = app.screen.query_one("#test_scenarios_preview_scenario_ids", Input)
        assert test_input.value == TEST_ID

        scenario_input.value = f"{SCENARIO_ID},{SECOND_SCENARIO_ID}"
        await pilot.press("enter")
        await pilot.pause()

        output = str(app.screen.query_one("#test_scenarios_preview_output", Static).renderable)
        assert "Request status: No request sent" in output
        assert "Operation: v1_tests_bulk_add_scenarios_create" in output
        assert "Method: POST" in output
        assert f'"id": "{TEST_ID}"' in output
        assert f'"{SCENARIO_ID}"' in output
        assert f'"{SECOND_SCENARIO_ID}"' in output
        assert not hasattr(app.screen, "apply")

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ScenariosPreviewScreen)


@pytest.mark.anyio
async def test_test_status_preview_palette_flow_is_contextual_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_auto_load(monkeypatch)
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )
    app = _build_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "preview:test-status" not in allowed_command_ids_for_tab("tab_status")
        assert "preview:test-status" not in allowed_command_ids_for_tab("tab_assessments")
        assert "preview:test-status" in allowed_command_ids_for_tab("tab_tests")

        tabs = app.query_one("#main_tabs", TabbedContent)
        tabs.active = "tab_tests"
        tests_tab = app.query_one(WorkflowTestsTab)
        tests_tab.records = [
            {
                "id": TEST_ID,
                "name": "Status target",
                "project": "Preview assessment",
                "runnable": True,
            }
        ]
        tests_tab._configure_table()
        tests_tab._render_table()
        tests_tab.query_one("#tests_table", DataTable).move_cursor(row=0, column=0)

        app._execute_palette_command("preview:test-status")
        await pilot.pause()

        assert isinstance(app.screen, StatusPreviewScreen)
        test_input = app.screen.query_one("#test_status_preview_id", Input)
        assert test_input.value == TEST_ID

        await pilot.press("enter")
        await pilot.pause()

        output = str(app.screen.query_one("#test_status_preview_output", Static).renderable)
        assert "Request status: No request sent" in output
        assert "Operation: v1_tests_get_status_retrieve" in output
        assert "Method: GET" in output
        assert f'"id": "{TEST_ID}"' in output
        assert not hasattr(app.screen, "apply")

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, StatusPreviewScreen)


@pytest.mark.anyio
async def test_assessment_preview_invalid_input_stays_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_auto_load(monkeypatch)
    app = _build_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(AssessmentRunPreviewScreen(cast(Any, _Resolver())))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        error = str(app.screen.query_one("#assessment_run_preview_error", Static).renderable)
        output = str(app.screen.query_one("#assessment_run_preview_output", Static).renderable)
        assert error == "Assessment ID is required."
        assert output == ""
