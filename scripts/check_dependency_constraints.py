"""Verify dependency metadata and pinned constraints stay aligned."""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback.
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
PIN_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)==")


def normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def requirement_name(value: str) -> str:
    match = NAME_RE.match(value)
    if not match:
        raise ValueError(f"Unable to parse requirement name: {value!r}")
    return normalize_name(match.group(1))


def load_pyproject() -> tuple[list[str], list[str]]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    runtime = list(project.get("dependencies", []))
    dev = list(project.get("optional-dependencies", {}).get("dev", []))
    return runtime, dev


def load_requirement_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def load_constraints(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.match(line)
        if not match:
            raise ValueError(f"Constraint must use an exact == pin: {line!r}")
        pins[normalize_name(match.group(1))] = line
    return pins


def main() -> int:
    runtime, dev = load_pyproject()
    requirements = load_requirement_lines(ROOT / "requirements.txt")
    constraints = load_constraints(ROOT / "constraints.txt")

    runtime_by_name = {requirement_name(line): line for line in runtime}
    requirements_by_name = {requirement_name(line): line for line in requirements}
    if runtime_by_name != requirements_by_name:
        print("requirements.txt does not match [project].dependencies.", file=sys.stderr)
        print(f"pyproject: {sorted(runtime_by_name.values())}", file=sys.stderr)
        print(f"requirements: {sorted(requirements_by_name.values())}", file=sys.stderr)
        return 1

    direct_names = {requirement_name(line) for line in runtime}
    direct_names.update(requirement_name(line) for line in dev)
    direct_names.add("pip-audit")
    missing = sorted(name for name in direct_names if name not in constraints)
    if missing:
        print("constraints.txt is missing direct dependency pins:", file=sys.stderr)
        for name in missing:
            print(f"- {name}", file=sys.stderr)
        return 1

    print("Dependency metadata and constraints are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
