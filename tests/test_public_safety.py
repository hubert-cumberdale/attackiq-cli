from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PUBLIC_SAFETY_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_public_safety.py"
_PUBLIC_SAFETY_SPEC = importlib.util.spec_from_file_location(
    "check_public_safety", _PUBLIC_SAFETY_PATH
)
assert _PUBLIC_SAFETY_SPEC is not None
assert _PUBLIC_SAFETY_SPEC.loader is not None
check_public_safety = importlib.util.module_from_spec(_PUBLIC_SAFETY_SPEC)
sys.modules[_PUBLIC_SAFETY_SPEC.name] = check_public_safety
_PUBLIC_SAFETY_SPEC.loader.exec_module(check_public_safety)


def test_public_safety_tracked_files_pass():
    assert check_public_safety.check_public_safety(scan_package=False) == []


def test_public_safety_rejects_blocked_reference():
    blocked_name = "Hy" + "dra"
    errors = check_public_safety._scan_text("example.md", f"see the private {blocked_name} export")

    assert errors == ["example.md:1: blocked private exposure repository name"]


def test_public_safety_rejects_disallowed_wheel_paths():
    errors = check_public_safety.validate_wheel_entries(
        ["attackiq_cli/cli.py", "docs/internal.md", "taskpacks/example/task.yml"]
    )

    assert errors == [
        "wheel contains disallowed path: docs/internal.md",
        "wheel contains disallowed path: taskpacks/example/task.yml",
    ]
