from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = REPO_ROOT / "docs" / "contracts"


def load_contracts(*, domains: set[str] | None = None) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for path in sorted(CONTRACTS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Contract is not a mapping: {path}")
        data["_contract_path"] = str(path.relative_to(REPO_ROOT))
        validate_contract(data)
        if domains and data["domain"] not in domains:
            continue
        contracts.append(data)
    return contracts


def validate_contract(contract: dict[str, Any]) -> None:
    required = {
        "version",
        "domain",
        "title",
        "summary",
        "template",
        "generated_doc",
        "command_surface",
        "invariants",
        "artifacts",
        "code_references",
        "test_references",
        "help_checks",
    }
    missing = sorted(required - contract.keys())
    if missing:
        raise ValueError(f"Missing required contract keys: {', '.join(missing)}")

    if not isinstance(contract["command_surface"], dict):
        raise ValueError("contract.command_surface must be a mapping")
    for key in ("invariants", "artifacts", "code_references", "test_references", "help_checks"):
        if not isinstance(contract[key], list):
            raise ValueError(f"contract.{key} must be a list")


def _format_option_rows(options: list[dict[str, Any]]) -> str:
    if not options:
        return "- None"
    lines = ["| Option | Required | Default | Allowed |", "| --- | --- | --- | --- |"]
    for option in options:
        allowed = option.get("allowed_values") or []
        allowed_text = ", ".join(str(item) for item in allowed) if allowed else "-"
        default = option.get("default")
        default_text = "null" if default is None else str(default)
        required = "yes" if option.get("required") else "no"
        lines.append(
            f"| `{option.get('name', '')}` | {required} | `{default_text}` | `{allowed_text}` |"
        )
    return "\n".join(lines)


def _format_subcommand_rows(subcommands: list[dict[str, Any]]) -> str:
    if not subcommands:
        return ""
    lines = ["", "Subcommands:"]
    for subcommand in subcommands:
        name = subcommand.get("name", "")
        options = subcommand.get("options") or []
        option_text = ", ".join(f"`{item}`" for item in options) if options else "none"
        lines.append(f"- `{name}`: {option_text}")
    return "\n".join(lines)


def _format_command_surface(surface: dict[str, Any]) -> str:
    command = surface.get("command", "")
    options = surface.get("options") or []
    subcommands = surface.get("subcommands") or []
    return (
        f"Command: `{command}`\n\n"
        f"{_format_option_rows(options)}"
        f"{_format_subcommand_rows(subcommands)}"
    )


def _format_simple_list(items: list[str], *, empty_text: str = "- None") -> str:
    if not items:
        return empty_text
    return "\n".join(f"- {item}" for item in items)


def _format_code_refs(items: list[dict[str, str]]) -> str:
    if not items:
        return "- None"
    return "\n".join(
        f"- `{item['path']}` -> `{item['symbol']}`"
        for item in items
    )


def _format_test_refs(items: list[dict[str, str]]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- `{item['path']}`" for item in items)


def _format_help_checks(help_checks: list[dict[str, Any]]) -> str:
    if not help_checks:
        return "- None"
    lines: list[str] = []
    for check in help_checks:
        command = " ".join(check.get("command") or [])
        options = check.get("options") or []
        lines.append(f"- `{command}`")
        if options:
            lines.append(f"  - options: {', '.join(f'`{item}`' for item in options)}")
    return "\n".join(lines)


def render_contract(contract: dict[str, Any]) -> str:
    template_path = REPO_ROOT / str(contract["template"])
    template = template_path.read_text(encoding="utf-8")

    replacements: dict[str, str] = {
        "TITLE": str(contract["title"]),
        "SUMMARY": str(contract["summary"]),
        "COMMAND_SURFACE": _format_command_surface(contract["command_surface"]),
        "INVARIANTS": _format_simple_list(contract["invariants"]),
        "ARTIFACTS": _format_simple_list(contract["artifacts"]),
        "CODE_REFERENCES": _format_code_refs(contract["code_references"]),
        "TEST_REFERENCES": _format_test_refs(contract["test_references"]),
        "HELP_TARGETS": _format_help_checks(contract["help_checks"]),
    }

    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def compute_drift(contracts: list[dict[str, Any]]) -> list[str]:
    drift: list[str] = []
    for contract in contracts:
        output_rel = str(contract["generated_doc"])
        output_path = REPO_ROOT / output_rel
        expected = render_contract(contract)
        current = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        if expected != current:
            drift.append(output_rel)
    return drift


def write_outputs(contracts: list[dict[str, Any]]) -> None:
    for contract in contracts:
        output_path = REPO_ROOT / str(contract["generated_doc"])
        output_path.write_text(render_contract(contract), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render deep-dive docs from contracts.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated docs are out of date.",
    )
    parser.add_argument(
        "--domain",
        action="append",
        default=[],
        help="Render/check only specific domain(s).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    domains = set(args.domain) if args.domain else None
    contracts = load_contracts(domains=domains)
    if not contracts:
        print("No contracts found.")
        return 1

    if args.check:
        drift = compute_drift(contracts)
        if drift:
            print("Deep-dive docs are out of date:")
            for item in drift:
                print(f"- {item}")
            return 1
        print("Deep-dive docs are up to date.")
        return 0

    write_outputs(contracts)
    print(f"Rendered {len(contracts)} deep-dive document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
