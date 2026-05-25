import json
from pathlib import Path

from attackiq_cli.joiner.cli import JoinOptions, run_join


def test_joiner_outputs_match_golden(tmp_path: Path) -> None:
    fixtures = Path(__file__).resolve().parent / "fixtures" / "joiner"
    golden = fixtures / "golden"
    outdir = tmp_path / "out"

    options = JoinOptions(
        assessments=fixtures / "assessments.csv",
        scenarios=fixtures / "scenarios.csv",
        issues=fixtures / "issues.csv",
        outdir=outdir,
        timestamp="2026-01-09T00:00:00Z",
        fail_on_missing_scenario=True,
        fail_on_malformed_scenario_technique=True,
    )

    run_join(options)

    for name in [
        "assessment_scenario.csv",
        "issue_scenario.csv",
        "assessment_scenario_issue.csv",
        "issues_unmapped.csv",
    ]:
        assert (outdir / name).read_bytes() == (golden / name).read_bytes()

    manifest = json.loads((outdir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1"
    assert manifest["created_utc"] == "2026-01-09T00:00:00Z"

    input_names = {entry["name"] for entry in manifest["inputs"]}
    output_names = {entry["name"] for entry in manifest["outputs"]}

    assert input_names == {"assessments.csv", "scenarios.csv", "issues.csv"}
    assert output_names == {
        "assessment_scenario.csv",
        "issue_scenario.csv",
        "assessment_scenario_issue.csv",
        "issues_unmapped.csv",
    }

