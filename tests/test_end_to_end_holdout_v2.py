"""
Structural and immutability checks for End-to-End Holdout V2.

These tests validate the frozen dataset contract only. They deliberately do
not call the planner, retriever, generator, or evaluation runner.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / "eval" / "end_to_end_holdout_20_v1.jsonl"
V2_PATH = ROOT / "eval" / "end_to_end_holdout_20_v2.jsonl"
MANIFEST_PATH = (
    ROOT
    / "eval"
    / "end_to_end_holdout_20_v2_manifest.json"
)
EXPECTED_CATEGORIES = {
    "catalog": 5,
    "concept": 5,
    "mixed": 5,
    "safety": 5,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load one UTF-8 JSONL file."""
    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(
            file,
            start=1,
        ):
            normalized = line.strip()

            if not normalized:
                continue

            value = json.loads(normalized)

            if not isinstance(value, dict):
                raise AssertionError(
                    f"line {line_number} is not an object"
                )

            records.append(value)

    return records


def test_v2_has_twenty_unique_balanced_samples() -> None:
    """V2 must contain 20 unique samples balanced across four categories."""
    records = load_jsonl(V2_PATH)

    assert len(records) == 20

    query_ids = [
        str(record["query_id"])
        for record in records
    ]
    queries = [
        str(record["query"])
        for record in records
    ]

    assert len(set(query_ids)) == 20
    assert len(set(queries)) == 20
    assert all(
        query_id.startswith("e2e_v2_")
        for query_id in query_ids
    )

    category_counts = Counter(
        str(record["category"])
        for record in records
    )

    assert dict(category_counts) == (
        EXPECTED_CATEGORIES
    )


def test_v2_gold_contract_shape() -> None:
    """Each category must expose the expected gold fields."""
    records = load_jsonl(V2_PATH)

    expected_tools = {
        "catalog": [
            "safety_check",
            "event_search",
            "event_statistics",
        ],
        "concept": [
            "safety_check",
            "doc_retrieval",
        ],
        "mixed": [
            "safety_check",
            "event_search",
            "event_statistics",
            "doc_retrieval",
        ],
        "safety": [
            "safety_check",
        ],
    }

    for record in records:
        category = str(record["category"])

        assert record["gold_query_type"] == category
        assert record["gold_tools"] == (
            expected_tools[category]
        )
        assert isinstance(record["query"], str)
        assert record["query"].strip()
        assert isinstance(
            record["forbidden_behavior"],
            list,
        )

        if category == "catalog":
            assert record["gold_event_required"] is True
            assert record["gold_doc_required"] is False

        elif category == "concept":
            assert record["gold_event_required"] is False
            assert record["gold_doc_required"] is True
            assert isinstance(
                record["gold_doc_requirements"],
                dict,
            )

        elif category == "mixed":
            assert record["gold_event_required"] is True
            assert record["gold_doc_required"] is True
            assert isinstance(
                record["gold_event_constraints"],
                dict,
            )
            assert isinstance(
                record["gold_doc_requirements"],
                dict,
            )

        else:
            assert record["gold_event_required"] is False
            assert record["gold_doc_required"] is False
            assert record[
                "gold_safety_constraints"
            ][
                "must_not_predict_future_earthquakes"
            ] is True


def test_v2_queries_are_exactly_disjoint_from_v1() -> None:
    """No V2 query string may duplicate a V1 query string."""
    v1_queries = {
        str(record["query"]).strip()
        for record in load_jsonl(V1_PATH)
    }
    v2_queries = {
        str(record["query"]).strip()
        for record in load_jsonl(V2_PATH)
    }

    assert v1_queries.isdisjoint(v2_queries)


def test_v2_manifest_matches_dataset_bytes() -> None:
    """Manifest count, categories, and SHA-256 must match V2 exactly."""
    records = load_jsonl(V2_PATH)
    manifest = json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )
    digest = hashlib.sha256(
        V2_PATH.read_bytes()
    ).hexdigest()

    assert manifest["frozen"] is True
    assert manifest["version"] == "2.0.0"
    assert manifest["num_samples"] == len(records)
    assert manifest["category_counts"] == (
        EXPECTED_CATEGORIES
    )
    assert manifest["sha256"] == digest
    assert (
        manifest["evaluation_contract_version"]
        == "2.0.0"
    )


def test_all_declared_gold_sources_exist() -> None:
    """Every expected source filename must exist in the runtime corpus."""
    records = load_jsonl(V2_PATH)
    doc_root = (
        ROOT
        / "data"
        / "processed"
        / "docs"
    )

    expected_sources = {
        record["gold_doc_requirements"][
            "expected_source_path_contains"
        ]
        for record in records
        if record.get("gold_doc_required") is True
    }

    missing = [
        source_name
        for source_name in sorted(expected_sources)
        if not (doc_root / source_name).exists()
    ]

    assert missing == []
