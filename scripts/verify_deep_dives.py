from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts import render_deep_dives
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    module_path = Path(__file__).resolve().with_name("render_deep_dives.py")
    spec = importlib.util.spec_from_file_location("render_deep_dives", module_path)
    assert spec is not None
    assert spec.loader is not None
    render_deep_dives = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render_deep_dives)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _symbol_exists(path: Path, symbol: str) -> bool:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^\s*(?:def|class)\s+{re.escape(symbol)}\b", flags=re.MULTILINE)
    return bool(pattern.search(text))


def _resolve_cli_executable(requested: str) -> str:
    if requested != "attackiq":
        return requested
    local = REPO_ROOT / ".venv" / "bin" / "attackiq"
    if local.exists():
        return str(local)
    discovered = shutil.which("attackiq")
    if discovered:
        return discovered
    return requested


def run_help_command(args: list[str]) -> str:
    resolved = [_resolve_cli_executable(args[0]), *args[1:]]
    env = os.environ.copy()
    env.setdefault("COLUMNS", "220")
    result = subprocess.run(
        resolved,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout


def _collect_attackiq_help_tokens(args: list[str]) -> set[str] | None:
    if not args or args[0] != "attackiq" or args[-1] != "--help":
        return None
    try:
        attackiq_cli = importlib.import_module("attackiq_cli.cli")
        typer_main = importlib.import_module("typer.main")
    except ModuleNotFoundError:
        return None

    command = typer_main.get_command(attackiq_cli.app)
    for part in args[1:-1]:
        if not hasattr(command, "commands"):
            return None
        next_command = command.get_command(None, part)
        if next_command is None:
            return None
        command = next_command

    tokens: set[str] = set()
    if hasattr(command, "commands"):
        tokens.update(command.commands.keys())
    for param in getattr(command, "params", []):
        tokens.update(opt for opt in getattr(param, "opts", []) if opt)
        tokens.update(opt for opt in getattr(param, "secondary_opts", []) if opt)
    return tokens


def collect_verification_errors(contracts: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []

    drift = render_deep_dives.compute_drift(contracts)
    if drift:
        for item in drift:
            errors.append(f"render drift: {item}")

    for contract in contracts:
        domain = contract["domain"]

        for ref in contract["code_references"]:
            path = REPO_ROOT / ref["path"]
            symbol = ref["symbol"]
            if not path.exists():
                errors.append(f"[{domain}] missing code reference file: {ref['path']}")
                continue
            if not _symbol_exists(path, symbol):
                errors.append(f"[{domain}] missing symbol `{symbol}` in {ref['path']}")

        for ref in contract["test_references"]:
            path = REPO_ROOT / ref["path"]
            if not path.exists():
                errors.append(f"[{domain}] missing test reference file: {ref['path']}")

        for help_check in contract["help_checks"]:
            command = help_check.get("command") or []
            options = help_check.get("options") or []
            if not command:
                errors.append(f"[{domain}] empty help command in contract")
                continue
            attackiq_tokens = _collect_attackiq_help_tokens(command)
            if attackiq_tokens is not None:
                for option in options:
                    if option not in attackiq_tokens:
                        command_text = shlex.join(command)
                        message = (
                            f"[{domain}] help surface mismatch for `{command_text}`: "
                            f"missing `{option}`"
                        )
                        errors.append(
                            message
                        )
                continue
            try:
                stdout = run_help_command(command)
            except Exception as exc:  # pragma: no cover - subprocess failure path
                command_text = shlex.join(command)
                errors.append(f"[{domain}] failed help command `{command_text}`: {exc}")
                continue
            for option in options:
                if option not in stdout:
                    command_text = shlex.join(command)
                    errors.append(
                        f"[{domain}] help surface mismatch for `{command_text}`: missing `{option}`"
                    )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify deep-dive contracts and generated docs.")
    parser.add_argument(
        "--domain",
        action="append",
        default=[],
        help="Verify only specific domain(s).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    domains = set(args.domain) if args.domain else None
    contracts = render_deep_dives.load_contracts(domains=domains)
    errors = collect_verification_errors(contracts)
    if errors:
        print("Deep-dive verification failed:")
        for item in errors:
            print(f"- {item}")
        return 1
    print("Deep-dive verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
