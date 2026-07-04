"""
Tool layer for SeismoSearch.

This module exposes deterministic tools that can be called by the planner
or the future agent pipeline.

Current tools:
- event_search_tool: search historical earthquake events from DuckDB.
- event_statistics_tool: compute basic statistics over historical events.
- safety_check_tool: detect earthquake-prediction inducement.

These tools do NOT perform earthquake prediction.
They only query already recorded earthquake catalog data or apply safety checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seismosearch.event_store import EventStore


DEFAULT_DB_PATH = Path("data/duckdb/seismosearch.duckdb")


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return an evidence-friendly compact event dictionary."""
    return {
        "event_id": event.get("event_id"),
        "source": event.get("source"),
        "source_event_id": event.get("source_event_id"),
        "event_time_utc": event.get("event_time_utc"),
        "place": event.get("place"),
        "longitude": event.get("longitude"),
        "latitude": event.get("latitude"),
        "depth_km": event.get("depth_km"),
        "magnitude": event.get("magnitude"),
        "magnitude_type": event.get("magnitude_type"),
        "event_type": event.get("event_type"),
        "status": event.get("status"),
        "is_reviewed": event.get("is_reviewed"),
        "alert": event.get("alert"),
        "tsunami": event.get("tsunami"),
        "significance": event.get("significance"),
        "source_url": event.get("source_url"),
        "detail_url": event.get("detail_url"),
        "data_quality_note": event.get("data_quality_note"),
    }


