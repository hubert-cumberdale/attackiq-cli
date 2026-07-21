from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SECRET_SCAN_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_secret_scan.py"
_SECRET_SCAN_SPEC = importlib.util.spec_from_file_location("check_secret_scan", _SECRET_SCAN_PATH)
assert _SECRET_SCAN_SPEC is not None
assert _SECRET_SCAN_SPEC.loader is not None
check_secret_scan = importlib.util.module_from_spec(_SECRET_SCAN_SPEC)
sys.modules[_SECRET_SCAN_SPEC.name] = check_secret_scan
_SECRET_SCAN_SPEC.loader.exec_module(check_secret_scan)


def test_secret_scan_detects_assignment_without_echoing_secret() -> None:
    candidate = "sk_live_" + "1234567890abcdef"

    errors = check_secret_scan.scan_text("fixture.env", f"api_token={candidate}\n")

    assert errors == ["fixture.env:1: possible secret assignment"]
    assert candidate not in errors[0]


def test_secret_scan_ignores_placeholders() -> None:
    assert check_secret_scan.scan_text("docs/example.md", "token=<token>\n") == []
    assert check_secret_scan.scan_text("docs/example.md", "password=${PASSWORD}\n") == []


def test_secret_scan_allowlist_suppresses_matching_line() -> None:
    candidate = "sk_live_" + "1234567890abcdef"
    allowlist = (
        check_secret_scan.AllowlistEntry(
            path="fixture.env",
            labels=frozenset({"secret assignment"}),
            line_contains="api_token",
            note="intentional fixture",
        ),
    )

    errors = check_secret_scan.scan_text(
        "fixture.env",
        f"api_token={candidate}\n",
        allowlist=allowlist,
    )

    assert errors == []


def test_secret_scan_loads_allowlist(tmp_path: Path) -> None:
    path = tmp_path / "allowlist.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "allowlist": [
                    {
                        "path": "tests/fixture.txt",
                        "labels": ["secret assignment"],
                        "line_contains": "known fixture",
                        "note": "document why this fixture is safe",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    entries = check_secret_scan.load_allowlist(path)

    assert entries == (
        check_secret_scan.AllowlistEntry(
            path="tests/fixture.txt",
            labels=frozenset({"secret assignment"}),
            line_contains="known fixture",
            note="document why this fixture is safe",
        ),
    )
