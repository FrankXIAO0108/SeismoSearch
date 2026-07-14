"""
Tests for SeismoSearch generation citation contracts.
"""

from __future__ import annotations

from seismosearch.generator import generate_answer
from seismosearch.llm_generator import (
    build_controlled_evidence_context,
    validate_llm_generation,
)


def _concept_pack() -> dict:
    """Build a concept Evidence Pack with extra unused documents."""
    return {
        "query_id": "citation_test",
        "user_query": "震级和烈度有什么区别？",
        "query_type": "concept",
        "event_evidence": [],
        "computed_evidence": [],
        "doc_evidence": [
            {
                "evidence_id": "doc_001",
                "doc_title": "Concepts",
                "heading": "震级和烈度",
                "source_path": "data/processed/docs/concepts.md",
                "text": "震级描述能量，烈度描述地点影响。",
            },
            {
                "evidence_id": "doc_002",
                "doc_title": "Other",
                "heading": "候选证据",
                "source_path": "data/processed/docs/other.md",
                "text": "这是一条候选证据。",
            },
        ],
        "safety_evidence": {},
        "warnings": [],
        "answer_constraints": {
            "must_not_predict_future_earthquakes": False,
        },
    }


def test_deterministic_generator_declares_only_inline_citations() -> None:
    """Deterministic metadata must match citations visible in the answer."""
    result = generate_answer(_concept_pack())

    assert result["used_evidence_ids"] == ["doc_001"]
    assert "[doc_001]" in result["answer"]
    assert "[doc_002]" not in result["answer"]


def test_llm_validator_normalizes_safe_metadata_mismatch() -> None:
    """Valid inline citations should be authoritative over stale metadata."""
    pack = _concept_pack()
    context = build_controlled_evidence_context(pack)

    result = validate_llm_generation(
        parsed_output={
            "answer": "震级和烈度不同。[doc_001]",
            "used_evidence_ids": [
                "doc_001",
                "doc_002",
            ],
            "grounding_notes": [],
        },
        evidence_context=context,
    )

    assert result["used_evidence_ids"] == ["doc_001"]
    assert result["validation_warnings"] == [
        "used_evidence_ids_normalized_to_inline_citations"
    ]


def test_llm_validator_still_rejects_unknown_inline_citation() -> None:
    """Metadata repair must never permit hallucinated evidence IDs."""
    pack = _concept_pack()
    context = build_controlled_evidence_context(pack)

    try:
        validate_llm_generation(
            parsed_output={
                "answer": "错误引用。[doc_999]",
                "used_evidence_ids": ["doc_999"],
                "grounding_notes": [],
            },
            evidence_context=context,
        )
    except ValueError as error:
        assert "unavailable evidence IDs" in str(error)
    else:
        raise AssertionError(
            "Unknown evidence citation should have been rejected"
        )
