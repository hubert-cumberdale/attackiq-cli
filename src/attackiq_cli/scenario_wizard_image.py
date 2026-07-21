from __future__ import annotations

import contextlib
import datetime as dt
import json
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from attackiq_cli.scenario_wizard_validation import (
    SENSITIVE_FILENAMES,
    _contains_credentialed_url,
    _directory_files,
    _sha256_directory,
    _sha256_file,
    _string_value,
)
from attackiq_cli.scenario_wizard_validation import (
    ScenarioWizardError as ScenarioWizardError,
)

MAX_IMAGE_LAYER_BYTES = 512 * 1024 * 1024
IMAGE_LAYER_SPOOL_MEMORY_BYTES = 16 * 1024 * 1024
IMAGE_LAYER_READ_CHUNK_BYTES = 1024 * 1024
RUNTIME_SCRIPT_NAMES = {
    "check_versions.sh",
    "create_docker_venv.sh",
    "run_scenario.sh",
    "scenario_wizard.sh",
    "setup_scenario.sh",
    "test_scenario.sh",
}
RUNTIME_BIN_SCRIPT_NAMES = {
    "fullrelease",
    "package",
    "postrelease",
    "prerelease",
    "release",
    "setup_scenario_bin",
}
def inspect_image_tar_runtime(
    image_tar: Path,
    *,
    runtime_root: str | None = None,
    wheelhouse_path: str | None = None,
    requirements_path: str | None = None,
) -> dict[str, Any]:
    source = image_tar.expanduser()
    errors: list[str] = []
    warnings: list[str] = []
    if not source.exists():
        return _image_tar_inspection_error(source, f"Image tar not found: {source}")
    if not source.is_file():
        return _image_tar_inspection_error(source, f"Image tar path must be a file: {source}")
    try:
        index = _image_tar_index(source)
    except (ScenarioWizardError, tarfile.TarError, OSError) as exc:
        return _image_tar_inspection_error(source, f"Image tar could not be read: {exc}")

    try:
        normalized_runtime_root = _normalize_tar_path(runtime_root) if runtime_root else ""
    except ScenarioWizardError as exc:
        errors.append(str(exc))
        normalized_runtime_root = ""
    if normalized_runtime_root:
        runtime_entrypoint = f"{normalized_runtime_root}/scenario_wizard.sh"
        if runtime_entrypoint not in index["files"]:
            errors.append(f"Runtime entrypoint not found in image tar: {runtime_entrypoint}")
    else:
        runtime_entrypoint = _detect_runtime_entrypoint(index)
        if runtime_entrypoint:
            normalized_runtime_root = str(Path(runtime_entrypoint).parent).replace(".", "")
            normalized_runtime_root = normalized_runtime_root.strip("/")
        else:
            errors.append("Could not detect scenario_wizard.sh in image tar.")

    templates_dir = _detect_tar_directory(
        index,
        explicit_path=None,
        candidates=[
            f"{normalized_runtime_root}/templates",
            f"{normalized_runtime_root}/scenario_wizard/templates",
        ],
    )
    if not templates_dir:
        errors.append(
            "Runtime templates directory not found in image tar; checked "
            f"{normalized_runtime_root}/templates and "
            f"{normalized_runtime_root}/scenario_wizard/templates."
        )

    detected_wheelhouse = _detect_tar_directory(
        index,
        explicit_path=wheelhouse_path,
        candidates=[
            f"{normalized_runtime_root}/wheelhouse",
            f"{normalized_runtime_root}/.pipdownload",
            f"{normalized_runtime_root}/pipdownload",
            "wheelhouse",
            ".pipdownload",
        ],
    )
    if not detected_wheelhouse:
        errors.append("Could not detect a runtime wheelhouse directory in image tar.")
    wheelhouse_file_count = _count_prefix_files(index["files"], detected_wheelhouse)
    if detected_wheelhouse and wheelhouse_file_count < 1:
        errors.append(f"Runtime wheelhouse contains no files in image tar: {detected_wheelhouse}")

    detected_requirements = _detect_tar_file(
        index,
        explicit_path=requirements_path,
        candidates=[
            f"{normalized_runtime_root}/requirements.lock",
            f"{normalized_runtime_root}/requirements.txt",
            f"{normalized_runtime_root}/python/requirements.lock",
            "requirements.lock",
            "requirements.txt",
        ],
    )
    if not detected_requirements:
        errors.append("Could not detect runtime requirements in image tar.")

    detected_site_packages = _detect_tar_directory(
        index,
        explicit_path=None,
        candidates=[
            f"{normalized_runtime_root}/.venv/lib/python3.12/site-packages",
            "usr/local/lib/python3.12/site-packages",
            "usr/lib/python3.12/site-packages",
        ],
    )

    detected_version = _detect_image_tar_wizard_version(index, source, normalized_runtime_root)
    script_paths = [
        f"{normalized_runtime_root}/{name}".strip("/")
        for name in sorted(RUNTIME_SCRIPT_NAMES)
        if f"{normalized_runtime_root}/{name}".strip("/") in index["files"]
    ]
    bin_script_paths = _detect_bin_script_paths(index, normalized_runtime_root)
    sensitive_files = [
        path for path in sorted(index["files"]) if Path(path).name.lower() in SENSITIVE_FILENAMES
    ]
    if sensitive_files:
        warnings.append(
            "Image tar contains sensitive package configuration files; they are excluded."
        )

    return {
        "path": str(source),
        "exists": True,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "format": index["format"],
        "file_count": len(index["files"]),
        "directory_count": len(index["dirs"]),
        "runtime_root": normalized_runtime_root or None,
        "runtime_entrypoint": runtime_entrypoint or None,
        "templates_dir": templates_dir or None,
        "runtime_script_paths": script_paths,
        "bin_script_paths": bin_script_paths,
        "wheelhouse_path": detected_wheelhouse,
        "wheelhouse_file_count": wheelhouse_file_count,
        "requirements_path": detected_requirements,
        "site_packages_path": detected_site_packages,
        "site_packages_file_count": _count_prefix_files(index["files"], detected_site_packages),
        "wizard_version": detected_version,
        "sha256": _sha256_file(source),
        "sensitive_files_present": sensitive_files,
    }


