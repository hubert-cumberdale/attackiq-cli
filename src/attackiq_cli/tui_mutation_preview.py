from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from attackiq_cli.mutation_plans import MutationCallPlan

REQUEST_NOT_SENT_STATUS = "No request sent"
REDACTED_VALUE = "[REDACTED]"
MAX_PREVIEW_LIST_ITEMS = 20
MAX_PREVIEW_STRING_LENGTH = 200

SUPPORTED_TUI_PREVIEW_OPERATION_IDS = frozenset(
    {
        "det_pipeline_create_assessment",
        "v1_assessments_project_from_template_create",
        "v1_assessments_update_defaults_create",
        "v1_assessments_run_all_create",
        "v1_tests_create",
        "v1_tests_bulk_add_scenarios_create",
        "v1_tests_get_status_retrieve",
    }
)

_SENSITIVE_KEY_RE = re.compile(
    r"(authorization|api[_-]?key|bearer|cookie|credential|jwt|password|secret|token)",
    re.IGNORECASE,
)
_TOKEN_VALUE_RE = re.compile(r"^(bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{8,}$", re.IGNORECASE)
_JWT_VALUE_RE = re.compile(r"^[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}$")
_URL_VALUE_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


@dataclass(frozen=True)
class TuiMutationPreview:
    operation_id: str
    method: str
    path: str
    path_params: dict[str, Any]
    query_params: dict[str, Any]
    json_body_summary: Any | None
    request_status: str = REQUEST_NOT_SENT_STATUS

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "operation_id": self.operation_id,
            "method": self.method,
            "path": self.path,
            "path_params": self.path_params,
            "query_params": self.query_params,
            "request_status": self.request_status,
        }
        if self.json_body_summary is not None:
            payload["json_body_summary"] = self.json_body_summary
        return payload


def build_tui_mutation_preview(plan: MutationCallPlan) -> TuiMutationPreview:
    operation_id = plan.operation.operation_id
    if operation_id not in SUPPORTED_TUI_PREVIEW_OPERATION_IDS:
        raise ValueError(f"Unsupported TUI mutation preview operation: {operation_id}")
    return TuiMutationPreview(
        operation_id=operation_id,
        method=plan.operation.method.upper(),
        path=plan.operation.path,
        path_params=_summarize_preview_value(plan.path_params),
        query_params=_summarize_preview_value(plan.query_params),
        json_body_summary=(
            _summarize_preview_value(plan.json_body) if plan.json_body is not None else None
        ),
    )


def _summarize_preview_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY_RE.search(key):
        return REDACTED_VALUE
    if isinstance(value, dict):
        return {
            str(item_key): _summarize_preview_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        summarized = [_summarize_preview_value(item) for item in value[:MAX_PREVIEW_LIST_ITEMS]]
        remaining = len(value) - len(summarized)
        if remaining > 0:
            summarized.append(f"<{remaining} more items>")
        return summarized
    if isinstance(value, str):
        stripped = value.strip()
        if _TOKEN_VALUE_RE.match(stripped) or _JWT_VALUE_RE.match(stripped):
            return REDACTED_VALUE
        if _URL_VALUE_RE.search(stripped):
            return REDACTED_VALUE
        if len(value) > MAX_PREVIEW_STRING_LENGTH:
            return f"{value[:MAX_PREVIEW_STRING_LENGTH - 3]}..."
    return value
