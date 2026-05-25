from __future__ import annotations

import logging
from typing import Any

SENSITIVE_KEYS = {"authorization", "token", "jwt", "secret", "password"}


def redact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        key_lower = key.lower()
        if key_lower in SENSITIVE_KEYS or "token" in key_lower or "jwt" in key_lower:
            safe[key] = "***"
        else:
            safe[key] = value
    return safe


def log_event(
    logger: logging.Logger,
    *,
    level: int,
    event: str,
    fields: dict[str, Any],
) -> None:
    logger.log(
        level,
        event,
        extra={
            "event": event,
            "fields": redact_fields(fields),
        },
    )


# Example usage:
# log_event(logger, level=logging.INFO, event="export.started", fields={"count": 10})
