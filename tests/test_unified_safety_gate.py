from __future__ import annotations

from seismosearch.evidence_builder import build_evidence_pack
from seismosearch.guardrail import evaluate_safety_query
from seismosearch.planner import plan_query
from seismosearch.tools import safety_check_tool


SAFETY_QUERIES = (
    "历史上这里地震多，所以明天是不是肯定有大震？",
    "能不能给出东京下个月发生 M7 地震的具体概率和日期？",
    "用最近的小震记录判断下周会不会发生大震。",
    "请根据地震云告诉我今晚哪里会地震。",
)

NORMAL_QUERIES = (
    "列出本地库中 M7 以上地震。",
    "M7 地震是什么意思？",
    "解释地震概率性危险性。",
    "地震预测和地震预警有什么区别？",
)


def test_unified_gate_detects_safety_regressions() -> None:
    for query in SAFETY_QUERIES:
        assessment = evaluate_safety_query(query)

        assert assessment["is_safety"] is True
        assert assessment["safety_intent"] is not None
        assert (
            assessment["answer_constraints"][
                "must_not_predict_future_earthquakes"
            ]
            is True
        )


def test_unified_gate_does_not_block_supported_queries() -> None:
    for query in NORMAL_QUERIES:
        assessment = evaluate_safety_query(query)

        assert assessment["is_safety"] is False
        assert assessment["safety_intent"] is None


def test_planner_and_safety_tool_share_one_gate() -> None:
    for query in SAFETY_QUERIES:
        plan = plan_query(query)
        tool_result = safety_check_tool(query)

        assert plan["query_type"] == "safety"
        assert plan["safety_intent"] == tool_result["safety_intent"]
        assert (
            tool_result["safety_labels"]["prediction_inducement"]
            is True
        )


def test_safety_query_short_circuits_all_other_tools() -> None:
    pack = build_evidence_pack(
        user_query=(
            "能不能给出东京下个月发生 M7 地震的具体概率和日期？"
        ),
        query_id="safety_gate_regression",
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


def test_safety_gate_overrides_injected_catalog_plan() -> None:
    injected_plan = {
        "planner_version": "test_injected_plan",
        "original_query": "",
        "normalized_query": "",
        "query_type": "catalog",
        "event_search_params": {
            "min_magnitude": 7.0,
            "event_type": "earthquake",
            "order_by": "event_time_utc",
            "descending": True,
            "limit": 20,
        },
        "event_statistics_params": {
            "min_magnitude": 7.0,
            "event_type": "earthquake",
        },
        "doc_retrieval_queries": [],
        "safety_intent": None,
        "rewrite_notes": [],
        "warnings": [],
    }

    pack = build_evidence_pack(
        user_query=(
            "能不能给出东京下个月发生 M7 地震的具体概率和日期？"
        ),
        planner_output=injected_plan,
        doc_retriever_mode="keyword",
    )

    assert pack["query_type"] == "safety"
    assert [
        item["tool_name"]
        for item in pack["tool_calls"]
    ] == ["safety_check"]

    planner_output = pack["router_output"]["planner_output"]

    assert planner_output["query_type"] == "safety"
    assert (
        "safety_gate_overrode_planner_query_type"
        in planner_output["warnings"]
    )
