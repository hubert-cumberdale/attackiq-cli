#!/usr/bin/env python3
"""Run the standard local quality gate for this repository."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class GateCommand:
    name: str
    argv: list[str]


def build_commands(*, include_mkdocs: bool = True) -> list[GateCommand]:
    python = sys.executable
    commands = [
        GateCommand("dependency constraints", [python, "scripts/check_dependency_constraints.py"]),
        GateCommand("release governance", [python, "scripts/check_release_governance.py"]),
        GateCommand("public safety", [python, "scripts/check_public_safety.py"]),
        GateCommand(
            "public mirror dry run",
            [python, "scripts/check_public_mirror.py", "--allow-dirty", "--skip-wheel"],
        ),
        GateCommand(
            "AIQ Assist MCP provider contract",
            [python, "scripts/check_aiq_assist_mcp_contract.py"],
        ),
        GateCommand(
            "AIQ Assist MCP fixtures",
            [python, "scripts/check_aiq_assist_mcp_fixtures.py"],
        ),
        GateCommand(
            "ruff",
            [
                python,
                "-m",
                "ruff",
                "check",
                "src",
                "tests",
                "scripts/quality_gate.py",
                "scripts/check_public_mirror.py",
                "scripts/check_public_safety.py",
                "scripts/check_release_governance.py",
                "scripts/check_aiq_assist_mcp_contract.py",
                "scripts/check_aiq_assist_mcp_fixtures.py",
                "scripts/live_smoke.py",
            ],
        ),
        GateCommand(
            "mypy",
            [python, "-m", "mypy", "src", "tests", "--cache-dir", "/tmp/aiq-cli-mypy"],
        ),
        GateCommand("pytest", [python, "-m", "pytest", "-q"]),
        GateCommand("doc links", [python, "scripts/check_doc_links.py"]),
    ]
    if include_mkdocs:
        commands.append(GateCommand("mkdocs", [python, "-m", "mkdocs", "build"]))
    return commands


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    parser.add_argument(
        "--no-mkdocs",
        action="store_true",
        help="Skip MkDocs build when docs dependencies are intentionally absent.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    commands = build_commands(include_mkdocs=not args.no_mkdocs)
    for command in commands:
        printable = " ".join(command.argv)
        print(f"==> {command.name}: {printable}", flush=True)
        if args.dry_run:
            continue
        completed = subprocess.run(command.argv, cwd=ROOT, check=False)
        if completed.returncode:
            print(f"quality gate failed at: {command.name}", file=sys.stderr)
            return completed.returncode
    print("quality gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