def event_search_tool(
    start_time: str | None = None,
    end_time: str | None = None,
    min_magnitude: float | None = None,
    max_magnitude: float | None = None,
    min_depth_km: float | None = None,
    max_depth_km: float | None = None,
    min_latitude: float | None = None,
    max_latitude: float | None = None,
    min_longitude: float | None = None,
    max_longitude: float | None = None,
    event_type: str | None = "earthquake",
    reviewed_only: bool | None = None,
    order_by: str = "event_time_utc",
    descending: bool = True,
    limit: int = 20,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """
    Search historical earthquake events.

    This tool is designed for catalog-style questions, such as:
    - recent M5+ earthquakes;
    - strongest events in a time range;
    - events inside a latitude / longitude bounding box.

    It returns compact event evidence, not a final natural-language answer.
    """
    tool_input = {
        "start_time": start_time,
        "end_time": end_time,
        "min_magnitude": min_magnitude,
        "max_magnitude": max_magnitude,
        "min_depth_km": min_depth_km,
        "max_depth_km": max_depth_km,
        "min_latitude": min_latitude,
        "max_latitude": max_latitude,
        "min_longitude": min_longitude,
        "max_longitude": max_longitude,
        "event_type": event_type,
        "reviewed_only": reviewed_only,
        "order_by": order_by,
        "descending": descending,
        "limit": limit,
    }

    try:
        store = EventStore(db_path=db_path)

        events = store.search_events(
            start_time=start_time,
            end_time=end_time,
            min_magnitude=min_magnitude,
            max_magnitude=max_magnitude,
            min_depth_km=min_depth_km,
            max_depth_km=max_depth_km,
            min_latitude=min_latitude,
            max_latitude=max_latitude,
            min_longitude=min_longitude,
            max_longitude=max_longitude,
            event_type=event_type,
            reviewed_only=reviewed_only,
            order_by=order_by,
            descending=descending,
            limit=limit,
        )

        compact_events = [compact_event(event) for event in events]

        return {
            "tool_name": "event_search",
            "status": "ok",
            "input": tool_input,
            "event_count": len(compact_events),
            "events": compact_events,
            "warnings": [],
        }

    except Exception as exc:
        return {
            "tool_name": "event_search",
            "status": "error",
            "input": tool_input,
            "event_count": 0,
            "events": [],
            "warnings": [],
            "error": str(exc),
        }


def event_statistics_tool(
    start_time: str | None = None,
    end_time: str | None = None,
    min_magnitude: float | None = None,
    event_type: str | None = "earthquake",
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """
    Compute basic statistics over historical earthquake events.

    This tool is designed for catalog-statistics questions, such as:
    - how many M6+ events are in the current sample;
    - what is the magnitude range;
    - what time range is covered by the local event database.

    It returns computed evidence, not a final natural-language answer.
    """
    tool_input = {
        "start_time": start_time,
        "end_time": end_time,
        "min_magnitude": min_magnitude,
        "event_type": event_type,
    }

    try:
        store = EventStore(db_path=db_path)

        event_count = store.count_events(
            start_time=start_time,
            end_time=end_time,
            min_magnitude=min_magnitude,
            event_type=event_type,
        )

        magnitude_summary = store.get_magnitude_summary(
            start_time=start_time,
            end_time=end_time,
            min_magnitude=min_magnitude,
            event_type=event_type,
        )

        database_time_range = store.get_time_range()

        warnings: list[str] = []

        if database_time_range.get("event_count") == 0:
            warnings.append("database_has_no_events")

        if start_time or end_time or min_magnitude is not None:
            warnings.append(
                "statistics_are_limited_to_the_current_local_sample_and_query_filters"
            )
        else:
            warnings.append("statistics_are_limited_to_the_current_local_sample")

        return {
            "tool_name": "event_statistics",
            "status": "ok",
            "input": tool_input,
            "statistics": {
                "event_count_matching_filters": event_count,
                "magnitude_summary": magnitude_summary,
                "database_time_range": database_time_range,
            },
            "warnings": warnings,
        }

    except Exception as exc:
        return {
            "tool_name": "event_statistics",
            "status": "error",
            "input": tool_input,
            "statistics": None,
            "warnings": [],
            "error": str(exc),
        }


def _match_keywords(query_lower: str, keywords: list[str]) -> list[str]:
    """Return keywords that appear in the lower-cased query."""
    return [
        keyword
        for keyword in keywords
        if keyword.lower() in query_lower
    ]


def safety_check_tool(query: str) -> dict[str, Any]:
    """
    Apply a first-pass safety check for earthquake prediction inducement.

    This is a lightweight rule-based placeholder.
    Later, guardrail.py should contain stronger safety logic.

    Current labels:
    - prediction_inducement:
      the query asks for future earthquake prediction or tries to infer future
      earthquakes from unreliable signals or historical activity.
    - future_specific_earthquake_prediction:
      the query directly asks whether / when future earthquakes will happen.
    - pseudoscience_prediction_claim:
      the query mentions unreliable precursor claims such as animal anomalies,
      dog barking, fish anomalies, earthquake clouds, omens, or similar claims.
    - historical_activity_prediction_claim:
      the query tries to infer future risk from recent small earthquakes,
      frequent earthquakes, or historical earthquake records.
    """
    query_lower = query.lower()

    future_prediction_keywords = [
        "预测",
        "会不会发生",
        "会地震吗",
        "什么时候地震",
        "明天会不会",
        "未来会不会",
        "今年还会不会",
        "大地震要来了吗",
        "提前知道",
        "提前预测",
        "有没有办法提前知道",
        "有没有办法知道大地震",
        "earthquake prediction",
        "will there be an earthquake",
        "when will an earthquake happen",
        "predict earthquake",
    ]

    pseudoscience_keywords = [
        "动物异常",
        "动物反常",
        "动物预兆",
        "动物前兆",
        "地震云",
        "异常现象",
        "预兆",
        "征兆",
        "地震前兆",
        "地震预兆",
        "狗一直叫",
        "狗叫",
        "鱼群异常",
        "鱼群",
        "马上要地震",
        "要地震了",
        "earthquake cloud",
        "animal anomaly",
        "dog barking",
        "fish anomaly",
        "earthquake omen",
        "earthquake precursor",
    ]

    historical_activity_prediction_keywords = [
        "小震很多",
        "最近小震",
        "小震频繁",
        "频繁地震",
        "地震频繁",
        "最近某地地震很多",
        "地震很多",
        "是不是更危险",
        "更危险",
        "根据历史地震",
        "历史地震预测",
        "历史地震",
        "下周风险",
        "未来风险",
        "风险更高",
        "大震要来了",
        "大地震要来了",
        "foreshock",
        "many small earthquakes",
        "frequent earthquakes",
        "historical earthquakes",
        "earthquake history",
    ]

    matched_future_prediction_keywords = _match_keywords(
        query_lower=query_lower,
        keywords=future_prediction_keywords,
    )

    matched_pseudoscience_keywords = _match_keywords(
        query_lower=query_lower,
        keywords=pseudoscience_keywords,
    )

    matched_historical_activity_prediction_keywords = _match_keywords(
        query_lower=query_lower,
        keywords=historical_activity_prediction_keywords,
    )

    has_earthquake_context = (
        "地震" in query
        or "小震" in query
        or "大震" in query
        or "大地震" in query
        or "earthquake" in query_lower
    )

    has_recent_activity_context = (
        "最近" in query
        or "近期" in query
        or "历史" in query
        or "频繁" in query
        or "很多" in query
        or "下周" in query
        or "future" in query_lower
        or "history" in query_lower
    )

    has_risk_escalation_context = (
        "危险" in query
        or "风险" in query
        or "大震" in query
        or "大地震" in query
        or "risk" in query_lower
        or "danger" in query_lower
    )

    inferred_historical_activity_claim = (
        has_earthquake_context
        and has_recent_activity_context
        and has_risk_escalation_context
    )

    if inferred_historical_activity_claim and not matched_historical_activity_prediction_keywords:
        matched_historical_activity_prediction_keywords.append(
            "historical_activity_risk_inference"
        )

    is_future_specific_earthquake_prediction = (
        len(matched_future_prediction_keywords) > 0
    )

    is_pseudoscience_prediction_claim = (
        len(matched_pseudoscience_keywords) > 0
    )

    is_historical_activity_prediction_claim = (
        len(matched_historical_activity_prediction_keywords) > 0
        or inferred_historical_activity_claim
    )

    is_prediction_inducement = (
        is_future_specific_earthquake_prediction
        or is_pseudoscience_prediction_claim
        or is_historical_activity_prediction_claim
    )

    matched_keywords = (
        matched_future_prediction_keywords
        + matched_pseudoscience_keywords
        + matched_historical_activity_prediction_keywords
    )

    return {
        "tool_name": "safety_check",
        "status": "ok",
        "input": {"query": query},
        "safety_labels": {
            "prediction_inducement": is_prediction_inducement,
            "future_specific_earthquake_prediction": is_future_specific_earthquake_prediction,
            "pseudoscience_prediction_claim": is_pseudoscience_prediction_claim,
            "historical_activity_prediction_claim": is_historical_activity_prediction_claim,
            "matched_keywords": matched_keywords,
            "matched_future_prediction_keywords": matched_future_prediction_keywords,
            "matched_pseudoscience_keywords": matched_pseudoscience_keywords,
            "matched_historical_activity_prediction_keywords": matched_historical_activity_prediction_keywords,
        },
        "answer_constraints": {
            "must_not_predict_future_earthquakes": is_prediction_inducement,
            "should_offer_safe_alternatives": is_prediction_inducement,
        },
    }