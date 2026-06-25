from pathlib import Path

import attackiq_cli.spec as spec_module
from attackiq_cli.spec import SpecIndex


def test_spec_index_merges_path_and_operation_params():
    spec = {
        "paths": {
            "/items/{item_id}": {
                "parameters": [{"name": "item_id", "in": "path", "required": True}],
                "get": {
                    "operationId": "get_item",
                    "parameters": [{"name": "expand", "in": "query", "required": False}],
                },
            }
        }
    }
    index = SpecIndex(spec)
    op = index.get_operation("get_item")
    assert index.parameter_names(op, "path") == ["item_id"]
    assert index.parameter_names(op, "query") == ["expand"]


def test_spec_index_search_operations_matches_query_and_tag():
    spec = {
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "summary": "Retrieve Items",
                    "tags": ["catalog"],
                }
            },
            "/items/{item_id}": {
                "get": {
                    "operationId": "get_item",
                    "summary": "Get item details",
                    "tags": ["catalog", "detail"],
                }
            },
        }
    }
    index = SpecIndex(spec)

    matches = index.search_operations("item")
    assert [op.operation_id for op in matches] == ["get_item", "list_items"]

    tag_matches = index.search_operations("item", tag="DETAIL")
    assert [op.operation_id for op in tag_matches] == ["get_item"]


def test_spec_index_resolves_ref_parameters_and_schemas():
    spec = {
        "components": {
            "schemas": {"ItemId": {"type": "string"}},
            "parameters": {
                "ItemIdParam": {
                    "name": "item_id",
                    "in": "path",
                    "required": True,
                    "schema": {"$ref": "#/components/schemas/ItemId"},
                }
            },
        },
        "paths": {
            "/items/{item_id}": {
                "parameters": [{"$ref": "#/components/parameters/ItemIdParam"}],
                "get": {
                    "operationId": "get_item",
                    "parameters": [{"$ref": "#/components/parameters/ItemIdParam"}],
                },
            }
        },
    }
    index = SpecIndex(spec)
    op = index.get_operation("get_item")

    assert index.parameter_names(op, "path") == ["item_id"]
    schema = index.parameter_schema(op, "path", "item_id") or {}
    assert schema.get("type") == "string"


def test_spec_index_resolves_ref_request_body():
    spec = {
        "components": {
            "schemas": {
                "Item": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                }
            },
            "requestBodies": {
                "CreateItem": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Item"}}
                    },
                }
            },
        },
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "requestBody": {"$ref": "#/components/requestBodies/CreateItem"},
                }
            }
        },
    }
    index = SpecIndex(spec)
    op = index.get_operation("create_item")

    assert index.request_body_content_types(op) == ["application/json"]
    schema = index.request_body_schema(op) or {}
    assert schema.get("type") == "object"
    assert schema.get("properties", {}).get("name", {}).get("type") == "string"


def test_spec_index_from_file_uses_memory_cache(tmp_path, monkeypatch):
    path = tmp_path / "openapi.yaml"
    path.write_text(
        "openapi: 3.0.0\npaths:\n  /items:\n    get:\n      operationId: list_items\n",
        encoding="utf-8",
    )
    spec_module._SPEC_INDEX_MEMORY_CACHE.clear()

    count = {"calls": 0}
    original = spec_module.load_spec

    def _tracked_load_spec(value: Path):
        count["calls"] += 1
        return original(value)

    monkeypatch.setattr(spec_module, "load_spec", _tracked_load_spec)
    monkeypatch.setenv(spec_module.ENV_SPEC_CACHE_DISABLED, "1")

    first = SpecIndex.from_file(path)
    second = SpecIndex.from_file(path)

    assert count["calls"] == 1
    assert first is second
    assert second.load_source == "memory"


def test_spec_index_from_file_invalidates_on_file_change(tmp_path, monkeypatch):
    path = tmp_path / "openapi.yaml"
    path.write_text(
        "openapi: 3.0.0\npaths:\n  /items:\n    get:\n      operationId: list_items\n",
        encoding="utf-8",
    )
    spec_module._SPEC_INDEX_MEMORY_CACHE.clear()

    count = {"calls": 0}
    original = spec_module.load_spec

    def _tracked_load_spec(value: Path):
        count["calls"] += 1
        return original(value)

    monkeypatch.setattr(spec_module, "load_spec", _tracked_load_spec)
    monkeypatch.setenv(spec_module.ENV_SPEC_CACHE_DISABLED, "1")

    first = SpecIndex.from_file(path)
    path.write_text(
        "openapi: 3.0.0\npaths:\n  /items:\n    get:\n      operationId: list_items_v2\n",
        encoding="utf-8",
    )
    second = SpecIndex.from_file(path)

    assert count["calls"] == 2
    assert first is not second
    assert second.load_source == "file"
    assert second.get_operation("list_items_v2").operation_id == "list_items_v2"


def test_spec_index_from_file_uses_disk_cache(tmp_path, monkeypatch):
    path = tmp_path / "openapi.yaml"
    path.write_text(
        "openapi: 3.0.0\npaths:\n  /items:\n    get:\n      operationId: list_items\n",
        encoding="utf-8",
    )
    spec_module._SPEC_INDEX_MEMORY_CACHE.clear()
    monkeypatch.setenv(spec_module.ENV_SPEC_CACHE_DIR, str(tmp_path / "spec-cache"))
    monkeypatch.delenv(spec_module.ENV_SPEC_CACHE_DISABLED, raising=False)

    count = {"calls": 0}
    original = spec_module.load_spec

    def _tracked_load_spec(value: Path):
        count["calls"] += 1
        return original(value)

    monkeypatch.setattr(spec_module, "load_spec", _tracked_load_spec)

    first = SpecIndex.from_file(path)
    spec_module._SPEC_INDEX_MEMORY_CACHE.clear()
    second = SpecIndex.from_file(path)

    assert count["calls"] == 1
    assert first.load_source == "file"
    assert second.load_source == "disk-cache"
