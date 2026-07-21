from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from attackiq_cli.joiner import cli as joiner_cli

__all__ = ["join_exports"]


def join_exports(
    mode: Annotated[
        str,
        typer.Argument(help="Join mode: datasets (default) or det-pipeline."),
    ] = "datasets",
    assessments: Annotated[
        Path | None,
        typer.Option(
            "--assessments",
            exists=True,
            readable=True,
            help="Path to assessments CSV export.",
        ),
    ] = None,
    scenarios: Annotated[
        Path | None,
        typer.Option(
            "--scenarios",
            exists=True,
            readable=True,
            help="Path to scenarios CSV export.",
        ),
    ] = None,
    issues: Annotated[
        Path | None,
        typer.Option(
            "--issues",
            exists=True,
            readable=True,
            help="Path to GitLab issues CSV export.",
        ),
    ] = None,
    outdir: Annotated[
        Path | None,
        typer.Option("--outdir", help="Output directory for joined CSVs and manifest."),
    ] = None,
    project_id: Annotated[
        str | None,
        typer.Option("--project-id", help="GitLab project_id for det-pipeline apply mode."),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Apply network changes (GitLab updates + AttackIQ assessment creation).",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--no-dry-run", help="Dry-run mode (default true)."),
    ] = True,
    top_k: Annotated[
        int,
        typer.Option("--top-k", help="Max scenario recommendations per issue."),
    ] = 5,
    top_n_per_issue: Annotated[
        int,
        typer.Option(
            "--top-n-per-issue",
            help="Top N scenario ids per issue for DET assessment planning.",
        ),
    ] = 1,
    force_tool_label: Annotated[
        bool,
        typer.Option("--force-tool-label", help="Allow tool label updates in patch plan."),
    ] = False,
    allow_append_sections: Annotated[
        bool,
        typer.Option(
            "--allow-append-sections",
            help="Append Detection Mapping section when missing.",
        ),
    ] = False,
    timestamp: Annotated[
        str | None,
        typer.Option(
            "--timestamp",
            help="Override created_utc in manifest (UTC ISO8601, e.g. 2026-01-26T00:00:00Z).",
        ),
    ] = None,
    fail_on_missing_scenario: Annotated[
        bool,
        typer.Option(
            "--fail-on-missing-scenario/--no-fail-on-missing-scenario",
            help="Fail when an assessment references a missing scenario.",
        ),
    ] = True,
    fail_on_malformed_scenario_technique: Annotated[
        bool,
        typer.Option(
            "--fail-on-malformed-scenario-technique/--no-fail-on-malformed-scenario-technique",
            help="Fail when a scenario technique is malformed.",
        ),
    ] = True,
) -> None:
    normalized_mode = mode.strip().lower()
    if normalized_mode == "det-pipeline":
        if issues is None:
            raise typer.BadParameter("--issues is required for det-pipeline mode.")
        if scenarios is None:
            raise typer.BadParameter("--scenarios is required for det-pipeline mode.")
        if outdir is None:
            raise typer.BadParameter("--outdir is required for det-pipeline mode.")
        if project_id is None:
            raise typer.BadParameter("--project-id is required for det-pipeline mode.")
        det_options = joiner_cli.DetPipelineOptions(
            issues=issues,
            scenarios=scenarios,
            outdir=outdir,
            project_id=project_id,
            apply=apply,
            dry_run=(dry_run and not apply),
            top_k=top_k,
            top_n_per_issue=top_n_per_issue,
            force_tool_label=force_tool_label,
            allow_append_sections=allow_append_sections,
            timestamp=timestamp,
        )
        joiner_cli.run_det_pipeline(det_options)
        return
    if normalized_mode != "datasets":
        raise typer.BadParameter("mode must be either 'datasets' or 'det-pipeline'.")
    if assessments is None:
        raise typer.BadParameter("--assessments is required for datasets mode.")
    if scenarios is None:
        raise typer.BadParameter("--scenarios is required for datasets mode.")
    if issues is None:
        raise typer.BadParameter("--issues is required for datasets mode.")
    if outdir is None:
        raise typer.BadParameter("--outdir is required for datasets mode.")
    join_options = joiner_cli.JoinOptions(
        assessments=assessments,
        scenarios=scenarios,
        issues=issues,
        outdir=outdir,
        timestamp=timestamp,
        fail_on_missing_scenario=fail_on_missing_scenario,
        fail_on_malformed_scenario_technique=fail_on_malformed_scenario_technique,
    )
    joiner_cli.run_join(join_options)
