"""
Unified deterministic safety gate for SeismoSearch.

This module is the single source of truth for earthquake-prediction,
historical-activity inference, and pseudoscience routing.

The public output keeps the original safety-label contract:
- matched keyword fields contain actual query phrases;
- planner, safety tool, and Evidence Builder consume one assessment;
- safety intent takes priority over downstream retrieval.
"""

from __future__ import annotations

from typing import Any


SAFETY_GATE_VERSION = "deterministic_safety_gate_0.2.0"


# 直接的未来具体地震预测表达。
DIRECT_FUTURE_PREDICTION_KEYWORDS: tuple[str, ...] = (
    "会不会发生",
    "会地震吗",
    "什么时候地震",
    "大地震要来了吗",
    "提前知道",
    "提前预测",
    "有没有办法提前知道",
    "有没有办法知道大地震",
    "哪里会地震",
    "具体概率",
    "具体日期",
    "概率和日期",
    "will there be an earthquake",
    "when will an earthquake happen",
    "predict earthquake",
    "specific earthquake date",
)


# 表示用户正在询问未来时间点。
FUTURE_TIME_KEYWORDS: tuple[str, ...] = (
    "明天",
    "今晚",
    "后天",
    "下周",
    "下个月",
    "未来",
    "今年还会",
    "几天内",
    "三天内",
    "一周内",
    "一个月内",
    "tomorrow",
    "tonight",
    "next week",
    "next month",
    "in the future",
)


# 表示用户要求系统给出判断、时间或概率。
PREDICTION_REQUEST_KEYWORDS: tuple[str, ...] = (
    "会不会",
    "是否会",
    "是不是会",
    "会发生",
    "预测",
    "判断",
    "告诉我",
    "给出",
    "能不能",
    "可不可以",
    "什么时候",
    "哪里会",
    "哪天",
    "概率",
    "日期",
    "will there be",
    "when will",
    "predict",
    "probability",
)


# 伪科学前兆表达。这里保存实际文本，兼容原有评测契约。
PSEUDOSCIENCE_KEYWORDS: tuple[str, ...] = (
    "动物异常",
    "动物反常",
    "动物预兆",
    "动物前兆",
    "狗一直叫",
    "狗叫",
    "鱼群异常",
    "鱼群",
    "地震云",
    "地震前兆",
    "地震预兆",
    "异常现象",
    "预兆",
    "征兆",
    "earthquake cloud",
    "animal anomaly",
    "dog barking",
    "fish anomaly",
    "earthquake omen",
    "earthquake precursor",
)


# 用历史活动、小震或频繁事件推断未来风险的表达。
HISTORICAL_ACTIVITY_KEYWORDS: tuple[str, ...] = (
    "小震很多",
    "最近小震",
    "小震频繁",
    "频繁地震",
    "地震频繁",
    "最近某地地震很多",
    "地震很多",
    "根据历史地震",
    "历史地震预测",
    "下周风险",
    "未来风险",
    "风险更高",
    "大震要来了",
    "大地震要来了",
    "many small earthquakes",
    "frequent earthquakes",
    "historical earthquakes",
    "earthquake history",
)


RECENT_OR_HISTORICAL_MARKERS: tuple[str, ...] = (
    "历史",
    "最近",
    "近期",
    "小震",
    "频繁",
    "很多",
    "活动增多",
    "historical",
    "recent",
    "frequent",
)


RISK_ESCALATION_MARKERS: tuple[str, ...] = (
    "大震",
    "大地震",
    "更危险",
    "风险",
    "要来了",
    "肯定有",
    "肯定会",
    "说明",
    "所以",
    "是不是",
    "big earthquake",
    "higher risk",
    "more dangerous",
)


