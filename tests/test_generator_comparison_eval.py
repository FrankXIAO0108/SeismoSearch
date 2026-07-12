"""
Tests for deterministic generator-comparison evaluation helpers.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "run_generator_comparison_eval.py"
)


def load_runner_module() -> ModuleType:
    """Load the evaluation runner directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "run_generator_comparison_eval",
        RUNNER_PATH,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load evaluation runner: {RUNNER_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


runner = load_runner_module()

check_citation_validity = runner.check_citation_validity
check_required_terms = runner.check_required_terms
check_sample_limitation = runner.check_sample_limitation
collect_available_evidence_ids = (
    runner.collect_available_evidence_ids
)
extract_inline_citation_ids = (
    runner.extract_inline_citation_ids
)
safe_ratio = runner.safe_ratio


def test_citation_contract_matches_available_evidence() -> None:
    """Inline and declared IDs must match the Evidence Pack."""
    pack = {
        "event_evidence": [
            {"evidence_id": "event_001"}
        ],
        "computed_evidence": [],
        "doc_evidence": [
            {"evidence_id": "doc_001"}
        ],
    }

    available_ids = collect_available_evidence_ids(
        pack
    )
    answer = (
        "事件事实。[event_001] "
        "概念解释。[doc_001]"
    )

    assert extract_inline_citation_ids(answer) == [
        "event_001",
        "doc_001",
    ]
    assert check_citation_validity(
        answer=answer,
        used_evidence_ids=[
            "event_001",
            "doc_001",
        ],
        available_ids=available_ids,
    ) is True


def test_unknown_or_undeclared_citation_fails() -> None:
    """Hallucinated and undeclared citation IDs must fail."""
    assert check_citation_validity(
        answer="错误引用。[doc_999]",
        used_evidence_ids=["doc_999"],
        available_ids={"doc_001"},
    ) is False

    assert check_citation_validity(
        answer="有效引用。[doc_001]",
        used_evidence_ids=[],
        available_ids={"doc_001"},
    ) is False


def test_answer_requirement_helpers() -> None:
    """Term coverage and sample disclosure are inspectable."""
    concept_sample = {
        "gold_doc_requirements": {
            "must_contain_terms": [
                "震级",
                "烈度",
            ]
        }
    }
    catalog_sample = {
        "gold_query_type": "catalog"
    }

    assert check_required_terms(
        concept_sample,
        "震级和烈度是不同概念。",
    ) is True

    assert check_sample_limitation(
        catalog_sample,
        "结果来自当前本地样例库，不代表完整全球目录。",
    ) is True

    assert safe_ratio(
        [True, False, True]
    ) == (2 / 3)