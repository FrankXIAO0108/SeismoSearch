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

from seismosearch.guardrail import evaluate_safety_query


PLANNER_VERSION = "deterministic_0.3.1"


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


def detect_safety_intent(
    user_query: str,
) -> tuple[str | None, list[str]]:
    """
    Detect safety intent through the unified deterministic gate.

    Planner, safety_check_tool, and Evidence Builder now share the same
    authoritative assessment.
    """
    assessment = evaluate_safety_query(user_query)
    safety_intent = assessment.get("safety_intent")
    matched_rules = assessment.get("matched_rules", [])

    notes = [
        (
            "Unified safety gate detected "
            f"{safety_intent} with rule '{rule_name}'."
        )
        for rule_name in matched_rules
    ]

    return safety_intent, notes

def has_event_intent(
    user_query: str,
    min_magnitude: float | None,
) -> bool:
    """
    Decide whether the query needs structured event tools.

    The detector combines three signals instead of relying on one exact phrase:
    catalog scope, event object, and selection/ranking intent.
    """
    if min_magnitude is not None:
        return True

    query_lower = user_query.lower()

    explanation_markers = (
        "什么是",
        "是什么意思",
        "代表什么",
        "含义",
        "区别",
        "为什么",
        "解释",
        "定义",
        "meaning",
        "difference",
        "explain",
        "definition",
        "why",
    )
    has_explanation_request = any(
        marker.lower() in query_lower
        for marker in explanation_markers
    )

    explicit_catalog_phrases = (
        "地震有哪些",
        "有哪些地震",
        "哪些地震",
        "哪些事件",
        "事件有哪些",
        "哪些记录",
        "记录有哪些",
        "列出地震",
        "列出事件",
        "列出记录",
        "查找地震",
        "查找事件",
        "查找记录",
        "查询地震",
        "查询事件",
        "查询记录",
        "找出地震",
        "找出事件",
        "找出记录",
        "发生过哪些",
        "show earthquakes",
        "list earthquakes",
        "find earthquakes",
        "show events",
        "list events",
        "find events",
    )

    if any(
        phrase.lower() in query_lower
        for phrase in explicit_catalog_phrases
    ):
        return True

    standalone_catalog_entities = (
        "地震记录",
        "事件记录",
        "earthquake records",
        "earthquake events",
    )

    if (
        not has_explanation_request
        and any(
            phrase.lower() in query_lower
            for phrase in standalone_catalog_entities
        )
    ):
        return True

    event_object_markers = (
        "地震",
        "强震",
        "事件",
        "记录",
        "earthquake",
        "event",
        "record",
    )
    has_event_object = any(
        marker.lower() in query_lower
        for marker in event_object_markers
    )

    direct_selection_actions = (
        "列出",
        "查找",
        "查询",
        "找出",
        "看看",
        "展示",
        "给我",
        "show",
        "list",
        "find",
    )
    has_direct_selection_action = any(
        marker.lower() in query_lower
        for marker in direct_selection_actions
    )

    if (
        has_event_object
        and has_direct_selection_action
        and not has_explanation_request
    ):
        return True

    recent_markers = (
        "最近",
        "最新",
        "近期",
        "recent",
        "latest",
    )

    if (
        has_event_object
        and any(
            marker.lower() in query_lower
            for marker in recent_markers
        )
        and not has_explanation_request
    ):
        return True

    catalog_scope_markers = (
        "地震目录",
        "事件目录",
        "目录",
        "本地库",
        "样例库",
        "本地样例库",
        "本地样本",
        "样本库",
        "样本",
        "样例数据",
        "当前样例数据",
        "本地数据",
        "catalog",
        "database",
        "sample database",
        "sample data",
        "local sample",
    )
    selection_markers = (
        "哪些",
        "有什么",
        "几次",
        "几条",
        "哪次",
        "哪几次",
        "列出",
        "查找",
        "查询",
        "找出",
        "看看",
        "发生",
        "最强",
        "最大",
        "最高",
        "震级最高",
        "震级最大",
        "多少",
        "which",
        "list",
        "show",
        "find",
        "strongest",
        "largest",
        "highest",
        "top",
    )

    has_catalog_scope = any(
        marker.lower() in query_lower
        for marker in catalog_scope_markers
    )
    has_selection_intent = any(
        marker.lower() in query_lower
        for marker in selection_markers
    )

    return (
        has_catalog_scope
        and has_event_object
        and has_selection_intent
    )