def _image_tar_inspection_error(path: Path, error: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "valid": False,
        "errors": [error],
        "warnings": [],
        "format": None,
        "file_count": 0,
        "directory_count": 0,
        "runtime_root": None,
        "runtime_entrypoint": None,
        "templates_dir": None,
        "runtime_script_paths": [],
        "bin_script_paths": [],
        "wheelhouse_path": None,
        "wheelhouse_file_count": 0,
        "requirements_path": None,
        "site_packages_path": None,
        "site_packages_file_count": 0,
        "wizard_version": None,
        "sha256": _sha256_file(path) if path.exists() and path.is_file() else None,
        "sensitive_files_present": [],
    }


def _select_image_runtime_files(
    files: dict[str, Any],
    *,
    runtime_root: str,
    templates_dir: str,
    wheelhouse_path: str,
) -> list[str]:
    selected: set[str] = set()
    selected.update(_prefix_files(files, templates_dir))
    selected.update(_prefix_files(files, f"{runtime_root}/scenario_wizard"))
    selected.update(_prefix_files(files, f"{runtime_root}/template_test_config"))
    wheelhouse_prefix = wheelhouse_path.rstrip("/") + "/"
    runtime_prefix = runtime_root.rstrip("/") + "/"
    for path in _prefix_files(files, runtime_root):
        if wheelhouse_path and path.startswith(wheelhouse_prefix):
            continue
        relative = path[len(runtime_prefix) :] if path.startswith(runtime_prefix) else path
        if "/" not in relative and Path(relative).suffix in {".py", ".sh", ".txt"}:
            selected.add(path)
    return sorted(selected)


