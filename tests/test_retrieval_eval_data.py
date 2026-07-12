"""Validate versioned retrieval development and holdout datasets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_PATH = PROJECT_ROOT / "eval" / "retrieval_eval_60_corpus_v2.jsonl"
HOLDOUT_PATH = PROJECT_ROOT / "eval" / "retrieval_holdout_26_v1.jsonl"
MANIFEST_PATH = PROJECT_ROOT / "eval" / "retrieval_eval_manifest_v2.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as error:
                raise AssertionError(
                    f"{path} line {line_number} is invalid JSON: {error}"
                ) from error

    return records


def normalize_query(text: str) -> str:
    return " ".join(text.lower().split())


def validate_record(record: dict[str, Any]) -> None:
    required_string_fields = [
        "query_id",
        "query",
        "expected_source_path_contains",
        "expected_behavior",
    ]

    for field in required_string_fields:
        value = record.get(field)
        assert isinstance(value, str)
        assert value.strip()

    groups = record.get("must_contain_any_groups")
    assert isinstance(groups, list)
    assert groups

    for group in groups:
        assert isinstance(group, list)
        assert group
        assert all(
            isinstance(term, str) and term.strip()
            for term in group
        )


def test_retrieval_eval_files_exist() -> None:
    assert DEV_PATH.exists()
    assert HOLDOUT_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_retrieval_eval_record_schema() -> None:
    for record in load_jsonl(DEV_PATH) + load_jsonl(HOLDOUT_PATH):
        validate_record(record)


def test_query_ids_are_unique_across_dev_and_holdout() -> None:
    records = load_jsonl(DEV_PATH) + load_jsonl(HOLDOUT_PATH)
    query_ids = [record["query_id"] for record in records]

    assert len(query_ids) == len(set(query_ids))


def test_queries_are_unique_across_dev_and_holdout() -> None:
    development_queries = {
        normalize_query(record["query"])
        for record in load_jsonl(DEV_PATH)
    }
    holdout_queries = [
        normalize_query(record["query"])
        for record in load_jsonl(HOLDOUT_PATH)
    ]

    assert len(holdout_queries) == len(set(holdout_queries))
    assert development_queries.isdisjoint(holdout_queries)


def test_holdout_size_and_prefix_are_frozen() -> None:
    holdout_records = load_jsonl(HOLDOUT_PATH)

    assert len(holdout_records) == 26
    assert all(
        record["query_id"].startswith("holdout_")
        for record in holdout_records
    )


def test_manifest_references_frozen_datasets() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["development_set"] == (
        "eval/retrieval_eval_60_corpus_v2.jsonl"
    )
    assert manifest["holdout_set"] == (
        "eval/retrieval_holdout_26_v1.jsonl"
    )
    assert manifest["primary_metric"] == "requirement_hit_at_k"
    assert manifest["top_k"] == 5
    assert re.fullmatch(
        r"[0-9a-f]{40}",
        manifest["frozen_base_commit_sha"],
    )
