"""
Tests for SeismoSearch main pipeline.

These tests verify that run_pipeline connects:
- planner.py;
- evidence_builder.py;
- doc_retriever.py;
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

    assert evidence_pack["doc_evidence"] == []

    assert "event_001" in result["used_evidence_ids"]
    assert "computed_001" in result["used_evidence_ids"]


def test_pipeline_handles_safety_query_without_event_or_doc_tools() -> None:
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
    assert evidence_pack["doc_evidence"] == []

    planner_output = evidence_pack["router_output"]["planner_output"]

    assert planner_output["safety_intent"] == "future_specific_earthquake_prediction"
    assert planner_output["event_search_params"] is None
    assert planner_output["event_statistics_params"] is None
    assert planner_output["doc_retrieval_queries"] == []

    constraints = result["answer_constraints"]

    assert constraints["must_not_predict_future_earthquakes"] is True
    assert constraints["response_mode"] == "safe_refusal_with_alternatives"


def test_pipeline_handles_concept_query_with_doc_evidence() -> None:
    """Pipeline should answer concept query through planner and doc retrieval."""
    result = run_pipeline(
        "震级和烈度有什么区别？",
        include_evidence_pack=True,
    )

    assert result["status"] == "ok"
    assert result["query_type"] == "concept"

    answer = result["answer"]

    # Concept answer should now be based on retrieved document evidence.
    assert "根据当前检索到的文档证据" in answer
    assert "震级" in answer
    assert "烈度" in answer
    assert "[doc_001]" in answer

    # Old message should no longer appear when doc evidence exists.
    assert "还没有接入文档检索模块" not in answer
    assert "不会编造地震学概念解释" not in answer

    evidence_pack = result["evidence_pack"]

    assert len(evidence_pack["doc_evidence"]) >= 1
    assert evidence_pack["doc_evidence"][0]["evidence_id"] == "doc_001"

    tool_names = [tool_call["tool_name"] for tool_call in evidence_pack["tool_calls"]]

    assert tool_names == [
        "safety_check",
        "doc_retrieval",
    ]

    planner_output = evidence_pack["router_output"]["planner_output"]

    assert planner_output["query_type"] == "concept"
    assert "震级 烈度 区别" in planner_output["doc_retrieval_queries"]
    assert "seismic magnitude vs intensity" in planner_output["doc_retrieval_queries"]

    assert "doc_001" in result["used_evidence_ids"]

    constraints = result["answer_constraints"]
    assert constraints["must_cite_doc_evidence_when_using_document_facts"] is True
    assert constraints["response_mode"] == "concept_answer"


def test_pipeline_handles_mixed_query_with_event_and_doc_evidence() -> None:
    """Pipeline should support mixed event query plus concept explanation."""
    result = run_pipeline(
        "2025 年 M6 以上地震有哪些，并解释震级和烈度有什么区别？",
        include_evidence_pack=True,
    )

    assert result["status"] == "ok"
    assert result["query_type"] == "mixed"

    answer = result["answer"]

    # Mixed answer should include both catalog evidence and concept evidence.
    assert "当前本地样例库" in answer
    assert "[event_001]" in answer
    assert "根据当前检索到的文档证据" in answer
    assert "[doc_001]" in answer

    evidence_pack = result["evidence_pack"]

    assert len(evidence_pack["event_evidence"]) >= 1
    assert len(evidence_pack["computed_evidence"]) == 1
    assert len(evidence_pack["doc_evidence"]) >= 1

    tool_names = [tool_call["tool_name"] for tool_call in evidence_pack["tool_calls"]]

    assert tool_names == [
        "safety_check",
        "event_search",
        "event_statistics",
        "doc_retrieval",
    ]

    planner_output = evidence_pack["router_output"]["planner_output"]

    assert planner_output["query_type"] == "mixed"
    assert planner_output["event_search_params"]["min_magnitude"] == 6.0
    assert "震级 烈度 区别" in planner_output["doc_retrieval_queries"]

    assert "event_001" in result["used_evidence_ids"]
    assert "computed_001" in result["used_evidence_ids"]
    assert "doc_001" in result["used_evidence_ids"]

    constraints = result["answer_constraints"]
    assert constraints["must_cite_event_evidence_when_using_event_facts"] is True
    assert constraints["must_cite_doc_evidence_when_using_document_facts"] is True
    assert constraints["response_mode"] == "mixed_event_and_concept_answer"


def test_pipeline_rejects_non_string_query() -> None:
    """Pipeline should return a structured error for invalid query type."""
    result = run_pipeline(123)  # type: ignore[arg-type]

    assert result["status"] == "error"
    assert result["query_type"] is None
    assert result["answer"] == ""
    assert "user_query_must_be_a_string" in result["warnings"]