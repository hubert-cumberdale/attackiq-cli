from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from attackiq_cli.client import AttackIQClient, AuthContext, paginate_results
from attackiq_cli.config import (
    ConfigError,
    effective_account_token,
    effective_base_url,
    effective_jwt,
    load_config,
)
from attackiq_cli.logging_utils import setup_logging
from attackiq_cli.spec import SpecIndex


DEFAULT_SPEC_PATH = Path(__file__).resolve().parent.parent / "src" / "attackiq_cli" / "openapi.yaml"
MITRE_TAG_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$", re.IGNORECASE)


def main(output: Path, page_size: int = 200) -> None:
    try:
        cfg = load_config()
        base_url = effective_base_url(cfg)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    if not base_url:
        raise SystemExit("Base URL not configured. Run `attackiq config set --base-url https://...` first.")

    logger = setup_logging(cfg.log_level, cfg.log_json)
    auth = AuthContext(
        account_token=effective_account_token(cfg),
        jwt=effective_jwt(cfg),
        preferred_scheme="auto",
    )
    with AttackIQClient(
        base_url=base_url,
        auth=auth,
        verify_tls=cfg.verify_tls,
        timeout=cfg.timeout,
        logger=logger,
    ) as client:
        index = SpecIndex.from_file(DEFAULT_SPEC_PATH)
        scenarios_op = index.get_operation("v1_scenarios_list")
        scenario_tags_op = index.get_operation("v1_scenario_tags_list")
        tags_op = index.get_operation("v1_tags_list")

        tag_lookup = load_tags(client, tags_op, page_size)
        scenario_tag_index = load_scenario_tags(client, scenario_tags_op, page_size)
        rows = build_rows(
            client,
            scenarios_op,
            scenario_tag_index,
            tag_lookup,
            page_size,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["scenario_id", "scenario_name", "scenario_type", "technique", "subtechnique", "tag_display_name"]
        )
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output}")


def load_tags(client: AttackIQClient, op, page_size: int) -> Dict[str, Tuple[str, str]]:
    """Return tag_id -> (name, display_name)."""
    tags: Dict[str, Tuple[str, str]] = {}
    for tag in paginate(client, op, page_size):
        tag_id = tag.get("id")
        name = tag.get("name") or ""
        display_name = tag.get("display_name") or name
        if tag_id:
            tags[tag_id] = (name, display_name)
    return tags


def load_scenario_tags(client: AttackIQClient, op, page_size: int) -> Dict[str, List[str]]:
    """Return scenario_id -> list[tag_id]."""
    index: Dict[str, List[str]] = {}
    for row in paginate(client, op, page_size):
        scenario_id = row.get("scenario")
        tag_id = row.get("tag")
        if not scenario_id or not tag_id:
            continue
        index.setdefault(scenario_id, []).append(tag_id)
    return index


def build_rows(
    client: AttackIQClient,
    scenarios_op,
    scenario_tag_index: Dict[str, List[str]],
    tag_lookup: Dict[str, Tuple[str, str]],
    page_size: int,
) -> List[List[str]]:
    rows: List[List[str]] = []
    for scenario in paginate(client, scenarios_op, page_size):
        scenario_id = scenario.get("id") or ""
        name = scenario.get("name") or ""
        scenario_type = scenario.get("scenario_type") or ""
        tag_ids = scenario_tag_index.get(scenario_id, [])
        matched_tags = [tag_lookup[tid] for tid in tag_ids if tid in tag_lookup]
        for tag_name, tag_display in matched_tags:
            if not MITRE_TAG_RE.match(tag_name):
                continue
            technique, subtechnique = split_ttp(tag_name)
            rows.append([scenario_id, name, scenario_type, technique, subtechnique, tag_display])
    return rows


def split_ttp(tag: str) -> Tuple[str, str]:
    """Return (technique, subtechnique)."""
    tag_upper = tag.upper()
    if "." in tag_upper:
        technique, subtechnique = tag_upper.split(".", 1)
        return technique, subtechnique
    return tag_upper, ""


def paginate(client: AttackIQClient, op, page_size: int) -> Iterable[dict]:
    yield from paginate_results(client, op, page_size=page_size)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export AttackIQ scenarios mapped to MITRE tags.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("scenarios_mitre.csv"),
        help="Destination CSV file.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="Page size for API pagination.",
    )
    args = parser.parse_args()
    main(output=args.output, page_size=args.page_size)
