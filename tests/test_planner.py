"""
Tests for SeismoSearch query planner.

These tests verify the first version of query rewrite.

The planner should convert natural-language queries into structured plans:
- catalog query -> event tool parameters;
- safety query -> safety intent and no event tool parameters;
- concept query -> document retrieval queries;
- mixed query -> both event parameters and retrieval queries.
"""

from __future__ import annotations

from seismosearch.planner import plan_query


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


def test_planner_normalizes_safety_query_without_event_tools() -> None:
    """Future earthquake prediction query should not trigger event tools."""
    plan = plan_query("明天东京会不会发生大地震？")

    assert plan["query_type"] == "safety"
    assert plan["safety_intent"] == "future_specific_earthquake_prediction"

    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None
    assert plan["doc_retrieval_queries"] == []

    assert any(
        "location_parsing_not_implemented_yet" in warning
        for warning in plan["warnings"]
    )


def test_planner_normalizes_pseudoscience_prediction_query_without_event_tools() -> None:
    """Pseudoscience earthquake precursor query should not trigger event tools."""
    plan = plan_query("最近动物异常是不是说明马上要地震了？")

    assert plan["query_type"] == "safety"
    assert plan["safety_intent"] == "pseudoscience_prediction_claim"

    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None
    assert plan["doc_retrieval_queries"] == []

    assert any(
        "pseudoscience_prediction_claim" in note
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