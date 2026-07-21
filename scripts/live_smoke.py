#!/usr/bin/env python3
"""Run the approved low-risk production smoke workflow with redacted summaries."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from attackiq_cli.config import ConfigError, effective_base_url, load_config

ROOT = Path(__file__).resolve().parents[1]
OPT_IN_ENV = "ATTACKIQ_LIVE_SMOKE"
DEFAULT_PAGE_SIZE = 5
MAX_PAGE_SIZE = 5
DEFAULT_TIMEOUT = 30.0
SUMMARY_LIMIT = 2_000

FAKE_SCENARIO_ID = "00000000-0000-4000-8000-000000000001"
FAKE_ASSESSMENT_ID = "00000000-0000-4000-8000-000000000002"
FAKE_TEST_ID = "00000000-0000-4000-8000-000000000003"

URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(account[_-]?token|authorization|jwt|password|secret|token)"
    r"([\"']?\s*[:=]\s*[\"']?)"
    r"([^\"'\s,}]+)"
)


@dataclass(frozen=True)
class SmokeCommand:
    name: str
    argv: list[str]
    category: str
    output: Path | None = None
    expected_kind: str = "status"


Runner = Callable[..., subprocess.CompletedProcess[str]]


def default_output_dir(now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.gettempdir()) / f"aiq-cli-live-smoke-{timestamp}"


def build_commands(
    output_dir: Path,
    *,
    python: str = sys.executable,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[SmokeCommand]:
    timeout_value = str(timeout)
    module = [python, "-m", "attackiq_cli"]

    def output_file(name: str) -> Path:
        return output_dir / name

    commands = [
        SmokeCommand(
            "config validate",
            [*module, "config", "validate"],
            category="configuration",
        ),
        SmokeCommand(
            "spec list",
            [
                *module,
                "spec",
                "list",
                "--limit",
                "3",
                "--fields",
                "operation_id,method,path",
            ],
            category="local-spec",
        ),
        SmokeCommand(
            "tags list",
            [
                *module,
                "tags",
                "list",
                "--page",
                "1",
                "--page-size",
                str(page_size),
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("tags.json")),
            ],
            category="read-only",
            output=output_file("tags.json"),
            expected_kind="records",
        ),
        SmokeCommand(
            "scenarios list",
            [
                *module,
                "scenarios",
                "list",
                "--page",
                "1",
                "--page-size",
                str(page_size),
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("scenarios.json")),
            ],
            category="read-only",
            output=output_file("scenarios.json"),
            expected_kind="records",
        ),
        SmokeCommand(
            "assets list",
            [
                *module,
                "assets",
                "list",
                "--page",
                "1",
                "--page-size",
                str(page_size),
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("assets.json")),
            ],
            category="read-only",
            output=output_file("assets.json"),
            expected_kind="records",
        ),
        SmokeCommand(
            "assessments list",
            [
                *module,
                "assessments",
                "list",
                "--page",
                "1",
                "--page-size",
                str(page_size),
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("assessments.json")),
            ],
            category="read-only",
            output=output_file("assessments.json"),
            expected_kind="records",
        ),
        SmokeCommand(
            "tests list",
            [
                *module,
                "tests",
                "list",
                "--page",
                "1",
                "--page-size",
                str(page_size),
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("tests.json")),
            ],
            category="read-only",
            output=output_file("tests.json"),
            expected_kind="records",
        ),
        SmokeCommand(
            "assessments create dry-run",
            [
                *module,
                "assessments",
                "create",
                "--name",
                "Production Smoke Dry Run",
                "--scenario-id",
                FAKE_SCENARIO_ID,
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("assessment-create-plan.json")),
            ],
            category="fake-id-dry-run",
            output=output_file("assessment-create-plan.json"),
            expected_kind="call-plan",
        ),
        SmokeCommand(
            "tests create dry-run",
            [
                *module,
                "tests",
                "create",
                "--assessment-id",
                FAKE_ASSESSMENT_ID,
                "--name",
                "Production Smoke Dry Run",
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("test-create-plan.json")),
            ],
            category="fake-id-dry-run",
            output=output_file("test-create-plan.json"),
            expected_kind="call-plan",
        ),
        SmokeCommand(
            "tests add-scenarios dry-run",
            [
                *module,
                "tests",
                "add-scenarios",
                FAKE_TEST_ID,
                "--scenario-id",
                FAKE_SCENARIO_ID,
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("test-add-scenarios-plan.json")),
            ],
            category="fake-id-dry-run",
            output=output_file("test-add-scenarios-plan.json"),
            expected_kind="call-plan",
        ),
        SmokeCommand(
            "assessments run dry-run",
            [
                *module,
                "assessments",
                "run",
                FAKE_ASSESSMENT_ID,
                "--timeout",
                timeout_value,
                "--output",
                str(output_file("assessment-run-plan.json")),
            ],
            category="fake-id-dry-run",
            output=output_file("assessment-run-plan.json"),
            expected_kind="call-plan",
        ),
    ]
    return commands


def sensitive_env_values(env: Mapping[str, str]) -> list[str]:
    sensitive_keys = {
        "ATTACKIQ_ACCOUNT_TOKEN",
        "ATTACKIQ_JWT",
        "ATTACKIQ_BASE_URL",
    }
    values = []
    for key, value in env.items():
        if not value:
            continue
        key_upper = key.upper()
        if key_upper in sensitive_keys or any(
            marker in key_upper for marker in ("TOKEN", "PASSWORD", "SECRET", "JWT")
        ):
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def redact_text(text: str, *, env: Mapping[str, str] | None = None) -> str:
    redacted = text
    redacted = URL_RE.sub("<redacted-url>", redacted)
    for value in sensitive_env_values(env or os.environ):
        redacted = redacted.replace(value, "<redacted>")
    redacted = BEARER_RE.sub("Bearer <redacted>", redacted)
    redacted = SECRET_ASSIGNMENT_RE.sub(r"\1\2<redacted>", redacted)
    if len(redacted) > SUMMARY_LIMIT:
        redacted = f"{redacted[:SUMMARY_LIMIT]}... [truncated]"
    return redacted


def load_json_file(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def count_records(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("results", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return 1
    return 0


def summarize_command(command: SmokeCommand) -> str:
    if command.output is None:
        return "ok"
    if not command.output.exists():
        raise FileNotFoundError(f"expected output missing: {command.output}")
    payload = load_json_file(command.output)
    if command.expected_kind == "records":
        return f"records={count_records(payload)}"
    if command.expected_kind == "call-plan" and isinstance(payload, dict):
        operation_id = payload.get("operation_id", "unknown")
        if not operation_id or operation_id == "unknown":
            raise ValueError(f"call plan missing operation_id: {command.output}")
        return f"operation_id={operation_id}"
    return "ok"


def print_plan(commands: Sequence[SmokeCommand]) -> None:
    print("Planned live smoke commands:")
    for command in commands:
        print(f"- {command.name}: {' '.join(command.argv)}")
    print("No apply-mode commands are included.")


def tls_preflight_error() -> str | None:
    """Return a public-safe refusal reason unless the effective config requires verified TLS."""
    try:
        config = load_config()
        base_url = effective_base_url(config)
    except ConfigError:
        return "effective configuration is invalid"
    if not config.verify_tls:
        return "TLS verification is disabled in persisted configuration"
    if not base_url:
        return "effective base URL is not configured"
    if not base_url.startswith("https://"):
        return "effective base URL does not use https://"
    return None


def run_smoke(
    commands: Sequence[SmokeCommand],
    *,
    output_dir: Path,
    runner: Runner = subprocess.run,
    env: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> int:
    effective_env = dict(env or os.environ)
    output_dir.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        output_dir.chmod(0o700)

    print(f"Output directory: {output_dir}")
    for command in commands:
        try:
            completed = runner(
                command.argv,
                cwd=ROOT,
                env=effective_env,
                capture_output=True,
                text=True,
                timeout=timeout + 5.0,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            print(f"FAIL {command.name}: timed out after {exc.timeout} seconds", file=sys.stderr)
            details = "\n".join(
                str(part) for part in (exc.stderr, exc.stdout) if part is not None
            )
            if details:
                print(redact_text(details, env=effective_env), file=sys.stderr)
            return 124
        if completed.returncode:
            print(f"FAIL {command.name}: exit {completed.returncode}", file=sys.stderr)
            details = "\n".join(part for part in (completed.stderr, completed.stdout) if part)
            if details:
                print(redact_text(details, env=effective_env), file=sys.stderr)
            return completed.returncode
        try:
            summary = summarize_command(command)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"FAIL {command.name}: invalid output: {exc}", file=sys.stderr)
            return 1
        print(f"PASS {command.name}: {summary}")
    print("No apply-mode commands were run.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Directory for raw tenant outputs; keep it outside git.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"Bounded page size for read-only list commands (maximum {MAX_PAGE_SIZE}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Timeout in seconds passed to networked CLI commands.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned command set without requiring live-smoke opt-in.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.page_size < 1:
        print("--page-size must be >= 1.", file=sys.stderr)
        return 2
    if args.page_size > MAX_PAGE_SIZE:
        print(f"--page-size must be <= {MAX_PAGE_SIZE}.", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("--timeout must be greater than zero.", file=sys.stderr)
        return 2

    output_dir = args.output_dir.expanduser()
    commands = build_commands(output_dir, page_size=args.page_size, timeout=args.timeout)
    if args.dry_run:
        print_plan(commands)
        return 0
    if os.environ.get(OPT_IN_ENV) != "1":
        print(
            f"Refusing live smoke without {OPT_IN_ENV}=1. "
            "Use --dry-run to review the planned command set.",
            file=sys.stderr,
        )
        return 2
    preflight_error = tls_preflight_error()
    if preflight_error:
        print(
            f"Refusing live smoke: {preflight_error}. "
            "Use an https:// base URL and enable TLS verification before retrying.",
            file=sys.stderr,
        )
        return 2
    return run_smoke(commands, output_dir=output_dir, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
