"""
Evidence builder for SeismoSearch.

This module converts tool outputs into a structured Evidence Pack.

The Evidence Pack is the controlled context passed to the future answer
generator. It separates:
- user query metadata;
- router output;
- tool call records;
- event evidence;
- computed evidence;
- safety evidence;
- answer constraints.

This module does NOT generate the final answer.
It only prepares evidence for grounded answer generation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from seismosearch.tools import (
    event_search_tool,
    event_statistics_tool,
    safety_check_tool,
)


SCHEMA_VERSION = "0.1.0"


def utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_query_id(prefix: str = "query") -> str:
    """Create a short unique query ID for tracing."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def infer_query_type(user_query: str, safety_result: dict[str, Any]) -> str:
    """
    Infer a coarse query type.

    This is a lightweight placeholder before we implement router.py.

    Current query types:
    - safety: future earthquake prediction or unsafe request;
    - catalog: structured historical earthquake event query;
    - concept: concept explanation query;
    - mixed: event query plus concept explanation.

    The current heuristic is intentionally simple and should later be replaced
    by a real Query Router.
    """
    safety_labels = safety_result.get("safety_labels", {})
    prediction_inducement = safety_labels.get("prediction_inducement", False)

    # Safety has priority over other query types.
    if prediction_inducement:
        return "safety"

    query_lower = user_query.lower()

    event_keywords = [
        "地震",
        "earthquake",
        "magnitude",
        "震级",
        "m",
        "m6",
        "m7",
        "最近",
        "2025",
        "2024",
    ]

    concept_keywords = [
        "什么是",
        "区别",
        "解释",
        "为什么",
        "meaning",
        "difference",
        "explain",
        "震级和烈度",
        "烈度",
    ]

    has_event_intent = any(keyword.lower() in query_lower for keyword in event_keywords)
    has_concept_intent = any(keyword.lower() in query_lower for keyword in concept_keywords)

    # If the query asks for both events and explanation, treat it as mixed.
    if has_event_intent and has_concept_intent:
        return "mixed"

    if has_event_intent:
        return "catalog"

    if has_concept_intent:
        return "concept"

    # Default to concept because pure free-form questions are more likely to
    # need document retrieval later.
    return "concept"


def build_tool_call_record(
    tool_name: str,
    tool_result: dict[str, Any],
) -> dict[str, Any]:
    """Convert a tool result into a traceable tool call record."""
    return {
        "tool_name": tool_name,
        "status": tool_result.get("status"),
        "input": tool_result.get("input"),
        "error": tool_result.get("error"),
    }


