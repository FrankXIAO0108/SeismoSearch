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
- cite event evidence when using event facts;
- cite document evidence when using document facts;
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


def _format_doc_item(doc: dict[str, Any]) -> str:
    """Format one document evidence item into a citation line."""
    evidence_id = _as_text(doc.get("evidence_id"))
    doc_title = _as_text(doc.get("doc_title"))
    heading = _as_text(doc.get("heading"))
    source_path = _as_text(doc.get("source_path"))

    return f"- [{evidence_id}] {doc_title} / {heading} / {source_path}"


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
    """
    Render an answer for concept questions.

    If doc_evidence exists, answer strictly from retrieved document evidence.
    If doc_evidence is missing, refuse to fabricate an explanation.
    """
    user_query = evidence_pack.get("user_query", "")
    doc_evidence = evidence_pack.get("doc_evidence", [])
    warnings = evidence_pack.get("warnings", [])

    lines: list[str] = []

    lines.append(f"针对你的问题：{user_query}")
    lines.append("")

    # If document retrieval failed or returned nothing, keep conservative behavior.
    if not doc_evidence:
        lines.append("当前 Evidence Pack 中没有 doc_evidence。")
        lines.append("为了避免无依据生成，这一版 Generator 不会编造地震学概念解释。")

        if warnings:
            lines.append("")
            lines.append(f"当前警告信息：{warnings}")

        return "\n".join(lines)

    lines.append("根据当前检索到的文档证据，可以回答如下：")
    lines.append("")

    # First deterministic version:
    # Use the top retrieved chunk as the main evidence.
    # This is intentionally simple and testable before adding LLM generation.
    top_doc = doc_evidence[0]
    top_doc_id = _as_text(top_doc.get("evidence_id"))
    top_text = _as_text(top_doc.get("text"), fallback="")

    lines.append(top_text)
    lines.append("")

    lines.append("引用证据：")
    lines.append(_format_doc_item(top_doc))

    # If more evidence exists, list it as supporting evidence without expanding it.
    if len(doc_evidence) > 1:
        lines.append("")
        lines.append("其他候选文档证据：")

        for doc in doc_evidence[1:3]:
            lines.append(_format_doc_item(doc))

    lines.append("")
    lines.append(f"以上解释仅基于 Evidence Pack 中的文档证据 [{top_doc_id}]，未使用外部未检索知识。")

    return "\n".join(lines)


def _render_mixed_answer(evidence_pack: dict[str, Any]) -> str:
    """
    Render a mixed answer with both event evidence and document evidence.

    This first version concatenates catalog-style evidence and concept-style
    evidence. Later versions can use an LLM, but only after eval is ready.
    """
    lines: list[str] = []

    lines.append(_render_catalog_answer(evidence_pack))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(_render_concept_answer(evidence_pack))

    return "\n".join(lines)


def _collect_used_evidence_ids(evidence_pack: dict[str, Any]) -> list[str]:
    """Collect all evidence IDs used by the deterministic generator."""
    used_evidence_ids: list[str] = []

    for item in evidence_pack.get("event_evidence", []):
        evidence_id = item.get("evidence_id")
        if evidence_id is not None:
            used_evidence_ids.append(evidence_id)

    for item in evidence_pack.get("computed_evidence", []):
        evidence_id = item.get("evidence_id")
        if evidence_id is not None:
            used_evidence_ids.append(evidence_id)

    for item in evidence_pack.get("doc_evidence", []):
        evidence_id = item.get("evidence_id")
        if evidence_id is not None:
            used_evidence_ids.append(evidence_id)

    return used_evidence_ids


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
        answer = _render_mixed_answer(evidence_pack)
    elif query_type == "concept":
        answer = _render_concept_answer(evidence_pack)
    else:
        answer = (
            "当前 Evidence Pack 的 query_type 无法识别，因此不能生成可靠回答。"
        )

    used_evidence_ids = _collect_used_evidence_ids(evidence_pack)

    return {
        "status": "ok",
        "query_id": evidence_pack.get("query_id"),
        "query_type": query_type,
        "answer": answer,
        "used_evidence_ids": used_evidence_ids,
        "warnings": evidence_pack.get("warnings", []),
        "answer_constraints": answer_constraints,
    }