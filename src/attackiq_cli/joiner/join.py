"""Pure join logic for deterministic AttackIQ/GitLab datasets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from attackiq_cli.joiner.normalize import list_to_string
from attackiq_cli.joiner.parse_labels import TECHNIQUE_RE


@dataclass(frozen=True)
class Assessment:
    assessment_id: str
    name: str
    scenario_id: str


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    name: str
    technique: str
    supported_platforms: str
    capabilities: str


@dataclass(frozen=True)
class Issue:
    issue_id: str
    issue_iid: str
    title: str
    url: str
    state: str
    created_at_utc: str
    updated_at_utc: str
    labels_raw: str
    techniques: list[str]
    tactics: list[str]
    detection_strategy_ids: list[str]
    tools: list[str]
    csf: list[str]


def validate_scenario_techniques(
    scenarios: Iterable[Scenario],
    *,
    fail_on_malformed: bool,
) -> None:
    errors: list[str] = []
    for scenario in scenarios:
        if not scenario.technique:
            continue
        if not TECHNIQUE_RE.match(scenario.technique):
            errors.append(
                f"Scenario {scenario.scenario_id} has malformed technique '{scenario.technique}'."
            )
    if errors and fail_on_malformed:
        raise ValueError("\n".join(errors))


def join_assessments_to_scenarios(
    assessments: Iterable[Assessment],
    scenarios: Iterable[Scenario],
    *,
    fail_on_missing_scenario: bool,
) -> list[dict[str, str]]:
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    rows: list[dict[str, str]] = []
    errors: list[str] = []

    for assessment in assessments:
        if not assessment.scenario_id:
            if fail_on_missing_scenario:
                errors.append(
                    f"Assessment {assessment.assessment_id} missing scenario_id."
                )
            continue

        scenario = scenario_by_id.get(assessment.scenario_id)
        if not scenario:
            if fail_on_missing_scenario:
                errors.append(
                    f"Assessment {assessment.assessment_id} references unknown scenario_id "
                    f"{assessment.scenario_id}."
                )
            continue

        rows.append(
            {
                "assessment_id": assessment.assessment_id,
                "assessment_name": assessment.name,
                "scenario_id": scenario.scenario_id,
                "scenario_name": scenario.name,
                "scenario_technique": scenario.technique,
                "scenario_supported_platforms": scenario.supported_platforms,
                "scenario_capabilities": scenario.capabilities,
            }
        )

    if errors:
        raise ValueError("\n".join(errors))

    return rows


def join_issues_to_scenarios(
    issues: Iterable[Issue],
    scenarios: Iterable[Scenario],
    *,
    list_delimiter: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    scenarios_by_technique: dict[str, list[Scenario]] = {}
    for scenario in scenarios:
        if not scenario.technique:
            continue
        scenarios_by_technique.setdefault(scenario.technique, []).append(scenario)

    mapped_rows: list[dict[str, str]] = []
    unmapped_rows: list[dict[str, str]] = []

    for issue in issues:
        issue_techniques = list_to_string(issue.techniques, list_delimiter)
        issue_tactics = list_to_string(issue.tactics, list_delimiter)
        issue_detection = list_to_string(issue.detection_strategy_ids, list_delimiter)
        issue_tools = list_to_string(issue.tools, list_delimiter)
        issue_csf = list_to_string(issue.csf, list_delimiter)

        if not issue.techniques:
            unmapped_rows.append(
                {
                    "issue_id": issue.issue_id,
                    "issue_iid": issue.issue_iid,
                    "issue_title": issue.title,
                    "issue_url": issue.url,
                    "issue_state": issue.state,
                    "reason": "no_technique_labels",
                    "labels_raw": issue.labels_raw,
                    "issue_techniques": issue_techniques,
                }
            )
            continue

        matched = False
        for technique in issue.techniques:
            scenarios_for_technique = scenarios_by_technique.get(technique, [])
            if not scenarios_for_technique:
                continue
            matched = True
            for scenario in scenarios_for_technique:
                mapped_rows.append(
                    {
                        "issue_id": issue.issue_id,
                        "issue_iid": issue.issue_iid,
                        "issue_title": issue.title,
                        "issue_url": issue.url,
                        "issue_state": issue.state,
                        "issue_created_at_utc": issue.created_at_utc,
                        "issue_updated_at_utc": issue.updated_at_utc,
                        "scenario_id": scenario.scenario_id,
                        "scenario_name": scenario.name,
                        "scenario_technique": scenario.technique,
                        "issue_technique_token": technique,
                        "labels_raw": issue.labels_raw,
                        "issue_techniques": issue_techniques,
                        "issue_tactics": issue_tactics,
                        "issue_detection_strategy_ids": issue_detection,
                        "issue_tools": issue_tools,
                        "issue_csf": issue_csf,
                    }
                )

        if not matched:
            unmapped_rows.append(
                {
                    "issue_id": issue.issue_id,
                    "issue_iid": issue.issue_iid,
                    "issue_title": issue.title,
                    "issue_url": issue.url,
                    "issue_state": issue.state,
                    "reason": "no_scenario_match",
                    "labels_raw": issue.labels_raw,
                    "issue_techniques": issue_techniques,
                }
            )

    return mapped_rows, unmapped_rows


def left_join_assessment_scenario_issues(
    assessment_rows: Iterable[dict[str, str]],
    issue_rows: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    issues_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in issue_rows:
        issues_by_scenario.setdefault(row["scenario_id"], []).append(row)

    rows: list[dict[str, str]] = []
    for assessment in assessment_rows:
        scenario_id = assessment["scenario_id"]
        issues = issues_by_scenario.get(scenario_id)
        if not issues:
            rows.append(
                {
                    **assessment,
                    "issue_id": "",
                    "issue_iid": "",
                    "issue_title": "",
                    "issue_url": "",
                    "issue_state": "",
                    "issue_created_at_utc": "",
                    "issue_updated_at_utc": "",
                    "issue_technique_token": "",
                    "labels_raw": "",
                    "issue_techniques": "",
                    "issue_tactics": "",
                    "issue_detection_strategy_ids": "",
                    "issue_tools": "",
                    "issue_csf": "",
                }
            )
            continue

        for issue in issues:
            rows.append(
                {
                    **assessment,
                    "issue_id": issue["issue_id"],
                    "issue_iid": issue["issue_iid"],
                    "issue_title": issue["issue_title"],
                    "issue_url": issue["issue_url"],
                    "issue_state": issue["issue_state"],
                    "issue_created_at_utc": issue["issue_created_at_utc"],
                    "issue_updated_at_utc": issue["issue_updated_at_utc"],
                    "issue_technique_token": issue["issue_technique_token"],
                    "labels_raw": issue["labels_raw"],
                    "issue_techniques": issue["issue_techniques"],
                    "issue_tactics": issue["issue_tactics"],
                    "issue_detection_strategy_ids": issue["issue_detection_strategy_ids"],
                    "issue_tools": issue["issue_tools"],
                    "issue_csf": issue["issue_csf"],
                }
            )

    return rows


def sort_assessment_scenario_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: (row["scenario_id"], row["assessment_id"]))


def sort_issue_scenario_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (row["scenario_id"], row["issue_id"], row["issue_technique_token"]),
    )


def sort_assessment_scenario_issue_rows(
    rows: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            row["scenario_id"],
            row["assessment_id"],
            row["issue_id"] == "",
            row["issue_id"],
        ),
    )


def sort_unmapped_issue_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: row["issue_id"])