def build_event_evidence(search_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract event evidence records from event_search_tool output."""
    if search_result is None:
        return []

    if search_result.get("status") != "ok":
        return []

    events = search_result.get("events", [])

    event_evidence: list[dict[str, Any]] = []

    for rank, event in enumerate(events, start=1):
        # Keep a stable evidence_id so generator and evaluator can cite it.
        evidence_item = {
            "evidence_id": f"event_{rank:03d}",
            "evidence_type": "earthquake_event",
            "rank": rank,
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
        event_evidence.append(evidence_item)

    return event_evidence


def build_computed_evidence(
    statistics_result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Extract computed evidence from event_statistics_tool output."""
    if statistics_result is None:
        return []

    if statistics_result.get("status") != "ok":
        return []

    statistics = statistics_result.get("statistics")

    if statistics is None:
        return []

    return [
        {
            "evidence_id": "computed_001",
            "evidence_type": "event_statistics",
            "statistics": statistics,
            "warnings": statistics_result.get("warnings", []),
        }
    ]


def build_safety_evidence(safety_result: dict[str, Any]) -> dict[str, Any]:
    """Extract safety evidence from safety_check_tool output."""
    return {
        "tool_name": safety_result.get("tool_name"),
        "status": safety_result.get("status"),
        "safety_labels": safety_result.get("safety_labels", {}),
        "answer_constraints": safety_result.get("answer_constraints", {}),
    }


def build_answer_constraints(
    query_type: str,
    safety_result: dict[str, Any],
    has_event_evidence: bool,
    has_doc_evidence: bool,
) -> dict[str, Any]:
    """
    Build answer constraints for the future generator.

    These constraints tell the generator what it must or must not do.
    """
    safety_constraints = safety_result.get("answer_constraints", {})

    must_not_predict = bool(
        safety_constraints.get("must_not_predict_future_earthquakes", False)
    )

    constraints = {
        "must_use_evidence_pack": True,
        "must_not_predict_future_earthquakes": must_not_predict,
        "should_offer_safe_alternatives": bool(
            safety_constraints.get("should_offer_safe_alternatives", False)
        ),
        "must_cite_event_evidence_when_using_event_facts": has_event_evidence,
        "must_cite_doc_evidence_when_using_document_facts": has_doc_evidence,
        "should_state_sample_limitations": query_type in {"catalog", "mixed"},
        "should_not_claim_full_global_coverage": True,
    }

    if query_type == "safety":
        constraints["response_mode"] = "safe_refusal_with_alternatives"
    elif query_type == "catalog":
        constraints["response_mode"] = "catalog_answer"
    elif query_type == "mixed":
        constraints["response_mode"] = "mixed_event_and_concept_answer"
    else:
        constraints["response_mode"] = "concept_answer"

    return constraints


def build_evidence_pack(
    user_query: str,
    query_id: str | None = None,
    query_type: str | None = None,
    event_search_params: dict[str, Any] | None = None,
    event_statistics_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build an Evidence Pack for one user query.

    Parameters:
    - user_query: original user question;
    - query_id: optional external query ID;
    - query_type: optional pre-routed query type;
    - event_search_params: optional parameters for event_search_tool;
    - event_statistics_params: optional parameters for event_statistics_tool.

    This function currently supports event and safety evidence.
    Document evidence will be added after doc_retriever.py is implemented.
    """
    query_id = query_id or make_query_id()

    # Always run safety check first.
    safety_result = safety_check_tool(user_query)

    # Use provided query_type if available; otherwise use placeholder inference.
    resolved_query_type = query_type or infer_query_type(user_query, safety_result)

    router_output = {
        "query_type": resolved_query_type,
        "router_version": "heuristic_0.1.0",
        "notes": [
            "This router output is produced by a lightweight heuristic placeholder."
        ],
    }

    tool_calls: list[dict[str, Any]] = [
        build_tool_call_record("safety_check", safety_result)
    ]

    search_result: dict[str, Any] | None = None
    statistics_result: dict[str, Any] | None = None

    warnings: list[str] = []

    # Safety questions should not trigger event search by default.
    # They should first produce answer constraints.
    should_run_event_tools = resolved_query_type in {"catalog", "mixed"}

    if should_run_event_tools:
        search_params = event_search_params or {}
        statistics_params = event_statistics_params or {}

        search_result = event_search_tool(**search_params)
        statistics_result = event_statistics_tool(**statistics_params)

        tool_calls.append(build_tool_call_record("event_search", search_result))
        tool_calls.append(build_tool_call_record("event_statistics", statistics_result))

        warnings.extend(search_result.get("warnings", []))
        warnings.extend(statistics_result.get("warnings", []))

    if resolved_query_type in {"concept", "mixed"}:
        warnings.append("doc_retrieval_not_implemented_yet")

    event_evidence = build_event_evidence(search_result)
    computed_evidence = build_computed_evidence(statistics_result)

    # Document evidence is intentionally empty until doc_retriever.py is implemented.
    doc_evidence: list[dict[str, Any]] = []

    safety_evidence = build_safety_evidence(safety_result)

    answer_constraints = build_answer_constraints(
        query_type=resolved_query_type,
        safety_result=safety_result,
        has_event_evidence=len(event_evidence) > 0,
        has_doc_evidence=len(doc_evidence) > 0,
    )

    evidence_pack = {
        "schema_version": SCHEMA_VERSION,
        "query_id": query_id,
        "user_query": user_query,
        "query_type": resolved_query_type,
        "created_at_utc": utc_now_iso(),
        "router_output": router_output,
        "tool_calls": tool_calls,
        "event_evidence": event_evidence,
        "doc_evidence": doc_evidence,
        "computed_evidence": computed_evidence,
        "safety_evidence": safety_evidence,
        "answer_constraints": answer_constraints,
        "warnings": warnings,
    }

    return evidence_pack