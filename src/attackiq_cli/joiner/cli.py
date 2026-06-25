"""CLI for the deterministic AttackIQ/GitLab joiner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from attackiq_cli import __version__
from attackiq_cli.joiner.det_pipeline import (
    DetPipelineOptions,
    run_det_pipeline,
    stage_a_normalize_and_reconcile,
    stage_b_reconcile,
    stage_c_recommend,
    stage_d_plan_assessments,
    stage_e_build_patch_plan,
)
from attackiq_cli.joiner.emit import write_csv
from attackiq_cli.joiner.join import (
    Assessment,
    Issue,
    Scenario,
    join_assessments_to_scenarios,
    join_issues_to_scenarios,
    left_join_assessment_scenario_issues,
    sort_assessment_scenario_issue_rows,
    sort_assessment_scenario_rows,
    sort_issue_scenario_rows,
    sort_unmapped_issue_rows,
    validate_scenario_techniques,
)
from attackiq_cli.joiner.parse_labels import parse_labels
from attackiq_cli.joiner.schema import (
    ASSESSMENT_SCENARIO_HEADERS,
    ASSESSMENT_SCENARIO_ISSUE_HEADERS,
    ASSESSMENTS_HEADERS,
    ISSUE_FIELD_MAP,
    ISSUE_SCENARIO_HEADERS,
    ISSUES_HEADERS,
    ISSUES_UNMAPPED_HEADERS,
    SCENARIOS_HEADERS,
    SCHEMA_VERSION,
)

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DEFAULT_LABEL_DELIMITER = ", "
DEFAULT_LIST_DELIMITER = ", "


@dataclass(frozen=True)
class JoinOptions:
    assessments: Path
    scenarios: Path
    issues: Path
    outdir: Path
    timestamp: str | None
    fail_on_missing_scenario: bool
    fail_on_malformed_scenario_technique: bool
    label_delimiter: str = DEFAULT_LABEL_DELIMITER
    list_delimiter: str = DEFAULT_LIST_DELIMITER


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("Expected true or false.")


def validate_headers(actual: Sequence[str] | None, required: Sequence[str], path: Path) -> None:
    if actual is None:
        raise ValueError(f"Missing headers in {path}.")
    missing = [header for header in required if header not in actual]
    if missing:
        raise ValueError(f"Missing headers in {path}: {', '.join(missing)}")


def normalize_field(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def load_assessments(path: Path) -> list[Assessment]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_headers(reader.fieldnames, ASSESSMENTS_HEADERS, path)
        assessments = [
            Assessment(
                assessment_id=normalize_field(row, "id"),
                name=normalize_field(row, "name"),
                scenario_id=normalize_field(row, "scenario_id"),
            )
            for row in reader
        ]
    return assessments


def load_scenarios(path: Path) -> list[Scenario]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_headers(reader.fieldnames, SCENARIOS_HEADERS, path)
        scenarios = [
            Scenario(
                scenario_id=normalize_field(row, "id"),
                name=normalize_field(row, "name"),
                technique=normalize_field(row, "technique"),
                supported_platforms=normalize_field(row, "supported_platforms"),
                capabilities=normalize_field(row, "capabilities"),
            )
            for row in reader
        ]
    return scenarios


def load_issues(path: Path, label_delimiter: str) -> list[Issue]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_headers(reader.fieldnames, ISSUES_HEADERS, path)
        issues: list[Issue] = []
        for row in reader:
            labels_raw = normalize_field(row, ISSUE_FIELD_MAP["labels_raw"])
            parsed = parse_labels(labels_raw, delimiter=label_delimiter)
            issues.append(
                Issue(
                    issue_id=normalize_field(row, ISSUE_FIELD_MAP["issue_id"]),
                    issue_iid=normalize_field(row, ISSUE_FIELD_MAP["issue_iid"]),
                    title=normalize_field(row, ISSUE_FIELD_MAP["issue_title"]),
                    url=normalize_field(row, ISSUE_FIELD_MAP["issue_url"]),
                    state=normalize_field(row, ISSUE_FIELD_MAP["issue_state"]),
                    created_at_utc=normalize_field(row, ISSUE_FIELD_MAP["created_at_utc"]),
                    updated_at_utc=normalize_field(row, ISSUE_FIELD_MAP["updated_at_utc"]),
                    labels_raw=labels_raw,
                    techniques=parsed.techniques,
                    tactics=parsed.tactics,
                    detection_strategy_ids=parsed.detection_strategy_ids,
                    tools=parsed.tools,
                    csf=parsed.csf,
                )
            )
    return issues


def file_hash(path: Path) -> dict[str, str | int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
    return {"name": path.name, "sha256": hasher.hexdigest(), "bytes": size}


def resolve_created_utc(timestamp: str | None) -> str:
    if timestamp is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not TIMESTAMP_RE.match(timestamp):
        raise ValueError("--timestamp must be ISO8601 UTC like 2026-01-26T00:00:00Z")
    return timestamp


def build_manifest(
    *,
    created_utc: str,
    options: JoinOptions,
    inputs: Iterable[Path],
    outputs: Iterable[Path],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_utc": created_utc,
        "joiner_version": __version__,
        "python_version": platform.python_version(),
        "options": {
            "issue_label_delimiter": options.label_delimiter,
            "list_delimiter": options.list_delimiter,
            "fail_on_missing_scenario": options.fail_on_missing_scenario,
            "fail_on_malformed_scenario_technique": options.fail_on_malformed_scenario_technique,
        },
        "inputs": [file_hash(path) for path in inputs],
        "outputs": [file_hash(path) for path in outputs],
    }


def run_join(options: JoinOptions) -> None:
    assessments = load_assessments(options.assessments)
    scenarios = load_scenarios(options.scenarios)
    validate_scenario_techniques(
        scenarios,
        fail_on_malformed=options.fail_on_malformed_scenario_technique,
    )
    issues = load_issues(options.issues, options.label_delimiter)

    assessment_rows = join_assessments_to_scenarios(
        assessments,
        scenarios,
        fail_on_missing_scenario=options.fail_on_missing_scenario,
    )
    issue_rows, unmapped_rows = join_issues_to_scenarios(
        issues,
        scenarios,
        list_delimiter=options.list_delimiter,
    )
    assessment_issue_rows = left_join_assessment_scenario_issues(
        assessment_rows,
        issue_rows,
    )

    assessment_rows = sort_assessment_scenario_rows(assessment_rows)
    issue_rows = sort_issue_scenario_rows(issue_rows)
    assessment_issue_rows = sort_assessment_scenario_issue_rows(assessment_issue_rows)
    unmapped_rows = sort_unmapped_issue_rows(unmapped_rows)

    outdir = options.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    assessment_path = outdir / "assessment_scenario.csv"
    issue_path = outdir / "issue_scenario.csv"
    assessment_issue_path = outdir / "assessment_scenario_issue.csv"
    unmapped_path = outdir / "issues_unmapped.csv"

    write_csv(assessment_path, ASSESSMENT_SCENARIO_HEADERS, assessment_rows)
    write_csv(issue_path, ISSUE_SCENARIO_HEADERS, issue_rows)
    write_csv(assessment_issue_path, ASSESSMENT_SCENARIO_ISSUE_HEADERS, assessment_issue_rows)
    write_csv(unmapped_path, ISSUES_UNMAPPED_HEADERS, unmapped_rows)

    created_utc = resolve_created_utc(options.timestamp)
    manifest = build_manifest(
        created_utc=created_utc,
        options=options,
        inputs=[options.assessments, options.scenarios, options.issues],
        outputs=[assessment_path, issue_path, assessment_issue_path, unmapped_path],
    )

    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="attackiq-cli-joiner",
        description="Join AttackIQ exports with GitLab issues.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    join_parser = subparsers.add_parser("join", help="Join assessments, scenarios, and issues.")
    join_parser.add_argument("--assessments", required=True, type=Path)
    join_parser.add_argument("--scenarios", required=True, type=Path)
    join_parser.add_argument("--issues", required=True, type=Path)
    join_parser.add_argument("--outdir", required=True, type=Path)
    join_parser.add_argument("--timestamp", type=str)
    join_parser.add_argument(
        "--fail-on-missing-scenario",
        type=parse_bool,
        default=True,
        metavar="true|false",
    )
    join_parser.add_argument(
        "--fail-on-malformed-scenario-technique",
        type=parse_bool,
        default=True,
        metavar="true|false",
    )
    det_parser = subparsers.add_parser(
        "det-pipeline",
        help="Run deterministic DET pipeline (stages A-E).",
    )
    det_parser.add_argument("--issues", required=True, type=Path)
    det_parser.add_argument("--scenarios", required=True, type=Path)
    det_parser.add_argument("--outdir", required=True, type=Path)
    det_parser.add_argument("--project-id", required=True, type=str)
    det_parser.add_argument("--top-k", type=int, default=5)
    det_parser.add_argument("--top-n-per-issue", type=int, default=1)
    det_parser.add_argument("--force-tool-label", action="store_true", default=False)
    det_parser.add_argument("--allow-append-sections", action="store_true", default=False)
    det_parser.add_argument("--dry-run", action="store_true", default=True)
    det_parser.add_argument("--apply", action="store_true", default=False)

    stage_a_parser = subparsers.add_parser("det-stage-a", help="Run stage A (normalize/reconcile).")
    stage_a_parser.add_argument("--issues", required=True, type=Path)
    stage_a_parser.add_argument("--outdir", required=True, type=Path)
    stage_a_parser.add_argument("--dry-run", action="store_true", default=True)
    stage_a_parser.add_argument("--apply", action="store_true", default=False)

    stage_b_parser = subparsers.add_parser(
        "det-stage-b", help="Run stage B (technique reconciliation)."
    )
    stage_b_parser.add_argument("--issues", required=True, type=Path)
    stage_b_parser.add_argument("--outdir", required=True, type=Path)
    stage_b_parser.add_argument("--dry-run", action="store_true", default=True)
    stage_b_parser.add_argument("--apply", action="store_true", default=False)

    stage_c_parser = subparsers.add_parser(
        "det-stage-c", help="Run stage C (scenario recommendations)."
    )
    stage_c_parser.add_argument("--issues", required=True, type=Path)
    stage_c_parser.add_argument("--scenarios", required=True, type=Path)
    stage_c_parser.add_argument("--outdir", required=True, type=Path)
    stage_c_parser.add_argument("--top-k", type=int, default=5)
    stage_c_parser.add_argument("--dry-run", action="store_true", default=True)
    stage_c_parser.add_argument("--apply", action="store_true", default=False)

    stage_d_parser = subparsers.add_parser("det-stage-d", help="Run stage D (assessment plan).")
    stage_d_parser.add_argument("--issues", required=True, type=Path)
    stage_d_parser.add_argument("--scenarios", required=True, type=Path)
    stage_d_parser.add_argument("--outdir", required=True, type=Path)
    stage_d_parser.add_argument("--top-k", type=int, default=5)
    stage_d_parser.add_argument("--top-n-per-issue", type=int, default=1)
    stage_d_parser.add_argument("--dry-run", action="store_true", default=True)
    stage_d_parser.add_argument("--apply", action="store_true", default=False)

    stage_e_parser = subparsers.add_parser("det-stage-e", help="Run stage E (GitLab patch plan).")
    stage_e_parser.add_argument("--issues", required=True, type=Path)
    stage_e_parser.add_argument("--scenarios", required=True, type=Path)
    stage_e_parser.add_argument("--outdir", required=True, type=Path)
    stage_e_parser.add_argument("--top-k", type=int, default=5)
    stage_e_parser.add_argument("--force-tool-label", action="store_true", default=False)
    stage_e_parser.add_argument("--allow-append-sections", action="store_true", default=False)
    stage_e_parser.add_argument("--dry-run", action="store_true", default=True)
    stage_e_parser.add_argument("--apply", action="store_true", default=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "join":
        join_options = JoinOptions(
            assessments=args.assessments,
            scenarios=args.scenarios,
            issues=args.issues,
            outdir=args.outdir,
            timestamp=args.timestamp,
            fail_on_missing_scenario=args.fail_on_missing_scenario,
            fail_on_malformed_scenario_technique=args.fail_on_malformed_scenario_technique,
        )
        run_join(join_options)
        return 0
    if args.command == "det-pipeline":
        det_options = DetPipelineOptions(
            issues=args.issues,
            scenarios=args.scenarios,
            outdir=args.outdir,
            project_id=args.project_id,
            apply=args.apply,
            dry_run=not args.apply,
            top_k=args.top_k,
            top_n_per_issue=args.top_n_per_issue,
            force_tool_label=args.force_tool_label,
            allow_append_sections=args.allow_append_sections,
        )
        run_det_pipeline(det_options)
        return 0
    if args.command == "det-stage-a":
        stage_a_normalize_and_reconcile(args.issues, args.outdir)
        return 0
    if args.command == "det-stage-b":
        records, _findings = stage_a_normalize_and_reconcile(args.issues, args.outdir)
        stage_b_reconcile(records, args.outdir)
        return 0
    if args.command == "det-stage-c":
        records, _findings = stage_a_normalize_and_reconcile(args.issues, args.outdir)
        reconciled = stage_b_reconcile(records, args.outdir)
        stage_c_recommend(records, reconciled, args.scenarios, args.outdir, top_k=args.top_k)
        return 0
    if args.command == "det-stage-d":
        records, _findings = stage_a_normalize_and_reconcile(args.issues, args.outdir)
        reconciled = stage_b_reconcile(records, args.outdir)
        recommendations = stage_c_recommend(
            records, reconciled, args.scenarios, args.outdir, top_k=args.top_k
        )
        stage_d_plan_assessments(
            records,
            recommendations,
            args.outdir,
            top_n_per_issue=args.top_n_per_issue,
        )
        return 0
    if args.command == "det-stage-e":
        records, _findings = stage_a_normalize_and_reconcile(args.issues, args.outdir)
        reconciled = stage_b_reconcile(records, args.outdir)
        recommendations = stage_c_recommend(
            records, reconciled, args.scenarios, args.outdir, top_k=args.top_k
        )
        stage_e_build_patch_plan(
            records,
            reconciled,
            recommendations,
            args.outdir,
            force_tool_label=args.force_tool_label,
            allow_append_sections=args.allow_append_sections,
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
