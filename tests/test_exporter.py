from __future__ import annotations

from pathlib import Path
from typing import cast

from attackiq_cli.client import AttackIQClient
from attackiq_cli.exporter import (
    TEST_FIELD_ORDER,
    fieldnames_for_records,
    load_scenario_details_lenient,
    normalize_csv_value,
    resolve_format,
)


def test_resolve_format_prefers_extension():
    assert resolve_format(output=Path("out.csv"), file_format=None) == "csv"
    assert resolve_format(output=Path("out.json"), file_format=None) == "json"


def test_fieldnames_for_records_orders_preferred_then_sorted():
    records = [
        {"id": "1", "name": "one", "extra": "x"},
        {"id": "2", "name": "two", "other": "y"},
    ]
    fields = fieldnames_for_records(records, preferred_fields=["id", "name"])
    assert fields[:2] == ["id", "name"]
    assert sorted(fields[2:]) == sorted(["extra", "other"])


def test_fieldnames_for_records_accepts_test_field_order():
    records = [
        {"id": "1", "name": "alpha", "description": "desc", "extra": "x"},
        {"id": "2", "name": "beta", "modified": "2024-01-01"},
    ]
    fields = fieldnames_for_records(records, preferred_fields=TEST_FIELD_ORDER)
    assert fields[:3] == ["id", "name", "description"]


def test_fieldnames_for_records_allows_preferred_only():
    records = [{"id": "1", "name": "alpha", "extra": "x"}]
    fields = fieldnames_for_records(
        records,
        preferred_fields=["id", "name"],
        include_other_fields=False,
    )
    assert fields == ["id", "name"]


def test_normalize_csv_value_escapes_newlines():
    assert normalize_csv_value("alpha\nbeta") == "alpha\\nbeta"
    assert normalize_csv_value("alpha\r\nbeta") == "alpha\\nbeta"


def test_load_scenario_details_lenient_skips_failures():
    class DummyClient:
        def send(self, _op, *, path_params, **_kwargs):
            item_id = path_params["id"]
            if item_id == "bad":
                raise RuntimeError("boom")
            return type("Resp", (), {"json": lambda _self: {"name": "Ok", "scenario_type": "x"}})()

    lookup, failures = load_scenario_details_lenient(
        cast(AttackIQClient, DummyClient()),
        object(),
        ["good", "bad"],
        max_workers=1,
        retries=1,
    )
    assert lookup["good"] == ("Ok", "x")
    assert failures == ["bad"]
