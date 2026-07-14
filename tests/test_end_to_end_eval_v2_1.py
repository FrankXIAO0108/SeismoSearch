"""
Tests for independent end-to-end evaluation contract 2.1.
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
    / "run_end_to_end_eval_v2_1.py"
)


def load_runner() -> ModuleType:
    """Load contract 2.1 directly from its script path."""
    spec = importlib.util.spec_from_file_location(
        "run_end_to_end_eval_v2_1",
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
    """Return one bilingual mixed-query contract."""
    return {
        "query_id": "v2_1_bilingual_001",
        "query": (
            "列出 M6.6 以上事件，并解释相同震级的"
            "地震影响为什么可能不同。"
        ),
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
                "深度",
                "距离",
            ],
            "expected_source_path_contains": (
                "impact_factors.md"
            ),
        },
    }


def make_pack() -> dict:
    """Return English evidence for Chinese gold requirements."""
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
                "magnitude": 6.6,
            }
        ],
        "computed_evidence": [],
        "doc_evidence": [
            {
                "evidence_id": "doc_001",
                "source_path": (
                    "data/processed/docs/"
                    "impact_factors.md"
                ),
                "doc_title": (
                    "Earthquake Impact Factors"
                ),
                "heading": "Depth and Distance",
                "text": (
                    "Shaking impact can differ with "
                    "focal depth and epicentral distance."
                ),
            }
        ],
    }


def make_generation_result(
    answer: str,
) -> dict:
    """Return deterministic-shaped generation output."""
    return {
        "answer": answer,
        "used_evidence_ids": [
            "event_001",
            "doc_001",
        ],
        "generator_mode": "deterministic",
        "warnings": [],
    }


def evaluate(answer: str) -> dict:
    """Run contract 2.1 with synthetic evidence."""
    return runner.evaluate_mode(
        sample=make_sample(),
        evidence_pack=make_pack(),
        generation_result=(
            make_generation_result(answer)
        ),
        requested_mode="deterministic",
        generation_seconds=0.01,
        end_to_end_seconds=0.02,
    )


def test_v2_1_accepts_bilingual_doc_and_answer_terms() -> None:
    answer = (
        "当前本地样例库事件如下。[event_001] "
        "Impact can differ because of depth and distance."
        "[doc_001]"
    )

    record = evaluate(answer)

    assert (
        record["checks"][
            "doc_evidence_correct"
        ]
        is True
    )
    assert (
        record["checks"][
            "required_terms_correct"
        ]
        is True
    )
    assert (
        record["checks"][
            "citation_support_valid"
        ]
        is True
    )
    assert (
        record["checks"]["contract_pass"]
        is True
    )
    assert (
        record["evaluation_contract_version"]
        == "2.1.0"
    )


def test_base_v2_exact_matching_would_fail_same_case() -> None:
    answer = (
        "当前本地样例库事件如下。[event_001] "
        "Impact can differ because of depth and distance."
        "[doc_001]"
    )

    base_record = runner.V2.evaluate_mode(
        sample=make_sample(),
        evidence_pack=make_pack(),
        generation_result=(
            make_generation_result(answer)
        ),
        requested_mode="deterministic",
        generation_seconds=0.01,
        end_to_end_seconds=0.02,
    )

    assert (
        base_record["checks"][
            "doc_evidence_correct"
        ]
        is False
    )
    assert (
        base_record["checks"][
            "required_terms_correct"
        ]
        is False
    )
    assert (
        base_record["checks"]["contract_pass"]
        is False
    )


def test_missing_bilingual_answer_term_fails_contract() -> None:
    answer = (
        "当前本地样例库事件如下。[event_001] "
        "Impact can differ because of depth."
        "[doc_001]"
    )

    record = evaluate(answer)

    assert (
        record["checks"][
            "doc_evidence_correct"
        ]
        is True
    )
    assert (
        record["checks"][
            "required_terms_correct"
        ]
        is False
    )
    assert (
        record["checks"]["contract_pass"]
        is False
    )
    assert (
        record[
            "evaluation_v2_1_diagnostics"
        ]["answer_terms"]["missing_terms"]
        == ["距离"]
    )


@pytest.mark.parametrize(
    ("eval_file", "output_file"),
    [
        (
            Path(
                "eval/"
                "end_to_end_holdout_20_v2.jsonl"
            ),
            Path(
                "eval/results/dev.json"
            ),
        ),
        (
            Path("eval/dev.jsonl"),
            Path(
                "eval/results/"
                "end_to_end_holdout_20_v2_results.json"
            ),
        ),
        (
            Path(
                "eval/"
                "end_to_end_holdout_20_v1.jsonl"
            ),
            Path(
                "eval/results/dev.json"
            ),
        ),
    ],
)
def test_contract_v2_1_rejects_frozen_artifacts(
    eval_file: Path,
    output_file: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "must not use frozen V1 "
            "or official V2"
        ),
    ):
        runner.assert_safe_paths(
            eval_file=eval_file,
            output_file=output_file,
        )


def test_contract_v2_1_allows_fresh_dev_paths() -> None:
    runner.assert_safe_paths(
        eval_file=Path(
            "eval/custom_v2_1_dev.jsonl"
        ),
        output_file=Path(
            "eval/results/"
            "custom_v2_1_dev_results.json"
        ),
    )
