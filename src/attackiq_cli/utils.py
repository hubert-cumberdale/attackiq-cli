import ipaddress
import json
import re
import uuid
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def parse_key_value_pairs(items: Iterable[str], *, coerce: bool = True) -> dict[str, Any]:
    """Parse key=value pairs into a dict with optional type coercion."""
    parsed: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected key=value pair, got '{item}'")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Parameter keys cannot be empty.")
        cleaned = value.strip()
        parsed[key] = _coerce_value(cleaned) if coerce else cleaned
    return parsed


def _coerce_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def coerce_value_from_schema(raw: str, schema: dict[str, Any]) -> Any:
    """Coerce a raw string value using a basic OpenAPI schema."""
    if not schema:
        return raw
    schema_type = schema.get("type")
    if not schema_type:
        return raw
    if schema_type == "string":
        return raw
    if schema_type == "integer":
        return int(raw)
    if schema_type == "number":
        return float(raw)
    if schema_type == "boolean":
        lowered = raw.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        raise ValueError("expected boolean (true/false)")
    if schema_type == "array":
        cleaned = raw.strip()
        if cleaned.startswith("["):
            value = json.loads(cleaned)
            if not isinstance(value, list):
                raise ValueError("expected JSON array")
            return _coerce_array_items(value, schema.get("items", {}))
        items = [item.strip() for item in raw.split(",") if item.strip()]
        return _coerce_array_items(items, schema.get("items", {}))
    if schema_type == "object":
        cleaned = raw.strip()
        if not cleaned.startswith("{"):
            raise ValueError("expected JSON object")
        value = json.loads(cleaned)
        if not isinstance(value, dict):
            raise ValueError("expected JSON object")
        return value
    return raw


def _coerce_array_items(items: list[Any], item_schema: dict[str, Any]) -> list[Any]:
    if not item_schema:
        return items
    coerced = []
    for item in items:
        if isinstance(item, str):
            coerced.append(coerce_value_from_schema(item, item_schema))
        else:
            coerced.append(item)
    return coerced


def load_json_payload(body: str | None, body_file: Path | None) -> Any:
    """Load JSON from a string or a file; raise on invalid input."""
    if body and body_file:
        raise ValueError("Provide either --body or --body-file, not both.")
    if body_file:
        text = body_file.read_text(encoding="utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Body file is not valid JSON: {body_file}") from exc
    if body:
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Body string is not valid JSON.") from exc
    return None


