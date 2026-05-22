from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


FORMULA_PREFIXES = ("=", "+", "-", "@")


def main(inputs: Sequence[Path], output: Path, list_sep: str) -> None:
    rows: List[Tuple[str, str, str, str, str, str]] = []
    for input_path in inputs:
        rows.extend(parse_rule_file(input_path, list_sep))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "description", "query", "tactics", "techniques", "subtechniques"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output}")


def parse_rule_file(path: Path, list_sep: str) -> List[Tuple[str, str, str, str, str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    resources = extract_resources(data)
    rows: List[Tuple[str, str, str, str, str, str]] = []
    for resource in resources:
        props = resource.get("properties")
        if not isinstance(props, dict):
            continue
        name = props.get("displayName") or props.get("name") or resource.get("name") or ""
        description = props.get("description") or ""
        query = props.get("query") or ""
        tactics = normalize_list(props.get("tactics"), list_sep)
        techniques = normalize_list(props.get("techniques"), list_sep)
        subtechniques = normalize_list(
            props.get("subTechniques") or props.get("subtechniques"),
            list_sep,
        )
        rows.append(
            (
                sanitize_cell(str(name)),
                sanitize_cell(str(description)),
                sanitize_cell(str(query)),
                sanitize_cell(tactics),
                sanitize_cell(techniques),
                sanitize_cell(subtechniques),
            )
        )
    return rows


def extract_resources(data: object) -> Iterable[dict]:
    if isinstance(data, dict):
        if isinstance(data.get("resources"), list):
            return [item for item in data["resources"] if isinstance(item, dict)]
        if isinstance(data.get("value"), list):
            return [item for item in data["value"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def normalize_list(value: object, list_sep: str) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return list_sep.join(str(item) for item in value if item is not None)
    return str(value)


def sanitize_cell(value: str) -> str:
    if value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Azure Sentinel analytics rule exports to CSV.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="One or more JSON exports to convert.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("azure_sentinel_rules.csv"),
        help="Destination CSV file.",
    )
    parser.add_argument(
        "--list-sep",
        default=";",
        help="Separator used when joining tactics/techniques lists.",
    )
    return parser.parse_args()


def validate_inputs(paths: Sequence[Path]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        missing_list = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(f"Input file(s) not found:\n{missing_list}")


if __name__ == "__main__":
    args = parse_args()
    validate_inputs(args.inputs)
    main(args.inputs, args.output, args.list_sep)
