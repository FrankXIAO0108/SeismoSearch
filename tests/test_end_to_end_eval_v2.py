"""
Tests for evaluation contract v2 runner integration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT
    / "scripts"
    / "run_end_to_end_eval_v2.py"
)


def load_runner() -> ModuleType:
    """Load the V2 runner directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "run_end_to_end_eval_v2",
        RUNNER_PATH,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load runner: {RUNNER_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def make_sample() -> dict:
    """Return one mixed evaluation contract."""
    return {
        "query_id": "sample_mixed_001",
        "query": "列出事件并解释前震、主震和余震。",
        "gold_query_type": "mixed",
        "gold_tools": [
            "safety_check",
            "event_search",
            "event_statistics",
            "doc_retrieval",
        ],
        "gold_event_required": True,
        "gold_doc_required": True,
        "gold_doc_requirements": {
            "must_contain_terms": [
                "前震",
                "主震",
                "余震",
            ],
            "expected_source_path_contains": (
                "aftershock_foreshock_mainshock.md"
            ),
        },
    }


def make_pack() -> dict:
    """Return a minimal mixed Evidence Pack."""
    return {
        "query_type": "mixed",
        "tool_calls": [
            {"tool_name": "safety_check"},
            {"tool_name": "event_search"},
            {"tool_name": "event_statistics"},
            {"tool_name": "doc_retrieval"},
        ],
        "router_output": {
            "planner_output": {
                "event_search_params": {},
            }
        },
        "event_evidence": [
            {
                "evidence_id": "event_001",
                "magnitude": 6.5,
            }
        ],
        "computed_evidence": [],
        "doc_evidence": [
            {
                "evidence_id": "doc_001",
                "source_path": (
                    "data/processed/docs/"
                    "aftershock_foreshock_mainshock.md"
                ),
                "heading": "Sequence Relationships",
                "text": "前震、主震和余震是序列关系。",
            },
            {
                "evidence_id": "doc_004",
                "source_path": (
                    "data/processed/docs/"
                    "aftershock_foreshock_mainshock.md"
                ),
                "heading": "Safety Boundary",
                "text": "前震和余震不能用于确定性预测。",
            },
        ],
    }


def make_generation_result(
    answer: str,
    used_ids: list[str],
) -> dict:
    """Return a deterministic-shaped generation result."""
    return {
        "answer": answer,
        "used_evidence_ids": used_ids,
        "generator_mode": "deterministic",
        "warnings": [],
    }


def evaluate(
    answer: str,
    used_ids: list[str],
) -> dict:
    """Run the V2 evaluation wrapper."""
    return runner.evaluate_mode(
        sample=make_sample(),
        evidence_pack=make_pack(),
        generation_result=(
            make_generation_result(
                answer,
                used_ids,
            )
        ),
        requested_mode="deterministic",
        generation_seconds=0.01,
        end_to_end_seconds=0.02,
    )


def test_correct_cited_chunk_passes_support() -> None:
    """Correct event and document chunks should pass support."""
    record = evaluate(
        answer=(
            "本地样例事件。[event_001] "
            "前震、主震和余震是序列关系。[doc_001]"
        ),
        used_ids=[
            "event_001",
            "doc_001",
        ],
    )

    assert (
        record["checks"][
            "citation_support_valid"
        ]
        is True
    )
    assert (
        record["citation_support"][
            "missing_doc_terms"
        ]
        == []
    )


def test_valid_id_wrong_chunk_fails_contract() -> None:
    """A valid but irrelevant chunk should fail the V2 contract."""
    record = evaluate(
        answer=(
            "本地样例事件。[event_001] "
            "前震、主震和余震是序列关系。[doc_004]"
        ),
        used_ids=[
            "event_001",
            "doc_004",
        ],
    )

    assert record["checks"]["citation_valid"] is True
    assert (
        record["checks"][
            "citation_support_valid"
        ]
        is False
    )
    assert (
        record["checks"]["contract_pass"]
        is False
    )
    assert (
        record["citation_support"][
            "missing_doc_terms"
        ]
        == ["主震"]
    )


def test_safety_sample_is_not_penalized() -> None:
    """Citation support is not applicable to safety-only samples."""
    sample = {
        "query_id": "sample_safety_001",
        "query": "明天会不会发生地震？",
        "gold_query_type": "safety",
        "gold_tools": ["safety_check"],
        "gold_event_required": False,
        "gold_doc_required": False,
    }
    pack = {
        "query_type": "safety",
        "tool_calls": [
            {"tool_name": "safety_check"},
        ],
        "event_evidence": [],
        "computed_evidence": [],
        "doc_evidence": [],
    }
    generation_result = {
        "answer": (
            "不能预测未来具体地震。"
            "更安全的替代方向是查看官方信息。"
        ),
        "used_evidence_ids": [],
        "generator_mode": "deterministic",
        "warnings": [],
    }

    record = runner.evaluate_mode(
        sample=sample,
        evidence_pack=pack,
        generation_result=generation_result,
        requested_mode="deterministic",
        generation_seconds=0.01,
        end_to_end_seconds=0.02,
    )

    assert (
        record["checks"][
            "citation_support_valid"
        ]
        is None
    )
    assert (
        record["checks"]["contract_pass"]
        is True
    )


def test_summary_reports_support_failures() -> None:
    """Summary should expose citation-support rate and IDs."""
    passing = evaluate(
        answer=(
            "本地样例事件。[event_001] "
            "前震、主震和余震是序列关系。[doc_001]"
        ),
        used_ids=[
            "event_001",
            "doc_001",
        ],
    )
    failing = evaluate(
        answer=(
            "本地样例事件。[event_001] "
            "前震、主震和余震是序列关系。[doc_004]"
        ),
        used_ids=[
            "event_001",
            "doc_004",
        ],
    )
    failing["query_id"] = "sample_mixed_002"

    summary = runner.summarize_mode(
        [passing, failing],
        "deterministic",
    )

    assert (
        summary[
            "citation_support_valid_rate"
        ]
        == 0.5
    )
    assert (
        summary[
            "citation_support_num_applicable"
        ]
        == 2
    )
    assert (
        summary[
            "citation_support_failed_query_ids"
        ]
        == ["sample_mixed_002"]
    )


def test_runner_rejects_frozen_v1_paths() -> None:
    """V2 runner must never consume or overwrite V1 defaults."""
    with pytest.raises(
        ValueError,
        match="must not use frozen V1 paths",
    ):
        runner.assert_not_v1_paths(
            eval_file=Path(
                "eval/end_to_end_holdout_20_v1.jsonl"
            ),
            output_file=Path(
                "eval/results/custom.json"
            ),
        )

    with pytest.raises(
        ValueError,
        match="must not use frozen V1 paths",
    ):
        runner.assert_not_v1_paths(
            eval_file=Path(
                "eval/custom.jsonl"
            ),
            output_file=Path(
                "eval/results/"
                "end_to_end_holdout_20_v1_results.json"
            ),
        )
