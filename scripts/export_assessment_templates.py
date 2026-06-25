from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from attackiq_cli.client import AttackIQClient, AuthContext, fetch_by_ids, paginate_results
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
FORMAT_CHOICES = {"csv", "json"}


def main(
    output: Path,
    file_format: str | None,
    page_size: int = 200,
    include_empty: bool = False,
    include_scenario_details: bool = False,
    scenario_details_lenient: bool = False,
    scenario_details_retries: int = 0,
    scenario_concurrency: int = 4,
) -> None:
    fmt = resolve_format(output, file_format)

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
        templates_op = index.get_operation("v1_assessment_templates_list")
        template_tests_op = index.get_operation("v1_project_template_tests_list")
        scenario_retrieve_op = index.get_operation("v1_scenarios_retrieve")

        template_tests_index = load_template_tests_index(client, template_tests_op, page_size)
        templates, scenario_ids = build_template_records(
            client,
            templates_op,
            template_tests_index,
            page_size,
        )
        if include_scenario_details and scenario_ids:
            if scenario_details_lenient:
                scenario_lookup, failures = load_scenario_details_lenient(
                    client,
                    scenario_retrieve_op,
                    scenario_ids,
                    max_workers=scenario_concurrency,
                    retries=scenario_details_retries,
                )
                apply_scenario_details(templates, scenario_lookup)
                if failures:
                    print(f"Scenario detail lookup failed for {len(failures)} IDs.")
            else:
                scenario_lookup = load_scenario_details(
                    client,
                    scenario_retrieve_op,
                    scenario_ids,
                    max_workers=scenario_concurrency,
                )
                apply_scenario_details(templates, scenario_lookup)

    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        write_json(output, templates)
    else:
        write_csv(output, templates, include_empty=include_empty)

    print(f"Wrote {len(templates)} templates to {output} ({fmt}).")


def resolve_format(output: Path, file_format: str | None) -> str:
    if file_format:
        fmt = file_format.lower()
        if fmt not in FORMAT_CHOICES:
            raise SystemExit(f"Unsupported format '{file_format}'. Use csv or json.")
        return fmt
    suffix = output.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".csv":
        return "csv"
    return "csv"


def load_scenario_details(
    client: AttackIQClient,
    op,
    scenario_ids: Iterable[str],
    max_workers: int = 4,
) -> Dict[str, Tuple[str, str]]:
    """Return scenario_id -> (scenario_name, scenario_type)."""
    lookup: Dict[str, Tuple[str, str]] = {}
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    responses = fetch_by_ids(client, op, scenario_ids, max_workers=max_workers)
    for scenario_id, scenario in responses.items():
        name = scenario.get("name") or ""
        scenario_type = scenario.get("scenario_type") or ""
        lookup[scenario_id] = (name, scenario_type)
    return lookup


def load_scenario_details_lenient(
    client: AttackIQClient,
    op,
    scenario_ids: Iterable[str],
    *,
    max_workers: int = 4,
    retries: int = 0,
) -> Tuple[Dict[str, Tuple[str, str]], List[str]]:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    id_list = [item for item in scenario_ids if item]
    if not id_list:
        return {}, []

    import concurrent.futures

    def fetch_one(item_id: str) -> Tuple[str, dict[str, Any] | None]:
        last_exc: Exception | None = None
        for _ in range(retries + 1):
            try:
                payload = client.send(op, path_params={"id": item_id}).json()
                return item_id, payload
            except Exception as exc:
                last_exc = exc
        if last_exc:
            return item_id, None
        return item_id, None

    results: Dict[str, Tuple[str, str]] = {}
    failures: List[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, item_id): item_id for item_id in id_list}
        for future in concurrent.futures.as_completed(futures):
            item_id = futures[future]
            fetched_id, payload = future.result()
            if not isinstance(payload, dict):
                failures.append(item_id)
                continue
            results[fetched_id] = (
                payload.get("name") or "",
                payload.get("scenario_type") or "",
            )
    return results, failures


def build_template_records(
    client: AttackIQClient,
    templates_op,
    template_tests_index: Dict[str, List[dict[str, Any]]],
    page_size: int,
) -> Tuple[List[dict[str, Any]], set[str]]:
    templates: List[dict[str, Any]] = []
    scenario_ids: set[str] = set()
    for template in paginate(client, templates_op, page_size, extra_query=None):
        template_id = template.get("id") or ""
        template_name = template.get("template_name") or ""
        project_name = template.get("project_name") or ""
        template_type = template.get("project_template_type") or {}
        template_type_payload = {
            "id": template_type.get("id") if isinstance(template_type, dict) else "",
            "name": template_type.get("name") if isinstance(template_type, dict) else "",
            "description": template_type.get("description") if isinstance(template_type, dict) else "",
        }
        scenarios = load_template_scenarios(template_tests_index, template_id)
        for scenario in scenarios:
            scenario_id = scenario.get("scenario_id")
            if scenario_id:
                scenario_ids.add(scenario_id)
        templates.append(
            {
                "template_id": template_id,
                "template_name": template_name,
                "project_name": project_name,
                "template_type": template_type_payload,
                "scenarios": scenarios,
            }
        )
    return templates, scenario_ids