def normalize_query(query: str) -> str:
    """Normalize whitespace while preserving query wording."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")

    return " ".join(query.strip().split())


def match_keywords(
    query_lower: str,
    keywords: tuple[str, ...],
) -> list[str]:
    """Return actual matched keyword phrases without duplicates."""
    matched: list[str] = []

    for keyword in keywords:
        if (
            keyword.lower() in query_lower
            and keyword not in matched
        ):
            matched.append(keyword)

    return matched


def contains_any(
    query_lower: str,
    keywords: tuple[str, ...],
) -> bool:
    """Return whether at least one keyword occurs in the query."""
    return any(
        keyword.lower() in query_lower
        for keyword in keywords
    )


def unique_in_order(values: list[str]) -> list[str]:
    """Remove duplicates while preserving first appearance order."""
    result: list[str] = []

    for value in values:
        if value not in result:
            result.append(value)

    return result


def evaluate_safety_query(query: str) -> dict[str, Any]:
    """
    Evaluate one query before Planner and tool routing.

    Safety-intent priority:
    1. pseudoscience prediction claim;
    2. historical-activity prediction claim;
    3. future-specific earthquake prediction.

    Historical activity has priority over generic future language because a
    query such as "根据历史地震预测下周风险" should be diagnosed according
    to its unsafe reasoning source, not merely its future time expression.
    """
    normalized_query = normalize_query(query)
    query_lower = normalized_query.lower()

    has_earthquake_context = contains_any(
        query_lower,
        (
            "地震",
            "小震",
            "大震",
            "震级",
            "m5",
            "m6",
            "m7",
            "m8",
            "earthquake",
        ),
    )

    matched_direct_future = match_keywords(
        query_lower,
        DIRECT_FUTURE_PREDICTION_KEYWORDS,
    )
    matched_future_time = match_keywords(
        query_lower,
        FUTURE_TIME_KEYWORDS,
    )
    matched_prediction_request = match_keywords(
        query_lower,
        PREDICTION_REQUEST_KEYWORDS,
    )
    matched_pseudoscience = match_keywords(
        query_lower,
        PSEUDOSCIENCE_KEYWORDS,
    )
    matched_historical = match_keywords(
        query_lower,
        HISTORICAL_ACTIVITY_KEYWORDS,
    )

    has_recent_or_historical_context = contains_any(
        query_lower,
        RECENT_OR_HISTORICAL_MARKERS,
    )
    has_risk_escalation_context = contains_any(
        query_lower,
        RISK_ESCALATION_MARKERS,
    )

    raw_pseudoscience_claim = bool(
        matched_pseudoscience
    )

    inferred_historical_claim = (
        has_earthquake_context
        and has_recent_or_historical_context
        and has_risk_escalation_context
    )

    raw_historical_activity_claim = (
        bool(matched_historical)
        or inferred_historical_claim
    )

    raw_future_specific_claim = (
        has_earthquake_context
        and (
            bool(matched_direct_future)
            or (
                bool(matched_future_time)
                and bool(matched_prediction_request)
            )
        )
    )

    # 使用互斥的最终 subtype，避免同一查询同时被标为多个主类别。
    if raw_pseudoscience_claim:
        safety_intent = (
            "pseudoscience_prediction_claim"
        )
    elif raw_historical_activity_claim:
        safety_intent = (
            "historical_activity_prediction_claim"
        )
    elif raw_future_specific_claim:
        safety_intent = (
            "future_specific_earthquake_prediction"
        )
    else:
        safety_intent = None

    is_pseudoscience_claim = (
        safety_intent
        == "pseudoscience_prediction_claim"
    )
    is_historical_activity_claim = (
        safety_intent
        == "historical_activity_prediction_claim"
    )
    is_future_specific_claim = (
        safety_intent
        == "future_specific_earthquake_prediction"
    )

    # 若历史活动由组合语义推断命中，但没有现成完整短语，
    # 记录能够解释判断的实际查询片段。
    if (
        is_historical_activity_claim
        and not matched_historical
    ):
        inferred_matches = match_keywords(
            query_lower,
            (
                "历史",
                "最近",
                "近期",
                "小震",
                "频繁",
                "很多",
                "地震多",
                "更危险",
                "风险",
                "大震",
                "大地震",
                "所以",
                "说明",
                "是不是",
            ),
        )
        matched_historical.extend(
            inferred_matches
        )

    matched_future = unique_in_order(
        matched_direct_future
        + matched_future_time
        + matched_prediction_request
    )
    matched_pseudoscience = unique_in_order(
        matched_pseudoscience
    )
    matched_historical = unique_in_order(
        matched_historical
    )

    matched_keywords = unique_in_order(
        matched_future
        + matched_pseudoscience
        + matched_historical
    )

    matched_rules: list[str] = []

    if is_pseudoscience_claim:
        matched_rules.append(
            "pseudoscience_prediction_claim"
        )
    if is_historical_activity_claim:
        matched_rules.append(
            "historical_activity_prediction_claim"
        )
    if is_future_specific_claim:
        matched_rules.append(
            "future_specific_earthquake_prediction"
        )

    prediction_inducement = (
        safety_intent is not None
    )

    return {
        "gate_version": SAFETY_GATE_VERSION,
        "normalized_query": normalized_query,
        "is_safety": prediction_inducement,
        "safety_intent": safety_intent,
        "matched_rules": matched_rules,
        "safety_labels": {
            "prediction_inducement": (
                prediction_inducement
            ),
            "future_specific_earthquake_prediction": (
                is_future_specific_claim
            ),
            "pseudoscience_prediction_claim": (
                is_pseudoscience_claim
            ),
            "historical_activity_prediction_claim": (
                is_historical_activity_claim
            ),
            "matched_keywords": matched_keywords,
            "matched_future_prediction_keywords": (
                matched_future
            ),
            "matched_pseudoscience_keywords": (
                matched_pseudoscience
            ),
            "matched_historical_activity_prediction_keywords": (
                matched_historical
            ),
        },
        "answer_constraints": {
            "must_not_predict_future_earthquakes": (
                prediction_inducement
            ),
            "should_offer_safe_alternatives": (
                prediction_inducement
            ),
        },
    }