def has_concept_intent(user_query: str) -> bool:
    """
    Decide whether the query needs document retrieval or explanation.

    This intentionally includes relation, field-meaning, and naming language,
    not only explicit "解释/定义" wording.
    """
    query_lower = user_query.lower()

    concept_keywords = (
        "什么是",
        "是什么意思",
        "代表什么",
        "含义",
        "区别",
        "为什么",
        "解释",
        "说明",
        "原理",
        "定义",
        "不是一回事",
        "不一样",
        "如何命名",
        "怎么命名",
        "如何分类",
        "怎么分类",
        "字段含义",
        "meaning",
        "difference",
        "explain",
        "definition",
        "why",
        "describe",
        "not the same",
        "how are",
        "how is",
        "震级和烈度",
        "烈度",
        "mmi",
        "modified mercalli",
        "magnitude vs intensity",
        "seismic intensity",
        "地震深度",
        "震源深度",
        "深源地震",
        "浅源地震",
        "地表影响",
        "地表震感",
        "surface shaking",
        "earthquake depth",
        "前震",
        "主震",
        "余震",
        "foreshock",
        "mainshock",
        "aftershock",
        "reviewed",
        "automatic",
        "审核状态",
        "自动状态",
        "海啸",
        "tsunami",
        "alert",
    )

    return any(
        keyword.lower() in query_lower
        for keyword in concept_keywords
    )

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


def build_doc_retrieval_queries(
    user_query: str,
) -> tuple[list[str], list[str]]:
    """
    Build retrieval-oriented query rewrites for document retrieval.

    The original query is retained. Additional focused rewrites isolate
    concept clauses from mixed catalog-plus-concept questions.

    Existing stable rewrites are preserved for backward compatibility.
    """
    notes: list[str] = []
    queries: list[str] = []

    normalized_query = normalize_query(user_query)
    queries.append(normalized_query)

    query_lower = normalized_query.lower()

    has_magnitude = (
        "震级" in normalized_query
        or "magnitude" in query_lower
    )

    has_intensity = (
        "烈度" in normalized_query
        or "intensity" in query_lower
        or "mmi" in query_lower
        or "modified mercalli" in query_lower
    )

    if has_magnitude:
        queries.append("地震 震级 magnitude 定义")
        queries.append("earthquake magnitude definition")

    if has_intensity:
        queries.append("地震 烈度 MMI intensity 定义")
        queries.append(
            "Modified Mercalli Intensity MMI definition"
        )

    if (
        has_magnitude
        and has_intensity
    ) or "不是一回事" in normalized_query:
        queries.append("震级 烈度 区别")
        queries.append("seismic magnitude vs intensity")
        queries.append(
            "MMI 烈度 magnitude 震级 区别 地点影响"
        )
        queries.append(
            "Modified Mercalli Intensity versus earthquake magnitude"
        )

    depth_markers = (
        "深度",
        "震源深度",
        "深源地震",
        "浅源地震",
        "地表影响",
        "地表震感",
        "地面影响",
        "surface shaking",
        "surface impact",
        "depth",
        "deep earthquake",
        "shallow earthquake",
    )

    if any(
        marker.lower() in query_lower
        for marker in depth_markers
    ):
        queries.append("地震 深度 震源深度")
        queries.append("earthquake depth hypocenter depth")
        queries.append(
            "深源地震 浅源地震 震源深度 地表震感 影响因素"
        )
        queries.append(
            "earthquake focal depth surface shaking "
            "intensity distance geology buildings"
        )

    sequence_markers = (
        "前震",
        "主震",
        "余震",
        "foreshock",
        "mainshock",
        "aftershock",
        "如何命名",
        "怎么命名",
    )

    if any(
        marker.lower() in query_lower
        for marker in sequence_markers
    ):
        queries.append(
            "前震 主震 余震 定义 命名 回顾性 分类变化"
        )
        queries.append(
            "foreshock mainshock aftershock definitions "
            "retrospective classification"
        )

    review_markers = (
        "reviewed",
        "automatic",
        "审核状态",
        "自动状态",
        "人工审核",
        "自动生成",
    )

    if any(
        marker.lower() in query_lower
        for marker in review_markers
    ):
        queries.append(
            "reviewed automatic 地震事件状态 人工审核 自动生成"
        )
        queries.append(
            "earthquake event reviewed automatic status meaning"
        )

    if (
        "海啸" in normalized_query
        or "tsunami" in query_lower
    ):
        queries.append("地震 海啸 tsunami alert 含义")
        queries.append("earthquake tsunami alert meaning")
        queries.append("earthquake tsunami warning explanation")
        queries.append(
            "地震目录 tsunami flag 海啸字段 含义"
        )
        queries.append(
            "earthquake catalog tsunami flag meaning"
        )
        queries.append(
            "tsunami flag does not guarantee a tsunami"
        )

    deduplicated_queries = list(dict.fromkeys(queries))

    if len(deduplicated_queries) > 1:
        notes.append(
            "Expanded user query into focused bilingual "
            "document retrieval queries."
        )

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
