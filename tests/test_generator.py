"""
Tests for SeismoSearch deterministic answer generator.

These tests verify that the generator:
- uses Evidence Pack content;
- states sample limitations for catalog answers;
- refuses future earthquake prediction requests;
- does not fabricate concept answers before document retrieval exists.
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


def test_concept_generator_does_not_fabricate_without_doc_evidence() -> None:
    """Concept answer should not fabricate explanations before doc retrieval exists."""
    pack = build_evidence_pack(
        user_query="震级和烈度有什么区别？",
        query_type="concept",
    )

    result = generate_answer(pack)

    assert result["status"] == "ok"
    assert result["query_type"] == "concept"

    answer = result["answer"]

    # Since doc_retriever.py is not implemented yet, generator should not
    # invent a seismology explanation.
    assert "还没有接入文档检索模块" in answer
    assert "不会编造地震学概念解释" in answer

    # There should be no event or computed evidence used.
    assert result["used_evidence_ids"] == []