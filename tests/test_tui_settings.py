from __future__ import annotations

from types import SimpleNamespace

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_settings


def _state() -> SimpleNamespace:
    return SimpleNamespace(
        base_url="https://api.example.com",
        base_url_source="env",
        auth_mode="account-token",
        auth_source="env",
        spec_cache_status="enabled",
        spec_cache_dir="/tmp/spec-cache",
        spec_cache_dir_source="default",
        spec_load_source="bundled",
        workspace_full="/tmp/workspace",
    )


def _provider() -> SimpleNamespace:
    return SimpleNamespace(
        options=SimpleNamespace(
            timeout=None,
            timeout_source="config",
            insecure=False,
            insecure_source="config",
            page_size=20,
        ),
        cache_max_entries=lambda: 128,
        cache_ttl_seconds=lambda: None,
        scenarios_cache_stats=lambda: (1, 2),
        results_cache_stats=lambda: (3, 4, 5),
        assessments_cache_stats=lambda: (6, 7),
        tests_cache_stats=lambda: (8, 9),
        assets_cache_stats=lambda: (10, 11),
        templates_cache_stats=lambda: (12, 13),
    )


def test_build_settings_records_includes_config_runtime_cache_and_workspace() -> None:
    records = tui_settings.build_settings_records(_state(), _provider())  # type: ignore[arg-type]
    by_key = {record["key"]: record for record in records}

    assert by_key["base_url"] == {
        "key": "base_url",
        "value": "https://api.example.com",
        "source": "env",
        "category": "config",
    }
    assert by_key["timeout"]["value"] == "None"
    assert by_key["cache_ttl"]["value"] == "none"
    assert by_key["cache_entries_scenarios"]["value"] == "3"
    assert by_key["cache_entries_results"]["value"] == "12"
    assert by_key["cache_entries_total"]["value"] == "91"
    assert by_key["workspace"]["value"] == "/tmp/workspace"


def test_build_settings_detail_formats_record_fields() -> None:
    assert tui_settings.build_settings_detail(
        {
            "key": "base_url",
            "value": "https://api.example.com",
            "source": "env",
            "category": "config",
        }
    ) == "\n".join(
        [
            "Key: base_url",
            "Value: https://api.example.com",
            "Source: env",
            "Category: config",
        ]
    )


def test_tui_module_reexports_settings_helpers_for_compatibility() -> None:
    assert tui_module.WorkflowSettingsTab is tui_settings.WorkflowSettingsTab
    assert tui_module.build_settings_records is tui_settings.build_settings_records
    assert tui_module.build_settings_detail is tui_settings.build_settings_detail
