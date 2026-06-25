from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from attackiq_cli.client import paginate_results
from attackiq_cli.service_core import (
    ServiceContext,
    _normalize_filter,
    _optional_text,
    build_client,
    ensure_auth,
)

EDR_SCAN_SCHEDULE_TYPES = {"DAILY", "ONE_SHOT", "WEEKLY"}


@dataclass(frozen=True)
class EdrScanScheduleFilters:
    data_source: str | None = None
    enabled: bool | None = None
    schedule_type: str | None = None
    targeted: bool | None = None


@dataclass(frozen=True)
class EdrScanScheduleSummary:
    schedule_id: str | None
    name: str | None
    data_source_id: str | None
    data_source: str | None
    schedule_type: str | None
    fire_at: str | None
    time_of_day: str | None
    days_of_week: Any | None
    day_of_week: str | None
    week_interval: str | None
    enabled: str | None
    targeted: str | None
    target_asset_count: str | None
    last_fired_at: str | None
    created: str | None
    modified: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> EdrScanScheduleSummary:
        target_asset_ids = payload.get("target_asset_ids", _MISSING)
        targeted = (
            None if target_asset_ids is _MISSING else target_asset_ids is not None
        )

        return cls(
            schedule_id=_optional_text(payload.get("id")),
            name=_optional_text(payload.get("name")),
            data_source_id=_optional_text(payload.get("data_source_id")),
            data_source=_optional_text(payload.get("data_source")),
            schedule_type=_optional_text(payload.get("schedule_type")),
            fire_at=_optional_text(payload.get("fire_at")),
            time_of_day=_optional_text(payload.get("time_of_day")),
            days_of_week=payload.get("days_of_week"),
            day_of_week=_optional_text(payload.get("day_of_week")),
            week_interval=_optional_text(payload.get("week_interval")),
            enabled=_optional_text(payload.get("enabled")),
            targeted=_optional_text(targeted),
            target_asset_count=_target_asset_count(target_asset_ids),
            last_fired_at=_optional_text(payload.get("last_fired_at")),
            created=_optional_text(payload.get("created")),
            modified=_optional_text(payload.get("modified")),
        )

    def to_record(self) -> dict[str, Any | None]:
        return {
            "id": self.schedule_id,
            "name": self.name,
            "data_source_id": self.data_source_id,
            "data_source": self.data_source,
            "schedule_type": self.schedule_type,
            "fire_at": self.fire_at,
            "time_of_day": self.time_of_day,
            "days_of_week": self.days_of_week,
            "day_of_week": self.day_of_week,
            "week_interval": self.week_interval,
            "enabled": self.enabled,
            "targeted": self.targeted,
            "target_asset_count": self.target_asset_count,
            "last_fired_at": self.last_fired_at,
            "created": self.created,
            "modified": self.modified,
        }


_MISSING = object()


def build_edr_scan_schedule_query_params(
    filters: EdrScanScheduleFilters,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if (data_source := _normalize_filter(filters.data_source)) is not None:
        params["data_source"] = data_source
    if filters.enabled is not None:
        params["enabled"] = filters.enabled
    if (schedule_type := _normalize_filter(filters.schedule_type)) is not None:
        normalized_schedule_type = schedule_type.upper()
        if normalized_schedule_type not in EDR_SCAN_SCHEDULE_TYPES:
            raise ValueError("schedule-type must be one of: DAILY, ONE_SHOT, WEEKLY.")
        params["schedule_type"] = normalized_schedule_type
    if filters.targeted is not None:
        params["targeted"] = filters.targeted
    return params


def build_edr_scan_schedule_summary_records(
    items: list[dict[str, Any]],
) -> list[dict[str, Any | None]]:
    return [EdrScanScheduleSummary.from_payload(item).to_record() for item in items]


def list_edr_scan_schedules(
    context: ServiceContext,
    *,
    page: int | None,
    page_size: int,
    filters: EdrScanScheduleFilters,
    insecure: bool,
    timeout: float | None,
    check_auth: bool = True,
) -> list[dict[str, Any]]:
    op = context.spec.get_operation("v1_emm_edr_scan_schedules_list")
    if check_auth:
        ensure_auth(op, context.auth)
    query_params = build_edr_scan_schedule_query_params(filters)
    with build_client(
        context.base_url,
        context.config,
        context.auth,
        insecure=insecure,
        timeout=timeout,
    ) as client:
        if page is None:
            return list(
                paginate_results(
                    client,
                    op,
                    page_size=page_size,
                    query_params=query_params or None,
                )
            )
        payload = client.send(
            op,
            path_params={},
            query_params={"page": page, "page_size": page_size, **(query_params or {})},
            headers={},
        ).json()
    if not isinstance(payload, dict):
        raise ValueError("EDR scan schedule list response must be an object.")
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("EDR scan schedule list response results must be a list.")
    return list(items)


def _target_asset_count(value: Any) -> str | None:
    if value is _MISSING or value is None:
        return None
    if isinstance(value, dict | list | tuple | set):
        return str(len(value))
    return None
