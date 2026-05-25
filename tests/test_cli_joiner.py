from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from attackiq_cli import cli
from attackiq_cli.joiner import cli as joiner_cli


def test_cli_join_forwards_options(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def _run_join(options: joiner_cli.JoinOptions) -> None:
        captured["options"] = options

    monkeypatch.setattr(joiner_cli, "run_join", _run_join)

    assessments = tmp_path / "assessments.csv"
    scenarios = tmp_path / "scenarios.csv"
    issues = tmp_path / "issues.csv"
    assessments.write_text("id,name,scenario_id\n", encoding="utf-8")
    scenarios.write_text(
        "id,name,technique,supported_platforms,capabilities\n",
        encoding="utf-8",
    )
    issues.write_text(
        "id,iid,title,url,state,created_at,updated_at,labels\n",
        encoding="utf-8",
    )
    outdir = tmp_path / "joined"

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "join",
            "--assessments",
            str(assessments),
            "--scenarios",
            str(scenarios),
            "--issues",
            str(issues),
            "--outdir",
            str(outdir),
            "--timestamp",
            "2026-01-26T00:00:00Z",
            "--no-fail-on-missing-scenario",
            "--no-fail-on-malformed-scenario-technique",
        ],
    )

    assert result.exit_code == 0
    options = captured["options"]
    assert options.assessments == assessments
    assert options.scenarios == scenarios
    assert options.issues == issues
    assert options.outdir == outdir
    assert options.timestamp == "2026-01-26T00:00:00Z"
    assert options.fail_on_missing_scenario is False
    assert options.fail_on_malformed_scenario_technique is False
    assert options.label_delimiter == joiner_cli.DEFAULT_LABEL_DELIMITER
    assert options.list_delimiter == joiner_cli.DEFAULT_LIST_DELIMITER


def test_cli_join_det_pipeline_forwards_options(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def _run_det_pipeline(options: joiner_cli.DetPipelineOptions) -> None:
        captured["options"] = options

    monkeypatch.setattr(joiner_cli, "run_det_pipeline", _run_det_pipeline)

    issues = tmp_path / "issues.csv"
    scenarios = tmp_path / "scenarios.csv"
    issues.write_text("IID,Title,Description,Labels\n", encoding="utf-8")
    scenarios.write_text("id,name,scenario_tags,supported_platform\n", encoding="utf-8")
    outdir = tmp_path / "pipeline"

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "join",
            "det-pipeline",
            "--issues",
            str(issues),
            "--scenarios",
            str(scenarios),
            "--outdir",
            str(outdir),
            "--project-id",
            "42",
            "--top-k",
            "7",
            "--top-n-per-issue",
            "2",
            "--force-tool-label",
            "--allow-append-sections",
            "--apply",
        ],
    )

    assert result.exit_code == 0
    options = captured["options"]
    assert options.issues == issues
    assert options.scenarios == scenarios
    assert options.outdir == outdir
    assert options.project_id == "42"
    assert options.top_k == 7
    assert options.top_n_per_issue == 2
    assert options.force_tool_label is True
    assert options.allow_append_sections is True
    assert options.apply is True
