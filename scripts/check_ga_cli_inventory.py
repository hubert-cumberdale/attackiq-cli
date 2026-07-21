#!/usr/bin/env python3
"""Verify the documented GA CLI inventory against metadata and classifications."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PATH = ROOT / "docs/GA_STABLE_CONTRACT.md"
CLI_FIXTURE_PATH = ROOT / "tests/fixtures/cli_command_tree.json"
CLASSIFICATION_PATH = ROOT / "tests/fixtures/ga_cli_inventory.json"

INVENTORY_START = "## Command And Option Inventory"
INVENTORY_END = "## Persisted Configuration Inventory"
ALLOWED_CLASSIFICATIONS = {"excluded", "proposed-stable"}
OPTION_RE = re.compile(r"(?<![\w-])(?:--[a-z0-9][a-z0-9-]*|-[A-Za-z0-9])(?![\w-])")
OPTION_VALUE_RE = re.compile(r"(--[a-z0-9][a-z0-9-]*)\s+([A-Za-z0-9][A-Za-z0-9_-]*)")
FENCE_RE = re.compile(r"```text\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class DocumentedInventory:
    commands: frozenset[str]
    options: dict[str, frozenset[str]]
    option_values: dict[str, frozenset[str]]


def _inventory_region(document: str) -> str:
    if INVENTORY_START not in document or INVENTORY_END not in document:
        raise ValueError("GA command inventory headings are missing")
    inventory = document.split(INVENTORY_START, 1)[1].split(INVENTORY_END, 1)[0]
    if not inventory.strip():
        raise ValueError("GA command inventory is empty")
    return inventory


def _command_path(line: str) -> str:
    tokens = line.split()
    command_tokens: list[str] = []
    for token in tokens:
        if token.startswith(("-", "<", "[")):
            break
        command_tokens.append(token)
    if not command_tokens or command_tokens[0] != "attackiq":
        raise ValueError(f"invalid documented command line: {line}")
    return " ".join(command_tokens)


def parse_documented_inventory(document: str) -> DocumentedInventory:
    commands: set[str] = set()
    options: dict[str, set[str]] = {}
    option_values: dict[str, set[str]] = {}

    fences = FENCE_RE.findall(_inventory_region(document))
    if not fences:
        raise ValueError("GA command inventory contains no text fences")

    for fence in fences:
        current_command: str | None = None
        for raw_line in fence.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("attackiq"):
                current_command = _command_path(line)
                commands.add(current_command)
                options.setdefault(current_command, set())
                option_values.setdefault(current_command, set())
                for option, value in OPTION_VALUE_RE.findall(line):
                    option_values[current_command].add(f"{option}={value}")
            elif current_command is None:
                raise ValueError(f"option line appears before a command: {line}")
            options[current_command].update(OPTION_RE.findall(line))

    for command in commands:
        options[command].add("--help")

    return DocumentedInventory(
        commands=frozenset(commands),
        options={command: frozenset(values) for command, values in options.items()},
        option_values={
            command: frozenset(values)
            for command, values in option_values.items()
            if values
        },
    )


def cli_surfaces(contract: dict[str, Any]) -> dict[str, set[str]]:
    surfaces: dict[str, set[str]] = {}
    for command in contract["commands"]:
        command_options: set[str] = set()
        for parameter in command["parameters"]:
            command_options.update(parameter["opts"])
            command_options.update(parameter["secondary_opts"])
        surfaces[command["path"]] = command_options
    return surfaces


def _classification_maps(
    classification: dict[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    if classification.get("schema_version") != 1:
        raise ValueError("GA CLI inventory classification schema_version must be 1")
    commands = classification.get("commands")
    options = classification.get("options")
    option_values = classification.get("option_values")
    if not isinstance(commands, dict) or not isinstance(options, dict):
        raise ValueError("GA CLI inventory classifications must define commands and options")
    if not isinstance(option_values, dict):
        raise ValueError("GA CLI inventory classifications must define option_values")
    return commands, options, option_values


def _surface_differences(
    *,
    label: str,
    expected: set[str] | frozenset[str],
    actual: set[str] | frozenset[str],
) -> list[str]:
    errors: list[str] = []
    missing = sorted(expected - actual)
    stale = sorted(actual - expected)
    if missing:
        errors.append(f"unclassified documented {label}: {', '.join(missing)}")
    if stale:
        errors.append(f"classified {label} absent from documentation: {', '.join(stale)}")
    return errors


def validate_inventory(
    documented: DocumentedInventory,
    contract: dict[str, Any],
    classification: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    cli = cli_surfaces(contract)
    command_classes, option_classes, option_value_classes = _classification_maps(classification)

    for command in sorted(documented.commands):
        if command not in cli:
            errors.append(f"documented command absent from CLI metadata: {command}")
            continue
        for option in sorted(documented.options[command] - cli[command]):
            errors.append(f"documented option absent from CLI metadata: {command} {option}")

    errors.extend(
        _surface_differences(
            label="commands",
            expected=documented.commands,
            actual=set(command_classes),
        )
    )
    errors.extend(
        _surface_differences(
            label="option command groups",
            expected=documented.commands,
            actual=set(option_classes),
        )
    )
    for command in sorted(documented.commands & set(option_classes)):
        errors.extend(
            _surface_differences(
                label=f"options for {command}",
                expected=documented.options[command],
                actual=set(option_classes[command]),
            )
        )
    errors.extend(
        _surface_differences(
            label="option-value command groups",
            expected=set(documented.option_values),
            actual=set(option_value_classes),
        )
    )
    for command in sorted(set(documented.option_values) & set(option_value_classes)):
        errors.extend(
            _surface_differences(
                label=f"option values for {command}",
                expected=documented.option_values[command],
                actual=set(option_value_classes[command]),
            )
        )

    classified_values: list[tuple[str, str]] = []
    classified_values.extend(
        (f"command {surface}", value) for surface, value in command_classes.items()
    )
    classified_values.extend(
        (f"option {command} {surface}", value)
        for command, surfaces in option_classes.items()
        for surface, value in surfaces.items()
    )
    classified_values.extend(
        (f"option value {command} {surface}", value)
        for command, surfaces in option_value_classes.items()
        for surface, value in surfaces.items()
    )
    for surface, value in classified_values:
        if value not in ALLOWED_CLASSIFICATIONS:
            errors.append(f"invalid classification for {surface}: {value!r}")

    experimental_command = "attackiq platform-api parity"
    if command_classes.get(experimental_command) != "excluded":
        errors.append(f"experimental command must remain excluded: {experimental_command}")
    for option, value in option_classes.get(experimental_command, {}).items():
        if value != "excluded":
            errors.append(
                f"experimental option must remain excluded: {experimental_command} {option}"
            )
    for command, surfaces in option_classes.items():
        if surfaces.get("--apply") not in {None, "excluded"}:
            errors.append(f"apply option must remain excluded: {command} --apply")
    for command, surfaces in option_value_classes.items():
        for surface, value in surfaces.items():
            if surface.endswith("=platform-api") and value != "excluded":
                errors.append(
                    f"experimental option value must remain excluded: {command} {surface}"
                )
    return errors


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def check_inventory(
    *,
    document_path: Path = DOCUMENT_PATH,
    cli_fixture_path: Path = CLI_FIXTURE_PATH,
    classification_path: Path = CLASSIFICATION_PATH,
) -> bool:
    try:
        documented = parse_documented_inventory(document_path.read_text(encoding="utf-8"))
        errors = validate_inventory(
            documented,
            _load_json(cli_fixture_path),
            _load_json(classification_path),
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"GA CLI inventory check could not run: {exc}", file=sys.stderr)
        return False
    if errors:
        print("GA CLI inventory parity failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return False
    print(
        "GA CLI inventory matches CLI metadata and every documented surface is classified."
    )
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", type=Path, default=DOCUMENT_PATH)
    parser.add_argument("--cli-fixture", type=Path, default=CLI_FIXTURE_PATH)
    parser.add_argument("--classifications", type=Path, default=CLASSIFICATION_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return (
        0
        if check_inventory(
            document_path=args.document,
            cli_fixture_path=args.cli_fixture,
            classification_path=args.classifications,
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
