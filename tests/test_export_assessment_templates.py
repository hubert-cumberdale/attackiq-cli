from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module():
    module_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "export_assessment_templates.py"
    )
    spec = importlib.util.spec_from_file_location("export_assessment_templates", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_format_prefers_explicit_choice():
    mod = load_module()
    assert mod.resolve_format(Path("out.csv"), "json") == "json"
    assert mod.resolve_format(Path("out.json"), "CSV") == "csv"


def test_resolve_format_infers_from_extension():
    mod = load_module()
    assert mod.resolve_format(Path("out.json"), None) == "json"
    assert mod.resolve_format(Path("out.csv"), None) == "csv"
    assert mod.resolve_format(Path("out.data"), None) == "csv"


def test_flatten_templates_includes_scenarios_and_empty_rows():
    mod = load_module()
    templates = [
        {
            "template_id": "template-1",
            "template_name": "Template One",
            "project_name": "Project One",
            "template_type": {"id": "type-1", "name": "Type One"},
            "scenarios": [
                {
                    "scenario_id": "scenario-1",
                    "scenario_name": "Scenario One",
                    "scenario_type": "atomic",
                    "test_id": "test-1",
                    "test_name": "Test One",
                }
            ],
        },
        {
            "template_id": "template-2",
            "template_name": "Template Two",
            "project_name": "",
            "template_type": {},
            "scenarios": [],
        },
    ]
    rows = mod.flatten_templates(templates, include_empty=True)
    assert rows[0] == [
        "template-1",
        "Template One",
        "Project One",
        "type-1",
        "Type One",
        "scenario-1",
        "Scenario One",
        "atomic",
        "test-1",
        "Test One",
    ]
    assert rows[1] == [
        "template-2",
        "Template Two",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]
