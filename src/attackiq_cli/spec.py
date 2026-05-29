from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from attackiq_cli.config import config_dir

ENV_SPEC_CACHE_DISABLED = "ATTACKIQ_SPEC_CACHE_DISABLE"
ENV_SPEC_CACHE_DIR = "ATTACKIQ_SPEC_CACHE_DIR"
SPEC_CACHE_DIRNAME = "spec-cache"

_SPEC_INDEX_MEMORY_CACHE: dict[tuple[str, int, int], SpecIndex] = {}


@dataclass
class Operation:
    operation_id: str
    method: str
    path: str
    summary: str
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None
    tags: list[str]
    security: list[dict[str, Any]]


def load_spec(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency issue signaled to user
        raise RuntimeError("PyYAML is required to load the OpenAPI schema.") from exc

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("OpenAPI schema must be a mapping at the document root.")
    return cast(dict[str, Any], data)


def _cache_key(path: Path) -> tuple[str, int, int]:
    resolved = path.resolve()
    stat = resolved.stat()
    return str(resolved), stat.st_mtime_ns, stat.st_size


def _cache_enabled() -> bool:
    raw = os.getenv(ENV_SPEC_CACHE_DISABLED, "").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


def _cache_directory() -> Path:
    override = os.getenv(ENV_SPEC_CACHE_DIR)
    if override:
        return Path(override)
    return config_dir() / SPEC_CACHE_DIRNAME


def _cache_file_path(path: Path) -> Path:
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()
    return _cache_directory() / f"{digest}.json"


def _load_spec_from_disk_cache(
    path: Path, *, mtime_ns: int, size: int
) -> dict[str, Any] | None:
    cache_path = _cache_file_path(path)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    source = payload.get("source")
    if not isinstance(source, dict):
        return None
    if (
        source.get("path") != str(path.resolve())
        or source.get("mtime_ns") != mtime_ns
        or source.get("size") != size
    ):
        return None
    spec = payload.get("spec")
    if not isinstance(spec, dict):
        return None
    return cast(dict[str, Any], spec)


def _write_spec_to_disk_cache(
    path: Path, *, mtime_ns: int, size: int, spec: dict[str, Any]
) -> None:
    cache_path = _cache_file_path(path)
    payload = {
        "source": {"path": str(path.resolve()), "mtime_ns": mtime_ns, "size": size},
        "spec": spec,
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        return


class SpecIndex:
    def __init__(self, spec: dict[str, Any], *, load_source: str = "file"):
        self._spec = spec
        self._default_security = spec.get("security", [])
        self._operations: dict[str, Operation] = {}
        self.load_source = load_source
        self._index()

    @classmethod
    def from_file(cls, path: Path) -> SpecIndex:
        cache_key = _cache_key(path)
        cached = _SPEC_INDEX_MEMORY_CACHE.get(cache_key)
        if cached is not None:
            cached.load_source = "memory"
            return cached

        path_str, mtime_ns, size = cache_key
        spec: dict[str, Any] | None = None
        source = "file"
        if _cache_enabled():
            spec = _load_spec_from_disk_cache(path, mtime_ns=mtime_ns, size=size)
            if spec is not None:
                source = "disk-cache"
        if spec is None:
            spec = load_spec(path)
            if _cache_enabled():
                _write_spec_to_disk_cache(path, mtime_ns=mtime_ns, size=size, spec=spec)

        index = cls(spec, load_source=source)
        _SPEC_INDEX_MEMORY_CACHE[cache_key] = index
        _purge_stale_memory_entries(path_str, keep=cache_key)
        return index

    def _index(self) -> None:
        paths = self._spec.get("paths", {})
        for path, path_item in paths.items():
            path_level_params = [
                self._resolve_parameter_entry(param)
                for param in path_item.get("parameters", [])
                if isinstance(param, dict)
            ]
            for method, details in path_item.items():
                if method.lower() not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                }:
                    continue
                operation_id = details.get("operationId")
                if not operation_id:
                    continue
                merged_params = []
                merged_params.extend(path_level_params)
                merged_params.extend(
                    self._resolve_parameter_entry(param)
                    for param in details.get("parameters", [])
                    if isinstance(param, dict)
                )
                normalized_params: list[dict[str, Any]] = [
                    param
                    for param in merged_params
                    if isinstance(param, dict)
                    and param.get("name")
                    and param.get("in")
                ]
                unique_params: dict[tuple[str, str], dict[str, Any]] = {}
                for param in normalized_params:
                    key = (str(param.get("in")), str(param.get("name")))
                    unique_params[key] = param
                merged_params = list(unique_params.values())
                request_body = details.get("requestBody")
                if isinstance(request_body, dict):
                    request_body = self._resolve_ref_object(request_body)
                operation = Operation(
                    operation_id=operation_id,
                    method=method.lower(),
                    path=path,
                    summary=details.get("summary", "") or details.get("description", "") or "",
                    parameters=merged_params,
                    request_body=request_body,
                    tags=details.get("tags", []),
                    security=details.get("security", self._default_security),
                )
                self._operations[operation_id] = operation

    @property
    def operations(self) -> dict[str, Operation]:
        return self._operations

    def list_operations(self, tag: str | None = None) -> list[Operation]:
        ops = list(self._operations.values())
        if tag:
            ops = [op for op in ops if tag in op.tags]
        return sorted(ops, key=lambda op: op.operation_id)

    def search_operations(self, query: str, tag: str | None = None) -> list[Operation]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []
        normalized_tag = tag.strip().lower() if tag else None

        matches = []
        for op in self._operations.values():
            if normalized_tag:
                tag_matches = [value.lower() for value in op.tags]
                if normalized_tag not in tag_matches:
                    continue
            if self._matches_query(op, normalized_query):
                matches.append(op)
        return sorted(matches, key=lambda op: op.operation_id)

    def get_operation(self, operation_id: str) -> Operation:
        try:
            return self._operations[operation_id]
        except KeyError as exc:
            raise KeyError(f"Operation '{operation_id}' not found in spec.") from exc

    def parameter_names(self, operation: Operation, location: str) -> list[str]:
        return [
            param["name"]
            for param in operation.parameters
            if param.get("in") == location
        ]

    def required_parameters(self, operation: Operation, location: str) -> list[str]:
        return [
            param["name"]
            for param in operation.parameters
            if param.get("in") == location and param.get("required")
        ]

    def parameter_schema(
        self, operation: Operation, location: str, name: str
    ) -> dict[str, Any] | None:
        for param in operation.parameters:
            if param.get("in") == location and param.get("name") == name:
                schema = param.get("schema") or {}
                if isinstance(schema, dict):
                    return self.resolve_schema(schema)
                return {}
        return None

    def request_body_schema(
        self, operation: Operation, content_type: str = "application/json"
    ) -> dict[str, Any] | None:
        request_body = operation.request_body or {}
        content = request_body.get("content", {})
        media = content.get(content_type)
        if not isinstance(media, dict):
            return None
        schema = media.get("schema")
        if not isinstance(schema, dict):
            return None
        return self.resolve_schema(schema)

    def request_body_content_types(self, operation: Operation) -> list[str]:
        request_body = operation.request_body or {}
        content = request_body.get("content", {})
        if not isinstance(content, dict):
            return []
        return sorted(
            [content_type for content_type in content if isinstance(content_type, str)]
        )

    def resolve_schema(
        self, schema: dict[str, Any], _seen: set[str] | None = None
    ) -> dict[str, Any]:
        if "$ref" not in schema:
            return schema
        ref = schema.get("$ref")
        if not isinstance(ref, str):
            return {}
        seen = set() if _seen is None else _seen
        if ref in seen:
            return {}
        seen.add(ref)
        resolved = self._resolve_ref(ref)
        if not isinstance(resolved, dict):
            return {}
        siblings = {key: value for key, value in schema.items() if key != "$ref"}
        merged = {**resolved, **siblings} if siblings else dict(resolved)
        if "$ref" in merged:
            return self.resolve_schema(merged, _seen=seen)
        return merged

    def _resolve_ref(self, ref: str) -> Any:
        if not ref.startswith("#/"):
            return {}
        target: Any = self._spec
        for part in ref.lstrip("#/").split("/"):
            if not isinstance(target, dict):
                return {}
            target = target.get(part)
        return target or {}

    def _resolve_parameter_entry(self, param: dict[str, Any]) -> dict[str, Any]:
        return self._resolve_ref_object(param)

    def _resolve_ref_object(
        self, value: dict[str, Any], _seen: set[str] | None = None
    ) -> dict[str, Any]:
        if "$ref" not in value:
            return value
        ref = value.get("$ref")
        if not isinstance(ref, str):
            return value
        seen = set() if _seen is None else _seen
        if ref in seen:
            return {}
        seen.add(ref)
        resolved = self._resolve_ref(ref)
        if not isinstance(resolved, dict):
            return {}
        siblings = {key: entry for key, entry in value.items() if key != "$ref"}
        merged = {**resolved, **siblings} if siblings else dict(resolved)
        if "$ref" in merged:
            return self._resolve_ref_object(merged, _seen=seen)
        return merged

    @staticmethod
    def _matches_query(operation: Operation, query: str) -> bool:
        if query in operation.operation_id.lower():
            return True
        if query in operation.path.lower():
            return True
        if query in (operation.summary or "").lower():
            return True
        tags = [value.lower() for value in operation.tags]
        return any(query in tag for tag in tags)


def _purge_stale_memory_entries(path_str: str, keep: tuple[str, int, int]) -> None:
    stale = [key for key in _SPEC_INDEX_MEMORY_CACHE if key[0] == path_str and key != keep]
    for key in stale:
        _SPEC_INDEX_MEMORY_CACHE.pop(key, None)
