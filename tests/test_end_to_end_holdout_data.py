from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "eval" / "end_to_end_holdout_20_v1.jsonl"


def load_records() -> list[dict]:
    with HOLDOUT.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def test_end_to_end_holdout_v1_schema_and_balance() -> None:
    records = load_records()

    assert len(records) == 20
    assert len({item["query_id"] for item in records}) == 20
    assert len({item["query"] for item in records}) == 20

    assert Counter(item["gold_query_type"] for item in records) == Counter(
        {"catalog": 5, "concept": 5, "mixed": 5, "safety": 5}
    )

    for item in records:
        assert item["gold_tools"][0] == "safety_check"
        assert item["expected_behavior"]
        assert isinstance(item["forbidden_behavior"], list)
