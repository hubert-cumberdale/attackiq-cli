from __future__ import annotations

import json
from pathlib import Path

from attackiq_cli.joiner.det_pipeline import (
    DetPipelineOptions,
    normalize_issues,
    reconcile_techniques,
    rewrite_detection_mapping_section,
    run_det_pipeline,
    stage_a_normalize_and_reconcile,
    stage_b_reconcile,
    stage_c_recommend,
)


def _write_issues_csv(path: Path, rows: list[dict[str, str]]) -> None:
    headers = ["IID", "Title", "Description", "Labels"]
    lines = [",".join(headers)]
    for row in rows:
        values = [
            row.get("IID", ""),
            row.get("Title", ""),
            row.get("Description", ""),
            row.get("Labels", ""),
        ]
        escaped = ['"' + value.replace('"', '""') + '"' for value in values]
        lines.append(",".join(escaped))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_scenarios_csv(path: Path, rows: list[dict[str, str]]) -> None:
    headers = ["id", "name", "scenario_tags", "supported_platform"]
    lines = [",".join(headers)]
    for row in rows:
        values = [
            row.get("id", ""),
            row.get("name", ""),
            row.get("scenario_tags", ""),
            row.get("supported_platform", ""),
        ]
        escaped = ['"' + value.replace('"', '""') + '"' for value in values]
        lines.append(",".join(escaped))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_normalize_labels_extracts_tool_det_and_env_tags(tmp_path: Path) -> None:
    issues = tmp_path / "issues.csv"
    _write_issues_csv(
        issues,
        [
            {
                "IID": "12",
                "Title": "Detect suspicious process",
                "Description": "## Detection Mapping\nMatched Scenarios: abc-123",
                "Labels": "tool::SplunkES,DET1234,T1059,TA0001,os-win,env::Azure,platform::Server",
            }
        ],
    )
    records = normalize_issues(issues)
    assert records[0].tool == "tool::SplunkES"
    assert records[0].det_id == "1234"
    assert records[0].technique_tokens == ["T1059"]
    assert records[0].os_tags == ["os-win"]
    assert records[0].env_tags == ["env::Azure"]
    assert records[0].platform_tags == ["platform::Server"]


def test_rewrite_detection_mapping_is_heading_bounded() -> None:
    description = (
        "Intro paragraph.\n\n"
        "## Detection Mapping\n"
        "Old line\n\n"
        "## Other Section\n"
        "Keep me\n"
    )
    updated, changed, findings = rewrite_detection_mapping_section(
        description,
        "Tool: tool::SplunkES\nDetection Strategy (DET####): DET1234",
        allow_append_sections=False,
    )
    assert changed is True
    assert findings == []
    assert "Old line" not in updated
    assert "## Other Section\nKeep me" in updated


def test_reconcile_technique_confidence_behavior(tmp_path: Path) -> None:
    issues = tmp_path / "issues.csv"
    _write_issues_csv(
        issues,
        [
            {
                "IID": "1",
                "Title": "One",
                "Description": "Body",
                "Labels": "T1003",
            },
            {
                "IID": "2",
                "Title": "Two",
                "Description": "Observed technique T1059 in logs.",
                "Labels": "",
            },
            {
                "IID": "3",
                "Title": "Three",
                "Description": "T1003 and T1059 observed.",
                "Labels": "",
            },
        ],
    )
    records = normalize_issues(issues)
    reconciled = reconcile_techniques(records)
    by_iid = {item.iid: item for item in reconciled}
    assert by_iid["1"].confidence == "high"
    assert by_iid["1"].technique_final == "T1003"
    assert by_iid["2"].confidence == "medium"
    assert by_iid["2"].technique_final == "T1059"
    assert by_iid["3"].needs_review is True
    assert by_iid["3"].technique_final is None


def test_recommendations_match_scenario_tags_with_parent_fallback(tmp_path: Path) -> None:
    issues = tmp_path / "issues.csv"
    scenarios = tmp_path / "scenarios.csv"
    outdir = tmp_path / "out"
    _write_issues_csv(
        issues,
        [
            {
                "IID": "1",
                "Title": "Powershell activity",
                "Description": "## Detection Mapping\nTechnique T1059.001",
                "Labels": "DET1234,tool::SplunkES",
            }
        ],
    )
    _write_scenarios_csv(
        scenarios,
        [
            {
                "id": "s-parent",
                "name": "Command and Scripting Interpreter",
                "scenario_tags": "T1059",
                "supported_platform": "Windows",
            }
        ],
    )
    records, _findings = stage_a_normalize_and_reconcile(issues, outdir)
    reconciled = stage_b_reconcile(records, outdir)
    recommendations = stage_c_recommend(records, reconciled, scenarios, outdir, top_k=3)
    assert recommendations["1"][0].scenario_id == "s-parent"


def test_stage_a_manifest_is_deterministic(tmp_path: Path) -> None:
    issues = tmp_path / "issues.csv"
    outdir = tmp_path / "out"
    _write_issues_csv(
        issues,
        [
            {"IID": "2", "Title": "B", "Description": "Body", "Labels": "T1059"},
            {"IID": "1", "Title": "A", "Description": "Body", "Labels": "T1003"},
        ],
    )
    stage_a_normalize_and_reconcile(issues, outdir)
    manifest_first = (outdir / "artifacts" / "manifest.json").read_text(encoding="utf-8")
    stage_a_normalize_and_reconcile(issues, outdir)
    manifest_second = (outdir / "artifacts" / "manifest.json").read_text(encoding="utf-8")
    assert manifest_first == manifest_second


def test_patch_plan_is_idempotent(tmp_path: Path) -> None:
    issues = tmp_path / "issues.csv"
    scenarios = tmp_path / "scenarios.csv"
    outdir = tmp_path / "out"
    _write_issues_csv(
        issues,
        [
            {
                "IID": "1",
                "Title": "Suspicious script",
                "Description": "## Detection Mapping\nOld",
                "Labels": "tool::SplunkES,DET1234,T1059",
            }
        ],
    )
    _write_scenarios_csv(
        scenarios,
        [
            {
                "id": "s-1",
                "name": "Suspicious script execution",
                "scenario_tags": "T1059",
                "supported_platform": "Windows",
            }
        ],
    )
    options = DetPipelineOptions(
        issues=issues,
        scenarios=scenarios,
        outdir=outdir,
        project_id="123",
        apply=False,
        dry_run=True,
    )
    run_det_pipeline(options)
    first_plan = json.loads(
        (outdir / "artifacts" / "gitlab_patch_plan.json").read_text(encoding="utf-8")
    )
    run_det_pipeline(options)
    second_plan = json.loads(
        (outdir / "artifacts" / "gitlab_patch_plan.json").read_text(encoding="utf-8")
    )
    assert first_plan == second_plan
