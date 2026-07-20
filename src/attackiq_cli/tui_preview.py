"""Read-only Textual screens for local mutation call-plan previews."""

from __future__ import annotations

import json
import uuid

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from attackiq_cli.mutation_plans import (
    OperationResolver,
    build_add_scenarios_to_test_plan,
    build_create_assessment_from_scenarios_plan,
    build_create_assessment_from_template_plan,
    build_create_test_plan,
    build_get_test_status_plan,
    build_run_assessment_plan,
    build_update_assessment_defaults_plan,
)
from attackiq_cli.tui_mutation_preview import (
    REQUEST_NOT_SENT_STATUS,
    TuiMutationPreview,
    build_tui_mutation_preview,
)


def build_assessment_run_preview(
    resolver: OperationResolver,
    *,
    assessment_id: str,
) -> TuiMutationPreview:
    normalized_id = _normalize_uuid(assessment_id, label="Assessment ID")
    plan = build_run_assessment_plan(resolver, assessment_id=normalized_id)
    return build_tui_mutation_preview(plan)


def build_test_status_preview(
    resolver: OperationResolver,
    *,
    test_id: str,
) -> TuiMutationPreview:
    normalized_id = _normalize_uuid(test_id, label="Test ID")
    plan = build_get_test_status_plan(resolver, test_id=normalized_id)
    return build_tui_mutation_preview(plan)


def build_new_test_preview(
    resolver: OperationResolver,
    *,
    assessment_id: str,
    name: str,
) -> TuiMutationPreview:
    normalized_id = _normalize_uuid(assessment_id, label="Assessment ID")
    normalized_name = _normalize_required_text(name, label="Test name")
    plan = build_create_test_plan(
        resolver,
        assessment_id=normalized_id,
        name=normalized_name,
    )
    return build_tui_mutation_preview(plan)


def build_test_scenarios_preview(
    resolver: OperationResolver,
    *,
    test_id: str,
    scenario_ids: str,
) -> TuiMutationPreview:
    normalized_test_id = _normalize_uuid(test_id, label="Test ID")
    normalized_scenario_ids = _normalize_uuid_list(scenario_ids, label="Scenario ID")
    plan = build_add_scenarios_to_test_plan(
        resolver,
        test_id=normalized_test_id,
        scenario_ids=normalized_scenario_ids,
    )
    return build_tui_mutation_preview(plan)


def build_assessment_defaults_preview(
    resolver: OperationResolver,
    *,
    assessment_id: str,
    asset_ids: str,
    asset_group_ids: str,
) -> TuiMutationPreview:
    normalized_assessment_id = _normalize_uuid(assessment_id, label="Assessment ID")
    normalized_asset_ids = _normalize_optional_uuid_list(asset_ids, label="Asset ID")
    normalized_asset_group_ids = _normalize_optional_uuid_list(
        asset_group_ids,
        label="Asset group ID",
    )
    if not normalized_asset_ids and not normalized_asset_group_ids:
        raise ValueError("At least one Asset ID or Asset group ID is required.")
    plan = build_update_assessment_defaults_plan(
        resolver,
        assessment_id=normalized_assessment_id,
        asset_ids=normalized_asset_ids,
        asset_group_ids=normalized_asset_group_ids,
    )
    return build_tui_mutation_preview(plan)


def build_new_assessment_preview(
    *,
    scenario_ids: str,
    name: str,
) -> TuiMutationPreview:
    normalized_scenario_ids = _normalize_uuid_list(scenario_ids, label="Scenario ID")
    normalized_name = _normalize_required_text(name, label="Assessment name")
    plan = build_create_assessment_from_scenarios_plan(
        name=normalized_name,
        scenario_ids=normalized_scenario_ids,
    )
    return build_tui_mutation_preview(plan)


def build_assessment_from_template_preview(
    resolver: OperationResolver,
    *,
    template_id: str,
    name: str,
    blueprint_id: str,
) -> TuiMutationPreview:
    normalized_template_id = _normalize_uuid(template_id, label="Template ID")
    normalized_name = _normalize_required_text(name, label="Assessment name")
    normalized_blueprint_id = (
        _normalize_uuid(blueprint_id, label="Blueprint ID") if blueprint_id.strip() else None
    )
    plan = build_create_assessment_from_template_plan(
        resolver,
        template_id=normalized_template_id,
        project_name=normalized_name,
        blueprint_id=normalized_blueprint_id,
    )
    return build_tui_mutation_preview(plan)


