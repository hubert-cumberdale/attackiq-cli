from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from attackiq_cli.service_core import (
    ServiceContext,
    _optional_nested_text,
    _optional_text,
    build_client,
    ensure_auth,
)


@dataclass(frozen=True)
class AssessmentScheduleSummary:
    project_id: str | None
    project_name: str | None
    project_template_name: str | None
    schedule_version: str | None
    schedule_present: str | None
    crontab_minute: str | None
    crontab_hour: str | None
    crontab_day_of_week: str | None
    crontab_day_of_month: str | None
    crontab_month_of_year: str | None
    crontab_timezone: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AssessmentScheduleSummary:
        project = payload.get("project")
        schedule = payload.get("schedule")
        crontab = schedule.get("crontab") if isinstance(schedule, dict) else None
        crontab_present = isinstance(crontab, dict)

        return cls(
            project_id=_optional_nested_text(project, "id")
            or _optional_nested_text(project, "uuid"),
            project_name=_optional_nested_text(project, "name"),
            project_template_name=_optional_nested_text(project, "project_template_name"),
            schedule_version=_optional_nested_text(schedule, "schedule_version"),
            schedule_present=_optional_text(crontab_present),
            crontab_minute=_optional_nested_text(crontab, "minute"),
            crontab_hour=_optional_nested_text(crontab, "hour"),
            crontab_day_of_week=_optional_nested_text(crontab, "day_of_week"),
            crontab_day_of_month=_optional_nested_text(crontab, "day_of_month"),
            crontab_month_of_year=_optional_nested_text(crontab, "month_of_year"),
            crontab_timezone=_optional_nested_text(crontab, "timezone"),
        )

    def to_record(self) -> dict[str, str | None]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_template_name": self.project_template_name,
            "schedule_version": self.schedule_version,
            "schedule_present": self.schedule_present,
            "crontab_minute": self.crontab_minute,
            "crontab_hour": self.crontab_hour,
            "crontab_day_of_week": self.crontab_day_of_week,
            "crontab_day_of_month": self.crontab_day_of_month,
            "crontab_month_of_year": self.crontab_month_of_year,
            "crontab_timezone": self.crontab_timezone,
        }


def build_assessment_schedule_summary_records(
    items: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    return [AssessmentScheduleSummary.from_payload(item).to_record() for item in items]


def list_assessment_schedules(
    context: ServiceContext,
    *,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("get_project_schedule_list")
    if check_auth:
        ensure_auth(op, context.auth)

    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        payload = client.send(
            op,
            path_params={},
            query_params={},
            headers={},
        ).json()

    if not isinstance(payload, list):
        raise ValueError("Assessment schedule list response must be a list.")
    if not all(isinstance(item, dict) for item in payload):
        raise ValueError("Assessment schedule list response items must be objects.")
    return cast(list[dict[str, Any]], list(payload))
