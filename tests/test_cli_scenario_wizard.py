from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from typer.testing import CliRunner

import attackiq_cli.scenario_wizard as scenario_wizard
import attackiq_cli.scenario_wizard_image as scenario_wizard_image
from attackiq_cli import cli
from attackiq_cli.scenario_wizard import (
    apply_scenario_wizard_create,
    apply_scenario_wizard_package,
    build_runtime_prepare_from_image_tar_plan,
    build_runtime_prepare_plan,
    build_scenario_wizard_create_plan,
    build_scenario_wizard_package_plan,
    inspect_image_tar_runtime,
    inspect_scenario_wizard_zip,
    prepare_runtime_bundle_from_bundle,
    prepare_runtime_bundle_from_image_tar,
    validate_runtime_bundle,
)


def _write_wizard_zip(path: Path, *, pip_conf: str = "token=secret-value") -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Makefile", "run:\n\tpython run_script.py latest\n")
        archive.writestr("README.md", "Scenario Wizard")
        archive.writestr("run_script.py", "print('hello')")
        archive.writestr(
            "version.txt",
            json.dumps({"self": "0.0.3", "minimal_docker_image_version": "0.0.2"}),
        )
        archive.writestr("pip.conf", pip_conf)
    return path


def _write_runtime_bundle(
    path: Path,
    *,
    wizard_version: str = "0.0.3",
    entrypoint: str = "#!/bin/sh\n",
    requirements: str = "example==0.0.0\n",
    create_failure: bool = False,
) -> Path:
    (path / "runtime" / "templates").mkdir(parents=True)
    (path / "runtime" / "scenario_wizard" / "impl").mkdir(parents=True)
    (path / "wheelhouse").mkdir()
    (path / "python").mkdir()
    (path / "runtime" / "scenario_wizard.sh").write_text(entrypoint, encoding="utf-8")
    (path / "runtime" / "scenario_wizard" / "__init__.py").write_text("", encoding="utf-8")
    (path / "runtime" / "scenario_wizard" / "impl" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
    (path / "runtime" / "scenario_wizard" / "impl" / "scenario_params.py").write_text(
        "class ScenarioParamsClass:\n"
        "    def _GetScenarioDirInput(self):\n"
        "        return '/usr/src/folder'\n",
        encoding="utf-8",
    )
    if create_failure:
        make_scenario = (
            "import sys\n"
            "class ScenarioTemplateClass:\n"
            "    def __init__(self, config):\n"
            "        self.config = config\n"
            "    def Run(self):\n"
            "        print('token=do-not-leak', file=sys.stderr)\n"
            "        return False\n"
        )
    else:
        make_scenario = (
            "import json\n"
            "import pathlib\n"
            "import re\n"
            "from scenario_wizard.impl.scenario_params import ScenarioParamsClass\n"
            "class ScenarioTemplateClass:\n"
            "    def __init__(self, config):\n"
            "        self.config = config\n"
            "    def Run(self):\n"
            "        root = pathlib.Path(ScenarioParamsClass()._GetScenarioDirInput())\n"
            "        raw_name = self.config['scenario_name'].strip().lower()\n"
            "        slug = re.sub(r'[^a-z0-9]+', '_', raw_name)\n"
            "        slug = re.sub(r'_+', '_', slug).strip('_') or 'scenario'\n"
            "        scenario = root / slug\n"
            "        scenario.mkdir(parents=True, exist_ok=False)\n"
            "        (scenario / 'scenario.json').write_text(json.dumps({\n"
            "            'scenario_name': self.config['scenario_name'],\n"
            "        }, sort_keys=True), encoding='utf-8')\n"
            "        return True\n"
        )
    (path / "runtime" / "scenario_wizard" / "impl" / "make_scenario.py").write_text(
        make_scenario,
        encoding="utf-8",
    )
    (path / "runtime" / "templates" / "template.txt").write_text("template\n", encoding="utf-8")
    (path / "wheelhouse" / "example-0.0.0-py3-none-any.whl").write_text(
        "wheel\n",
        encoding="utf-8",
    )
    (path / "python" / "requirements.lock").write_text(requirements, encoding="utf-8")
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-04T00:00:00Z",
                "wizard_version": wizard_version,
                "runtime_version": "0.0.2",
                "source_type": "fixture",
                "python_version": "3.12.2",
            }
        ),
        encoding="utf-8",
    )
    return path


def _fixture_create_entrypoint() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
python - "$1" <<'PY'
import json
import pathlib
import re
import sys

