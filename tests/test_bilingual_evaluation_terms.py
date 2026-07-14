"""
Tests for bilingual evaluation-term normalization.
"""

from __future__ import annotations

from seismosearch.citation_support import check_reference_citation_support
from seismosearch.evaluation_terms import (
    TERM_MATCH_CONTRACT_VERSION,
    check_required_terms,
    contains_required_term,
    find_missing_required_terms,
    get_equivalent_terms,
    normalize_evaluation_text,
)


def test_normalization_handles_unicode_case_and_whitespace() -> None:
    text = "  DEPTH\n\tDistance  "
    assert normalize_evaluation_text(text) == "depth distance"


def test_chinese_requirements_accept_english_answer_terms() -> None:
    answer = (
        "The impact can differ because of depth, distance, "
        "local geology, and buildings."
    )
    assert check_required_terms(
        answer,
        ["深度", "距离", "地质", "建筑"],
    )


def test_english_requirements_accept_chinese_answer_terms() -> None:
    answer = "影响还取决于震源深度、震中距、局地地质和建筑物。"
    assert check_required_terms(
        answer,
        ["depth", "distance", "geology", "buildings"],
    )


def test_ascii_boundary_avoids_deptherror_false_positive() -> None:
    assert contains_required_term("The field is depthError.", "深度") is False


def test_unknown_terms_keep_exact_normalized_matching() -> None:
    assert contains_required_term("Status is reviewed.", "reviewed")
    assert not contains_required_term("Status is automatic.", "reviewed")


def test_missing_terms_preserve_original_contract_terms() -> None:
    missing = find_missing_required_terms(
        "The answer mentions depth only.",
        ["深度", "距离"],
    )
    assert missing == ["距离"]


def test_alias_lookup_is_bidirectional() -> None:
    assert "深度" in get_equivalent_terms("depth")
    assert "depth" in get_equivalent_terms("震源深度")


def test_citation_support_uses_bilingual_term_matching() -> None:
    sample = {
        "gold_event_required": False,
        "gold_doc_required": True,
        "gold_doc_requirements": {
            "must_contain_terms": ["深度", "距离"],
            "expected_source_path_contains": "impact_factors.md",
        },
    }
    pack = {
        "event_evidence": [],
        "computed_evidence": [],
        "doc_evidence": [
            {
                "evidence_id": "doc_001",
                "source_path": "data/processed/docs/impact_factors.md",
                "doc_title": "Impact Factors",
                "heading": "Depth and Distance",
                "text": (
                    "Shaking differs with focal depth "
                    "and epicentral distance."
                ),
            }
        ],
    }

    result = check_reference_citation_support(
        sample=sample,
        answer="影响取决于多种因素。[doc_001]",
        evidence_pack=pack,
    )

    assert result["valid"] is True
    assert result["missing_doc_terms"] == []
    assert (
        result["term_match_contract_version"]
        == TERM_MATCH_CONTRACT_VERSION
    )


def test_citation_support_reports_original_missing_term() -> None:
    sample = {
        "gold_event_required": False,
        "gold_doc_required": True,
        "gold_doc_requirements": {
            "must_contain_terms": ["深度", "距离"],
        },
    }
    pack = {
        "event_evidence": [],
        "computed_evidence": [],
        "doc_evidence": [
            {
                "evidence_id": "doc_001",
                "source_path": "impact_factors.md",
                "doc_title": "Impact Factors",
                "heading": "Depth",
                "text": "Focal depth affects shaking.",
            }
        ],
    }

    result = check_reference_citation_support(
        sample=sample,
        answer="解释见证据。[doc_001]",
        evidence_pack=pack,
    )

    assert result["valid"] is False
    assert result["missing_doc_terms"] == ["距离"]