def render_mutation_preview(preview: TuiMutationPreview) -> str:
    body = preview.json_body_summary if preview.json_body_summary is not None else {}
    return "\n".join(
        [
            f"Request status: {preview.request_status}",
            f"Operation: {preview.operation_id}",
            f"Method: {preview.method}",
            f"Path: {preview.path}",
            "Path params:",
            _pretty_json(preview.path_params),
            "Query params:",
            _pretty_json(preview.query_params),
            "JSON body summary:",
            _pretty_json(body),
        ]
    )


def _normalize_uuid(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} is required.")
    try:
        uuid.UUID(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} must be a UUID.") from exc
    return cleaned


def _normalize_required_text(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} is required.")
    return cleaned


def _normalize_uuid_list(value: str, *, label: str) -> list[str]:
    requested = [item.strip() for item in value.split(",") if item.strip()]
    if not requested:
        raise ValueError(f"At least one {label} is required.")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in requested:
        normalized_item = _normalize_uuid(item, label=label)
        if normalized_item in seen:
            continue
        seen.add(normalized_item)
        normalized.append(normalized_item)
    return normalized


def _normalize_optional_uuid_list(value: str, *, label: str) -> list[str]:
    if not value.strip():
        return []
    return _normalize_uuid_list(value, label=label)


def _pretty_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


