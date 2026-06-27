"""
Deterministic answer generator for SeismoSearch.

This module converts an Evidence Pack into a user-facing answer.

Important design choice:
- This first version does NOT call an LLM.
- It uses deterministic templates so we can verify the full pipeline first.
- Later, this module can be extended with an LLM-backed generator, but the LLM
  should still be constrained by the Evidence Pack.

The generator must:
- use only evidence contained in the Evidence Pack;
- respect answer_constraints;
- refuse future earthquake prediction requests;
- state sample limitations for catalog answers;
- avoid claiming full global coverage.
"""

from __future__ import annotations

from typing import Any


def _as_text(value: Any, fallback: str = "unknown") -> str:
    """Convert a value into display text."""
    if value is None:
        return fallback

    return str(value)


def _format_float(value: Any, digits: int = 3, fallback: str = "unknown") -> str:
    """Format numeric values for user-facing answers."""
    if value is None:
        return fallback

    try:
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _get_first_computed_statistics(evidence_pack: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first computed statistics block, if available."""
    computed_evidence = evidence_pack.get("computed_evidence", [])

    if not computed_evidence:
        return None

    first_item = computed_evidence[0]
    return first_item.get("statistics")


def _format_event_item(event: dict[str, Any]) -> str:
    """Format one event evidence item into a concise answer line."""
    evidence_id = _as_text(event.get("evidence_id"))
    event_time = _as_text(event.get("event_time_utc"))
    place = _as_text(event.get("place"))
    magnitude = _format_float(event.get("magnitude"), digits=1)
    magnitude_type = _as_text(event.get("magnitude_type"))
    depth_km = _format_float(event.get("depth_km"), digits=3)
    latitude = _format_float(event.get("latitude"), digits=4)
    longitude = _format_float(event.get("longitude"), digits=4)
    status = _as_text(event.get("status"))

    return (
        f"- [{evidence_id}] {event_time}，{place}，"
        f"M{magnitude}（{magnitude_type}），深度 {depth_km} km，"
        f"坐标 ({latitude}, {longitude})，状态：{status}。"
    )


def _render_catalog_answer(evidence_pack: dict[str, Any]) -> str:
    """Render an answer for catalog-style historical event queries."""
    user_query = evidence_pack.get("user_query", "")
    event_evidence = evidence_pack.get("event_evidence", [])
    statistics = _get_first_computed_statistics(evidence_pack)

    lines: list[str] = []

    lines.append(f"针对你的问题：{user_query}")
    lines.append("")

    # Catalog answers must explicitly state that the answer is based on the
    # current local sample, not a full global catalog.
    lines.append("根据当前本地样例库检索，结果如下。注意：这不是完整全球地震目录统计，不能表述为全球全部结果。")
    lines.append("")

    if statistics is not None:
        event_count = statistics.get("event_count_matching_filters")
        magnitude_summary = statistics.get("magnitude_summary", {})
        database_time_range = statistics.get("database_time_range", {})

        min_time = database_time_range.get("min_event_time_utc")
        max_time = database_time_range.get("max_event_time_utc")
        database_count = database_time_range.get("event_count")

        lines.append(
            "统计口径："
            f"当前本地库共有 {database_count} 条样例事件，"
            f"时间范围为 {min_time} 至 {max_time}。"
        )

        lines.append(
            "在本次过滤条件下，"
            f"匹配事件数为 {event_count}；"
            f"震级范围为 M{_format_float(magnitude_summary.get('min_magnitude'), digits=1)}"
            f" 至 M{_format_float(magnitude_summary.get('max_magnitude'), digits=1)}，"
            f"平均震级约为 M{_format_float(magnitude_summary.get('avg_magnitude'), digits=2)}。"
        )
        lines.append("")

    if not event_evidence:
        lines.append("当前 Evidence Pack 中没有可用的事件证据，因此不能列出具体地震事件。")
        return "\n".join(lines)

    lines.append("可引用事件证据：")

    for event in event_evidence:
        lines.append(_format_event_item(event))

    lines.append("")
    lines.append("以上事件事实均来自 Evidence Pack 中的 event_evidence，后续如果接入 LLM，也应只基于这些证据生成回答。")

    return "\n".join(lines)


def _render_safety_answer(evidence_pack: dict[str, Any]) -> str:
    """Render a safe answer for future earthquake prediction requests."""
    user_query = evidence_pack.get("user_query", "")
    safety_evidence = evidence_pack.get("safety_evidence", {})
    safety_labels = safety_evidence.get("safety_labels", {})
    matched_keywords = safety_labels.get("matched_keywords", [])

    lines: list[str] = []

    lines.append(f"针对你的问题：{user_query}")
    lines.append("")
    lines.append("我不能预测某个具体地点在未来某一天是否会发生大地震，也不能把历史地震记录当成未来地震的确定性判断依据。")

    if matched_keywords:
        lines.append(f"这个问题被识别为未来地震预测类请求，触发关键词包括：{matched_keywords}。")

    lines.append("")
    lines.append("更安全、可用的替代方向是：")
    lines.append("- 查看官方地震监测机构发布的实时地震信息和预警信息；")
    lines.append("- 了解当地应急避难场所、家庭应急包和建筑抗震安全建议；")
    lines.append("- 如果你关心东京附近历史地震活动，可以改问“东京附近过去一年 M5+ 地震有哪些？”。")
    lines.append("")
    lines.append("当前回答遵守 Evidence Pack 中的安全约束：不预测未来具体地震，只提供风险沟通和安全替代建议。")

    return "\n".join(lines)


def _render_concept_answer(evidence_pack: dict[str, Any]) -> str:
    """Render a conservative answer for concept questions before doc retrieval exists."""
    user_query = evidence_pack.get("user_query", "")
    warnings = evidence_pack.get("warnings", [])

    lines: list[str] = []

    lines.append(f"针对你的问题：{user_query}")
    lines.append("")
    lines.append("当前系统还没有接入文档检索模块，因此 Evidence Pack 中没有 doc_evidence。")
    lines.append("为了避免无依据生成，这一版 Generator 不会编造地震学概念解释。")

    if warnings:
        lines.append("")
        lines.append(f"当前警告信息：{warnings}")

    lines.append("")
    lines.append("下一步接入 doc_retriever.py 后，这类问题应由文档证据支持，再生成带引用的解释。")

    return "\n".join(lines)


def generate_answer(evidence_pack: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a user-facing answer from an Evidence Pack.

    Returns a structured generation result:
    - status: generation status;
    - query_id: trace ID from the Evidence Pack;
    - query_type: resolved query type;
    - answer: user-facing answer text;
    - used_evidence_ids: evidence IDs used by the answer;
    - warnings: inherited warnings from the Evidence Pack.

    This function is deterministic and does not call any external model.
    """
    query_type = evidence_pack.get("query_type")
    answer_constraints = evidence_pack.get("answer_constraints", {})

    # Hard safety gate: if the Evidence Pack says not to predict future
    # earthquakes, always use the safety answer path.
    if answer_constraints.get("must_not_predict_future_earthquakes") is True:
        answer = _render_safety_answer(evidence_pack)
    elif query_type == "catalog":
        answer = _render_catalog_answer(evidence_pack)
    elif query_type == "mixed":
        # Mixed mode currently has event evidence but no document evidence.
        # Use catalog answer for the event part and explicitly preserve warnings.
        answer = _render_catalog_answer(evidence_pack)
    elif query_type == "concept":
        answer = _render_concept_answer(evidence_pack)
    else:
        answer = (
            "当前 Evidence Pack 的 query_type 无法识别，因此不能生成可靠回答。"
        )

    used_evidence_ids = [
        item.get("evidence_id")
        for item in evidence_pack.get("event_evidence", [])
        if item.get("evidence_id") is not None
    ]

    used_evidence_ids.extend(
        item.get("evidence_id")
        for item in evidence_pack.get("computed_evidence", [])
        if item.get("evidence_id") is not None
    )

    return {
        "status": "ok",
        "query_id": evidence_pack.get("query_id"),
        "query_type": query_type,
        "answer": answer,
        "used_evidence_ids": used_evidence_ids,
        "warnings": evidence_pack.get("warnings", []),
        "answer_constraints": answer_constraints,
    }