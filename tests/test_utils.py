from pathlib import Path

import pytest

from attackiq_cli.utils import coerce_value_from_schema, load_json_payload, parse_key_value_pairs


def test_parse_key_value_pairs_coerces_types():
    result = parse_key_value_pairs(["count=5", "enabled=true", "name=test"])
    assert result["count"] == 5
    assert result["enabled"] is True
    assert result["name"] == "test"

def test_parse_key_value_pairs_rejects_empty_key():
    with pytest.raises(ValueError):
        parse_key_value_pairs(["=value"])


def test_parse_key_value_pairs_without_coercion():
    result = parse_key_value_pairs(["count=5", "enabled=true"], coerce=False)
    assert result["count"] == "5"
    assert result["enabled"] == "true"


def test_coerce_value_from_schema_types():
    assert coerce_value_from_schema("5", {"type": "integer"}) == 5
    assert coerce_value_from_schema("5.5", {"type": "number"}) == 5.5
    assert coerce_value_from_schema("true", {"type": "boolean"}) is True
    assert coerce_value_from_schema("alpha", {"type": "string"}) == "alpha"
    assert coerce_value_from_schema("[1, 2]", {"type": "array", "items": {"type": "integer"}}) == [
        1,
        2,
    ]


def test_coerce_value_from_schema_array_split():
    schema = {"type": "array", "items": {"type": "string"}}
    assert coerce_value_from_schema("a, b, c", schema) == ["a", "b", "c"]


def test_load_json_payload_conflict():
    with pytest.raises(ValueError):
        load_json_payload("{}", Path(__file__))


def test_load_json_payload_invalid_json_string():
    with pytest.raises(ValueError):
        load_json_payload("{not-json}", None)
