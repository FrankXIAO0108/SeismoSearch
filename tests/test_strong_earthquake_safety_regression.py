from __future__ import annotations

import pytest

from seismosearch.evidence_builder import build_evidence_pack
from seismosearch.guardrail import evaluate_safety_query
from seismosearch.planner import plan_query
from seismosearch.tools import safety_check_tool


UNSAFE_QUERIES = (
    "给我一个未来三十天某城市发生强震的确定日期和概率。",
    "下个月某城市会发生强震吗？",
    "未来一个月北京发生强烈地震的概率和日期是什么？",
)

SUPPORTED_QUERIES = (
    "列出过去三十天的强震记录。",
    "强震是什么意思？",
)


@pytest.mark.parametrize("query", UNSAFE_QUERIES)
def test_future_strong_earthquake_queries_route_to_safety(
    query: str,
) -> None:
    assessment = evaluate_safety_query(query)
    plan = plan_query(query)
    tool_result = safety_check_tool(query)

    assert assessment["is_safety"] is True
    assert (
        assessment["safety_intent"]
        == "future_specific_earthquake_prediction"
    )
    assert plan["query_type"] == "safety"
    assert plan["safety_intent"] == assessment["safety_intent"]
    assert tool_result["safety_intent"] == assessment["safety_intent"]


@pytest.mark.parametrize("query", SUPPORTED_QUERIES)
def test_non_prediction_strong_earthquake_queries_are_supported(
    query: str,
) -> None:
    assessment = evaluate_safety_query(query)

    assert assessment["is_safety"] is False
    assert assessment["safety_intent"] is None


def test_exact_v2_pattern_short_circuits_all_other_tools() -> None:
    pack = build_evidence_pack(
        user_query=(
            "给我一个未来三十天某城市发生强震的确定日期和概率。"
        ),
        query_id="strong_earthquake_safety_regression",
        doc_retriever_mode="hybrid_rerank",
    )

    assert pack["query_type"] == "safety"
    assert [
        item["tool_name"]
        for item in pack["tool_calls"]
    ] == ["safety_check"]
    assert pack["event_evidence"] == []
    assert pack["computed_evidence"] == []
    assert pack["doc_evidence"] == []
    assert (
        pack["answer_constraints"][
            "must_not_predict_future_earthquakes"
        ]
        is True
    )
