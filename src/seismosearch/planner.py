"""
Query planner for SeismoSearch.

This module converts a user's natural-language query into a deterministic
execution plan.

The planner currently supports:
- catalog query planning;
- concept query planning;
- mixed query planning;
- safety query planning.

This first version is deterministic and rule-based.
It does NOT call an LLM.
"""

from __future__ import annotations

import re
from typing import Any


PLANNER_VERSION = "deterministic_0.1.0"


def normalize_query(user_query: str) -> str:
    """Normalize whitespace in a user query."""
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
    - 震级大于等于 6
    - magnitude 6.5
    - magnitude >= 6.5
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
    Detect unsafe earthquake-prediction or pseudoscience-prediction requests.

    This is safety-intent normalization, not factual answering.

    If triggered, downstream tools should NOT use historical event search to
    imply a future earthquake prediction.

    Supported safety intents:
    - future_specific_earthquake_prediction:
      direct requests about whether / when a future earthquake will happen.
    - pseudoscience_prediction_claim:
      requests that infer future earthquakes from unreliable signs, such as
      animal anomalies, dog barking, fish anomalies, earthquake clouds, or
      earthquake-omen claims.
    - historical_activity_prediction_claim:
      requests that infer future large earthquakes or future risk from recent
      small earthquakes, frequent earthquakes, or historical earthquake records.
    """
    notes: list[str] = []

    normalized = normalize_query(user_query)

    historical_activity_prediction_patterns = [
        r"小震.*大震",
        r"小震.*大地震",
        r"小震很多.*大震",
        r"小震很多.*大地震",
        r"最近小震.*大震",
        r"最近小震.*大地震",
        r"频繁地震.*大震",
        r"频繁地震.*大地震",
        r"地震频繁.*大震",
        r"地震频繁.*大地震",
        r"最近.*地震.*大震",
        r"最近.*地震.*大地震",
        r"是不是说明.*大震",
        r"是不是说明.*大地震",
        r"说明.*大震.*要来",
        r"说明.*大地震.*要来",
        r"大震要来了",
        r"大地震要来了",
        r"根据.*历史地震.*预测",
        r"历史地震.*预测.*风险",
        r"历史地震.*预测.*下周",
        r"历史地震.*预测.*未来",
        r"历史地震.*未来.*风险",
        r"地震.*很多.*更危险",
        r"地震.*很多.*危险",
        r"地震.*很多.*风险",
        r"最近.*地震.*很多.*更危险",
        r"最近.*地震.*很多.*危险",
        r"最近.*地震.*很多.*风险",
        r"近期.*地震.*很多.*更危险",
        r"近期.*地震.*很多.*风险",
        r"地震.*频繁.*更危险",
        r"地震.*频繁.*风险",
        r"foreshock",
        r"small earthquakes.*big earthquake",
        r"many small earthquakes",
        r"frequent earthquakes.*big earthquake",
        r"historical earthquakes.*predict",
        r"earthquake history.*predict",
    ]

    for pattern in historical_activity_prediction_patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            safety_intent = "historical_activity_prediction_claim"
            notes.append(
                f"Detected safety intent: {safety_intent} with pattern '{pattern}'."
            )
            return safety_intent, notes

    pseudoscience_patterns = [
        r"动物异常.*地震",
        r"动物反常.*地震",
        r"动物.*异常.*地震",
        r"动物.*反常.*地震",
        r"动物.*预兆.*地震",
        r"动物.*前兆.*地震",
        r"狗.*叫.*地震",
        r"狗.*叫.*前兆",
        r"狗.*地震前兆",
        r"猫.*异常.*地震",
        r"猫.*反常.*地震",
        r"鱼群.*异常.*地震",
        r"鱼群异常.*地震",
        r"鱼群.*要地震",
        r"地震云.*地震",
        r"地震云.*说明",
        r"地震云.*预示",
        r"异常现象.*地震",
        r"地震前兆",
        r"地震预兆",
        r"预兆.*地震",
        r"征兆.*地震",
        r"是不是说明.*要地震",
        r"是不是说明.*马上.*地震",
        r"说明.*马上.*地震",
        r"马上要地震",
        r"要地震了",
        r"earthquake cloud",
        r"animal.*earthquake",
        r"dog.*earthquake",
        r"fish.*earthquake",
        r"earthquake omen",
        r"earthquake precursor",
    ]

    for pattern in pseudoscience_patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            safety_intent = "pseudoscience_prediction_claim"
            notes.append(
                f"Detected safety intent: {safety_intent} with pattern '{pattern}'."
            )
            return safety_intent, notes

    future_prediction_patterns = [
        r"明天.*会不会.*地震",
        r"明天.*会不会发生.*地震",
        r"未来.*会不会.*地震",
        r"什么时候.*地震",
        r"会不会发生.*大地震",
        r"会不会.*大地震",
        r"预测.*地震",
        r"预测.*大地震",
        r"今年.*还会不会.*地震",
        r"今年.*还会不会.*大地震",
        r"今年.*会不会.*大地震",
        r"提前.*知道.*地震",
        r"提前.*知道.*大地震",
        r"提前.*预测.*地震",
        r"提前.*预测.*大地震",
        r"有没有办法.*提前.*知道.*地震",
        r"有没有办法.*提前.*知道.*大地震",
        r"有没有办法.*知道.*大地震",
        r"能不能.*提前.*知道.*地震",
        r"能不能.*提前.*知道.*大地震",
        r"will there be an earthquake",
        r"when will an earthquake happen",
        r"earthquake prediction",
        r"predict.*earthquake",
    ]

    for pattern in future_prediction_patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            safety_intent = "future_specific_earthquake_prediction"
            notes.append(
                f"Detected safety intent: {safety_intent} with pattern '{pattern}'."
            )
            return safety_intent, notes

    return None, notes


def has_event_intent(user_query: str, min_magnitude: float | None) -> bool:
    """
    Decide whether the query likely needs structured event tools.

    Concept-only questions should not trigger event search just because they
    contain seismology terms.
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
        "地震深度",
        "震源深度",
        "海啸",
        "tsunami",
        "alert",
        "magnitude vs intensity",
        "seismic intensity",
        "earthquake depth",
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
        "最高震级",
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
    Build retrieval-oriented query rewrites for doc_retriever.py.

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

    if "深度" in user_query or "depth" in query_lower:
        queries.append("地震 深度 震源深度")
        queries.append("earthquake depth hypocenter depth")

    if "海啸" in user_query or "tsunami" in query_lower:
        queries.append("地震 海啸 tsunami alert 含义")
        queries.append("earthquake tsunami alert meaning")
        queries.append("earthquake tsunami warning explanation")

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

    if "东京" in normalized_query or "日本" in normalized_query or "japan" in normalized_query.lower():
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
