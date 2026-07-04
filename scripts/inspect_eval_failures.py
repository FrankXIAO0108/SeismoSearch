"""
Inspect failed records from a SeismoSearch evaluation result file.

Usage:

python scripts/inspect_eval_failures.py --result-file eval/results/eval_20_results.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON result file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def is_failed_record(record: dict[str, Any]) -> bool:
    """
    Decide whether one eval record has any failed check.

    A check is considered passing if it is True or None.
    None means the metric is not applicable to that sample.
    """
    checks = record.get("checks", {})

    for value in checks.values():
        if value is not True and value is not None:
            return True

    return False


def print_failed_record(record: dict[str, Any]) -> None:
    """Print one failed eval record in a readable format."""
    print("=" * 80)
    print(f"query_id: {record.get('query_id')}")
    print(f"query: {record.get('query')}")
    print(f"gold_query_type: {record.get('gold_query_type')}")
    print(f"pred_query_type: {record.get('pred_query_type')}")
    print(f"gold_tools: {record.get('gold_tools')}")
    print(f"actual_tools: {record.get('actual_tools')}")
    print("checks:")

    checks = record.get("checks", {})

    for key, value in checks.items():
        print(f"  - {key}: {value}")

    print("warnings:")

    warnings = record.get("warnings", [])

    if not warnings:
        print("  - 无")
    else:
        for warning in warnings:
            print(f"  - {warning}")

    print("answer:")
    print(record.get("answer", ""))


def main() -> None:
    """Inspect failed records from a result file."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--result-file",
        type=Path,
        default=Path("eval/results/eval_20_results.json"),
        help="Path to an evaluation result JSON file.",
    )

    args = parser.parse_args()

    data = load_json(args.result_file)
    records = data.get("records", [])

    failed_records = [
        record for record in records
        if is_failed_record(record)
    ]

    print("Evaluation summary:")
    print(json.dumps(data.get("summary", {}), ensure_ascii=False, indent=2))
    print()

    if not failed_records:
        print("No failed records found.")
        return

    print(f"Failed records: {len(failed_records)}")
    print()

    for record in failed_records:
        print_failed_record(record)


if __name__ == "__main__":
    main()