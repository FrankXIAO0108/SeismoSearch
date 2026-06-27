"""
Tests for SeismoSearch main pipeline.

These tests verify that run_pipeline connects:
- planner.py;
- evidence_builder.py;
- generator.py.

The pipeline should accept a natural-language query and return a structured,
user-facing answer without requiring manual tool parameters.
"""

from __future__ import annotations

from seismosearch.pipeline import run_pipeline


def test_pipeline_answers_catalog_query_without_manual_params() -> None:
    """Pipeline should answer catalog query through planner-generated params."""
    result = run_pipeline(
        "最近 M6.5 以上地震有哪些？",
        include_evidence_pack=True,
    )

    assert result["status"] == "ok"
    assert result["query_type"] == "catalog"

    answer = result["answer"]

    assert "当前本地样例库" in answer
    assert "不是完整全球地震目录统计" in answer
    assert "匹配事件数为 7" in answer
    assert "[event_001]" in answer

    evidence_pack = result["evidence_pack"]
    planner_output = evidence_pack["router_output"]["planner_output"]

    assert planner_output["query_type"] == "catalog"
    assert planner_output["event_search_params"]["min_magnitude"] == 6.5
    assert planner_output["event_search_params"]["order_by"] == "event_time_utc"

    assert "event_001" in result["used_evidence_ids"]
    assert "computed_001" in result["used_evidence_ids"]


def test_pipeline_handles_safety_query_without_event_tools() -> None:
    """Pipeline should refuse future earthquake prediction safely."""
    result = run_pipeline(
        "明天东京会不会发生大地震？",
        include_evidence_pack=True,
    )

    assert result["status"] == "ok"
    assert result["query_type"] == "safety"

    answer = result["answer"]

    assert "不能预测" in answer
    assert "未来某一天是否会发生大地震" in answer
    assert "更安全、可用的替代方向" in answer

    evidence_pack = result["evidence_pack"]

    assert evidence_pack["event_evidence"] == []
    assert evidence_pack["computed_evidence"] == []

    planner_output = evidence_pack["router_output"]["planner_output"]

    assert planner_output["safety_intent"] == "future_specific_earthquake_prediction"
    assert planner_output["event_search_params"] is None

    constraints = result["answer_constraints"]

    assert constraints["must_not_predict_future_earthquakes"] is True
    assert constraints["response_mode"] == "safe_refusal_with_alternatives"


def test_pipeline_handles_concept_query_conservatively() -> None:
    """Pipeline should not fabricate concept answers before doc retrieval exists."""
    result = run_pipeline(
        "震级和烈度有什么区别？",
        include_evidence_pack=True,
    )

    assert result["status"] == "ok"
    assert result["query_type"] == "concept"

    answer = result["answer"]

    assert "还没有接入文档检索模块" in answer
    assert "不会编造地震学概念解释" in answer

    evidence_pack = result["evidence_pack"]

    assert evidence_pack["doc_evidence"] == []
    assert "doc_retrieval_not_implemented_yet" in evidence_pack["warnings"]
    assert "震级 烈度 区别" in evidence_pack["doc_retrieval_queries"]


def test_pipeline_rejects_non_string_query() -> None:
    """Pipeline should return a structured error for invalid query type."""
    result = run_pipeline(123)  # type: ignore[arg-type]

    assert result["status"] == "error"
    assert result["query_type"] is None
    assert result["answer"] == ""
    assert "user_query_must_be_a_string" in result["warnings"]
    