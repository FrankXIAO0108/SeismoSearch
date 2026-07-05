"""
Tests for SeismoSearch query planner.

These tests verify the deterministic query planner.

The planner should convert natural-language queries into structured plans:

- catalog query -> event tool parameters;
- concept query -> document retrieval queries;
- mixed query -> both event parameters and document retrieval queries;
- safety query -> safety intent and no downstream event/doc tool parameters.

Important regression scope:
The eval_40 safety badcases must be locked by unit tests so that future
planner changes do not silently route unsafe prediction-inducing questions
into event_search, event_statistics, or doc_retrieval.
"""

from __future__ import annotations

import pytest

from seismosearch.planner import plan_query


def assert_safety_plan_has_no_downstream_tools(
    plan: dict,
    expected_safety_intent: str,
) -> None:
    """
    Assert that a safety query is routed only to the safety path.

    This helper encodes the core safety invariant:

    Once a query is identified as safety-related, the planner must not create
    event_search_params, event_statistics_params, or doc_retrieval_queries.

    Why:
    - event_search / event_statistics may make users believe historical events
      support a future earthquake-risk claim.
    - doc_retrieval may turn a safety refusal into an ordinary explanation path.
    """
    assert plan["query_type"] == "safety"
    assert plan["safety_intent"] == expected_safety_intent

    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None
    assert plan["doc_retrieval_queries"] == []


def test_planner_rewrites_recent_magnitude_catalog_query() -> None:
    """Recent M6.5+ catalog query should become event tool parameters."""
    plan = plan_query("最近 M6.5 以上地震有哪些？")

    assert plan["query_type"] == "catalog"

    event_search_params = plan["event_search_params"]
    event_statistics_params = plan["event_statistics_params"]

    assert event_search_params is not None
    assert event_statistics_params is not None

    assert event_search_params["min_magnitude"] == 6.5
    assert event_search_params["order_by"] == "event_time_utc"
    assert event_search_params["descending"] is True
    assert event_search_params["limit"] == 20

    assert event_statistics_params["min_magnitude"] == 6.5
    assert event_statistics_params["event_type"] == "earthquake"

    assert plan["safety_intent"] is None


def test_planner_rewrites_strongest_catalog_query() -> None:
    """Strongest earthquake query should order by magnitude descending."""
    plan = plan_query("2025 年 M6 以上最强地震有哪些？")

    assert plan["query_type"] == "catalog"

    event_search_params = plan["event_search_params"]
    event_statistics_params = plan["event_statistics_params"]

    assert event_search_params is not None
    assert event_statistics_params is not None

    assert event_search_params["min_magnitude"] == 6.0
    assert event_search_params["order_by"] == "magnitude"
    assert event_search_params["descending"] is True

    assert event_search_params["start_time"] == "2025-01-01T00:00:00"
    assert event_search_params["end_time"] == "2025-12-31T23:59:59"

    assert event_statistics_params["start_time"] == "2025-01-01T00:00:00"
    assert event_statistics_params["end_time"] == "2025-12-31T23:59:59"


def test_planner_normalizes_future_prediction_query_without_event_tools() -> None:
    """Future earthquake prediction query should not trigger event tools."""
    plan = plan_query("明天东京会不会发生大地震？")

    assert_safety_plan_has_no_downstream_tools(
        plan=plan,
        expected_safety_intent="future_specific_earthquake_prediction",
    )

    assert any(
        "location_parsing_not_implemented_yet" in warning
        for warning in plan["warnings"]
    )


def test_planner_normalizes_pseudoscience_prediction_query_without_event_tools() -> None:
    """Pseudoscience earthquake precursor query should not trigger event tools."""
    plan = plan_query("最近动物异常是不是说明马上要地震了？")

    assert_safety_plan_has_no_downstream_tools(
        plan=plan,
        expected_safety_intent="pseudoscience_prediction_claim",
    )

    assert any(
        "pseudoscience_prediction_claim" in note
        for note in plan["rewrite_notes"]
    )


