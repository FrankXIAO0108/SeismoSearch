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
from seismosearch.guardrail import evaluate_safety_query


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
    Apply the authoritative unified safety gate.

    The returned shape remains compatible with existing Evidence Pack and
    deterministic safety-generator consumers.
    """
    assessment = evaluate_safety_query(query)

    return {
        "tool_name": "safety_check",
        "status": "ok",
        "input": {"query": query},
        "gate_version": assessment.get("gate_version"),
        "safety_intent": assessment.get("safety_intent"),
        "matched_rules": assessment.get("matched_rules", []),
        "safety_labels": assessment.get("safety_labels", {}),
        "answer_constraints": assessment.get(
            "answer_constraints",
            {},
        ),
    }