def _materialize_runtime_bundle_from_image_tar(
    image_tar: Path,
    destination: Path,
    *,
    inspection: dict[str, Any],
    wizard_version: str,
    python_version: str,
) -> None:
    index = _image_tar_index(image_tar)
    destination.mkdir(parents=True, exist_ok=True)
    runtime_root = _string_value(inspection.get("runtime_root"))
    templates_dir = _string_value(inspection.get("templates_dir"))
    wheelhouse_path = _string_value(inspection.get("wheelhouse_path"))
    requirements_path = _string_value(inspection.get("requirements_path"))
    site_packages_path = _string_value(inspection.get("site_packages_path"))
    runtime_files = set(inspection.get("runtime_script_paths") or [])
    runtime_files.update(
        _select_image_runtime_files(
            index["files"],
            runtime_root=runtime_root,
            templates_dir=templates_dir,
            wheelhouse_path=wheelhouse_path,
        )
    )
    selected_files: list[tuple[dict[str, str], Path, str]] = []

    for path in sorted(runtime_files):
        if Path(path).name.lower() in SENSITIVE_FILENAMES:
            continue
        relative = _relative_to_tar_root(path, runtime_root)
        selected_files.append((index["files"][path], destination / "runtime", relative))

    for path in sorted(inspection.get("bin_script_paths") or []):
        if path not in index["files"]:
            continue
        selected_files.append(
            (index["files"][path], destination / "python" / "bin", Path(path).name)
        )

    for path in _prefix_files(index["files"], wheelhouse_path):
        if Path(path).name.lower() in SENSITIVE_FILENAMES:
            continue
        relative = _relative_to_tar_root(path, wheelhouse_path)
        selected_files.append((index["files"][path], destination / "wheelhouse", relative))
    if site_packages_path:
        for path in _prefix_files(index["files"], site_packages_path):
            if Path(path).name.lower() in SENSITIVE_FILENAMES:
                continue
            relative = _relative_to_tar_root(path, site_packages_path)
            selected_files.append(
                (index["files"][path], destination / "python" / "site-packages", relative)
            )

    _write_image_tar_files(image_tar, selected_files)
    for script in _directory_files(destination / "python" / "bin"):
        script.chmod(0o755)
    _write_sanitized_image_requirements_lock(
        image_tar,
        index["files"][requirements_path],
        destination / "python" / "requirements.lock",
    )
    manifest = {
        "created_at": _utc_now_iso(),
        "python_version": python_version,
        "runtime_version": f"image-tar:{_sha256_file(image_tar)[:12]}",
        "source_type": "image_tar",
        "wheelhouse_sha256": _sha256_directory(destination / "wheelhouse"),
        "wizard_version": wizard_version,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_image_tar_files(
    image_tar: Path,
    selected_files: list[tuple[dict[str, str], Path, str]],
) -> None:
    layer_groups: dict[str, list[tuple[dict[str, str], Path, str]]] = {}
    with tarfile.open(image_tar) as archive:
        for source, destination_root, relative_path in selected_files:
            if source["type"] == "outer":
                extracted = archive.extractfile(source["member"])
                if extracted is None:
                    raise ScenarioWizardError(f"Could not read tar member: {source['member']}")
                _write_stream_to_destination(destination_root, relative_path, extracted)
                continue
            layer_groups.setdefault(source["layer"], []).append(
                (source, destination_root, relative_path)
            )
        for layer_name, layer_files in layer_groups.items():
            layer_member = _get_tar_member(archive, layer_name)
            with _spooled_image_layer_file(
                archive,
                layer_member,
                label=layer_name,
            ) as layer_file:
                layer_archive = tarfile.open(fileobj=layer_file, mode="r:*")
                with layer_archive:
                    layer_members = {member.name: member for member in layer_archive.getmembers()}
                    for source, destination_root, relative_path in layer_files:
                        member = layer_members.get(source["member"])
                        if member is None:
                            raise ScenarioWizardError(
                                f"Could not find layer member: {source['member']}"
                            )
                        extracted = layer_archive.extractfile(member)
                        if extracted is None:
                            raise ScenarioWizardError(
                                f"Could not read layer member: {source['member']}"
                            )
                        _write_stream_to_destination(
                            destination_root,
                            relative_path,
                            extracted,
                        )


def _write_stream_to_destination(destination_root: Path, relative_path: str, stream: Any) -> None:
    relative = _safe_relative_path(relative_path)
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        shutil.copyfileobj(stream, handle)


def _get_tar_member(archive: tarfile.TarFile, name: str) -> tarfile.TarInfo:
    try:
        return archive.getmember(name)
    except KeyError as exc:
        raise ScenarioWizardError(f"Could not find tar member: {name}") from exc


@contextlib.contextmanager
def _spooled_image_layer_file(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    *,
    label: str,
) -> Any:
    if member.size > MAX_IMAGE_LAYER_BYTES:
        raise ScenarioWizardError(
            f"Image layer {label} is {member.size} bytes, exceeding the "
            f"{MAX_IMAGE_LAYER_BYTES} byte limit."
        )
    extracted = archive.extractfile(member)
    if extracted is None:
        raise ScenarioWizardError(f"Could not read image layer: {label}")
    spool = tempfile.SpooledTemporaryFile(max_size=IMAGE_LAYER_SPOOL_MEMORY_BYTES)
    try:
        total = 0
        while True:
            chunk = extracted.read(IMAGE_LAYER_READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_IMAGE_LAYER_BYTES:
                raise ScenarioWizardError(
                    f"Image layer {label} exceeded the {MAX_IMAGE_LAYER_BYTES} byte limit."
                )
            spool.write(chunk)
        spool.seek(0)
        yield spool
    finally:
        with contextlib.suppress(OSError):
            extracted.close()
        spool.close()


def _write_sanitized_image_requirements_lock(
    image_tar: Path,
    source: dict[str, str],
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        _sanitize_requirements_lock(_read_image_tar_file(image_tar, source)),
        encoding="utf-8",
    )


def _image_tar_index(path: Path) -> dict[str, Any]:
    index: dict[str, Any] = {
        "files": {},
        "dirs": set(),
        "format": "filesystem",
    }
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        members_by_name: dict[str, tarfile.TarInfo] = {}
        for member in members:
            normalized = _normalize_tar_member_name(member.name)
            if not normalized:
                continue
            members_by_name[normalized] = member
        layer_names = _docker_save_layer_names(archive, members_by_name)
        if layer_names:
            index["format"] = "docker-save"
            for layer_name in layer_names:
                layer_member = members_by_name.get(layer_name)
                if layer_member is None or not layer_member.isfile():
                    continue
                with _spooled_image_layer_file(
                    archive,
                    layer_member,
                    label=layer_member.name,
                ) as layer_file:
                    _add_layer_tar_to_index(index, layer_member.name, layer_file)
            return index

        for member in members:
            normalized = _normalize_tar_member_name(member.name)
            if not normalized:
                continue
            if member.isfile() and normalized.endswith("layer.tar"):
                index["format"] = "docker-save"
                with _spooled_image_layer_file(archive, member, label=member.name) as layer_file:
                    _add_layer_tar_to_index(index, member.name, layer_file)
                continue
            _add_tar_member_to_index(
                index,
                normalized,
                source={"type": "outer", "member": member.name},
                is_dir=member.isdir(),
                is_file=member.isfile(),
                is_link=member.issym() or member.islnk(),
            )
    return index


def _docker_save_layer_names(
    archive: tarfile.TarFile,
    members_by_name: dict[str, tarfile.TarInfo],
) -> list[str]:
    manifest_member = members_by_name.get("manifest.json")
    if manifest_member is None or not manifest_member.isfile():
        return []
    extracted = archive.extractfile(manifest_member)
    if extracted is None:
        return []
    try:
        parsed = json.loads(extracted.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    layer_names: list[str] = []
    for image in parsed:
        if not isinstance(image, dict):
            continue
        layers = image.get("Layers")
        if not isinstance(layers, list):
            continue
        for layer in layers:
            normalized = _normalize_tar_member_name(str(layer))
            if normalized:
                layer_names.append(normalized)
    return layer_names


def _add_layer_tar_to_index(index: dict[str, Any], layer_name: str, layer_file: Any) -> None:
    with tarfile.open(fileobj=layer_file, mode="r:*") as layer:
        normalized_members: list[tuple[tarfile.TarInfo, str]] = []
        whiteouts: list[str] = []
        for member in layer.getmembers():
            normalized = _normalize_tar_member_name(member.name)
            if not normalized:
                continue
            if member.isfile() and _is_layer_whiteout(normalized):
                whiteouts.append(normalized)
                continue
            normalized_members.append((member, normalized))

        for whiteout in whiteouts:
            _apply_layer_whiteout(index, whiteout)

        for member, normalized in normalized_members:
            _add_tar_member_to_index(
                index,
                normalized,
                source={"type": "layer", "layer": layer_name, "member": member.name},
                is_dir=member.isdir(),
                is_file=member.isfile(),
                is_link=member.issym() or member.islnk(),
            )


def _is_layer_whiteout(path: str) -> bool:
    return Path(path).name.startswith(".wh.")


def _apply_layer_whiteout(index: dict[str, Any], whiteout_path: str) -> None:
    name = Path(whiteout_path).name
    parent = Path(whiteout_path).parent.as_posix()
    parent = "" if parent == "." else parent
    if name == ".wh..wh..opq":
        _remove_index_children(index, parent)
        return
    target_name = name.removeprefix(".wh.")
    if not target_name:
        return
    target = f"{parent}/{target_name}" if parent else target_name
    _remove_index_path(index, target)


def _remove_index_path(index: dict[str, Any], target: str) -> None:
    normalized = target.rstrip("/")
    if not normalized:
        return
    prefix = normalized + "/"
    for path in list(index["files"]):
        if path == normalized or path.startswith(prefix):
            del index["files"][path]
    for path in list(index["dirs"]):
        if path == normalized or path.startswith(prefix):
            index["dirs"].discard(path)


def _remove_index_children(index: dict[str, Any], parent: str) -> None:
    normalized = parent.rstrip("/")
    if not normalized:
        index["files"].clear()
        index["dirs"].clear()
        return
    prefix = normalized + "/"
    for path in list(index["files"]):
        if path.startswith(prefix):
            del index["files"][path]
    for path in list(index["dirs"]):
        if path.startswith(prefix):
            index["dirs"].discard(path)


def _add_tar_member_to_index(
    index: dict[str, Any],
    normalized: str,
    *,
    source: dict[str, str],
    is_dir: bool,
    is_file: bool,
    is_link: bool,
) -> None:
    if is_link:
        return
    if is_dir:
        _add_directory_parents(index["dirs"], normalized)
        return
    if is_file:
        if Path(normalized).name.startswith(".wh."):
            return
        _add_directory_parents(index["dirs"], str(Path(normalized).parent))
        index["files"][normalized] = source


def _add_directory_parents(dirs: set[str], path: str) -> None:
    normalized = path.strip("/")
    if not normalized or normalized == ".":
        return
    current = Path(normalized)
    dirs.add(current.as_posix())
    for parent in current.parents:
        parent_text = parent.as_posix()
        if parent_text == ".":
            break
        dirs.add(parent_text)


def _read_image_tar_file(image_tar: Path, source: dict[str, str]) -> bytes:
    with tarfile.open(image_tar) as archive:
        if source["type"] == "outer":
            extracted = archive.extractfile(source["member"])
            if extracted is None:
                raise ScenarioWizardError(f"Could not read tar member: {source['member']}")
            return extracted.read()
        layer_member = _get_tar_member(archive, source["layer"])
        with _spooled_image_layer_file(
            archive,
            layer_member,
            label=source["layer"],
        ) as layer_file, tarfile.open(fileobj=layer_file, mode="r:*") as layer_archive:
            extracted = layer_archive.extractfile(source["member"])
            if extracted is None:
                raise ScenarioWizardError(f"Could not read layer member: {source['member']}")
            return extracted.read()


def _detect_runtime_entrypoint(index: dict[str, Any]) -> str:
    files: dict[str, Any] = index["files"]
    candidates = sorted(path for path in files if path.endswith("/scenario_wizard.sh"))
    if "scenario_wizard.sh" in files:
        return "scenario_wizard.sh"
    preferred = [path for path in candidates if path.endswith("usr/src/folder/scenario_wizard.sh")]
    if preferred:
        return preferred[0]
    return candidates[0] if candidates else ""


def _detect_bin_script_paths(index: dict[str, Any], runtime_root: str) -> list[str]:
    files: dict[str, Any] = index["files"]
    candidates: list[str] = []
    for name in sorted(RUNTIME_BIN_SCRIPT_NAMES):
        for path in (
            f"usr/local/bin/{name}",
            f"{runtime_root}/.venv/bin/{name}".strip("/"),
            f"{runtime_root}/venv/bin/{name}".strip("/"),
            f"{runtime_root}/bin/{name}".strip("/"),
        ):
            if path in files:
                candidates.append(path)
                break
    return candidates


def _detect_tar_directory(
    index: dict[str, Any],
    *,
    explicit_path: str | None,
    candidates: list[str],
) -> str:
    if explicit_path:
        try:
            normalized = _normalize_tar_path(explicit_path)
        except ScenarioWizardError:
            return ""
        return normalized if _tar_directory_exists(index, normalized) else ""
    for candidate in candidates:
        normalized = _normalize_tar_member_name(candidate)
        if normalized and _tar_directory_exists(index, normalized):
            return normalized
    return ""


def _detect_tar_file(
    index: dict[str, Any],
    *,
    explicit_path: str | None,
    candidates: list[str],
) -> str:
    if explicit_path:
        try:
            normalized = _normalize_tar_path(explicit_path)
        except ScenarioWizardError:
            return ""
        return normalized if normalized in index["files"] else ""
    for candidate in candidates:
        normalized = _normalize_tar_member_name(candidate)
        if normalized in index["files"]:
            return normalized
    return ""


def _detect_image_tar_wizard_version(
    index: dict[str, Any],
    image_tar: Path,
    runtime_root: str,
) -> str | None:
    for candidate in (f"{runtime_root}/version.txt".strip("/"), "version.txt"):
        if candidate not in index["files"]:
            continue
        try:
            data = json.loads(_read_image_tar_file(image_tar, index["files"][candidate]))
        except (json.JSONDecodeError, UnicodeDecodeError, ScenarioWizardError):
            continue
        version = _string_value(data.get("self")) if isinstance(data, dict) else ""
        if version:
            return version
    return None


def _tar_directory_exists(index: dict[str, Any], path: str) -> bool:
    return path in index["dirs"] or _has_path_prefix(index["files"], path)


def _has_path_prefix(paths: dict[str, Any] | set[str], prefix: str) -> bool:
    if not prefix:
        return False
    normalized = prefix.rstrip("/") + "/"
    return any(path.startswith(normalized) for path in paths)


def _prefix_files(files: dict[str, Any], prefix: str) -> list[str]:
    if not prefix:
        return []
    normalized = prefix.rstrip("/") + "/"
    return sorted(path for path in files if path.startswith(normalized))


def _count_prefix_files(files: dict[str, Any], prefix: str) -> int:
    return len(_prefix_files(files, prefix))


def _relative_to_tar_root(path: str, root: str) -> str:
    root_prefix = root.rstrip("/") + "/"
    if root and path.startswith(root_prefix):
        return path[len(root_prefix) :]
    if path == root:
        return Path(path).name
    return Path(path).name


def _normalize_tar_member_name(path: str) -> str:
    try:
        return _normalize_tar_path(path)
    except ScenarioWizardError:
        return ""


def _normalize_tar_path(path: str | None) -> str:
    text = (path or "").replace("\\", "/").strip()
    text = re.sub(r"^/+", "", text)
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ScenarioWizardError(f"Unsafe tar path: {path}")
        parts.append(part)
    return "/".join(parts)


def _safe_relative_path(path: str) -> Path:
    normalized = _normalize_tar_path(path)
    if not normalized:
        raise ScenarioWizardError("Refusing to write empty relative path.")
    return Path(normalized)


def _sanitize_requirements_lock(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace")
    sanitized: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith(("--index-url", "--extra-index-url")) or lowered.startswith("-i "):
            continue
        if _contains_credentialed_url(stripped):
            continue
        sanitized.append(line)
    return "\n".join(sanitized).rstrip() + "\n"


def _utc_now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
