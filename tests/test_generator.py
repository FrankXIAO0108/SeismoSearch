"""
Tests for SeismoSearch deterministic answer generator.

These tests verify that the generator:
- uses Evidence Pack content;
- states sample limitations for catalog answers;
- refuses future earthquake prediction requests;
- uses doc_evidence for concept answers after doc retrieval is connected.
"""

from __future__ import annotations

from seismosearch.evidence_builder import build_evidence_pack
from seismosearch.generator import generate_answer


def test_catalog_generator_uses_event_and_computed_evidence() -> None:
    """Catalog answer should use event evidence and computed statistics."""
    pack = build_evidence_pack(
        user_query="最近 M6.5 以上地震有哪些？",
        query_type="catalog",
        event_search_params={
            "min_magnitude": 6.5,
            "order_by": "magnitude",
            "limit": 2,
        },
        event_statistics_params={
            "min_magnitude": 6.5,
        },
    )

    result = generate_answer(pack)

    assert result["status"] == "ok"
    assert result["query_type"] == "catalog"

    answer = result["answer"]

    # The answer must state local sample limitations.
    assert "当前本地样例库" in answer
    assert "不是完整全球地震目录统计" in answer

    # The answer should include computed statistics.
    assert "匹配事件数为 7" in answer
    assert "M6.5" in answer
    assert "M7.6" in answer

    # The answer should cite stable event evidence IDs.
    assert "[event_001]" in answer
    assert "[event_002]" in answer

    # The generator should report which evidence IDs it used.
    assert "event_001" in result["used_evidence_ids"]
    assert "event_002" in result["used_evidence_ids"]
    assert "computed_001" in result["used_evidence_ids"]


def test_safety_generator_refuses_future_prediction() -> None:
    """Safety answer should refuse future earthquake prediction."""
    pack = build_evidence_pack(
        user_query="明天东京会不会发生大地震？",
    )

    result = generate_answer(pack)

    assert result["status"] == "ok"
    assert result["query_type"] == "safety"

    answer = result["answer"]

    # The answer must refuse concrete future earthquake prediction.
    assert "不能预测" in answer
    assert "未来某一天是否会发生大地震" in answer

    # The answer should provide safe alternatives rather than stopping at refusal.
    assert "更安全、可用的替代方向" in answer
    assert "官方地震监测机构" in answer
    assert "应急" in answer

    constraints = result["answer_constraints"]
    assert constraints["must_not_predict_future_earthquakes"] is True
    assert constraints["response_mode"] == "safe_refusal_with_alternatives"


def test_concept_generator_uses_doc_evidence() -> None:
    """Concept answer should use retrieved document evidence."""
    pack = build_evidence_pack(
        user_query="震级和烈度有什么区别？",
        query_type="concept",
    )

    result = generate_answer(pack)

    assert result["status"] == "ok"
    assert result["query_type"] == "concept"

    answer = result["answer"]

    # The answer should now be based on doc evidence.
    assert "根据当前检索到的文档证据" in answer
    assert "震级" in answer
    assert "烈度" in answer

    # The answer should cite stable document evidence IDs.
    assert "[doc_001]" in answer

    # The old conservative message should no longer appear when doc evidence exists.
    assert "还没有接入文档检索模块" not in answer
    assert "不会编造地震学概念解释" not in answer

    # The generator should report document evidence usage.
    assert "doc_001" in result["used_evidence_ids"]

    constraints = result["answer_constraints"]
    assert constraints["must_cite_doc_evidence_when_using_document_facts"] is True


def test_concept_generator_stays_conservative_without_doc_evidence() -> None:
    """Concept answer should still refuse to fabricate if doc_evidence is missing."""
    pack = {
        "query_id": "test_query",
        "query_type": "concept",
        "user_query": "震级和烈度有什么区别？",
        "doc_evidence": [],
        "event_evidence": [],
        "computed_evidence": [],
        "warnings": ["no_document_evidence_for_test"],
        "answer_constraints": {
            "must_use_evidence_pack": True,
            "must_not_predict_future_earthquakes": False,
            "must_cite_doc_evidence_when_using_document_facts": False,
            "response_mode": "concept_answer",
        },
    }

    result = generate_answer(pack)

    answer = result["answer"]

    assert result["status"] == "ok"
    assert result["query_type"] == "concept"
    assert "当前 Evidence Pack 中没有 doc_evidence" in answer
    assert "不会编造地震学概念解释" in answer
    assert result["used_evidence_ids"] == []