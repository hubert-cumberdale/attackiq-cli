from __future__ import annotations

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from attackiq_cli.spec import Operation, SpecIndex

console = Console()

spec_app = typer.Typer(
    help="Inspect the bundled OpenAPI specification.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "format_security",
    "list_operations",
    "normalize_spec_fields",
    "render_operations_table",
    "search_operations",
    "show_operation",
    "slice_operations",
    "spec_app",
]


def render_operations_table(
    operations: list[Operation],
    *,
    title: str = "Operations",
    fields: list[str] | None = None,
) -> Table:
    table = Table(title=title, box=box.MINIMAL_DOUBLE_HEAD)
    field_map = {
        "operation_id": ("OperationId", lambda op: op.operation_id),
        "method": ("Method", lambda op: op.method.upper()),
        "path": ("Path", lambda op: op.path),
        "summary": ("Summary", lambda op: op.summary or "-"),
        "tags": ("Tags", lambda op: ", ".join(op.tags)),
    }
    selected_fields = fields or ["operation_id", "method", "path", "tags"]
    for field in selected_fields:
        label, _getter = field_map[field]
        table.add_column(label)
    for op in operations:
        row = []
        for field in selected_fields:
            _label, getter = field_map[field]
            row.append(getter(op))
        table.add_row(*row)
    return table


def normalize_spec_fields(raw_fields: str | None, *, default: list[str]) -> list[str]:
    allowed = {"operation_id", "method", "path", "summary", "tags"}
    if raw_fields is None:
        return default
    fields = []
    for entry in raw_fields.split(","):
        cleaned = entry.strip().lower().replace("-", "_")
        if not cleaned:
            continue
        if cleaned not in allowed:
            raise typer.BadParameter(
                "fields must be: operation_id, method, path, summary, tags."
            )
        fields.append(cleaned)
    if not fields:
        raise typer.BadParameter(
            "fields must include at least one of: operation_id, method, path, summary, tags."
        )
    return fields


def slice_operations(
    operations: list[Operation], *, limit: int | None, offset: int
) -> list[Operation]:
    if offset < 0:
        raise typer.BadParameter("offset must be >= 0.")
    if limit is not None and limit <= 0:
        raise typer.BadParameter("limit must be >= 1.")
    if offset:
        operations = operations[offset:]
    if limit is not None:
        operations = operations[:limit]
    return operations


def format_security(entries: list[dict]) -> list[str]:
    names: list[str] = []
    for entry in entries or []:
        names.extend(entry.keys())
    return names


@spec_app.command("list")
def list_operations(
    ctx: typer.Context,
    tag: str | None = typer.Option(None, help="Filter operations by tag."),
    limit: int | None = typer.Option(None, "--limit", help="Limit number of results."),
    offset: int = typer.Option(0, "--offset", help="Offset into the results list."),
    fields: str | None = typer.Option(
        None,
        "--fields",
        help="Comma-separated fields: operation_id,method,path,summary,tags.",
    ),
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    ops = index.list_operations(tag=tag)
    selected_fields = normalize_spec_fields(
        fields, default=["operation_id", "method", "path", "tags"]
    )
    ops = slice_operations(ops, limit=limit, offset=offset)
    console.print(render_operations_table(ops, fields=selected_fields))


@spec_app.command("search")
@spec_app.command("find")
def search_operations(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search operationId, path, tags, or summary."),
    tag: str | None = typer.Option(None, help="Filter operations by tag."),
    limit: int | None = typer.Option(None, "--limit", help="Limit number of results."),
    offset: int = typer.Option(0, "--offset", help="Offset into the results list."),
    fields: str | None = typer.Option(
        None,
        "--fields",
        help="Comma-separated fields: operation_id,method,path,summary,tags.",
    ),
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    ops = index.search_operations(query, tag=tag)
    if not ops:
        console.print("[yellow]No operations matched the search query.[/yellow]")
        return
    selected_fields = normalize_spec_fields(
        fields, default=["operation_id", "method", "path", "summary", "tags"]
    )
    ops = slice_operations(ops, limit=limit, offset=offset)
    console.print(render_operations_table(ops, title="Search Results", fields=selected_fields))


@spec_app.command("show")
def show_operation(ctx: typer.Context, operation_id: str = typer.Argument(...)) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation(operation_id)
    table = Table(title=operation_id, box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Method", op.method.upper())
    table.add_row("Path", op.path)
    table.add_row("Summary", op.summary or "-")
    table.add_row("Tags", ", ".join(op.tags) or "-")
    table.add_row("Security", ", ".join(format_security(op.security)) or "-")
    if op.parameters:
        params_table = Table(title="Parameters", box=box.MINIMAL_DOUBLE_HEAD)
        params_table.add_column("Name")
        params_table.add_column("In")
        params_table.add_column("Required")
        params_table.add_column("Type")
        for param in op.parameters:
            schema = param.get("schema", {})
            params_table.add_row(
                param.get("name", ""),
                param.get("in", ""),
                "yes" if param.get("required") else "no",
                schema.get("type", ""),
            )
        console.print(params_table)
    console.print(table)
