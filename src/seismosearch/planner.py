"""
Query planner for SeismoSearch.

This module performs the first version of query rewrite / query planning.

It converts a user's natural-language query into a structured plan that can
drive downstream tools.

The planner currently supports three types of query rewrite:

1. Structured tool-argument rewrite
   Example:
   "最近 M6.5 以上地震有哪些？"
   -> event_search_params={"min_magnitude": 6.5, "order_by": "event_time_utc"}

2. Retrieval query rewrite
   Example:
   "震级和烈度有什么区别？"
   -> doc_retrieval_queries=[
        "震级 烈度 区别",
        "seismic magnitude vs intensity"
      ]

3. Safety-intent normalization
   Example:
   "明天东京会不会发生大地震？"
   -> query_type="safety", safety_intent="future_specific_earthquake_prediction"

This first version is deterministic and rule-based.
It does NOT call an LLM.

Reason:
- deterministic planning is easier to test;
- errors are easier to locate;
- later LLM-based planning can be evaluated against this baseline.
"""

from __future__ import annotations

import re
from typing import Any


PLANNER_VERSION = "deterministic_0.1.0"


def normalize_query(user_query: str) -> str:
    """Normalize whitespace in user query."""
    return " ".join(user_query.strip().split())


def parse_min_magnitude(user_query: str) -> tuple[float | None, list[str]]:
    """
    Parse a minimum magnitude threshold from the query.

    Supported examples:
    - M6.5
    - M 6.5
    - M6+
    - 6.5级以上
    - 6.5 级以上
    - magnitude 6.5
    - magnitude >= 6.5

    This function treats parsed magnitude as a lower-bound threshold because
    most catalog queries ask for "M6+" or "M6.5 以上" style filtering.
    """
    notes: list[str] = []

    patterns = [
        r"\b[Mm]\s*(\d+(?:\.\d+)?)\s*\+?",
        r"(\d+(?:\.\d+)?)\s*级\s*(?:以上|及以上|\+)?",
        r"震级\s*(?:大于等于|不低于|至少|>=|以上)?\s*(\d+(?:\.\d+)?)",
        r"magnitude\s*(?:>=|above|over|at\s+least)?\s*(\d+(?:\.\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, user_query, flags=re.IGNORECASE)
        if match:
            magnitude = float(match.group(1))
            notes.append(f"Parsed magnitude threshold as min_magnitude={magnitude}.")
            return magnitude, notes

    return None, notes


def parse_year_range(user_query: str) -> tuple[str | None, str | None, list[str]]:
    """
    Parse year constraints from the query.

    Supported examples:
    - 2025 年
    - 2024
    - 2024 到 2025

    Output uses ISO-like strings accepted by DuckDB comparisons.
    """
    notes: list[str] = []

    years = re.findall(r"(19\d{2}|20\d{2})\s*年?", user_query)

    if not years:
        return None, None, notes

    unique_years = sorted({int(year) for year in years})

    start_year = unique_years[0]
    end_year = unique_years[-1]

    start_time = f"{start_year}-01-01T00:00:00"
    end_time = f"{end_year}-12-31T23:59:59"

    if start_year == end_year:
        notes.append(f"Parsed year {start_year} as full-year time range.")
    else:
        notes.append(
            f"Parsed year range {start_year}-{end_year} as full-year time range."
        )

    return start_time, end_time, notes


def detect_safety_intent(user_query: str) -> tuple[str | None, list[str]]:
    """
    Detect future-specific earthquake prediction requests.

    This is safety-intent normalization, not factual answering.

    If triggered, downstream tools should NOT use historical event search to
    imply a future earthquake prediction.
    """
    notes: list[str] = []

    safety_patterns = [
        "明天.*会不会.*地震",
        "明天.*会不会发生.*地震",
        "未来.*会不会.*地震",
        "什么时候.*地震",
        "会不会发生.*大地震",
        "大地震.*要来了吗",
        "预测.*地震",
        "will there be an earthquake",
        "when will an earthquake happen",
        "earthquake prediction",
    ]

    for pattern in safety_patterns:
        if re.search(pattern, user_query, flags=re.IGNORECASE):
            safety_intent = "future_specific_earthquake_prediction"
            notes.append(
                f"Detected safety intent: {safety_intent} with pattern '{pattern}'."
            )
            return safety_intent, notes

    return None, notes


def has_event_intent(user_query: str, min_magnitude: float | None) -> bool:
    """
    Decide whether the query likely needs structured event tools.

    This is intentionally conservative.
    Concept-only questions such as "震级和烈度有什么区别？" should not trigger
    event search just because they contain seismology terms.
    """
    event_keywords = [
        "地震有哪些",
        "地震记录",
        "地震事件",
        "最近",
        "最新",
        "列出",
        "查询",
        "发生过",
        "earthquakes",
        "earthquake events",
        "recent earthquakes",
        "latest earthquakes",
        "show earthquakes",
    ]

    if min_magnitude is not None:
        return True

    query_lower = user_query.lower()

    return any(keyword.lower() in query_lower for keyword in event_keywords)


def has_concept_intent(user_query: str) -> bool:
    """Decide whether the query likely needs document retrieval or explanation."""
    concept_keywords = [
        "什么是",
        "是什么意思",
        "区别",
        "为什么",
        "解释",
        "原理",
        "定义",
        "meaning",
        "difference",
        "explain",
        "definition",
        "why",
        "震级和烈度",
        "烈度",
        "magnitude vs intensity",
        "seismic intensity",
    ]

    query_lower = user_query.lower()

    return any(keyword.lower() in query_lower for keyword in concept_keywords)


def infer_order_by(user_query: str) -> tuple[str, bool, list[str]]:
    """
    Infer event search ordering.

    Examples:
    - 最近 / 最新 -> event_time_utc descending
    - 最大 / 最强 / 震级最高 -> magnitude descending
    """
    notes: list[str] = []

    query_lower = user_query.lower()

    strongest_keywords = [
        "最大",
        "最强",
        "震级最高",
        "strongest",
        "largest",
        "highest magnitude",
    ]

    recent_keywords = [
        "最近",
        "最新",
        "recent",
        "latest",
    ]

    if any(keyword.lower() in query_lower for keyword in strongest_keywords):
        notes.append("Parsed ordering intent as magnitude descending.")
        return "magnitude", True, notes

    if any(keyword.lower() in query_lower for keyword in recent_keywords):
        notes.append("Parsed ordering intent as event_time_utc descending.")
        return "event_time_utc", True, notes

    notes.append("No explicit ordering intent found; default to event_time_utc descending.")
    return "event_time_utc", True, notes


def build_event_params(
    user_query: str,
    min_magnitude: float | None,
    start_time: str | None,
    end_time: str | None,
    default_limit: int,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Build event_search_params and event_statistics_params."""
    notes: list[str] = []

    order_by, descending, order_notes = infer_order_by(user_query)
    notes.extend(order_notes)

    event_search_params = {
        "start_time": start_time,
        "end_time": end_time,
        "min_magnitude": min_magnitude,
        "event_type": "earthquake",
        "order_by": order_by,
        "descending": descending,
        "limit": default_limit,
    }

    event_statistics_params = {
        "start_time": start_time,
        "end_time": end_time,
        "min_magnitude": min_magnitude,
        "event_type": "earthquake",
    }

    return event_search_params, event_statistics_params, notes


def build_doc_retrieval_queries(user_query: str) -> tuple[list[str], list[str]]:
    """
    Build retrieval-oriented query rewrites for future doc_retriever.py.

    The first query remains close to the user query.
    Additional queries expand domain terms in Chinese and English.
    """
    notes: list[str] = []
    queries: list[str] = []

    normalized_query = normalize_query(user_query)
    queries.append(normalized_query)

    query_lower = user_query.lower()

    if "震级" in user_query or "magnitude" in query_lower:
        queries.append("地震 震级 magnitude 定义")
        queries.append("earthquake magnitude definition")

    if "烈度" in user_query or "intensity" in query_lower:
        queries.append("地震 烈度 intensity 定义")
        queries.append("seismic intensity definition")

    if "震级" in user_query and "烈度" in user_query:
        queries.append("震级 烈度 区别")
        queries.append("seismic magnitude vs intensity")

    if "海啸" in user_query or "tsunami" in query_lower:
        queries.append("earthquake tsunami warning explanation")

    # Remove duplicates while preserving order.
    deduplicated_queries = list(dict.fromkeys(queries))

    if len(deduplicated_queries) > 1:
        notes.append("Expanded user query into multiple document retrieval queries.")

    return deduplicated_queries, notes


def infer_query_type(
    safety_intent: str | None,
    event_intent: bool,
    concept_intent: bool,
) -> str:
    """Infer query type from detected intents."""
    if safety_intent is not None:
        return "safety"

    if event_intent and concept_intent:
        return "mixed"

    if event_intent:
        return "catalog"

    if concept_intent:
        return "concept"

    return "concept"


def plan_query(
    user_query: str,
    default_limit: int = 20,
) -> dict[str, Any]:
    """
    Rewrite a natural-language user query into a structured execution plan.

    The returned plan is the interface between user intent and downstream tools.
    """
    normalized_query = normalize_query(user_query)

    rewrite_notes: list[str] = []
    warnings: list[str] = []

    if not normalized_query:
        return {
            "planner_version": PLANNER_VERSION,
            "original_query": user_query,
            "normalized_query": normalized_query,
            "query_type": "concept",
            "event_search_params": None,
            "event_statistics_params": None,
            "doc_retrieval_queries": [],
            "safety_intent": None,
            "rewrite_notes": [],
            "warnings": ["empty_query"],
        }

    safety_intent, safety_notes = detect_safety_intent(normalized_query)
    rewrite_notes.extend(safety_notes)

    min_magnitude, magnitude_notes = parse_min_magnitude(normalized_query)
    rewrite_notes.extend(magnitude_notes)

    start_time, end_time, time_notes = parse_year_range(normalized_query)
    rewrite_notes.extend(time_notes)

    event_intent = has_event_intent(normalized_query, min_magnitude)
    concept_intent = has_concept_intent(normalized_query)

    query_type = infer_query_type(
        safety_intent=safety_intent,
        event_intent=event_intent,
        concept_intent=concept_intent,
    )

    event_search_params: dict[str, Any] | None = None
    event_statistics_params: dict[str, Any] | None = None
    doc_retrieval_queries: list[str] = []

    # Safety questions should not trigger historical event search by default.
    if query_type in {"catalog", "mixed"}:
        event_search_params, event_statistics_params, event_notes = build_event_params(
            user_query=normalized_query,
            min_magnitude=min_magnitude,
            start_time=start_time,
            end_time=end_time,
            default_limit=default_limit,
        )
        rewrite_notes.extend(event_notes)

    if query_type in {"concept", "mixed"}:
        doc_retrieval_queries, doc_notes = build_doc_retrieval_queries(normalized_query)
        rewrite_notes.extend(doc_notes)

    if query_type == "concept" and not doc_retrieval_queries:
        warnings.append("concept_query_without_doc_retrieval_queries")

    if query_type in {"catalog", "mixed"} and min_magnitude is None:
        warnings.append("catalog_query_without_magnitude_filter")

    if "东京" in normalized_query or "japan" in normalized_query.lower():
        warnings.append(
            "location_parsing_not_implemented_yet; no latitude_longitude_bbox_applied"
        )

    return {
        "planner_version": PLANNER_VERSION,
        "original_query": user_query,
        "normalized_query": normalized_query,
        "query_type": query_type,
        "event_search_params": event_search_params,
        "event_statistics_params": event_statistics_params,
        "doc_retrieval_queries": doc_retrieval_queries,
        "safety_intent": safety_intent,
        "rewrite_notes": rewrite_notes,
        "warnings": warnings,
    }