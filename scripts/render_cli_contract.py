#!/usr/bin/env python3
"""Render or verify the committed Typer/Click command-tree contract fixture."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

import click
from typer.main import get_command

from attackiq_cli.cli import app

ROOT_COMMAND = "attackiq"
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "tests/fixtures/cli_command_tree.json"
SCHEMA_VERSION = 1


def _normalize_path_default(value: Path) -> str:
    if not value.is_absolute():
        return value.as_posix()
    parts = value.parts
    if "attackiq_cli" not in parts:
        raise ValueError(f"absolute CLI default is not a package resource: {value.name}")
    package_index = len(parts) - 1 - tuple(reversed(parts)).index("attackiq_cli")
    return f"package://{'/'.join(parts[package_index:])}"


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Path):
        return _normalize_path_default(value)
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise TypeError(f"unsupported CLI metadata value: {type(value).__name__}")


def _serialize_parameter(parameter: click.Parameter, *, source: str) -> dict[str, Any]:
    return {
        "count": bool(getattr(parameter, "count", False)),
        "default": _json_value(parameter.default),
        "envvar": _json_value(parameter.envvar),
        "flag_value": _json_value(getattr(parameter, "flag_value", None)),
        "help": getattr(parameter, "help", None),
        "hidden": bool(getattr(parameter, "hidden", False)),
        "is_eager": bool(getattr(parameter, "is_eager", False)),
        "is_flag": bool(getattr(parameter, "is_flag", False)),
        "kind": parameter.param_type_name,
        "metavar": parameter.metavar,
        "multiple": parameter.multiple,
        "name": parameter.name,
        "nargs": parameter.nargs,
        "opts": list(getattr(parameter, "opts", [])),
        "required": parameter.required,
        "secondary_opts": list(getattr(parameter, "secondary_opts", [])),
        "show_choices": getattr(parameter, "show_choices", None),
        "show_default": _json_value(getattr(parameter, "show_default", None)),
        "source": source,
        "type": _json_value(parameter.type.to_info_dict()),
    }


def _command_context(
    command: click.Command,
    *,
    name: str,
    parent: click.Context | None,
) -> click.Context:
    settings = dict(command.context_settings or {})
    return click.Context(command, info_name=name, parent=parent, **settings)


def _serialize_command(
    command: click.Command,
    *,
    path: str,
    context: click.Context,
) -> dict[str, Any]:
    parameters = [
        _serialize_parameter(parameter, source="declared") for parameter in command.params
    ]
    help_option = command.get_help_option(context)
    if help_option is not None:
        parameters.append(_serialize_parameter(help_option, source="automatic-help"))

    subcommands = sorted(command.commands) if isinstance(command, click.Group) else []
    return {
        "deprecated": _json_value(command.deprecated),
        "epilog": command.epilog,
        "help": command.help,
        "hidden": command.hidden,
        "kind": "group" if isinstance(command, click.Group) else "command",
        "name": command.name,
        "no_args_is_help": bool(getattr(command, "no_args_is_help", False)),
        "parameters": parameters,
        "path": path,
        "short_help": command.short_help,
        "subcommands": subcommands,
    }


def build_contract() -> dict[str, Any]:
    root = get_command(app)
    commands: list[dict[str, Any]] = []

    def visit(
        command: click.Command,
        *,
        path: str,
        name: str,
        parent: click.Context | None,
    ) -> None:
        context = _command_context(command, name=name, parent=parent)
        commands.append(_serialize_command(command, path=path, context=context))
        if not isinstance(command, click.Group):
            return
        for child_name in sorted(command.commands):
            child = command.get_command(context, child_name)
            if child is None:
                raise ValueError(f"registered command could not be resolved: {path} {child_name}")
            visit(
                child,
                path=f"{path} {child_name}",
                name=child_name,
                parent=context,
            )

    visit(root, path=ROOT_COMMAND, name=ROOT_COMMAND, parent=None)
    return {
        "command_count": len(commands),
        "commands": commands,
        "declared_parameter_count": sum(
            1
            for command in commands
            for parameter in command["parameters"]
            if parameter["source"] == "declared"
        ),
        "root": ROOT_COMMAND,
        "schema_version": SCHEMA_VERSION,
    }


def render_contract() -> str:
    return f"{json.dumps(build_contract(), indent=2, sort_keys=True)}\n"


def check_fixture(path: Path = FIXTURE_PATH) -> bool:
    if not path.exists():
        print(f"CLI contract fixture is missing: {path}", file=sys.stderr)
        return False
    expected = path.read_text(encoding="utf-8")
    actual = render_contract()
    if expected == actual:
        print("CLI command-tree contract is up to date.")
        return True
    print("CLI command-tree contract drift detected:", file=sys.stderr)
    diff = difflib.unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        fromfile=str(path),
        tofile="current Typer/Click metadata",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    print(
        "Review the public CLI change, then rerun scripts/render_cli_contract.py if intentional.",
        file=sys.stderr,
    )
    return False


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed fixture differs from current Typer/Click metadata.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=FIXTURE_PATH,
        help="Fixture path to write or verify.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    output = args.output
    if args.check:
        return 0 if check_fixture(output) else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_contract(), encoding="utf-8")
    print(f"Wrote CLI command-tree contract: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
