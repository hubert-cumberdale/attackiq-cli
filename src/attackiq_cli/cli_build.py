from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Annotated, Any

import typer

from attackiq_cli.exporter import write_json
from attackiq_cli.spec import SpecIndex
from attackiq_cli.utils import validate_json_payload

build_app = typer.Typer(
    help="Build request payloads and call plans (no network).",
    pretty_exceptions_show_locals=False,
)
build_assessment_app = typer.Typer(
    help="Assessment build helpers.",
    pretty_exceptions_show_locals=False,
)
build_test_app = typer.Typer(
    help="Test build helpers.",
    pretty_exceptions_show_locals=False,
)

build_app.add_typer(build_assessment_app, name="assessment")
build_app.add_typer(build_test_app, name="test")

__all__ = [
    "build_app",
    "build_assessment_app",
    "build_assessment_from_template",
    "build_test_add_scenarios",
    "build_test_app",
    "build_test_create",
]


def _normalize_uuid(value: str, *, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise typer.BadParameter(f"{label} is required.")
    try:
        uuid.UUID(cleaned)
    except ValueError as exc:
        raise typer.BadParameter(f"{label} must be a UUID.") from exc
    return cleaned


def _load_uuid_list_from_text(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        parts = [item.strip() for item in cleaned.split(",") if item.strip()]
        items.extend(parts)
    return items


def _load_uuid_list_from_file(path: Path) -> list[str]:
    return _load_uuid_list_from_text(path.read_text(encoding="utf-8"))


def _stable_dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _print_call_hint(
    *, operation_id: str, output: Path | None, path_params: dict[str, Any] | None = None
) -> None:
    parts = ["attackiq", "call", operation_id]
    for key, value in sorted((path_params or {}).items()):
        parts.extend(["--param", f"{key}={value}"])
    if output is not None:
        parts.extend(["--body-file", str(output)])
    else:
        parts.extend(["--body", "<JSON>"])
    typer.secho("Suggested call:", err=True, fg=typer.colors.YELLOW)
    typer.secho(" ".join(parts), err=True, fg=typer.colors.YELLOW)


@build_assessment_app.command("from-template")
def build_assessment_from_template(
    ctx: typer.Context,
    template_id: Annotated[str, typer.Option("--template-id", help="Assessment template UUID.")],
    name: Annotated[str, typer.Option("--name", help="Assessment name (project_name).")],
    blueprint_id: Annotated[
        str | None,
        typer.Option("--blueprint-id", help="Blueprint UUID."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write payload JSON to a file (otherwise stdout)."),
    ] = None,
    print_call: Annotated[
        bool,
        typer.Option(
            "--print-call",
            help="Print a suggested `attackiq call ...` command to stderr.",
        ),
    ] = False,
    strict_spec: Annotated[
        bool,
        typer.Option(
            "--strict-spec",
            help="Fail if the payload does not validate against the bundled OpenAPI schema.",
        ),
    ] = False,
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_assessments_project_from_template_create")
    body: dict[str, Any] = {
        "template": _normalize_uuid(template_id, label="--template-id"),
        "project_name": (name or "").strip(),
    }
    if not body["project_name"]:
        raise typer.BadParameter("--name is required.")
    if blueprint_id is not None:
        body["blueprint"] = _normalize_uuid(blueprint_id, label="--blueprint-id")

    # Validate against the spec when possible. This endpoint's spec is generally consistent.
    schema = index.request_body_schema(op)
    if schema:
        errors = validate_json_payload(body, schema, index.resolve_schema)
        if errors:
            message = "Payload does not match spec:\n" + "\n".join(f"- {err}" for err in errors)
            if strict_spec:
                raise typer.BadParameter(message)
            typer.secho(message, err=True, fg=typer.colors.YELLOW)

    if output is None:
        write_json(sys.stdout, body)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, body)
    if print_call:
        _print_call_hint(operation_id=op.operation_id, output=output)


@build_test_app.command("create")
def build_test_create(
    ctx: typer.Context,
    assessment_id: Annotated[str, typer.Option("--assessment-id", help="Assessment UUID.")],
    name: Annotated[str, typer.Option("--name", help="Test name.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write payload JSON to a file (otherwise stdout)."),
    ] = None,
    print_call: Annotated[
        bool,
        typer.Option(
            "--print-call",
            help="Print a suggested `attackiq call ...` command to stderr.",
        ),
    ] = False,
    strict_spec: Annotated[
        bool,
        typer.Option(
            "--strict-spec",
            help="Fail if the payload does not validate against the bundled OpenAPI schema.",
        ),
    ] = False,
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_tests_create")

    # The bundled schema for v1_tests_create currently marks fields like cron_expression/insights
    # as required, but the API examples show only project+name. We enforce minimal invariants
    # here and only use spec validation as an optional strict gate.
    body: dict[str, Any] = {
        "project": _normalize_uuid(assessment_id, label="--assessment-id"),
        "name": (name or "").strip(),
    }
    if not body["name"]:
        raise typer.BadParameter("--name is required.")

    schema = index.request_body_schema(op)
    if strict_spec and schema:
        errors = validate_json_payload(body, schema, index.resolve_schema)
        if errors:
            message = "Payload does not match spec:\n" + "\n".join(f"- {err}" for err in errors)
            raise typer.BadParameter(message)

    if output is None:
        write_json(sys.stdout, body)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, body)
    if print_call:
        _print_call_hint(operation_id=op.operation_id, output=output)


@build_test_app.command("add-scenarios")
def build_test_add_scenarios(
    ctx: typer.Context,
    test_id: Annotated[str, typer.Argument(help="Test UUID.")],
    scenario_id: Annotated[
        list[str] | None,
        typer.Option("--scenario-id", help="Scenario UUID to include (repeatable)."),
    ] = None,
    scenario_ids_file: Annotated[
        Path | None,
        typer.Option(
            "--scenario-ids-file",
            exists=True,
            readable=True,
            help="Text file containing scenario UUIDs (one per line or comma-separated).",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write payload JSON to a file (otherwise stdout)."),
    ] = None,
    print_call: Annotated[
        bool,
        typer.Option(
            "--print-call",
            help="Print a suggested `attackiq call ...` command to stderr.",
        ),
    ] = False,
    strict_spec: Annotated[
        bool,
        typer.Option(
            "--strict-spec",
            help="Fail if the payload does not validate against the bundled OpenAPI schema.",
        ),
    ] = False,
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_tests_bulk_add_scenarios_create")

    requested: list[str] = []
    requested.extend([value for value in scenario_id or [] if value and value.strip()])
    if scenario_ids_file is not None:
        requested.extend(_load_uuid_list_from_file(scenario_ids_file))
    requested = _stable_dedup([value.strip() for value in requested if value.strip()])
    if not requested:
        raise typer.BadParameter("At least one --scenario-id (or --scenario-ids-file) is required.")

    include = [_normalize_uuid(value, label="scenario-id") for value in requested]
    path_params = {"id": _normalize_uuid(test_id, label="test-id")}
    body: dict[str, Any] = {"include": include}

    # The bundled schema for this endpoint is inconsistent (it points at the test serializer).
    # We still allow strict validation if desired, but default to a minimal payload.
    schema = index.request_body_schema(op)
    if strict_spec and schema:
        errors = validate_json_payload(body, schema, index.resolve_schema)
        if errors:
            message = "Payload does not match spec:\n" + "\n".join(f"- {err}" for err in errors)
            raise typer.BadParameter(message)

    if output is None:
        write_json(sys.stdout, body)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, body)
    if print_call:
        _print_call_hint(operation_id=op.operation_id, output=output, path_params=path_params)