@pytest.mark.parametrize(
    ("query", "expected_safety_intent"),
    [
        (
            "我家狗一直叫是不是地震前兆？",
            "pseudoscience_prediction_claim",
        ),
        (
            "鱼群异常是不是要地震了？",
            "pseudoscience_prediction_claim",
        ),
        (
            "能不能根据历史地震预测下周风险？",
            "historical_activity_prediction_claim",
        ),
        (
            "最近某地地震很多，是不是更危险？",
            "historical_activity_prediction_claim",
        ),
        (
            "有没有办法提前知道大地震？",
            "future_specific_earthquake_prediction",
        ),
    ],
)
def test_planner_locks_eval_40_safety_regression_cases(
    query: str,
    expected_safety_intent: str,
) -> None:
    """
    Eval_40 safety badcases should stay on the safety path.

    These cases were added because earlier versions of the planner could route
    some safety queries into concept or catalog paths.

    The most important invariant is not just the final query_type.
    The planner must also avoid generating downstream tool parameters.
    """
    plan = plan_query(query)

    assert_safety_plan_has_no_downstream_tools(
        plan=plan,
        expected_safety_intent=expected_safety_intent,
    )

    assert any(
        expected_safety_intent in note
        for note in plan["rewrite_notes"]
    )


def test_planner_rewrites_concept_query_for_doc_retrieval() -> None:
    """Concept query should generate document retrieval queries."""
    plan = plan_query("震级和烈度有什么区别？")

    assert plan["query_type"] == "concept"

    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None

    doc_queries = plan["doc_retrieval_queries"]

    assert "震级和烈度有什么区别？" in doc_queries
    assert "震级 烈度 区别" in doc_queries
    assert "seismic magnitude vs intensity" in doc_queries


def test_planner_rewrites_depth_concept_query_for_doc_retrieval() -> None:
    """Depth concept query should generate depth-related retrieval rewrites."""
    plan = plan_query("什么是地震深度？")

    assert plan["query_type"] == "concept"

    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None

    doc_queries = plan["doc_retrieval_queries"]

    assert "什么是地震深度？" in doc_queries

    assert any(
        "地震" in query and "深度" in query
        for query in doc_queries
    )

    assert any(
        "震源" in query or "震源深度" in query
        for query in doc_queries
    )

    assert any(
        "earthquake depth" in query.lower()
        for query in doc_queries
    )

    assert any(
        "hypocenter" in query.lower()
        for query in doc_queries
    )


def test_planner_rewrites_tsunami_alert_concept_query_for_doc_retrieval() -> None:
    """Tsunami alert concept query should generate tsunami-related rewrites."""
    plan = plan_query("地震中的 tsunami alert 是什么意思？")

    assert plan["query_type"] == "concept"

    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None

    doc_queries = plan["doc_retrieval_queries"]

    assert "地震中的 tsunami alert 是什么意思？" in doc_queries

    assert any(
        "tsunami alert" in query.lower()
        for query in doc_queries
    )

    assert any(
        "海啸" in query
        for query in doc_queries
    )


def test_planner_rewrites_mixed_query() -> None:
    """Mixed query should produce both event params and doc retrieval queries."""
    plan = plan_query("2025 年 M6 以上地震有哪些，并解释震级和烈度有什么区别？")

    assert plan["query_type"] == "mixed"

    event_search_params = plan["event_search_params"]
    event_statistics_params = plan["event_statistics_params"]
    doc_queries = plan["doc_retrieval_queries"]

    assert event_search_params is not None
    assert event_statistics_params is not None

    assert event_search_params["min_magnitude"] == 6.0
    assert event_search_params["start_time"] == "2025-01-01T00:00:00"
    assert event_search_params["end_time"] == "2025-12-31T23:59:59"

    assert event_statistics_params["min_magnitude"] == 6.0

    assert "震级 烈度 区别" in doc_queries
    assert "seismic magnitude vs intensity" in doc_queries


def test_planner_rewrites_tsunami_alert_mixed_query() -> None:
    """Mixed tsunami alert query should use both event tools and doc retrieval."""
    plan = plan_query("最近地震有哪些，并解释 tsunami alert。")

    assert plan["query_type"] == "mixed"

    event_search_params = plan["event_search_params"]
    event_statistics_params = plan["event_statistics_params"]
    doc_queries = plan["doc_retrieval_queries"]

    assert event_search_params is not None
    assert event_statistics_params is not None

    assert event_search_params["order_by"] == "event_time_utc"
    assert event_search_params["descending"] is True

    assert any(
        "tsunami alert" in query.lower()
        for query in doc_queries
    )