"""Parse GitLab issue labels for joiner semantics."""

from __future__ import annotations

import re
from dataclasses import dataclass

from attackiq_cli.joiner.normalize import stable_unique

TECHNIQUE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")
TACTIC_RE = re.compile(r"^TA\d{4}$")
DETECTION_STRATEGY_RE = re.compile(r"^DET\d{4}$")
TOOL_RE = re.compile(r"^tool::.+$")
CSF_RE = re.compile(r"^[A-Z]{2}\.[A-Z]{2}$")


@dataclass(frozen=True)
class LabelParseResult:
    techniques: list[str]
    tactics: list[str]
    detection_strategy_ids: list[str]
    tools: list[str]
    csf: list[str]


def split_labels(labels_raw: str, delimiter: str) -> list[str]:
    if not labels_raw:
        return []
    return [label.strip() for label in labels_raw.split(delimiter) if label.strip()]


def parse_labels(labels_raw: str, delimiter: str = ", ") -> LabelParseResult:
    techniques: list[str] = []
    tactics: list[str] = []
    detection_strategy_ids: list[str] = []
    tools: list[str] = []
    csf: list[str] = []

    for token in split_labels(labels_raw, delimiter):
        if TECHNIQUE_RE.match(token):
            techniques.append(token)
        elif TACTIC_RE.match(token):
            tactics.append(token)
        elif DETECTION_STRATEGY_RE.match(token):
            detection_strategy_ids.append(token)
        elif TOOL_RE.match(token):
            tools.append(token)
        elif CSF_RE.match(token):
            csf.append(token)

    return LabelParseResult(
        techniques=stable_unique(techniques),
        tactics=stable_unique(tactics),
        detection_strategy_ids=stable_unique(detection_strategy_ids),
        tools=stable_unique(tools),
        csf=stable_unique(csf),
    )

