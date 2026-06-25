"""Schema definitions for the AttackIQ/GitLab joiner."""

from __future__ import annotations

SCHEMA_VERSION = "1"

ASSESSMENTS_HEADERS = ("name", "id", "scenario", "scenario_id")
SCENARIOS_HEADERS = (
    "name",
    "id",
    "technique",
    "supported_platforms",
    "capabilities",
)
ISSUES_HEADERS = (
    "ID",
    "IID",
    "Title",
    "Description",
    "Type",
    "URL",
    "State",
    "Confidential",
    "Locked",
    "Milestone",
    "Labels",
    "Author",
    "Auther Username",
    "Assignee",
    "Assignee Username",
    "Created At (UTC)",
    "Updated At (UTC)",
    "Closed At (UTC)",
    "Due Date",
    "Start Date",
    "Parent ID",
    "Parent IID",
    "Parent Title",
    "Time Estimate",
    "Time Spent",
    "Weight",
)

ASSESSMENT_SCENARIO_HEADERS = (
    "assessment_id",
    "assessment_name",
    "scenario_id",
    "scenario_name",
    "scenario_technique",
    "scenario_supported_platforms",
    "scenario_capabilities",
)

ISSUE_SCENARIO_HEADERS = (
    "issue_id",
    "issue_iid",
    "issue_title",
    "issue_url",
    "issue_state",
    "issue_created_at_utc",
    "issue_updated_at_utc",
    "scenario_id",
    "scenario_name",
    "scenario_technique",
    "issue_technique_token",
    "labels_raw",
    "issue_techniques",
    "issue_tactics",
    "issue_detection_strategy_ids",
    "issue_tools",
    "issue_csf",
)

ASSESSMENT_SCENARIO_ISSUE_HEADERS = (
    "assessment_id",
    "assessment_name",
    "scenario_id",
    "scenario_name",
    "scenario_technique",
    "scenario_supported_platforms",
    "scenario_capabilities",
    "issue_id",
    "issue_iid",
    "issue_title",
    "issue_url",
    "issue_state",
    "issue_created_at_utc",
    "issue_updated_at_utc",
    "issue_technique_token",
    "labels_raw",
    "issue_techniques",
    "issue_tactics",
    "issue_detection_strategy_ids",
    "issue_tools",
    "issue_csf",
)

ISSUES_UNMAPPED_HEADERS = (
    "issue_id",
    "issue_iid",
    "issue_title",
    "issue_url",
    "issue_state",
    "reason",
    "labels_raw",
    "issue_techniques",
)

ISSUE_FIELD_MAP = {
    "issue_id": "ID",
    "issue_iid": "IID",
    "issue_title": "Title",
    "issue_url": "URL",
    "issue_state": "State",
    "created_at_utc": "Created At (UTC)",
    "updated_at_utc": "Updated At (UTC)",
    "labels_raw": "Labels",
}

ISSUE_LIST_FIELDS = (
    "issue_techniques",
    "issue_tactics",
    "issue_detection_strategy_ids",
    "issue_tools",
    "issue_csf",
)

