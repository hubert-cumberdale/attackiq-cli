from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        event = getattr(record, "event", None)
        if event:
            payload["event"] = event
        fields = getattr(record, "fields", None)
        if fields:
            payload["fields"] = fields
        return json.dumps(payload)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname}: {record.getMessage()}"
        event = getattr(record, "event", None)
        fields = getattr(record, "fields", None)
        if event and fields:
            return f"{base} {event} {fields}"
        if event:
            return f"{base} {event}"
        return base


def setup_logging(level: str, json_output: bool) -> logging.Logger:
    logger = logging.getLogger("attackiq-cli")
    logger.setLevel(level)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter() if json_output else TextFormatter())
    logger.handlers = [handler]
    return logger
