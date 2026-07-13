"""
Tests for deterministic citation-support evaluation.
"""

from __future__ import annotations

from seismosearch.citation_support import (
    build_evidence_index,
    check_reference_citation_support,
    extract_inline_citation_ids,
)


def make_mixed_sample() -> dict:
    """Return a mixed-query reference contract."""
    return {
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
    """Return an Evidence Pack with one correct and one wrong chunk."""
    return {
        "event_evidence": [
            {
                "evidence_id": "event_001",
                "place": "Sample Region",
                "magnitude": 6.5,
            }
        ],
        "computed_evidence": [
            {
                "evidence_id": "computed_001",
                "statistics": {
                    "event_count_matching_filters": 1,
                },
            }
        ],
        "doc_evidence": [
            {
                "evidence_id": "doc_001",
                "source_path": (
                    "data/processed/docs/"
                    "aftershock_foreshock_mainshock.md"
                ),
                "heading": "Sequence Relationships",
                "text": (
                    "前震、主震和余震描述同一地震序列中"
                    "事件之间的关系。"
                ),
            },
            {
                "evidence_id": "doc_004",
                "source_path": (
                    "data/processed/docs/"
                    "aftershock_foreshock_mainshock.md"
                ),
                "heading": "Safety Boundary",
                "text": (
                    "不能根据一次小地震预测未来具体地震。"
                    "前震和余震概念不能用于确定性预测。"
                ),
            },
        ],
    }


def test_extract_inline_citation_ids_deduplicates() -> None:
    """Inline citations should preserve order and remove duplicates."""
    answer = (
        "事件事实。[event_001] "
        "概念解释。[doc_001] "
        "再次引用。[event_001]"
    )

    assert extract_inline_citation_ids(answer) == [
        "event_001",
        "doc_001",
    ]


def test_build_evidence_index_uses_all_evidence_fields() -> None:
    """Event, computed, and document evidence should be indexed."""
    index = build_evidence_index(make_pack())

    assert set(index) == {
        "event_001",
        "computed_001",
        "doc_001",
        "doc_004",
    }


def test_valid_mixed_citations_pass() -> None:
    """Correct event and document citations should satisfy the contract."""
    result = check_reference_citation_support(
        sample=make_mixed_sample(),
        answer=(
            "样例事件为 M6.5。[event_001] "
            "前震、主震和余震属于序列关系。[doc_001]"
        ),
        evidence_pack=make_pack(),
    )

    assert result["valid"] is True
    assert result["missing_doc_terms"] == []
    assert result["source_path_match"] is True


def test_valid_but_wrong_chunk_fails_support() -> None:
    """
    A valid citation ID must fail when its chunk lacks required support.

    This reproduces the End-to-End Holdout V1 mixed_005 failure class:
    the answer cites a real Safety Boundary chunk, but that chunk does not
    support the complete foreshock-mainshock-aftershock explanation.
    """
    result = check_reference_citation_support(
        sample=make_mixed_sample(),
        answer=(
            "样例事件为 M6.5。[event_001] "
            "前震、主震和余震属于序列关系。[doc_004]"
        ),
        evidence_pack=make_pack(),
    )

    assert result["valid"] is False
    assert result["unknown_citation_ids"] == []
    assert result["missing_doc_terms"] == ["主震"]
    assert result["source_path_match"] is True


def test_wrong_source_fails_support() -> None:
    """A cited chunk from the wrong source should fail."""
    pack = make_pack()
    pack["doc_evidence"][0]["source_path"] = (
        "data/processed/docs/unrelated.md"
    )

    result = check_reference_citation_support(
        sample=make_mixed_sample(),
        answer=(
            "样例事件为 M6.5。[event_001] "
            "前震、主震和余震属于序列关系。[doc_001]"
        ),
        evidence_pack=pack,
    )

    assert result["valid"] is False
    assert result["source_path_match"] is False


def test_mixed_answer_requires_event_citation() -> None:
    """Document citation alone is insufficient for a mixed answer."""
    result = check_reference_citation_support(
        sample=make_mixed_sample(),
        answer=(
            "前震、主震和余震属于序列关系。[doc_001]"
        ),
        evidence_pack=make_pack(),
    )

    assert result["valid"] is False
    assert result["missing_event_citation"] is True


def test_mixed_answer_requires_doc_citation() -> None:
    """Event citation alone is insufficient for a mixed answer."""
    result = check_reference_citation_support(
        sample=make_mixed_sample(),
        answer="样例事件为 M6.5。[event_001]",
        evidence_pack=make_pack(),
    )

    assert result["valid"] is False
    assert result["missing_doc_citation"] is True
    assert result["missing_doc_terms"] == [
        "前震",
        "主震",
        "余震",
    ]


def test_unknown_inline_citation_fails_support() -> None:
    """Unknown inline evidence IDs should fail support validation."""
    result = check_reference_citation_support(
        sample=make_mixed_sample(),
        answer=(
            "样例事件为 M6.5。[event_001] "
            "前震、主震和余震属于序列关系。[doc_999]"
        ),
        evidence_pack=make_pack(),
    )

    assert result["valid"] is False
    assert result["unknown_citation_ids"] == [
        "doc_999",
    ]


def test_safety_sample_is_not_applicable() -> None:
    """Safety-only samples have no event or document support contract."""
    result = check_reference_citation_support(
        sample={
            "gold_event_required": False,
            "gold_doc_required": False,
        },
        answer="不能预测未来具体地震。",
        evidence_pack={},
    )

    assert result["applicable"] is False
    assert result["valid"] is None
