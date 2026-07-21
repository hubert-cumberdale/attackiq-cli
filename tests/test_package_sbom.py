from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

_SBOM_PATH = Path(__file__).resolve().parents[1] / "scripts" / "package_sbom.py"
_SBOM_SPEC = importlib.util.spec_from_file_location("package_sbom", _SBOM_PATH)
assert _SBOM_SPEC is not None
assert _SBOM_SPEC.loader is not None
package_sbom = importlib.util.module_from_spec(_SBOM_SPEC)
sys.modules[_SBOM_SPEC.name] = package_sbom
_SBOM_SPEC.loader.exec_module(package_sbom)


def _write_wheel(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr("attackiq_cli/__init__.py", "__version__ = '1.2.3'\n")
        wheel.writestr(
            "attackiq_cli-1.2.3.dist-info/METADATA",
            "Metadata-Version: 2.1\n"
            "Name: attackiq-cli\n"
            "Version: 1.2.3\n"
            "Requires-Dist: httpx>=0.27,<0.28\n"
            "Requires-Dist: rich>=13,<14\n",
        )


def test_build_package_sbom_records_root_and_dependencies(tmp_path: Path) -> None:
    wheel_path = tmp_path / "attackiq_cli-1.2.3-py3-none-any.whl"
    _write_wheel(wheel_path)
    manifest = {
        "source_ref": "v1.2.3",
        "source_commit": "abc123",
        "package_version": "1.2.3",
        "artifacts": [
            {
                "filename": wheel_path.name,
                "sha256": "a" * 64,
                "type": "wheel",
            }
        ],
    }

    sbom = package_sbom.build_package_sbom(
        manifest=manifest,
        wheel_path=wheel_path,
        wheel_sha256="a" * 64,
        generated_utc="2026-05-28T00:00:00+00:00",
    )
    sbom_path = package_sbom.write_package_sbom(tmp_path, sbom)
    loaded, load_errors = package_sbom.load_package_sbom(sbom_path)

    assert load_errors == []
    assert loaded is not None
    assert loaded["spdxVersion"] == "SPDX-2.3"
    package_names = {package["name"] for package in loaded["packages"]}
    assert {"attackiq-cli", "httpx", "rich"} <= package_names
    assert package_sbom.validate_package_sbom(
        manifest=manifest,
        sbom=loaded,
        sbom_filename=package_sbom.SBOM_NAME,
    ) == []


def test_validate_package_sbom_rejects_root_checksum_mismatch(tmp_path: Path) -> None:
    wheel_path = tmp_path / "attackiq_cli-1.2.3-py3-none-any.whl"
    _write_wheel(wheel_path)
    manifest = {
        "package_version": "1.2.3",
        "artifacts": [{"filename": wheel_path.name, "sha256": "b" * 64, "type": "wheel"}],
    }
    sbom = package_sbom.build_package_sbom(
        manifest=manifest,
        wheel_path=wheel_path,
        wheel_sha256="a" * 64,
        generated_utc="2026-05-28T00:00:00+00:00",
    )

    errors = package_sbom.validate_package_sbom(
        manifest=manifest,
        sbom=json.loads(json.dumps(sbom)),
        sbom_filename=package_sbom.SBOM_NAME,
    )

    assert f"{package_sbom.SBOM_NAME}: attackiq-cli SHA256 must match wheel artifact" in errors