def validate_json_payload(
    payload: Any, schema: dict[str, Any], resolve_schema: Callable[[dict[str, Any]], dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    _validate_json_payload(payload, schema, resolve_schema, "$", errors)
    return errors


def _validate_json_payload(
    payload: Any,
    schema: dict[str, Any],
    resolve_schema: Callable[[dict[str, Any]], dict[str, Any]],
    path: str,
    errors: list[str],
) -> None:
    if not schema:
        return
    resolved = resolve_schema(schema)
    if not resolved:
        return
    if resolved.get("nullable") and payload is None:
        return
    if "enum" in resolved and payload not in resolved["enum"]:
        errors.append(f"{path}: expected one of {resolved['enum']}")
        return
    if "oneOf" in resolved:
        _validate_one_of(payload, resolved["oneOf"], resolve_schema, path, errors)
        return
    if "anyOf" in resolved:
        _validate_any_of(payload, resolved["anyOf"], resolve_schema, path, errors)
        return
    if "allOf" in resolved:
        for entry in resolved["allOf"]:
            if isinstance(entry, dict):
                _validate_json_payload(payload, entry, resolve_schema, path, errors)
        return
    schema_type = resolved.get("type")
    if isinstance(schema_type, list):
        for candidate in schema_type:
            candidate_schema = dict(resolved)
            candidate_schema["type"] = candidate
            candidate_errors: list[str] = []
            _validate_json_payload(
                payload, candidate_schema, resolve_schema, path, candidate_errors
            )
            if not candidate_errors:
                return
        errors.append(f"{path}: expected one of types {', '.join(schema_type)}")
        return
    if schema_type is None and "properties" in resolved:
        schema_type = "object"
    if schema_type == "object":
        if not isinstance(payload, dict):
            errors.append(f"{path}: expected object")
            return
        min_properties = resolved.get("minProperties")
        if isinstance(min_properties, int) and len(payload) < min_properties:
            errors.append(f"{path}: expected at least {min_properties} properties")
        max_properties = resolved.get("maxProperties")
        if isinstance(max_properties, int) and len(payload) > max_properties:
            errors.append(f"{path}: expected at most {max_properties} properties")
        required = resolved.get("required") or []
        for name in required:
            if name not in payload:
                errors.append(f"{path}: missing required property '{name}'")
        properties = resolved.get("properties") or {}
        additional = resolved.get("additionalProperties", True)
        if isinstance(properties, dict):
            for name, prop_schema in properties.items():
                if name in payload and isinstance(prop_schema, dict):
                    _validate_json_payload(
                        payload[name],
                        prop_schema,
                        resolve_schema,
                        f"{path}.{name}",
                        errors,
                    )
        if additional is False and isinstance(properties, dict):
            for key in payload:
                if key not in properties:
                    errors.append(f"{path}: unexpected property '{key}'")
        if isinstance(additional, dict):
            for key, value in payload.items():
                if isinstance(properties, dict) and key in properties:
                    continue
                _validate_json_payload(
                    value,
                    additional,
                    resolve_schema,
                    f"{path}.{key}",
                    errors,
                )
        return
    if schema_type == "array":
        if not isinstance(payload, list):
            errors.append(f"{path}: expected array")
            return
        min_items = resolved.get("minItems")
        if isinstance(min_items, int) and len(payload) < min_items:
            errors.append(f"{path}: expected at least {min_items} items")
        max_items = resolved.get("maxItems")
        if isinstance(max_items, int) and len(payload) > max_items:
            errors.append(f"{path}: expected at most {max_items} items")
        if resolved.get("uniqueItems") is True:
            seen: list[Any] = []
            for item in payload:
                if any(item == prior for prior in seen):
                    errors.append(f"{path}: expected unique items")
                    break
                seen.append(item)
        items_schema = resolved.get("items")
        if isinstance(items_schema, dict):
            for idx, item in enumerate(payload):
                _validate_json_payload(
                    item, items_schema, resolve_schema, f"{path}[{idx}]", errors
                )
        return
    if schema_type:
        if not _matches_schema_type(payload, schema_type):
            errors.append(f"{path}: expected {schema_type}")
            return
        fmt = resolved.get("format")
        format_error = _validate_format(payload, fmt)
        if format_error:
            errors.append(f"{path}: {format_error}")
        for constraint_error in _validate_value_constraints(payload, resolved):
            errors.append(f"{path}: {constraint_error}")


def _matches_schema_type(value: Any, schema_type: str) -> bool:
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "null":
        return value is None
    return True


def _validate_value_constraints(value: Any, schema: dict[str, Any]) -> list[str]:
    schema_type = schema.get("type")
    if schema_type == "string" and isinstance(value, str):
        return _validate_string_constraints(value, schema)
    if schema_type in {"integer", "number"} and isinstance(value, int | float):
        if isinstance(value, bool):
            return []
        return _validate_numeric_constraints(value, schema)
    return []


def _validate_string_constraints(value: str, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(value) < min_length:
        errors.append(f"expected length >= {min_length}")
    max_length = schema.get("maxLength")
    if isinstance(max_length, int) and len(value) > max_length:
        errors.append(f"expected length <= {max_length}")
    pattern = schema.get("pattern")
    if isinstance(pattern, str):
        try:
            matched = re.search(pattern, value) is not None
        except re.error as exc:
            errors.append(f"invalid schema pattern {pattern!r}: {exc}")
        else:
            if not matched:
                errors.append(f"expected string matching pattern {pattern!r}")
    return errors


def _validate_numeric_constraints(value: int | float, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    minimum = schema.get("minimum")
    exclusive_minimum = schema.get("exclusiveMinimum")
    if isinstance(minimum, int | float) and not isinstance(minimum, bool):
        if exclusive_minimum is True:
            if value <= minimum:
                errors.append(f"expected > {minimum}")
        elif value < minimum:
            errors.append(f"expected >= {minimum}")
    elif (
        isinstance(exclusive_minimum, int | float)
        and not isinstance(exclusive_minimum, bool)
        and value <= exclusive_minimum
    ):
        errors.append(f"expected > {exclusive_minimum}")

    maximum = schema.get("maximum")
    exclusive_maximum = schema.get("exclusiveMaximum")
    if isinstance(maximum, int | float) and not isinstance(maximum, bool):
        if exclusive_maximum is True:
            if value >= maximum:
                errors.append(f"expected < {maximum}")
        elif value > maximum:
            errors.append(f"expected <= {maximum}")
    elif (
        isinstance(exclusive_maximum, int | float)
        and not isinstance(exclusive_maximum, bool)
        and value >= exclusive_maximum
    ):
        errors.append(f"expected < {exclusive_maximum}")

    multiple_of = schema.get("multipleOf")
    if (
        isinstance(multiple_of, int | float)
        and not isinstance(multiple_of, bool)
        and multiple_of > 0
        and value % multiple_of != 0
    ):
        errors.append(f"expected multiple of {multiple_of}")
    return errors


def _validate_one_of(
    payload: Any,
    entries: list[Any],
    resolve_schema: Callable[[dict[str, Any]], dict[str, Any]],
    path: str,
    errors: list[str],
) -> None:
    matches = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_errors: list[str] = []
        _validate_json_payload(payload, entry, resolve_schema, path, entry_errors)
        if not entry_errors:
            matches += 1
    if matches != 1:
        errors.append(f"{path}: expected to match exactly one schema option")


def _validate_any_of(
    payload: Any,
    entries: list[Any],
    resolve_schema: Callable[[dict[str, Any]], dict[str, Any]],
    path: str,
    errors: list[str],
) -> None:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_errors: list[str] = []
        _validate_json_payload(payload, entry, resolve_schema, path, entry_errors)
        if not entry_errors:
            return
    errors.append(f"{path}: expected to match at least one schema option")


def _validate_format(value: Any, fmt: str | None) -> str | None:
    if not fmt:
        return None
    if fmt == "uuid":
        try:
            uuid.UUID(str(value))
        except ValueError:
            return "expected uuid format"
        return None
    if fmt in {"date-time", "date"}:
        if not isinstance(value, str):
            return f"expected {fmt} string"
        text = value
        if fmt == "date-time" and text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            if fmt == "date-time":
                datetime.fromisoformat(text)
            else:
                date.fromisoformat(text)
        except ValueError:
            return f"expected {fmt} format"
        return None
    if fmt == "email":
        if not isinstance(value, str) or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            return "expected email format"
        return None
    if fmt == "uri":
        if not isinstance(value, str):
            return "expected uri string"
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            return "expected uri format"
        return None
    if fmt in {"ipv4", "ipv6"}:
        if not isinstance(value, str):
            return f"expected {fmt} string"
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            return f"expected {fmt} format"
        if fmt == "ipv4" and ip.version != 4:
            return "expected ipv4 format"
        if fmt == "ipv6" and ip.version != 6:
            return "expected ipv6 format"
        return None
    if fmt == "hostname":
        if not isinstance(value, str):
            return "expected hostname string"
        if len(value) > 253:
            return "expected hostname format"
        labels = value.split(".")
        for label in labels:
            if not label or len(label) > 63:
                return "expected hostname format"
            if label.startswith("-") or label.endswith("-"):
                return "expected hostname format"
            if not re.match(r"^[A-Za-z0-9-]+$", label):
                return "expected hostname format"
        return None
    if fmt == "int64":
        if not isinstance(value, int) or isinstance(value, bool):
            return "expected int64 format"
        if value < -(2**63) or value > 2**63 - 1:
            return "expected int64 range"
        return None
    if fmt in {"float", "double"}:
        if isinstance(value, bool) or not isinstance(value, int | float):
            return f"expected {fmt} format"
        return None
    return None
