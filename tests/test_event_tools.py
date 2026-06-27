"""
Tests for SeismoSearch tool layer.

These tests verify that the public tool functions behave consistently
with the DuckDB-backed event store.

They focus on:
- event search output shape;
- event statistics filter consistency;
- safety check behavior for prediction-inducing questions.
"""

from __future__ import annotations

from pathlib import Path

from seismosearch.tools import (
    event_search_tool,
    event_statistics_tool,
    safety_check_tool,
)


DB_PATH = Path("data/duckdb/seismosearch.duckdb")


def test_event_search_tool_returns_compact_events() -> None:
    """event_search_tool should return compact event evidence."""
    result = event_search_tool(
        min_magnitude=6.5,
        order_by="magnitude",
        limit=2,
        db_path=DB_PATH,
    )

    # The tool call itself should succeed.
    assert result["status"] == "ok"

    # The current sample has at least two M6.5+ events.
    assert result["event_count"] == 2

    # The returned payload should contain compact event dictionaries.
    events = result["events"]
    assert isinstance(events, list)
    assert len(events) == 2

    # Each compact event should contain evidence-facing fields.
    first_event = events[0]
    assert "event_id" in first_event
    assert "event_time_utc" in first_event
    assert "magnitude" in first_event
    assert "magnitude_type" in first_event
    assert "place" in first_event
    assert "source_url" in first_event

    # Since results are ordered by magnitude descending, the first event
    # should be at least as large as the second event.
    assert events[0]["magnitude"] >= events[1]["magnitude"]


def test_event_statistics_tool_uses_consistent_min_magnitude_filter() -> None:
    """event_statistics_tool should apply min_magnitude to all statistics."""
    result = event_statistics_tool(
        min_magnitude=6.0,
        db_path=DB_PATH,
    )

    # The tool call itself should succeed.
    assert result["status"] == "ok"

    statistics = result["statistics"]
    assert statistics is not None

    event_count_matching_filters = statistics["event_count_matching_filters"]
    magnitude_summary = statistics["magnitude_summary"]

    # This is the bug we just fixed:
    # count_events and get_magnitude_summary must use the same min_magnitude filter.
    assert event_count_matching_filters == magnitude_summary["event_count"]

    # Since the query asks for M6.0+, the minimum magnitude in the summary
    # must not be below 6.0.
    assert magnitude_summary["min_magnitude"] >= 6.0

    # The local database still contains 1000 total sample events.
    assert statistics["database_time_range"]["event_count"] == 1000


def test_safety_check_tool_detects_prediction_inducement() -> None:
    """safety_check_tool should flag future earthquake prediction questions."""
    result = safety_check_tool("明天东京会不会发生大地震？")

    # The safety check should succeed.
    assert result["status"] == "ok"

    labels = result["safety_labels"]
    constraints = result["answer_constraints"]

    # This query is asking about a future specific earthquake,
    # so it should be treated as prediction inducement.
    assert labels["prediction_inducement"] is True

    # The tool should produce answer constraints for the generator / guardrail.
    assert constraints["must_not_predict_future_earthquakes"] is True
    assert constraints["should_offer_safe_alternatives"] is True


def test_safety_check_tool_allows_historical_catalog_question() -> None:
    """safety_check_tool should not flag ordinary historical catalog queries."""
    result = safety_check_tool("2025 年 12 月 M6 以上地震有哪些？")

    # The safety check should succeed.
    assert result["status"] == "ok"

    labels = result["safety_labels"]
    constraints = result["answer_constraints"]

    # This is a historical catalog query, not a future prediction question.
    assert labels["prediction_inducement"] is False
    assert constraints["must_not_predict_future_earthquakes"] is False