def load_template_tests_index(
    client: AttackIQClient,
    op,
    page_size: int,
) -> Dict[str, List[dict[str, Any]]]:
    index: Dict[str, List[dict[str, Any]]] = {}
    for test in paginate(client, op, page_size, extra_query=None):
        template_id = test.get("project_template") or ""
        if not template_id:
            continue
        index.setdefault(template_id, []).append(test)
    return index


def load_template_scenarios(
    template_tests_index: Dict[str, List[dict[str, Any]]],
    template_id: str,
) -> List[dict[str, str]]:
    scenarios: List[dict[str, str]] = []
    if not template_id:
        return scenarios
    for test in template_tests_index.get(template_id, []):
        test_id = test.get("id") or ""
        test_name = test.get("name") or ""
        for scenario_id in test.get("scenarios") or []:
            scenarios.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_name": "",
                    "scenario_type": "",
                    "test_id": test_id,
                    "test_name": test_name,
                }
            )
    return scenarios


def apply_scenario_details(
    templates: List[dict[str, Any]],
    scenario_lookup: Dict[str, Tuple[str, str]],
) -> None:
    for template in templates:
        for scenario in template.get("scenarios") or []:
            scenario_id = scenario.get("scenario_id")
            if not scenario_id:
                continue
            name, scenario_type = scenario_lookup.get(scenario_id, ("", ""))
            scenario["scenario_name"] = name
            scenario["scenario_type"] = scenario_type


def write_json(output: Path, templates: List[dict[str, Any]]) -> None:
    with output.open("w", encoding="utf-8") as handle:
        json.dump(templates, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_csv(output: Path, templates: List[dict[str, Any]], include_empty: bool) -> None:
    rows = flatten_templates(templates, include_empty=include_empty)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "template_id",
                "template_name",
                "project_name",
                "template_type_id",
                "template_type_name",
                "scenario_id",
                "scenario_name",
                "scenario_type",
                "test_id",
                "test_name",
            ]
        )
        writer.writerows(rows)


def flatten_templates(templates: List[dict[str, Any]], include_empty: bool) -> List[List[str]]:
    rows: List[List[str]] = []
    for template in templates:
        template_type = template.get("template_type") or {}
        template_row_prefix = [
            template.get("template_id", ""),
            template.get("template_name", ""),
            template.get("project_name", ""),
            template_type.get("id", "") if isinstance(template_type, dict) else "",
            template_type.get("name", "") if isinstance(template_type, dict) else "",
        ]
        scenarios = template.get("scenarios") or []
        if not scenarios and include_empty:
            rows.append(template_row_prefix + ["", "", "", "", ""])
            continue
        for scenario in scenarios:
            rows.append(
                template_row_prefix
                + [
                    scenario.get("scenario_id", ""),
                    scenario.get("scenario_name", ""),
                    scenario.get("scenario_type", ""),
                    scenario.get("test_id", ""),
                    scenario.get("test_name", ""),
                ]
            )
    return rows


def paginate(
    client: AttackIQClient,
    op,
    page_size: int,
    extra_query: dict[str, Any] | None,
) -> Iterable[dict]:
    yield from paginate_results(
        client,
        op,
        page_size=page_size,
        query_params=extra_query,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Export assessment templates and their scenarios to CSV or JSON."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("assessment_templates.csv"),
        help="Destination file (.csv or .json).",
    )
    parser.add_argument(
        "--format",
        choices=sorted(FORMAT_CHOICES),
        help="Output format. Defaults to file extension or csv.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="Page size for API pagination.",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Include templates with no scenarios (CSV only).",
    )
    parser.add_argument(
        "--scenario-details",
        action="store_true",
        help="Fetch scenario names/types via per-ID lookups (slower).",
    )
    parser.add_argument(
        "--scenario-details-lenient",
        action="store_true",
        help="Continue if individual scenario lookups fail.",
    )
    parser.add_argument(
        "--scenario-details-retries",
        type=int,
        default=0,
        help="Retry attempts per scenario ID when --scenario-details-lenient is set.",
    )
    parser.add_argument(
        "--scenario-concurrency",
        type=int,
        default=4,
        help="Max concurrent per-ID scenario lookups when --scenario-details is set.",
    )
    args = parser.parse_args()
    main(
        output=args.output,
        file_format=args.format,
        page_size=args.page_size,
        include_empty=args.include_empty,
        include_scenario_details=args.scenario_details,
        scenario_details_lenient=args.scenario_details_lenient,
        scenario_details_retries=args.scenario_details_retries,
        scenario_concurrency=args.scenario_concurrency,
    )
