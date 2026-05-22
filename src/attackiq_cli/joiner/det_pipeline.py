"""Deterministic DET pipeline for GitLab issue reconciliation and AttackIQ planning."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from attackiq_cli.config import load_config
from attackiq_cli.joiner.normalize import stable_unique
from attackiq_cli.joiner.parse_labels import DETECTION_STRATEGY_RE, TACTIC_RE, TECHNIQUE_RE, TOOL_RE
from attackiq_cli.services import (
    build_auth_context,
    build_client,
    build_det_pipeline_create_assessment_operation,
    resolve_base_url,
)

HEADING_RE = re.compile(r"(?im)^#{1,6}\s+(.+?)\s*$")
TECHNIQUE_TOKEN_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
IID_DIGITS_RE = re.compile(r"^\d+$")
SCENARIO_ID_RE = re.compile(r"\b[0-9a-fA-F-]{8,}\b")
OS_LABEL_RE = re.compile(r"^os-(?:win|nix|mac)$")
ENV_LABEL_RE = re.compile(r"^env::.+$")
PLATFORM_LABEL_RE = re.compile(r"^platform::.+$")
SCHEMA_VERSION = "det-pipeline-v1"
ISSUES_NORMALIZED_FILENAME = "issues_normalized.jsonl"
ISSUES_FINDINGS_FILENAME = "issues_findings.csv"
STAGE_A_MANIFEST_FILENAME = "manifest.json"
TECHNIQUE_RECONCILIATION_FILENAME = "technique_reconciliation.json"
RECOMMENDATIONS_FILENAME = "recommendations.json"
ISSUE_CANDIDATES_FILENAME = "issue_to_scenario_candidates.csv"
ASSESSMENT_PLAN_FILENAME = "assessment_plan.json"
ASSESSMENT_PLAN_CSV_FILENAME = "assessment_plan.csv"
ASSESSMENT_REQUESTS_FILENAME = "attackiq_create_requests.ndjson"
PATCH_PLAN_FILENAME = "gitlab_patch_plan.json"
PATCH_PREVIEWS_FILENAME = "gitlab_description_previews.jsonl"
APPLY_REPORT_FILENAME = "apply_report.json"


@dataclass(frozen=True)
class RuleRecord:
    iid: str
    title: str
    description: str
    labels_raw: str
    tool: str | None
    det_id: str | None
    technique_tokens: list[str]
    tactic_tokens: list[str]
    os_tags: list[str]
    env_tags: list[str]
    platform_tags: list[str]
    matched_scenarios: list[str]


@dataclass(frozen=True)
class ReconciliationRecord:
    iid: str
    technique_final: str | None
    confidence: str
    candidates: list[str]
    needs_review: bool
    source: str


@dataclass(frozen=True)
class ScenarioRecord:
    scenario_id: str
    name: str
    scenario_tags: str
    supported_platform: str
    technique_tokens: list[str]


@dataclass(frozen=True)
class RecommendationEntry:
    scenario_id: str
    scenario_name: str
    score: float
    score_breakdown: dict[str, float]


@dataclass(frozen=True)
class DetPipelineOptions:
    issues: Path
    scenarios: Path
    outdir: Path
    project_id: str
    apply: bool = False
    dry_run: bool = True
    top_k: int = 5
    top_n_per_issue: int = 1
    force_tool_label: bool = False
    allow_append_sections: bool = False
    timestamp: str | None = None


def _as_int_sort_key(value: str) -> tuple[int, str]:
    if IID_DIGITS_RE.match(value):
        return int(value), value
    return 10**9, value


def _stable_json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, items: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [{k: (v or "") for k, v in row.items()} for row in rows]


def _value(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row and row[name] is not None:
            return str(row[name]).strip()
    return ""


def _extract_detection_mapping_body(description: str) -> str | None:
    match = _find_section_span(description, "Detection Mapping")
    if match is None:
        return None
    _, _, body_start, body_end = match
    return description[body_start:body_end]


def _extract_matched_scenarios(description: str) -> list[str]:
    body = _extract_detection_mapping_body(description)
    if body is None:
        return []
    if "Matched Scenarios" not in body:
        return []
    after = body.split("Matched Scenarios", 1)[1]
    values = SCENARIO_ID_RE.findall(after)
    return stable_unique([value.strip() for value in values if value.strip()])


def _extract_description_technique_tokens(description: str) -> list[str]:
    return stable_unique(TECHNIQUE_TOKEN_RE.findall(description))


def _canonical_det_id(tokens: list[str]) -> str | None:
    matches = [token for token in tokens if DETECTION_STRATEGY_RE.match(token)]
    if not matches:
        return None
    first = matches[0]
    return first.removeprefix("DET")


def _canonical_tool(tokens: list[str]) -> str | None:
    matches = [token for token in tokens if TOOL_RE.match(token)]
    return matches[0] if matches else None


def _canonical_list(items: Sequence[str]) -> list[str]:
    return sorted(stable_unique([item.strip() for item in items if item.strip()]))


def normalize_issues(issues_csv: Path) -> list[RuleRecord]:
    rows = _load_csv(issues_csv)
    records: list[RuleRecord] = []
    for row in rows:
        iid = _value(row, "IID", "iid")
        title = _value(row, "Title", "title")
        description = _value(row, "Description", "description")
        labels_raw = _value(row, "Labels", "labels")
        labels = [label.strip() for label in labels_raw.split(",") if label.strip()]
        techniques = [label for label in labels if TECHNIQUE_RE.match(label)]
        tactics = [label for label in labels if TACTIC_RE.match(label)]
        det_tokens = [label for label in labels if DETECTION_STRATEGY_RE.match(label)]
        tool_tokens = [label for label in labels if TOOL_RE.match(label)]
        os_tags = [label for label in labels if OS_LABEL_RE.match(label)]
        env_tags = [label for label in labels if ENV_LABEL_RE.match(label)]
        platform_tags = [label for label in labels if PLATFORM_LABEL_RE.match(label)]
        records.append(
            RuleRecord(
                iid=iid,
                title=title,
                description=description,
                labels_raw=labels_raw,
                tool=_canonical_tool(tool_tokens),
                det_id=_canonical_det_id(det_tokens),
                technique_tokens=_canonical_list(techniques),
                tactic_tokens=_canonical_list(tactics),
                os_tags=_canonical_list(os_tags),
                env_tags=_canonical_list(env_tags),
                platform_tags=_canonical_list(platform_tags),
                matched_scenarios=_canonical_list(_extract_matched_scenarios(description)),
            )
        )
    return sorted(records, key=lambda item: (_as_int_sort_key(item.iid), item.title.lower()))


def compute_findings(records: Sequence[RuleRecord]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for record in records:
        description_techniques = set(_extract_description_technique_tokens(record.description))
        label_techniques = set(record.technique_tokens)
        stale = bool(
            description_techniques
            and label_techniques
            and description_techniques.isdisjoint(label_techniques)
        )
        checks = [
            ("missing_det_id", record.det_id is None),
            ("missing_tool", record.tool is None),
            ("multiple_techniques", len(record.technique_tokens) > 1),
            ("no_technique", len(record.technique_tokens) == 0),
            ("stale_mapping_suspected", stale),
        ]
        for finding_type, present in checks:
            if not present:
                continue
            findings.append(
                {
                    "iid": record.iid,
                    "title": record.title,
                    "finding": finding_type,
                }
            )
    return sorted(findings, key=lambda item: (_as_int_sort_key(item["iid"]), item["finding"]))


def stage_a_normalize_and_reconcile(
    issues_csv: Path, outdir: Path
) -> tuple[list[RuleRecord], list[dict[str, str]]]:
    artifacts = outdir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    records = normalize_issues(issues_csv)
    findings = compute_findings(records)

    normalized_path = artifacts / ISSUES_NORMALIZED_FILENAME
    findings_path = artifacts / ISSUES_FINDINGS_FILENAME
    manifest_path = artifacts / STAGE_A_MANIFEST_FILENAME
    _write_jsonl(normalized_path, [record.__dict__ for record in records])
    _write_findings_csv(findings_path, findings)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": [{"name": issues_csv.name, "sha256": _sha256(issues_csv)}],
        "outputs": [
            {"name": normalized_path.name, "sha256": _sha256(normalized_path)},
            {"name": findings_path.name, "sha256": _sha256(findings_path)},
        ],
    }
    _stable_json_dump(manifest_path, manifest)
    return records, findings


def _write_findings_csv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["iid", "title", "finding"], lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def reconcile_techniques(records: Sequence[RuleRecord]) -> list[ReconciliationRecord]:
    reconciled: list[ReconciliationRecord] = []
    for record in records:
        description_tokens = _extract_description_technique_tokens(record.description)
        if len(record.technique_tokens) == 1:
            reconciled.append(
                ReconciliationRecord(
                    iid=record.iid,
                    technique_final=record.technique_tokens[0],
                    confidence="high",
                    candidates=[record.technique_tokens[0]],
                    needs_review=False,
                    source="label",
                )
            )
            continue
        if len(description_tokens) == 1:
            value = description_tokens[0]
            reconciled.append(
                ReconciliationRecord(
                    iid=record.iid,
                    technique_final=value,
                    confidence="medium",
                    candidates=[value],
                    needs_review=False,
                    source="description",
                )
            )
            continue
        candidates = sorted(set(record.technique_tokens) | set(description_tokens))
        reconciled.append(
            ReconciliationRecord(
                iid=record.iid,
                technique_final=None,
                confidence="low",
                candidates=candidates,
                needs_review=True,
                source="ambiguous",
            )
        )
    return sorted(reconciled, key=lambda item: _as_int_sort_key(item.iid))


def stage_b_reconcile(records: Sequence[RuleRecord], outdir: Path) -> list[ReconciliationRecord]:
    reconciled = reconcile_techniques(records)
    path = outdir / "artifacts" / TECHNIQUE_RECONCILIATION_FILENAME
    payload = {"items": [item.__dict__ for item in reconciled]}
    _stable_json_dump(path, payload)
    return reconciled


def _load_scenarios(scenarios_csv: Path) -> list[ScenarioRecord]:
    rows = _load_csv(scenarios_csv)
    records: list[ScenarioRecord] = []
    for row in rows:
        scenario_id = _value(row, "id", "ID")
        name = _value(row, "name", "Name")
        tags = _value(row, "scenario_tags", "Scenario Tags")
        platform = _value(row, "supported_platform", "supported_platforms", "Supported Platform")
        techniques = stable_unique(TECHNIQUE_TOKEN_RE.findall(tags))
        records.append(
            ScenarioRecord(
                scenario_id=scenario_id,
                name=name,
                scenario_tags=tags,
                supported_platform=platform,
                technique_tokens=sorted(techniques),
            )
        )
    return sorted(records, key=lambda item: (item.name.lower(), item.scenario_id))


def _title_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token}


def _platform_penalty(record: RuleRecord, scenario: ScenarioRecord) -> float:
    if not record.os_tags:
        return 0.0
    supported = scenario.supported_platform.lower()
    wants = {
        "os-win": "win" in supported or "windows" in supported,
        "os-nix": "linux" in supported or "unix" in supported or "nix" in supported,
        "os-mac": "mac" in supported,
    }
    for os_tag in record.os_tags:
        if os_tag in wants and wants[os_tag]:
            return 0.0
    return -0.5


def _parent_technique(token: str) -> str:
    if "." not in token:
        return token
    return token.split(".", 1)[0]


def build_recommendations(
    records: Sequence[RuleRecord],
    reconciled: Sequence[ReconciliationRecord],
    scenarios: Sequence[ScenarioRecord],
    *,
    top_k: int,
) -> tuple[dict[str, list[RecommendationEntry]], list[dict[str, str]]]:
    reconciliation_by_iid = {item.iid: item for item in reconciled}
    recommendations: dict[str, list[RecommendationEntry]] = {}
    csv_rows: list[dict[str, str]] = []
    for record in records:
        recon = reconciliation_by_iid.get(record.iid)
        technique = recon.technique_final if recon else None
        candidates = []
        if technique:
            candidates = [item for item in scenarios if technique in item.technique_tokens]
            if not candidates and "." in technique:
                parent = _parent_technique(technique)
                candidates = [item for item in scenarios if parent in item.technique_tokens]
        scored: list[RecommendationEntry] = []
        issue_tokens = _title_tokens(record.title)
        for scenario in candidates:
            overlap = float(len(issue_tokens & _title_tokens(scenario.name)))
            platform_penalty = _platform_penalty(record, scenario)
            total = overlap + platform_penalty
            scored.append(
                RecommendationEntry(
                    scenario_id=scenario.scenario_id,
                    scenario_name=scenario.name,
                    score=total,
                    score_breakdown={
                        "title_overlap": overlap,
                        "platform_penalty": platform_penalty,
                    },
                )
            )
        scored = sorted(
            scored,
            key=lambda item: (-item.score, item.scenario_name.lower(), item.scenario_id),
        )[:top_k]
        recommendations[record.iid] = scored
        for idx, item in enumerate(scored, start=1):
            csv_rows.append(
                {
                    "iid": record.iid,
                    "rank": str(idx),
                    "scenario_id": item.scenario_id,
                    "scenario_name": item.scenario_name,
                    "score": f"{item.score:.3f}",
                }
            )
    csv_rows = sorted(
        csv_rows,
        key=lambda row: (
            _as_int_sort_key(row["iid"]),
            int(row["rank"]),
            row["scenario_id"],
        ),
    )
    return recommendations, csv_rows


def stage_c_recommend(
    records: Sequence[RuleRecord],
    reconciled: Sequence[ReconciliationRecord],
    scenarios_csv: Path,
    outdir: Path,
    *,
    top_k: int,
) -> dict[str, list[RecommendationEntry]]:
    scenarios = _load_scenarios(scenarios_csv)
    recommendations, csv_rows = build_recommendations(
        records, reconciled, scenarios, top_k=top_k
    )
    artifacts = outdir / "artifacts"
    recommendations_path = artifacts / RECOMMENDATIONS_FILENAME
    candidates_path = artifacts / ISSUE_CANDIDATES_FILENAME
    serializable = {
        "items": [
            {
                "iid": iid,
                "recommendations": [
                    {
                        "scenario_id": entry.scenario_id,
                        "scenario_name": entry.scenario_name,
                        "score": entry.score,
                        "score_breakdown": entry.score_breakdown,
                    }
                    for entry in items
                ],
            }
            for iid, items in sorted(
                recommendations.items(), key=lambda item: _as_int_sort_key(item[0])
            )
        ]
    }
    _stable_json_dump(recommendations_path, serializable)
    with candidates_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["iid", "rank", "scenario_id", "scenario_name", "score"],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
    return recommendations


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "det"


def _assessment_name(tool: str, det_id: str, title: str) -> str:
    return f"DRV::{tool}::DET-{det_id}::{_slugify(title)[:36]}"


def stage_d_plan_assessments(
    records: Sequence[RuleRecord],
    recommendations: dict[str, list[RecommendationEntry]],
    outdir: Path,
    *,
    top_n_per_issue: int,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[RuleRecord]] = defaultdict(list)
    for record in records:
        if not record.det_id or not record.tool:
            continue
        grouped[(record.tool, record.det_id)].append(record)

    plan: list[dict[str, Any]] = []
    for (tool, det_id), items in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        scenario_ids: list[str] = []
        issue_iids: list[str] = []
        titles: list[str] = []
        for issue in sorted(items, key=lambda item: _as_int_sort_key(item.iid)):
            issue_iids.append(issue.iid)
            titles.append(issue.title)
            top = recommendations.get(issue.iid, [])[:top_n_per_issue]
            scenario_ids.extend([entry.scenario_id for entry in top if entry.scenario_id])
        deduped_ids = sorted(set(scenario_ids))
        plan.append(
            {
                "tool": tool,
                "det_id": det_id,
                "assessment_name": _assessment_name(tool, det_id, titles[0] if titles else det_id),
                "issue_iids": issue_iids,
                "scenario_ids": deduped_ids,
            }
        )

    artifacts = outdir / "artifacts"
    _stable_json_dump(artifacts / ASSESSMENT_PLAN_FILENAME, {"items": plan})
    with (artifacts / ASSESSMENT_PLAN_CSV_FILENAME).open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["tool", "det_id", "assessment_name", "issue_iids", "scenario_ids"],
            lineterminator="\n",
        )
        writer.writeheader()
        for item in plan:
            writer.writerow(
                {
                    "tool": item["tool"],
                    "det_id": item["det_id"],
                    "assessment_name": item["assessment_name"],
                    "issue_iids": ",".join(item["issue_iids"]),
                    "scenario_ids": ",".join(item["scenario_ids"]),
                }
            )
    requests_path = artifacts / ASSESSMENT_REQUESTS_FILENAME
    _write_jsonl(
        requests_path,
        [
            {
                "operation": "create_assessment",
                "payload": {
                    "name": item["assessment_name"],
                    "scenario_ids": item["scenario_ids"],
                    "det_id": item["det_id"],
                },
            }
            for item in plan
        ],
    )
    return plan


def _find_section_span(
    text: str, heading_name: str
) -> tuple[int, int, int, int] | None:
    matches = list(HEADING_RE.finditer(text))
    target_lower = heading_name.strip().lower()
    for index, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        if heading != target_lower:
            continue
        heading_start, heading_end = match.span()
        next_heading_start = len(text)
        if index + 1 < len(matches):
            next_heading_start = matches[index + 1].start()
        return heading_start, heading_end, heading_end, next_heading_start
    return None


def rewrite_detection_mapping_section(
    description: str,
    mapping_body: str,
    *,
    allow_append_sections: bool,
) -> tuple[str, bool, list[str]]:
    findings: list[str] = []
    span = _find_section_span(description, "Detection Mapping")
    if span is None:
        findings.append("missing_detection_mapping_section")
        if not allow_append_sections:
            return description, False, findings
        suffix = "" if not description.strip() else "\n\n"
        new_text = f"{description.rstrip()}{suffix}## Detection Mapping\n{mapping_body}\n"
        return new_text, True, findings

    heading_start, heading_end, _body_start, body_end = span
    heading = description[heading_start:heading_end]
    replacement = f"{heading}\n{mapping_body}\n"
    updated = f"{description[:heading_start]}{replacement}{description[body_end:]}"
    return updated, updated != description, findings


def rewrite_matched_scenarios_section(
    description: str, recommendations: Sequence[RecommendationEntry]
) -> tuple[str, bool]:
    span = _find_section_span(description, "Matched Scenarios")
    if span is None:
        return description, False
    heading_start, heading_end, _body_start, body_end = span
    heading = description[heading_start:heading_end]
    lines = [f"- {item.scenario_id}: {item.scenario_name}" for item in recommendations]
    body = "\n".join(lines)
    replacement = f"{heading}\n{body}\n"
    updated = f"{description[:heading_start]}{replacement}{description[body_end:]}"
    return updated, updated != description


def _render_mapping_body(
    record: RuleRecord,
    reconciliation: ReconciliationRecord | None,
    recommendations: Sequence[RecommendationEntry],
) -> str:
    det_label = f"DET{record.det_id}" if record.det_id else ""
    confidence = reconciliation.confidence if reconciliation else "low"
    technique_final = reconciliation.technique_final if reconciliation else ""
    candidates = reconciliation.candidates if reconciliation else []
    scenarios_line = ", ".join(
        [f"{item.scenario_id} ({item.scenario_name})" for item in recommendations]
    )
    lines = [
        f"Tool: {record.tool or ''}",
        f"Detection Strategy (DET####): {det_label}",
        f"Technique Final + Confidence: {technique_final} ({confidence})",
    ]
    if candidates:
        lines.append(f"Technique Candidates: {', '.join(candidates)}")
    lines.append(
        "OS / ENV / PLATFORM tags: "
        f"{', '.join(record.os_tags + record.env_tags + record.platform_tags)}"
    )
    lines.append(f"Matched Scenarios: {scenarios_line}")
    return "\n".join(lines)


def stage_e_build_patch_plan(
    records: Sequence[RuleRecord],
    reconciled: Sequence[ReconciliationRecord],
    recommendations: dict[str, list[RecommendationEntry]],
    outdir: Path,
    *,
    force_tool_label: bool,
    allow_append_sections: bool,
) -> list[dict[str, Any]]:
    reconciliation_by_iid = {item.iid: item for item in reconciled}
    patch_plan: list[dict[str, Any]] = []
    preview_rows: list[dict[str, Any]] = []

    for record in records:
        labels = stable_unique(
            [value.strip() for value in record.labels_raw.split(",") if value.strip()]
        )
        recon = reconciliation_by_iid.get(record.iid)
        findings: list[str] = []
        add_labels: list[str] = []
        remove_labels: list[str] = []
        technique_labels = [label for label in labels if TECHNIQUE_RE.match(label)]
        if record.tool and record.tool not in labels:
            if force_tool_label:
                add_labels.append(record.tool)
            else:
                findings.append("missing_tool_label")
        if record.det_id:
            det_label = f"DET{record.det_id}"
            if det_label not in labels:
                add_labels.append(det_label)
        else:
            findings.append("missing_det_label")

        if recon and recon.confidence == "high" and recon.technique_final:
            if recon.technique_final not in labels:
                add_labels.append(recon.technique_final)
            for label in technique_labels:
                if label != recon.technique_final:
                    remove_labels.append(label)
        elif technique_labels:
            findings.append("technique_label_alignment_skipped_low_confidence")

        has_recommendations = bool(recommendations.get(record.iid))
        if has_recommendations:
            if "needs-scenario" in labels:
                remove_labels.append("needs-scenario")
        else:
            add_labels.append("needs-scenario")

        mapping_body = _render_mapping_body(record, recon, recommendations.get(record.iid, []))
        updated_description, changed, rewrite_findings = rewrite_detection_mapping_section(
            record.description,
            mapping_body,
            allow_append_sections=allow_append_sections,
        )
        updated_description, matched_changed = rewrite_matched_scenarios_section(
            updated_description,
            recommendations.get(record.iid, []),
        )
        changed = changed or matched_changed
        findings.extend(rewrite_findings)

        final_labels = sorted(set(labels + add_labels) - set(remove_labels))
        patch_plan.append(
            {
                "iid": record.iid,
                "project_id": "",
                "add_labels": sorted(set(add_labels)),
                "remove_labels": sorted(set(remove_labels)),
                "final_labels": final_labels,
                "description_changed": changed,
                "description": updated_description if changed else record.description,
                "findings": sorted(set(findings)),
            }
        )
        preview_rows.append(
            {
                "iid": record.iid,
                "description_original": record.description,
                "description_rewritten": updated_description,
            }
        )
    patch_plan = sorted(patch_plan, key=lambda item: _as_int_sort_key(item["iid"]))
    artifacts = outdir / "artifacts"
    _stable_json_dump(artifacts / PATCH_PLAN_FILENAME, {"items": patch_plan})
    _write_jsonl(artifacts / PATCH_PREVIEWS_FILENAME, preview_rows)
    return patch_plan


def _is_retryable_gitlab(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return bool(isinstance(exc, httpx.RequestError))


class GitLabClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = httpx.Client(timeout=30.0)

    def close(self) -> None:
        self._client.close()

    @retry(
        retry=retry_if_exception(lambda exc: _is_retryable_gitlab(exc)),
        wait=wait_exponential(multiplier=0.5, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def update_issue(
        self, *, project_id: str, iid: str, labels: Sequence[str], description: str
    ) -> dict[str, Any]:
        url = f"{self.base_url}/api/v4/projects/{project_id}/issues/{iid}"
        response = self._client.put(
            url,
            headers={"PRIVATE-TOKEN": self.token},
            data={"labels": ",".join(labels), "description": description},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


def _apply_attackiq_assessments(plan: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    config = load_config()
    base_url = resolve_base_url(config, None)
    auth = build_auth_context(config, preferred_scheme="auto")
    operation = build_det_pipeline_create_assessment_operation()
    results: list[dict[str, Any]] = []
    with build_client(
        base_url,
        config,
        auth,
        insecure=False,
        timeout=None,
    ) as client:
        for item in plan:
            try:
                payload = {
                    "name": item["assessment_name"],
                    "scenario_ids": item["scenario_ids"],
                }
                response = client.send(
                    operation,
                    path_params={},
                    query_params={},
                    headers={},
                    json_body=payload,
                ).json()
                results.append(
                    {
                        "assessment_name": item["assessment_name"],
                        "created_id": str(response.get("id") or response.get("project_id") or ""),
                        "status": "success",
                    }
                )
            except Exception as exc:  # pragma: no cover - network
                results.append(
                    {
                        "assessment_name": item["assessment_name"],
                        "created_id": "",
                        "status": "failed",
                        "error": str(exc),
                    }
                )
    return results


def _apply_gitlab_updates(
    patch_plan: Sequence[dict[str, Any]], *, project_id: str
) -> list[dict[str, Any]]:
    import os

    base_url = os.getenv("GITLAB_BASE_URL", "").strip()
    token = os.getenv("GITLAB_TOKEN", "").strip()
    if not base_url or not token:
        raise ValueError("GITLAB_BASE_URL and GITLAB_TOKEN are required in apply mode.")
    client = GitLabClient(base_url, token)
    results: list[dict[str, Any]] = []
    try:
        for item in patch_plan:
            iid = str(item["iid"])
            try:
                response = client.update_issue(
                    project_id=project_id,
                    iid=iid,
                    labels=item["final_labels"],
                    description=item["description"],
                )
                results.append(
                    {
                        "iid": iid,
                        "status": "success",
                        "web_url": response.get("web_url") or "",
                    }
                )
            except Exception as exc:  # pragma: no cover - network
                results.append({"iid": iid, "status": "failed", "error": str(exc)})
    finally:
        client.close()
    return results


def run_det_pipeline(options: DetPipelineOptions) -> dict[str, Any]:
    artifacts = options.outdir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    records, findings = stage_a_normalize_and_reconcile(options.issues, options.outdir)
    reconciled = stage_b_reconcile(records, options.outdir)
    recommendations = stage_c_recommend(
        records,
        reconciled,
        options.scenarios,
        options.outdir,
        top_k=options.top_k,
    )
    assessment_plan = stage_d_plan_assessments(
        records,
        recommendations,
        options.outdir,
        top_n_per_issue=options.top_n_per_issue,
    )
    patch_plan = stage_e_build_patch_plan(
        records,
        reconciled,
        recommendations,
        options.outdir,
        force_tool_label=options.force_tool_label,
        allow_append_sections=options.allow_append_sections,
    )

    report: dict[str, Any] = {
        "dry_run": options.dry_run and not options.apply,
        "apply_requested": options.apply,
        "issues_total": len(records),
        "findings_total": len(findings),
        "assessment_plan_total": len(assessment_plan),
        "patch_plan_total": len(patch_plan),
        "gitlab_updates": [],
        "attackiq_assessments": [],
    }

    if options.apply:
        report["gitlab_updates"] = _apply_gitlab_updates(
            patch_plan, project_id=options.project_id
        )
        report["attackiq_assessments"] = _apply_attackiq_assessments(assessment_plan)

    _stable_json_dump(artifacts / APPLY_REPORT_FILENAME, report)
    return report