data = json.loads(sys.argv[1])
slug = re.sub(r"[^a-z0-9]+", "_", data["scenario_name"].strip().lower())
slug = re.sub(r"_+", "_", slug).strip("_") or "scenario"
scenario = pathlib.Path(slug)
scenario.mkdir(parents=True, exist_ok=False)
(scenario / "scenario.json").write_text(json.dumps({
    "scenario_name": data["scenario_name"],
}, sort_keys=True), encoding="utf-8")
PY
"""


def _write_scenario_config(path: Path, *, secret: str | None = None) -> Path:
    payload = {
        "scenario_name": "Endpoint Agent Health Check",
        "scenario_description": "Validate endpoint agent health.",
        "phase_description": "Check process, service, and driver indicators.",
    }
    if secret is not None:
        payload["api_token"] = secret
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_generated_scenario(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".pipdownload").mkdir()
    (path / "requirements.txt").write_text("", encoding="utf-8")
    (path / "descriptor.json").write_text("{}", encoding="utf-8")
    (path / "setup.cfg").write_text("[metadata]\nname = fixture\n", encoding="utf-8")
    (path / "main.py").write_text("print('fixture')\n", encoding="utf-8")
    (path / "version.txt").write_text("1.0.0\n", encoding="utf-8")
    return path


def _write_package_executable(scenario: Path, *, failure: bool = False) -> Path:
    venv = scenario / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
    executable = bin_dir / ("package.exe" if sys.platform == "win32" else "package")
    if failure:
        script = (
            f"#!{sys.executable}\n"
            "import sys\n"
            "print('password=do-not-leak', file=sys.stderr)\n"
            "raise SystemExit(4)\n"
        )
    else:
        script = (
            f"#!{sys.executable}\n"
            "import pathlib\n"
            "import zipfile\n"
            "target = pathlib.Path('target')\n"
            "target.mkdir(exist_ok=True)\n"
            "with zipfile.ZipFile(target / 'folder-1.0.0.zip', 'w') as archive:\n"
            "    archive.writestr('descriptor.json', '{}')\n"
            "print('packaged fixture')\n"
        )
    executable.write_text(script, encoding="utf-8")
    executable.chmod(0o755)
    return executable


def _write_runtime_site_package_packager(path: Path) -> Path:
    bin_dir = path.parent / "bin"
    bin_dir.mkdir(parents=True)
    fullrelease = bin_dir / "fullrelease"
    fullrelease.write_text(f"#!{sys.executable}\nprint('fullrelease fixture')\n", encoding="utf-8")
    fullrelease.chmod(0o755)
    package_dir = path / "scenario_packaging"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "package.py").write_text(
        "import pathlib\n"
        "import shutil\n"
        "import sys\n"
        "\n"
        "if shutil.which('fullrelease') is None:\n"
        "    raise SystemExit('fullrelease not found on PATH')\n"
        "if len(sys.argv) > 1 and sys.argv[1] == 'd':\n"
        "    pathlib.Path('descriptor-processed.json').write_text('{}', encoding='utf-8')\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit('unexpected package invocation')\n",
        encoding="utf-8",
    )
    (package_dir / "compress_scenario.py").write_text(
        "import pathlib\n"
        "import zipfile\n\n"
        "class CompressScenario:\n"
        "    FILES_TO_IGNORE = []\n\n"
        "    def __init__(self, bin_folder):\n"
        "        self.bin_folder = bin_folder\n\n"
        "    def compress_scenario(self):\n"
        "        target = pathlib.Path('target')\n"
        "        target.mkdir(exist_ok=True)\n"
        "        with zipfile.ZipFile(target / 'folder-1.0.0.zip', 'w') as archive:\n"
        "            archive.writestr('descriptor.json', '{}')\n"
        "        print('packaged from runtime site-packages')\n"
        "        return True\n",
        encoding="utf-8",
    )
    return path


def _tar_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _gzip_tar_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gzip_file:
        gzip_file.write(_tar_bytes(files))
    return buffer.getvalue()


def _image_tar_files() -> dict[str, bytes]:
    return {
        "usr/src/folder/scenario_wizard.sh": b"#!/bin/sh\n",
        "usr/src/folder/setup_scenario.sh": b"#!/bin/sh\n",
        "usr/src/folder/scenario_wizard/__init__.py": b"",
        "usr/src/folder/scenario_wizard/impl/__init__.py": b"",
        "usr/src/folder/scenario_wizard/impl/make_scenario.py": b"print('create')\n",
        "usr/src/folder/scenario_wizard/impl/scenario_params.py": b"",
        "usr/src/folder/templates/template.txt": b"template\n",
        "usr/src/folder/wheelhouse/example-0.0.0-py3-none-any.whl": b"wheel\n",
        "usr/src/folder/requirements.txt": b"example==0.0.0\n",
        "usr/src/folder/version.txt": json.dumps({"self": "0.0.3"}).encode(),
    }


def _image_tar_files_nested_runtime() -> dict[str, bytes]:
    return {
        "usr/src/app/scenario_wizard.sh": (
            b"#!/usr/bin/env bash\n"
            b"root=$(dirname \"${BASH_SOURCE:=$0}\")\n"
            b"python \"$root/scenario_wizard/impl/make_scenario.py\" \"$1\"\n"
        ),
        "usr/src/app/setup_scenario.sh": b"#!/bin/sh\n",
        "usr/src/app/scenario_wizard/__init__.py": b"",
        "usr/src/app/scenario_wizard/impl/__init__.py": b"",
        "usr/src/app/scenario_wizard/impl/make_scenario.py": b"print('create')\n",
        "usr/src/app/scenario_wizard/templates/__init__.py": b"",
        "usr/src/app/scenario_wizard/templates/cookiecutter-scenario/template.txt": b"template\n",
        "usr/src/app/pipdownload/example-0.0.0-py3-none-any.whl": b"wheel\n",
        "usr/src/app/requirements.txt": (
            b"--index-url https://user:password@example.invalid/simple\n"
            b"example==0.0.0\n"
        ),
        "usr/local/bin/fullrelease": b"#!/usr/bin/env python\nprint('fullrelease')\n",
        "usr/local/bin/package": b"#!/usr/bin/env python\nprint('package')\n",
        "usr/local/lib/python3.12/site-packages/example/__init__.py": b"",
        "usr/src/app/version.txt": json.dumps({"self": "0.0.2"}).encode(),
    }


def _write_image_filesystem_tar(path: Path) -> Path:
    path.write_bytes(_tar_bytes(_image_tar_files()))
    return path


def _write_docker_save_tar(path: Path) -> Path:
    layer_bytes = _tar_bytes(_image_tar_files())
    with tarfile.open(path, mode="w") as archive:
        layer_info = tarfile.TarInfo("layer.tar")
        layer_info.size = len(layer_bytes)
        archive.addfile(layer_info, io.BytesIO(layer_bytes))
        manifest = json.dumps([{"Layers": ["layer.tar"]}]).encode()
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest)
        archive.addfile(manifest_info, io.BytesIO(manifest))
    return path


def _write_docker_save_tar_layers(path: Path, layers: list[dict[str, bytes]]) -> Path:
    layer_names = [f"layers/{index}/layer.tar" for index, _layer in enumerate(layers)]
    with tarfile.open(path, mode="w") as archive:
        for layer_name, layer_files in zip(layer_names, layers, strict=True):
            layer_bytes = _tar_bytes(layer_files)
            layer_info = tarfile.TarInfo(layer_name)
            layer_info.size = len(layer_bytes)
            archive.addfile(layer_info, io.BytesIO(layer_bytes))
        manifest = json.dumps([{"Layers": layer_names}]).encode()
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest)
        archive.addfile(manifest_info, io.BytesIO(manifest))
    return path


def _write_oci_docker_save_tar(path: Path) -> Path:
    layer_name = "blobs/sha256/example-layer"
    layer_bytes = _gzip_tar_bytes(_image_tar_files_nested_runtime())
    with tarfile.open(path, mode="w") as archive:
        for directory in ("blobs", "blobs/sha256"):
            directory_info = tarfile.TarInfo(directory)
            directory_info.type = tarfile.DIRTYPE
            archive.addfile(directory_info)
        layer_info = tarfile.TarInfo(layer_name)
        layer_info.size = len(layer_bytes)
        archive.addfile(layer_info, io.BytesIO(layer_bytes))
        manifest = json.dumps([{"Layers": [layer_name]}]).encode()
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest)
        archive.addfile(manifest_info, io.BytesIO(manifest))
        layout = b'{"imageLayoutVersion":"1.0.0"}'
        layout_info = tarfile.TarInfo("oci-layout")
        layout_info.size = len(layout)
        archive.addfile(layout_info, io.BytesIO(layout))
    return path


def test_inspect_scenario_wizard_zip_redacts_pip_conf(tmp_path):
    zip_path = _write_wizard_zip(tmp_path / "scenario-wizard.zip")

    payload = inspect_scenario_wizard_zip(zip_path, cache_dir=tmp_path / "cache")

    assert payload["wrapper_version"] == "0.0.3"
    assert payload["minimal_docker_image_version"] == "0.0.2"
    assert payload["wrapper_only"] is True
    assert payload["contains_local_runtime"] is False
    assert payload["sensitive_files_present"] == ["pip.conf"]
    pip_entry = next(entry for entry in payload["files"] if entry["name"] == "pip.conf")
    assert pip_entry["sha256"] is None
    assert "secret-value" not in json.dumps(payload)


def test_inspect_scenario_wizard_zip_detects_runtime_bundle(tmp_path):
    zip_path = _write_wizard_zip(tmp_path / "scenario-wizard.zip")
    _write_runtime_bundle(tmp_path / "cache" / "0.0.3")

    payload = inspect_scenario_wizard_zip(zip_path, cache_dir=tmp_path / "cache")

    assert payload["runtime_bundle"]["exists"] is True
    assert payload["runtime_bundle"]["manifest_valid"] is True
    assert payload["runtime_bundle"]["runtime_entrypoint_exists"] is True
    assert payload["runtime_bundle"]["manifest"] == {
        "created_at": "2026-05-04T00:00:00Z",
        "python_version": "3.12.2",
        "runtime_version": "0.0.2",
        "source_type": "fixture",
        "wizard_version": "0.0.3",
    }


def test_validate_runtime_bundle_rejects_secret_like_manifest_keys(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "bundle")
    (bundle / "manifest.json").write_text(
        json.dumps(
            {
                "wizard_version": "0.0.3",
                "runtime_version": "0.0.2",
                "source_type": "fixture",
                "python_version": "3.12.2",
                "api_token": "must-not-render",
            }
        ),
        encoding="utf-8",
    )

    payload = validate_runtime_bundle(bundle)

    assert payload["valid"] is False
    assert "api_token" in payload["secret_like_manifest_keys"]
    assert "must-not-render" not in json.dumps(payload)


def test_validate_runtime_bundle_rejects_version_mismatch(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "bundle")

    payload = validate_runtime_bundle(bundle, expected_wizard_version="0.0.4")

    assert payload["valid"] is False
    assert "does not match expected version 0.0.4" in " ".join(payload["errors"])


def test_validate_runtime_bundle_rejects_symlinks(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "bundle")
    (bundle / "runtime" / "templates" / "linked.txt").symlink_to("template.txt")

    payload = validate_runtime_bundle(bundle)

    assert payload["valid"] is False
    assert payload["symlinks_present"] == ["runtime/templates/linked.txt"]


def test_validate_runtime_bundle_rejects_credentialed_requirements_lock(tmp_path):
    bundle = _write_runtime_bundle(
        tmp_path / "bundle",
        requirements="--index-url https://user:password@example.invalid/simple\nexample==0.0.0\n",
    )

    payload = validate_runtime_bundle(bundle)

    assert payload["valid"] is False
    assert "credentialed URLs" in " ".join(payload["errors"])


def test_build_runtime_prepare_plan_ready(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "source")
    cache_dir = tmp_path / "cache"

    payload = build_runtime_prepare_plan(bundle, cache_dir=cache_dir, wizard_version="0.0.3")

    assert payload["ready"] is True
    assert payload["source"]["validation"]["valid"] is True
    assert payload["destination"]["path"] == str(cache_dir / "0.0.3")
    assert payload["planned_actions"][2]["name"] == "copy_runtime_bundle"


def test_runtime_prepare_rejects_existing_destination_without_force(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "source")
    destination = _write_runtime_bundle(tmp_path / "cache" / "0.0.3")

    payload = build_runtime_prepare_plan(bundle, cache_dir=destination.parent)

    assert payload["ready"] is False
    assert "already exists" in " ".join(payload["errors"])


def test_prepare_runtime_bundle_from_bundle_copies_to_cache(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "source")
    cache_dir = tmp_path / "cache"

    payload = prepare_runtime_bundle_from_bundle(
        bundle,
        cache_dir=cache_dir,
        wizard_version="0.0.3",
    )

    destination = cache_dir / "0.0.3"
    assert payload["prepared"] is True
    assert destination.is_dir()
    assert (destination / "runtime" / "scenario_wizard.sh").is_file()
    assert payload["destination"]["validation"]["valid"] is True


def test_inspect_image_tar_runtime_detects_filesystem_tar(tmp_path):
    image_tar = _write_image_filesystem_tar(tmp_path / "image.tar")

    payload = inspect_image_tar_runtime(image_tar)

    assert payload["valid"] is True
    assert payload["format"] == "filesystem"
    assert payload["runtime_root"] == "usr/src/folder"
    assert payload["wheelhouse_path"] == "usr/src/folder/wheelhouse"
    assert payload["requirements_path"] == "usr/src/folder/requirements.txt"
    assert payload["wizard_version"] == "0.0.3"


def test_build_runtime_prepare_from_image_tar_plan_ready(tmp_path):
    image_tar = _write_image_filesystem_tar(tmp_path / "image.tar")
    cache_dir = tmp_path / "cache"

    payload = build_runtime_prepare_from_image_tar_plan(image_tar, cache_dir=cache_dir)

    assert payload["ready"] is True
    assert payload["source"]["inspection"]["valid"] is True
    assert payload["destination"]["path"] == str(cache_dir / "0.0.3")
    assert payload["planned_actions"][2]["name"] == "extract_selected_runtime_files"


def test_prepare_runtime_bundle_from_image_tar_materializes_cache_bundle(tmp_path):
    image_tar = _write_image_filesystem_tar(tmp_path / "image.tar")
    cache_dir = tmp_path / "cache"

    payload = prepare_runtime_bundle_from_image_tar(image_tar, cache_dir=cache_dir)

    destination = cache_dir / "0.0.3"
    assert payload["prepared"] is True
    assert (destination / "runtime" / "scenario_wizard.sh").is_file()
    assert (destination / "runtime" / "templates" / "template.txt").is_file()
    assert (destination / "wheelhouse" / "example-0.0.0-py3-none-any.whl").is_file()
    assert (destination / "python" / "requirements.lock").read_text(encoding="utf-8")
    assert payload["destination"]["validation"]["valid"] is True
    assert payload["destination"]["validation"]["manifest"]["source_type"] == "image_tar"


def test_prepare_runtime_bundle_from_docker_save_tar_materializes_cache_bundle(tmp_path):
    image_tar = _write_docker_save_tar(tmp_path / "image-save.tar")
    cache_dir = tmp_path / "cache"

    payload = prepare_runtime_bundle_from_image_tar(image_tar, cache_dir=cache_dir)

    assert payload["prepared"] is True
    assert payload["source"]["inspection"]["format"] == "docker-save"
    assert (cache_dir / "0.0.3" / "runtime" / "scenario_wizard.sh").is_file()


def test_prepare_runtime_bundle_from_docker_save_tar_applies_whiteout_file(tmp_path):
    lower = {
        **_image_tar_files(),
        "usr/src/folder/templates/deleted.txt": b"deleted lower layer\n",
    }
    upper = {
        "usr/src/folder/templates/.wh.deleted.txt": b"",
    }
    image_tar = _write_docker_save_tar_layers(tmp_path / "image-save.tar", [lower, upper])
    cache_dir = tmp_path / "cache"

    payload = prepare_runtime_bundle_from_image_tar(image_tar, cache_dir=cache_dir)

    assert payload["prepared"] is True
    assert (cache_dir / "0.0.3" / "runtime" / "templates" / "template.txt").is_file()
    assert not (cache_dir / "0.0.3" / "runtime" / "templates" / "deleted.txt").exists()


def test_prepare_runtime_bundle_from_docker_save_tar_applies_opaque_whiteout(tmp_path):
    lower = {
        **_image_tar_files(),
        "usr/src/folder/templates/stale.txt": b"stale lower layer\n",
    }
    upper = {
        "usr/src/folder/templates/.wh..wh..opq": b"",
        "usr/src/folder/templates/template.txt": b"replacement template\n",
    }
    image_tar = _write_docker_save_tar_layers(tmp_path / "image-save.tar", [lower, upper])
    cache_dir = tmp_path / "cache"

    payload = prepare_runtime_bundle_from_image_tar(image_tar, cache_dir=cache_dir)

    assert payload["prepared"] is True
    template = cache_dir / "0.0.3" / "runtime" / "templates" / "template.txt"
    assert template.read_text(encoding="utf-8") == "replacement template\n"
    assert not (cache_dir / "0.0.3" / "runtime" / "templates" / "stale.txt").exists()


def test_inspect_image_tar_runtime_rejects_oversized_docker_layer(
    tmp_path,
    monkeypatch,
):
    image_tar = _write_docker_save_tar(tmp_path / "image-save.tar")
    monkeypatch.setattr(scenario_wizard_image, "MAX_IMAGE_LAYER_BYTES", 32)

    payload = inspect_image_tar_runtime(image_tar)

    assert payload["valid"] is False
    assert "exceeding the 32 byte limit" in " ".join(payload["errors"])


def test_prepare_runtime_bundle_from_oci_docker_save_tar_materializes_cache_bundle(tmp_path):
    image_tar = _write_oci_docker_save_tar(tmp_path / "image-oci-save.tar")
    cache_dir = tmp_path / "cache"

    payload = prepare_runtime_bundle_from_image_tar(image_tar, cache_dir=cache_dir)

    assert payload["prepared"] is True
    assert payload["source"]["inspection"]["format"] == "docker-save"
    assert payload["source"]["inspection"]["runtime_root"] == "usr/src/app"
    assert payload["source"]["inspection"]["templates_dir"] == (
        "usr/src/app/scenario_wizard/templates"
    )
    assert (cache_dir / "0.0.2" / "runtime" / "scenario_wizard.sh").is_file()
    assert (
        cache_dir / "0.0.2" / "runtime" / "scenario_wizard" / "impl" / "make_scenario.py"
    ).is_file()
    assert (cache_dir / "0.0.2" / "python" / "bin" / "fullrelease").is_file()
    assert (cache_dir / "0.0.2" / "python" / "site-packages" / "example" / "__init__.py").is_file()
    requirements = (cache_dir / "0.0.2" / "python" / "requirements.lock").read_text(
        encoding="utf-8"
    )
    assert "user:password" not in requirements
    assert "example==0.0.0" in requirements


def test_scenario_wizard_runtime_inspect_cli(tmp_path):
    zip_path = _write_wizard_zip(tmp_path / "scenario-wizard.zip")

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "runtime",
            "inspect",
            "--zip",
            str(zip_path),
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["wrapper_version"] == "0.0.3"
    assert payload["wrapper_only"] is True
    assert "secret-value" not in result.output


def test_scenario_wizard_runtime_inspect_missing_zip(tmp_path):
    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "runtime",
            "inspect",
            "--zip",
            str(tmp_path / "missing.zip"),
        ],
    )

    assert result.exit_code == 1
    assert "Scenario Wizard zip not found" in result.output


def test_scenario_wizard_runtime_validate_cli(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "bundle")

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "runtime",
            "validate",
            "--bundle",
            str(bundle),
            "--wizard-version",
            "0.0.3",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["manifest"]["wizard_version"] == "0.0.3"


def test_scenario_wizard_runtime_prepare_cli_dry_run(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "source")
    cache_dir = tmp_path / "cache"

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "runtime",
            "prepare",
            "--from-bundle",
            str(bundle),
            "--cache-dir",
            str(cache_dir),
            "--wizard-version",
            "0.0.3",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["ready"] is True
    assert payload["destination"]["path"] == str(cache_dir / "0.0.3")
    assert not (cache_dir / "0.0.3").exists()


def test_scenario_wizard_runtime_prepare_cli_apply(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "source")
    cache_dir = tmp_path / "cache"

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "runtime",
            "prepare",
            "--apply",
            "--from-bundle",
            str(bundle),
            "--cache-dir",
            str(cache_dir),
            "--wizard-version",
            "0.0.3",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["prepared"] is True
    assert (cache_dir / "0.0.3" / "manifest.json").is_file()


def test_scenario_wizard_runtime_prepare_cli_from_image_tar_dry_run(tmp_path):
    image_tar = _write_image_filesystem_tar(tmp_path / "image.tar")
    cache_dir = tmp_path / "cache"

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "runtime",
            "prepare",
            "--from-image-tar",
            str(image_tar),
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["ready"] is True
    assert payload["source"]["type"] == "image_tar"
    assert payload["destination"]["path"] == str(cache_dir / "0.0.3")
    assert not (cache_dir / "0.0.3").exists()


def test_scenario_wizard_runtime_prepare_cli_rejects_multiple_sources(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "source")
    image_tar = _write_image_filesystem_tar(tmp_path / "image.tar")

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "runtime",
            "prepare",
            "--from-bundle",
            str(bundle),
            "--from-image-tar",
            str(image_tar),
        ],
    )

    assert result.exit_code == 2
    assert "Provide exactly one source" in result.output


def test_build_scenario_wizard_create_plan_ready(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "bundle")
    config = _write_scenario_config(tmp_path / "scenario_configuration.json")

    payload = build_scenario_wizard_create_plan(
        config,
        tmp_path / "generated",
        bundle,
        expected_wizard_version="0.0.3",
    )

    assert payload["ready"] is True
    assert payload["configuration"]["scenario_slug"] == "endpoint_agent_health_check"
    assert payload["runtime_bundle"]["valid"] is True
    assert payload["planned_actions"][-1]["name"] == "run_scenario_wizard"
    assert payload["planned_actions"][-1]["argv"][-1] == "<scenario_configuration_file>"


def test_scenario_wizard_create_cli_outputs_dry_run_plan(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "bundle")
    config = _write_scenario_config(tmp_path / "scenario_configuration.json")

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "create",
            "--dry-run",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "generated"),
            "--runtime-bundle",
            str(bundle),
            "--wizard-version",
            "0.0.3",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["ready"] is True


def test_apply_scenario_wizard_create_generates_with_fixture_runtime(tmp_path):
    bundle = _write_runtime_bundle(
        tmp_path / "bundle",
        entrypoint=_fixture_create_entrypoint(),
        requirements="",
    )
    config = _write_scenario_config(tmp_path / "scenario_configuration.json")
    output = tmp_path / "generated"

    payload = apply_scenario_wizard_create(
        config,
        output,
        bundle,
        expected_wizard_version="0.0.3",
        python_executable=sys.executable,
        timeout_seconds=30.0,
    )

    scenario_path = output / "endpoint_agent_health_check"
    assert payload["created"] is True
    assert scenario_path.is_dir()
    assert payload["output"]["generated_files"] == ["scenario.json"]
    assert [action["name"] for action in payload["actions"]] == [
        "create_virtualenv",
        "install_runtime_dependencies",
        "run_scenario_wizard",
    ]
    assert payload["actions"][-1]["argv"][-1] == "<scenario_configuration_file>"
    action_text = json.dumps(payload["actions"])
    assert "Endpoint Agent Health Check" not in action_text
    assert "Validate endpoint agent health." not in action_text
    assert not list((output / ".aiq-scenario-wizard-home").glob("scenario-configuration-*.json"))


def test_apply_scenario_wizard_create_uses_allowlisted_environment(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ATTACKIQ_ACCOUNT_TOKEN", "do-not-leak")
    monkeypatch.setenv("PIP_INDEX_URL", "https://user:password@example.invalid/simple")
    monkeypatch.setenv("PYTHONPATH", "do-not-inherit")
    monkeypatch.setenv("PATH", os.defpath)
    captured_envs: list[dict[str, str]] = []
    captured_argvs: list[list[str]] = []

    def _fake_run_subprocess_action(
        name,
        argv,
        *,
        cwd,
        env,
        timeout_seconds,
        display_argv=None,
    ):
        del timeout_seconds, display_argv
        captured_argvs.append(list(argv))
        captured_envs.append(dict(env))
        if name == "run_scenario_wizard":
            scenario = cwd / "endpoint_agent_health_check"
            scenario.mkdir()
            (scenario / "scenario.json").write_text("{}", encoding="utf-8")
        return {
            "name": name,
            "argv": [name],
            "cwd": str(cwd),
            "return_code": 0,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    monkeypatch.setattr(
        scenario_wizard,
        "_run_subprocess_action",
        _fake_run_subprocess_action,
    )
    bundle = _write_runtime_bundle(tmp_path / "bundle", requirements="")
    config = _write_scenario_config(tmp_path / "scenario_configuration.json")
    output = tmp_path / "generated"

    payload = apply_scenario_wizard_create(
        config,
        output,
        bundle,
        expected_wizard_version="0.0.3",
        python_executable=sys.executable,
        timeout_seconds=30.0,
    )

    assert payload["created"] is True
    assert captured_envs
    home_dir = output / ".aiq-scenario-wizard-home"
    run_argv = captured_argvs[-1]
    assert Path(run_argv[-1]).parent == home_dir
    assert "Endpoint Agent Health Check" not in json.dumps(captured_argvs)
    for env in captured_envs:
        assert "ATTACKIQ_ACCOUNT_TOKEN" not in env
        assert "PIP_INDEX_URL" not in env
        assert env["HOME"] == str(home_dir)
        assert env["XDG_CACHE_HOME"] == str(home_dir / ".cache")
        assert env["PIP_CACHE_DIR"] == str(home_dir / ".cache" / "pip")
        assert env["PIP_CONFIG_FILE"] == os.devnull
        assert env["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
        assert env["PIP_NO_INPUT"] == "1"
        assert env["PIP_NO_CACHE_DIR"] == "1"
        assert env["PYTHONNOUSERSITE"] == "1"


def test_scenario_wizard_create_cli_apply_generates_with_fixture_runtime(tmp_path):
    bundle = _write_runtime_bundle(
        tmp_path / "bundle",
        entrypoint=_fixture_create_entrypoint(),
        requirements="",
    )
    config = _write_scenario_config(tmp_path / "scenario_configuration.json")
    output = tmp_path / "generated"

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "create",
            "--apply",
            "--config",
            str(config),
            "--output",
            str(output),
            "--runtime-bundle",
            str(bundle),
            "--wizard-version",
            "0.0.3",
            "--python",
            sys.executable,
            "--timeout",
            "30",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["created"] is True
    assert (output / "endpoint_agent_health_check" / "scenario.json").is_file()


def test_scenario_wizard_create_cli_apply_reports_runtime_failure(tmp_path):
    bundle = _write_runtime_bundle(
        tmp_path / "bundle",
        requirements="",
        create_failure=True,
    )
    config = _write_scenario_config(tmp_path / "scenario_configuration.json")

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "create",
            "--apply",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "generated"),
            "--runtime-bundle",
            str(bundle),
            "--python",
            sys.executable,
            "--timeout",
            "30",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["created"] is False
    assert "run_scenario_wizard failed" in " ".join(payload["errors"])
    assert "do-not-leak" not in result.output
    assert "token=***" in result.output


def test_scenario_wizard_create_rejects_secret_like_config_keys(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "bundle")
    config = _write_scenario_config(tmp_path / "scenario_configuration.json", secret="do-not-leak")

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "create",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "generated"),
            "--runtime-bundle",
            str(bundle),
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ready"] is False
    assert payload["configuration"]["secret_like_keys"] == ["api_token"]
    assert "do-not-leak" not in result.output


def test_scenario_wizard_create_apply_rejects_invalid_plan(tmp_path):
    bundle = _write_runtime_bundle(tmp_path / "bundle")
    config = _write_scenario_config(tmp_path / "scenario_configuration.json")
    scenario_path = tmp_path / "generated" / "endpoint_agent_health_check"
    scenario_path.mkdir(parents=True)

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "create",
            "--apply",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "generated"),
            "--runtime-bundle",
            str(bundle),
        ],
    )

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_build_scenario_wizard_package_plan_ready(tmp_path):
    scenario = _write_generated_scenario(tmp_path / "scenario")

    payload = build_scenario_wizard_package_plan(scenario, python_executable=sys.executable)

    assert payload["ready"] is True
    assert payload["scenario"]["requirements_exists"] is True
    assert payload["planned_actions"][-1]["name"] == "collect_target_packages"


def test_build_scenario_wizard_package_plan_uses_runtime_site_packages(tmp_path):
    scenario = _write_generated_scenario(tmp_path / "scenario")
    site_packages = _write_runtime_site_package_packager(tmp_path / "runtime-site-packages")
    (scenario / ".aiq-runtime-site-packages").write_text(str(site_packages), encoding="utf-8")

    payload = build_scenario_wizard_package_plan(scenario, python_executable=sys.executable)

    action_names = [action["name"] for action in payload["planned_actions"]]
    assert "create_virtualenv" in action_names
    assert "install_package_dependencies" in action_names
    assert "link_runtime_site_packages" in action_names
    assert "create_descriptor_processed" in action_names
    assert "copy_scenario_bin_dependencies" in action_names
    assert "compress_scenario" in action_names


def test_scenario_wizard_package_cli_dry_run(tmp_path):
    scenario = _write_generated_scenario(tmp_path / "scenario")

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "package",
            "--scenario",
            str(scenario),
            "--python",
            sys.executable,
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["ready"] is True


def test_apply_scenario_wizard_package_with_fixture_package_executable(tmp_path):
    scenario = _write_generated_scenario(tmp_path / "scenario")
    _write_package_executable(scenario)

    payload = apply_scenario_wizard_package(
        scenario,
        python_executable=sys.executable,
        timeout_seconds=30.0,
    )

    assert payload["packaged"] is True
    assert payload["packages"][0]["filename"] == "folder-1.0.0.zip"
    assert [action["name"] for action in payload["actions"]] == [
        "install_package_dependencies",
        "run_package",
    ]


def test_apply_scenario_wizard_package_isolates_home_and_cache(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ATTACKIQ_ACCOUNT_TOKEN", "do-not-leak")
    monkeypatch.setenv("PIP_INDEX_URL", "https://user:password@example.invalid/simple")
    monkeypatch.setenv("PYTHONPATH", "do-not-inherit")
    monkeypatch.setenv("PATH", os.defpath)
    scenario = _write_generated_scenario(tmp_path / "scenario")
    captured_envs: list[dict[str, str]] = []

    def _fake_run_subprocess_action(
        name,
        argv,
        *,
        cwd,
        env,
        timeout_seconds,
        display_argv=None,
    ):
        del argv, timeout_seconds, display_argv
        captured_envs.append(dict(env))
        if name == "run_package":
            target = cwd / "target"
            target.mkdir(exist_ok=True)
            with zipfile.ZipFile(target / "folder-1.0.0.zip", "w") as archive:
                archive.writestr("descriptor.json", "{}")
        return {
            "name": name,
            "argv": [name],
            "cwd": str(cwd),
            "return_code": 0,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    monkeypatch.setattr(
        scenario_wizard,
        "_run_subprocess_action",
        _fake_run_subprocess_action,
    )

    payload = apply_scenario_wizard_package(
        scenario,
        python_executable=sys.executable,
        timeout_seconds=30.0,
    )

    assert payload["packaged"] is True
    assert captured_envs
    home_dir = scenario.parent / ".scenario-aiq-scenario-wizard-package-home"
    assert home_dir.exists()
    assert scenario not in home_dir.parents
    for env in captured_envs:
        assert "ATTACKIQ_ACCOUNT_TOKEN" not in env
        assert "PIP_INDEX_URL" not in env
        assert env["HOME"] == str(home_dir)
        assert env["XDG_CACHE_HOME"] == str(home_dir / ".cache")
        assert env["PIP_CACHE_DIR"] == str(home_dir / ".cache" / "pip")
        assert env["TMPDIR"] == str(home_dir / "tmp")
        assert env["PIP_CONFIG_FILE"] == os.devnull
        assert "PYTHONPATH" not in env
        assert env["PYTHONNOUSERSITE"] == "1"


def test_apply_scenario_wizard_package_with_runtime_site_packages(tmp_path):
    scenario = _write_generated_scenario(tmp_path / "scenario")
    site_packages = _write_runtime_site_package_packager(tmp_path / "runtime-site-packages")
    (scenario / ".aiq-runtime-site-packages").write_text(str(site_packages), encoding="utf-8")

    payload = apply_scenario_wizard_package(
        scenario,
        python_executable=sys.executable,
        timeout_seconds=30.0,
    )

    assert payload["packaged"] is True
    assert payload["packages"][0]["filename"] == "folder-1.0.0.zip"
    assert [action["name"] for action in payload["actions"]] == [
        "create_virtualenv",
        "link_runtime_site_packages",
        "install_package_dependencies",
        "create_descriptor_processed",
        "copy_scenario_bin_dependencies",
        "compress_scenario",
    ]
    assert payload["actions"][3]["argv"][1:3] == ["-m", "scenario_packaging.package"]
    assert payload["actions"][5]["argv"][1:3] == ["-c", "<compress_scenario>"]
    assert (scenario / "venv").exists()
    pth_name = "attackiq_scenario_wizard_runtime.pth"
    if sys.platform == "win32":
        pth_file = scenario / "venv" / "Lib" / "site-packages" / pth_name
    else:
        pth_file = next((scenario / "venv" / "lib").glob(f"python*/site-packages/{pth_name}"))
    assert str(site_packages) in pth_file.read_text(encoding="utf-8")
    with zipfile.ZipFile(scenario / "target" / "folder-1.0.0.zip") as archive:
        assert ".aiq-runtime-site-packages" not in archive.namelist()


def test_scenario_wizard_package_cli_apply_with_fixture_package_executable(tmp_path):
    scenario = _write_generated_scenario(tmp_path / "scenario")
    _write_package_executable(scenario)

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "package",
            "--apply",
            "--scenario",
            str(scenario),
            "--python",
            sys.executable,
            "--timeout",
            "30",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["packaged"] is True
    assert payload["packages"][0]["filename"] == "folder-1.0.0.zip"


def test_scenario_wizard_package_rejects_existing_zip_without_force(tmp_path):
    scenario = _write_generated_scenario(tmp_path / "scenario")
    target = scenario / "target"
    target.mkdir()
    (target / "folder-1.0.0.zip").write_bytes(b"existing")

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "package",
            "--scenario",
            str(scenario),
            "--python",
            sys.executable,
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ready"] is False
    assert "already contains package zip files" in " ".join(payload["errors"])


def test_scenario_wizard_package_cli_apply_reports_failure_redacted(tmp_path):
    scenario = _write_generated_scenario(tmp_path / "scenario")
    _write_package_executable(scenario, failure=True)

    result = CliRunner().invoke(
        cli.app,
        [
            "scenario-wizard",
            "package",
            "--apply",
            "--scenario",
            str(scenario),
            "--python",
            sys.executable,
            "--timeout",
            "30",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["packaged"] is False
    assert "run_package failed" in " ".join(payload["errors"])
    assert "do-not-leak" not in result.output
    assert "password=***" in result.output