class _IdentifierPreviewScreen(ModalScreen[None]):
    BINDINGS = [("escape", "cancel", "Close")]
    preview_id_prefix = "request_preview"
    preview_title = "Request Preview"
    identifier_label = "ID"
    identifier_placeholder = "UUID"

    def __init__(self, resolver: OperationResolver, *, identifier: str | None = None) -> None:
        super().__init__()
        self.resolver = resolver
        self.initial_identifier = identifier or ""

    def _widget_id(self, suffix: str) -> str:
        return f"{self.preview_id_prefix}_{suffix}"

    def compose(self) -> ComposeResult:
        with Vertical(
            id=self._widget_id("dialog"),
            classes="request-preview-dialog",
        ):
            yield Static(
                self.preview_title,
                id=self._widget_id("title"),
                classes="pane-title",
            )
            yield Static(self.identifier_label, classes="preview-label")
            yield Input(
                value=self.initial_identifier,
                placeholder=self.identifier_placeholder,
                id=self._widget_id("id"),
            )
            with Horizontal(
                id=self._widget_id("actions"),
                classes="request-preview-actions",
            ):
                yield Button("Preview", id=self._widget_id("build"), variant="primary")
                yield Button("Close", id=self._widget_id("close"))
            yield Static(
                REQUEST_NOT_SENT_STATUS,
                id=self._widget_id("status"),
                classes="request-preview-status status-hint",
            )
            yield Static(
                "",
                id=self._widget_id("error"),
                classes="request-preview-error",
            )
            yield Static(
                "",
                id=self._widget_id("output"),
                classes="request-preview-output",
                markup=False,
            )

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_identifier)

    def _focus_identifier(self) -> None:
        self.query_one(f"#{self._widget_id('id')}", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == self._widget_id("id"):
            self._render_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == self._widget_id("close"):
            self.dismiss()
            return
        if event.button.id == self._widget_id("build"):
            self._render_preview()

    def action_cancel(self) -> None:
        self.dismiss()

    def _create_preview(self, identifier: str) -> TuiMutationPreview:
        raise NotImplementedError

    def _render_preview(self) -> None:
        identifier = self.query_one(f"#{self._widget_id('id')}", Input).value
        error = self.query_one(f"#{self._widget_id('error')}", Static)
        output = self.query_one(f"#{self._widget_id('output')}", Static)
        try:
            preview = self._create_preview(identifier)
        except (KeyError, ValueError) as exc:
            error.update(str(exc))
            output.update("")
            return
        error.update("")
        output.update(render_mutation_preview(preview))


class AssessmentRunPreviewScreen(_IdentifierPreviewScreen):
    preview_id_prefix = "assessment_run_preview"
    preview_title = "Assessment Run Request Preview"
    identifier_label = "Assessment ID"
    identifier_placeholder = "Assessment UUID"

    def __init__(self, resolver: OperationResolver, *, assessment_id: str | None = None) -> None:
        super().__init__(resolver, identifier=assessment_id)

    def _create_preview(self, identifier: str) -> TuiMutationPreview:
        return build_assessment_run_preview(self.resolver, assessment_id=identifier)


class TestStatusPreviewScreen(_IdentifierPreviewScreen):
    preview_id_prefix = "test_status_preview"
    preview_title = "Test Status Request Preview"
    identifier_label = "Test ID"
    identifier_placeholder = "Test UUID"

    def __init__(self, resolver: OperationResolver, *, test_id: str | None = None) -> None:
        super().__init__(resolver, identifier=test_id)

    def _create_preview(self, identifier: str) -> TuiMutationPreview:
        return build_test_status_preview(self.resolver, test_id=identifier)


class _IdentifierAndValuePreviewScreen(ModalScreen[None]):
    BINDINGS = [("escape", "cancel", "Close")]
    preview_id_prefix = "request_value_preview"
    preview_title = "Request Preview"
    identifier_label = "ID"
    identifier_placeholder = "UUID"
    identifier_suffix = "id"
    value_label = "Value"
    value_placeholder = "Value"
    value_suffix = "value"

    def __init__(self, *, identifier: str | None = None) -> None:
        super().__init__()
        self.initial_identifier = identifier or ""

    def _widget_id(self, suffix: str) -> str:
        return f"{self.preview_id_prefix}_{suffix}"

    def compose(self) -> ComposeResult:
        with Vertical(
            id=self._widget_id("dialog"),
            classes="request-preview-dialog",
        ):
            yield Static(
                self.preview_title,
                id=self._widget_id("title"),
                classes="pane-title",
            )
            yield Static(self.identifier_label, classes="preview-label")
            yield Input(
                value=self.initial_identifier,
                placeholder=self.identifier_placeholder,
                id=self._widget_id(self.identifier_suffix),
            )
            yield Static(self.value_label, classes="preview-label")
            yield Input(
                placeholder=self.value_placeholder,
                id=self._widget_id(self.value_suffix),
            )
            with Horizontal(
                id=self._widget_id("actions"),
                classes="request-preview-actions",
            ):
                yield Button("Preview", id=self._widget_id("build"), variant="primary")
                yield Button("Close", id=self._widget_id("close"))
            yield Static(
                REQUEST_NOT_SENT_STATUS,
                id=self._widget_id("status"),
                classes="request-preview-status status-hint",
            )
            yield Static(
                "",
                id=self._widget_id("error"),
                classes="request-preview-error",
            )
            yield Static(
                "",
                id=self._widget_id("output"),
                classes="request-preview-output",
                markup=False,
            )

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_initial_input)

    def _focus_initial_input(self) -> None:
        suffix = self.value_suffix if self.initial_identifier else self.identifier_suffix
        self.query_one(f"#{self._widget_id(suffix)}", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == self._widget_id(self.identifier_suffix):
            self.query_one(f"#{self._widget_id(self.value_suffix)}", Input).focus()
            return
        if event.input.id == self._widget_id(self.value_suffix):
            self._render_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == self._widget_id("close"):
            self.dismiss()
            return
        if event.button.id == self._widget_id("build"):
            self._render_preview()

    def action_cancel(self) -> None:
        self.dismiss()

    def _create_preview(self, identifier: str, value: str) -> TuiMutationPreview:
        raise NotImplementedError

    def _render_preview(self) -> None:
        identifier = self.query_one(
            f"#{self._widget_id(self.identifier_suffix)}",
            Input,
        ).value
        value = self.query_one(f"#{self._widget_id(self.value_suffix)}", Input).value
        error = self.query_one(f"#{self._widget_id('error')}", Static)
        output = self.query_one(f"#{self._widget_id('output')}", Static)
        try:
            preview = self._create_preview(identifier, value)
        except (KeyError, ValueError) as exc:
            error.update(str(exc))
            output.update("")
            return
        error.update("")
        output.update(render_mutation_preview(preview))


class NewTestPreviewScreen(_IdentifierAndValuePreviewScreen):
    preview_id_prefix = "new_test_preview"
    preview_title = "New Test Request Preview"
    identifier_label = "Assessment ID"
    identifier_placeholder = "Assessment UUID"
    identifier_suffix = "assessment_id"
    value_label = "Test name"
    value_placeholder = "Test name"
    value_suffix = "name"

    def __init__(self, resolver: OperationResolver, *, assessment_id: str | None = None) -> None:
        super().__init__(identifier=assessment_id)
        self.resolver = resolver

    def _create_preview(self, identifier: str, value: str) -> TuiMutationPreview:
        return build_new_test_preview(
            self.resolver,
            assessment_id=identifier,
            name=value,
        )


class TestScenariosPreviewScreen(_IdentifierAndValuePreviewScreen):
    preview_id_prefix = "test_scenarios_preview"
    preview_title = "Test Scenario Assignment Request Preview"
    identifier_label = "Test ID"
    identifier_placeholder = "Test UUID"
    identifier_suffix = "test_id"
    value_label = "Scenario IDs"
    value_placeholder = "Comma-separated scenario UUIDs"
    value_suffix = "scenario_ids"

    def __init__(self, resolver: OperationResolver, *, test_id: str | None = None) -> None:
        super().__init__(identifier=test_id)
        self.resolver = resolver

    def _create_preview(self, identifier: str, value: str) -> TuiMutationPreview:
        return build_test_scenarios_preview(
            self.resolver,
            test_id=identifier,
            scenario_ids=value,
        )


class NewAssessmentPreviewScreen(_IdentifierAndValuePreviewScreen):
    preview_id_prefix = "new_assessment_preview"
    preview_title = "New Assessment Request Preview"
    identifier_label = "Scenario IDs"
    identifier_placeholder = "Comma-separated scenario UUIDs"
    identifier_suffix = "scenario_ids"
    value_label = "Assessment name"
    value_placeholder = "Assessment name"
    value_suffix = "name"

    def __init__(self, *, scenario_id: str | None = None) -> None:
        super().__init__(identifier=scenario_id)

    def _create_preview(self, identifier: str, value: str) -> TuiMutationPreview:
        return build_new_assessment_preview(
            scenario_ids=identifier,
            name=value,
        )


class AssessmentFromTemplatePreviewScreen(ModalScreen[None]):
    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(self, resolver: OperationResolver) -> None:
        super().__init__()
        self.resolver = resolver

    def compose(self) -> ComposeResult:
        with Vertical(
            id="assessment_from_template_preview_dialog",
            classes="request-preview-dialog",
        ):
            yield Static(
                "Assessment From Template Request Preview",
                id="assessment_from_template_preview_title",
                classes="pane-title",
            )
            yield Static("Template ID", classes="preview-label")
            yield Input(
                placeholder="Assessment template UUID",
                id="assessment_from_template_preview_template_id",
            )
            yield Static("Assessment name", classes="preview-label")
            yield Input(
                placeholder="Assessment name",
                id="assessment_from_template_preview_name",
            )
            yield Static("Blueprint ID (optional)", classes="preview-label")
            yield Input(
                placeholder="Blueprint UUID",
                id="assessment_from_template_preview_blueprint_id",
            )
            with Horizontal(
                id="assessment_from_template_preview_actions",
                classes="request-preview-actions",
            ):
                yield Button(
                    "Preview",
                    id="assessment_from_template_preview_build",
                    variant="primary",
                )
                yield Button("Close", id="assessment_from_template_preview_close")
            yield Static(
                REQUEST_NOT_SENT_STATUS,
                id="assessment_from_template_preview_status",
                classes="request-preview-status status-hint",
            )
            yield Static(
                "",
                id="assessment_from_template_preview_error",
                classes="request-preview-error",
            )
            yield Static(
                "",
                id="assessment_from_template_preview_output",
                classes="request-preview-output",
                markup=False,
            )

    def on_mount(self) -> None:
        self.call_after_refresh(
            lambda: self.query_one("#assessment_from_template_preview_template_id", Input).focus()
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "assessment_from_template_preview_template_id":
            self.query_one("#assessment_from_template_preview_name", Input).focus()
            return
        if event.input.id == "assessment_from_template_preview_name":
            self.query_one("#assessment_from_template_preview_blueprint_id", Input).focus()
            return
        if event.input.id == "assessment_from_template_preview_blueprint_id":
            self._render_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "assessment_from_template_preview_close":
            self.dismiss()
            return
        if event.button.id == "assessment_from_template_preview_build":
            self._render_preview()

    def action_cancel(self) -> None:
        self.dismiss()

    def _render_preview(self) -> None:
        template_id = self.query_one("#assessment_from_template_preview_template_id", Input).value
        name = self.query_one("#assessment_from_template_preview_name", Input).value
        blueprint_id = self.query_one(
            "#assessment_from_template_preview_blueprint_id",
            Input,
        ).value
        error = self.query_one("#assessment_from_template_preview_error", Static)
        output = self.query_one("#assessment_from_template_preview_output", Static)
        try:
            preview = build_assessment_from_template_preview(
                self.resolver,
                template_id=template_id,
                name=name,
                blueprint_id=blueprint_id,
            )
        except (KeyError, ValueError) as exc:
            error.update(str(exc))
            output.update("")
            return
        error.update("")
        output.update(render_mutation_preview(preview))


class AssessmentDefaultsPreviewScreen(ModalScreen[None]):
    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(self, resolver: OperationResolver, *, assessment_id: str | None = None) -> None:
        super().__init__()
        self.resolver = resolver
        self.initial_assessment_id = assessment_id or ""

    def compose(self) -> ComposeResult:
        with Vertical(id="assessment_defaults_preview_dialog", classes="request-preview-dialog"):
            yield Static(
                "Assessment Default Targets Request Preview",
                id="assessment_defaults_preview_title",
                classes="pane-title",
            )
            yield Static("Assessment ID", classes="preview-label")
            yield Input(
                value=self.initial_assessment_id,
                placeholder="Assessment UUID",
                id="assessment_defaults_preview_assessment_id",
            )
            yield Static("Asset IDs", classes="preview-label")
            yield Input(
                placeholder="Comma-separated asset UUIDs",
                id="assessment_defaults_preview_asset_ids",
            )
            yield Static("Asset group IDs", classes="preview-label")
            yield Input(
                placeholder="Comma-separated asset group UUIDs",
                id="assessment_defaults_preview_asset_group_ids",
            )
            with Horizontal(
                id="assessment_defaults_preview_actions",
                classes="request-preview-actions",
            ):
                yield Button("Preview", id="assessment_defaults_preview_build", variant="primary")
                yield Button("Close", id="assessment_defaults_preview_close")
            yield Static(
                REQUEST_NOT_SENT_STATUS,
                id="assessment_defaults_preview_status",
                classes="request-preview-status status-hint",
            )
            yield Static(
                "",
                id="assessment_defaults_preview_error",
                classes="request-preview-error",
            )
            yield Static(
                "",
                id="assessment_defaults_preview_output",
                classes="request-preview-output",
                markup=False,
            )

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_initial_input)

    def _focus_initial_input(self) -> None:
        input_id = (
            "#assessment_defaults_preview_asset_ids"
            if self.initial_assessment_id
            else "#assessment_defaults_preview_assessment_id"
        )
        self.query_one(input_id, Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "assessment_defaults_preview_assessment_id":
            self.query_one("#assessment_defaults_preview_asset_ids", Input).focus()
            return
        if event.input.id == "assessment_defaults_preview_asset_ids" and not event.value.strip():
            self.query_one("#assessment_defaults_preview_asset_group_ids", Input).focus()
            return
        if event.input.id in {
            "assessment_defaults_preview_asset_ids",
            "assessment_defaults_preview_asset_group_ids",
        }:
            self._render_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "assessment_defaults_preview_close":
            self.dismiss()
            return
        if event.button.id == "assessment_defaults_preview_build":
            self._render_preview()

    def action_cancel(self) -> None:
        self.dismiss()

    def _render_preview(self) -> None:
        assessment_id = self.query_one("#assessment_defaults_preview_assessment_id", Input).value
        asset_ids = self.query_one("#assessment_defaults_preview_asset_ids", Input).value
        asset_group_ids = self.query_one(
            "#assessment_defaults_preview_asset_group_ids",
            Input,
        ).value
        error = self.query_one("#assessment_defaults_preview_error", Static)
        output = self.query_one("#assessment_defaults_preview_output", Static)
        try:
            preview = build_assessment_defaults_preview(
                self.resolver,
                assessment_id=assessment_id,
                asset_ids=asset_ids,
                asset_group_ids=asset_group_ids,
            )
        except (KeyError, ValueError) as exc:
            error.update(str(exc))
            output.update("")
            return
        error.update("")
        output.update(render_mutation_preview(preview))
