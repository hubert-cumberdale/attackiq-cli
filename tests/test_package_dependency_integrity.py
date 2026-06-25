from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_INTEGRITY_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "package_dependency_integrity.py"
)
_INTEGRITY_SPEC = importlib.util.spec_from_file_location(
    "package_dependency_integrity",
    _INTEGRITY_PATH,
)
assert _INTEGRITY_SPEC is not None
assert _INTEGRITY_SPEC.loader is not None
package_dependency_integrity = importlib.util.module_from_spec(_INTEGRITY_SPEC)
sys.modules[_INTEGRITY_SPEC.name] = package_dependency_integrity
_INTEGRITY_SPEC.loader.exec_module(package_dependency_integrity)


def test_build_dependency_integrity_records_exact_pins(tmp_path: Path) -> None:
    constraints_path = tmp_path / package_dependency_integrity.CONSTRAINTS_FILE_NAME
    constraints_path.write_text("# comment\nhttpx==0.27.2\nrich==13.9.4\n", encoding="utf-8")
    constraints_sha256 = package_dependency_integrity.sha256_file(constraints_path)
    manifest = {
        "constraints_file": {
            "filename": constraints_path.name,
            "sha256": constraints_sha256,
            "type": "install-constraints",
        }
    }

    integrity = package_dependency_integrity.build_dependency_integrity(
        constraints_path=constraints_path,
        constraints_sha256=constraints_sha256,
        generated_utc="2026-05-28T00:00:00+00:00",
    )
    integrity_path = package_dependency_integrity.write_dependency_integrity(tmp_path, integrity)
    loaded, load_errors = package_dependency_integrity.load_dependency_integrity(integrity_path)

    assert load_errors == []
    assert loaded is not None
    assert loaded["constraints"]["pinned_dependency_count"] == 2
    assert [item["normalized_name"] for item in loaded["pinned_dependencies"]] == [
        "httpx",
        "rich",
    ]
    assert package_dependency_integrity.validate_dependency_integrity(
        package_dir=tmp_path,
        manifest=manifest,
        integrity=loaded,
        integrity_filename=package_dependency_integrity.DEPENDENCY_INTEGRITY_NAME,
    ) == []


def test_validate_dependency_integrity_rejects_mismatched_constraints(tmp_path: Path) -> None:
    constraints_path = tmp_path / package_dependency_integrity.CONSTRAINTS_FILE_NAME
    constraints_path.write_text("httpx==0.27.2\n", encoding="utf-8")
    constraints_sha256 = package_dependency_integrity.sha256_file(constraints_path)
    manifest = {
        "constraints_file": {
            "filename": constraints_path.name,
            "sha256": constraints_sha256,
            "type": "install-constraints",
        }
    }
    integrity = package_dependency_integrity.build_dependency_integrity(
        constraints_path=constraints_path,
        constraints_sha256=constraints_sha256,
        generated_utc="2026-05-28T00:00:00+00:00",
    )
    tampered = json.loads(json.dumps(integrity))
    tampered["pinned_dependencies"][0]["version"] = "0.27.3"

    errors = package_dependency_integrity.validate_dependency_integrity(
        package_dir=tmp_path,
        manifest=manifest,
        integrity=tampered,
        integrity_filename=package_dependency_integrity.DEPENDENCY_INTEGRITY_NAME,
    )

    assert (
        f"{package_dependency_integrity.DEPENDENCY_INTEGRITY_NAME}: "
        "pinned_dependencies must match constraints.txt"
    ) in errors
