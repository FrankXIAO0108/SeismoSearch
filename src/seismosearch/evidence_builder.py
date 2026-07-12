"""
Evidence builder for SeismoSearch.

This module converts planner outputs and tool outputs into a structured
Evidence Pack.

The Evidence Pack is the controlled context passed to the future answer
generator. It separates:
- user query metadata;
- planner / router output;
- tool call records;
- event evidence;
- computed evidence;
- document evidence;
- safety evidence;
- answer constraints.

Important design choice:
- The Evidence Builder now calls planner.py by default.
- Manual query_type and tool params are still supported for debugging and tests.
- The Generator should consume Evidence Pack instead of raw tool outputs.
- Document retrieval is now connected through doc_retriever.py for concept
  and mixed queries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

# 新增：Evidence Builder 需要调用 doc_retriever，把文档检索结果转成 doc_evidence。
from seismosearch.doc_retriever import retrieve_docs
from seismosearch.hybrid_retriever import retrieve_docs_hybrid
from seismosearch.planner import plan_query
from seismosearch.reranker import retrieve_docs_hybrid_rerank
from seismosearch.tools import (
    event_search_tool,
    event_statistics_tool,
    safety_check_tool,
)


SCHEMA_VERSION = "0.2.0"
SUPPORTED_DOC_RETRIEVER_MODES = {
    "keyword",
    "hybrid",
    "hybrid_rerank",
}


def normalize_doc_retriever_mode(mode: str) -> str:
    """Validate one document retriever mode."""
    if not isinstance(mode, str):
        raise TypeError("doc_retriever_mode must be a string")

    normalized = mode.strip().lower()

    if normalized not in SUPPORTED_DOC_RETRIEVER_MODES:
        supported = ", ".join(sorted(SUPPORTED_DOC_RETRIEVER_MODES))
        raise ValueError(
            "doc_retriever_mode must be one of: "
            f"{supported}."
        )

    return normalized


def run_doc_retrieval(
    queries: str | list[str],
    top_k: int,
    mode: str,
) -> dict[str, Any]:
    """Run keyword, hybrid, or hybrid-rerank retrieval."""
    normalized = normalize_doc_retriever_mode(mode)

    if normalized == "hybrid_rerank":
        result = retrieve_docs_hybrid_rerank(
            queries=queries,
            top_k=top_k,
        )
    elif normalized == "hybrid":
        result = retrieve_docs_hybrid(
            queries=queries,
            top_k=top_k,
        )
    else:
        result = retrieve_docs(
            queries=queries,
            top_k=top_k,
        )

    result = dict(result)
    tool_input = dict(result.get("input", {}))
    tool_input["retriever"] = normalized
    result["input"] = tool_input
    return result


def utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_query_id(prefix: str = "query") -> str:
    """Create a short unique query ID for tracing."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def infer_query_type(user_query: str, safety_result: dict[str, Any]) -> str:
    """
    Fallback query-type inference.

    This function is kept for backward compatibility.
    The preferred path is now planner.plan_query().
    """
    safety_labels = safety_result.get("safety_labels", {})
    prediction_inducement = safety_labels.get("prediction_inducement", False)

    if prediction_inducement:
        return "safety"

    query_lower = user_query.lower()

    event_keywords = [
        "地震",
        "earthquake",
        "magnitude",
        "震级",
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

    if has_event_intent and has_concept_intent:
        return "mixed"

    if has_event_intent:
        return "catalog"

    if has_concept_intent:
        return "concept"

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


def build_doc_evidence(
    doc_result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Convert doc_retriever output into Evidence Pack doc_evidence.

    doc_retriever.py returns raw retrieval chunks.
    Evidence Builder converts those chunks into stable, citation-friendly
    evidence items for the Generator and future Evaluator.
    """
    # 如果这次 query 没有走文档检索，就没有 doc evidence。
    if doc_result is None:
        return []

    # 如果文档检索工具失败，不把失败结果伪装成证据。
    if doc_result.get("status") != "ok":
        return []

    # retrieve_docs() 返回的候选 chunk 列表。
    chunks = doc_result.get("chunks", [])

    # 防御性检查，避免异常数据结构进入 Evidence Pack。
    if not isinstance(chunks, list):
        return []

    doc_evidence: list[dict[str, Any]] = []

    for rank, chunk in enumerate(chunks, start=1):
        evidence_item = {
            # 稳定证据 ID，Generator 后面用 [doc_001] 这样的形式引用。
            "evidence_id": f"doc_{rank:03d}",

            # 明确这是文档 chunk 证据。
            "evidence_type": "document_chunk",

            # 检索排序位置。
            "rank": rank,

            # 原始 chunk 信息，来自 doc_retriever.py。
            "chunk_id": chunk.get("chunk_id"),
            "source_path": chunk.get("source_path"),
            "source_type": chunk.get("source_type"),
            "doc_title": chunk.get("doc_title"),
            "heading": chunk.get("heading"),
            "text": chunk.get("text"),
            "score": chunk.get("score"),
            "matched_terms": chunk.get("matched_terms", []),
            "retriever": chunk.get(
                "retriever",
                doc_result.get("input", {}).get("retriever"),
            ),
            "hybrid_rank": chunk.get("hybrid_rank"),
            "hybrid_score": chunk.get("hybrid_score"),
            "rerank_score": chunk.get("rerank_score"),
            "reranker_model_name": chunk.get(
                "reranker_model_name"
            ),
        }

        doc_evidence.append(evidence_item)

    return doc_evidence


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


def resolve_planner_output(
    user_query: str,
    planner_output: dict[str, Any] | None,
    use_planner: bool,
) -> dict[str, Any] | None:
    """
    Resolve planner output.

    If caller provides planner_output, use it directly.
    Otherwise, call plan_query() when use_planner is True.
    """
    if planner_output is not None:
        return planner_output

    if use_planner:
        return plan_query(user_query)

    return None


def build_router_output(
    resolved_query_type: str,
    planner_output: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build router/planner metadata for Evidence Pack."""
    if planner_output is not None:
        return {
            "query_type": resolved_query_type,
            "router_version": planner_output.get("planner_version"),
            "planner_output": planner_output,
            "notes": [
                "Query type and tool parameters were resolved through planner.py."
            ],
        }

    return {
        "query_type": resolved_query_type,
        "router_version": "heuristic_0.1.0",
        "notes": [
            "Planner was disabled or not provided; query type was resolved by fallback heuristic."
        ],
    }


def build_evidence_pack(
    user_query: str,
    query_id: str | None = None,
    query_type: str | None = None,
    event_search_params: dict[str, Any] | None = None,
    event_statistics_params: dict[str, Any] | None = None,
    planner_output: dict[str, Any] | None = None,
    use_planner: bool = True,
    doc_retriever_mode: str = "keyword",
) -> dict[str, Any]:
    """
    Build an Evidence Pack for one user query.

    Preferred usage:
        build_evidence_pack(user_query="最近 M6.5 以上地震有哪些？")

    Debugging / test usage:
        build_evidence_pack(
            user_query="最近 M6.5 以上地震有哪些？",
            query_type="catalog",
            event_search_params={...},
            event_statistics_params={...},
        )

    Parameters:
    - user_query: original user question;
    - query_id: optional external query ID;
    - query_type: optional manual query type override;
    - event_search_params: optional manual event_search_tool params override;
    - event_statistics_params: optional manual event_statistics_tool params override;
    - planner_output: optional precomputed planner output;
    - use_planner: whether to call planner.py automatically;
    - doc_retriever_mode: keyword, hybrid, or hybrid_rerank.
    """
    query_id = query_id or make_query_id()
    resolved_doc_retriever_mode = normalize_doc_retriever_mode(
        doc_retriever_mode
    )

    resolved_planner_output = resolve_planner_output(
        user_query=user_query,
        planner_output=planner_output,
        use_planner=use_planner,
    )

    # Always run safety check.
    # The planner is used for routing and tool parameters, while safety_check_tool
    # is still recorded as explicit safety evidence.
    safety_result = safety_check_tool(user_query)

    if query_type is not None:
        resolved_query_type = query_type
    elif resolved_planner_output is not None:
        resolved_query_type = resolved_planner_output.get("query_type", "concept")
    else:
        resolved_query_type = infer_query_type(user_query, safety_result)

    router_output = build_router_output(
        resolved_query_type=resolved_query_type,
        planner_output=resolved_planner_output,
    )

    tool_calls: list[dict[str, Any]] = [
        build_tool_call_record("safety_check", safety_result)
    ]

    search_result: dict[str, Any] | None = None
    statistics_result: dict[str, Any] | None = None
    doc_result: dict[str, Any] | None = None

    warnings: list[str] = []

    if resolved_planner_output is not None:
        warnings.extend(resolved_planner_output.get("warnings", []))

    # Manual parameters have priority.
    # If manual parameters are not provided, use planner-generated parameters.
    resolved_event_search_params = event_search_params
    resolved_event_statistics_params = event_statistics_params

    if resolved_event_search_params is None and resolved_planner_output is not None:
        resolved_event_search_params = resolved_planner_output.get("event_search_params")

    if resolved_event_statistics_params is None and resolved_planner_output is not None:
        resolved_event_statistics_params = resolved_planner_output.get(
            "event_statistics_params"
        )

    should_run_event_tools = resolved_query_type in {"catalog", "mixed"}

    if should_run_event_tools:
        search_params = resolved_event_search_params or {}
        statistics_params = resolved_event_statistics_params or {}

        search_result = event_search_tool(**search_params)
        statistics_result = event_statistics_tool(**statistics_params)

        tool_calls.append(build_tool_call_record("event_search", search_result))
        tool_calls.append(build_tool_call_record("event_statistics", statistics_result))

        warnings.extend(search_result.get("warnings", []))
        warnings.extend(statistics_result.get("warnings", []))

    doc_retrieval_queries: list[str] = []

    if resolved_planner_output is not None:
        doc_retrieval_queries = resolved_planner_output.get("doc_retrieval_queries", [])

    should_run_doc_retrieval = resolved_query_type in {"concept", "mixed"}

    if should_run_doc_retrieval:
        doc_result = run_doc_retrieval(
            queries=doc_retrieval_queries or [user_query],
            top_k=5,
            mode=resolved_doc_retriever_mode,
        )

        tool_calls.append(build_tool_call_record("doc_retrieval", doc_result))

        warnings.extend(doc_result.get("warnings", []))

    event_evidence = build_event_evidence(search_result)
    computed_evidence = build_computed_evidence(statistics_result)
    doc_evidence = build_doc_evidence(doc_result)
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
        "doc_retriever_mode": resolved_doc_retriever_mode,
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

    # Keep retrieval rewrites visible for evaluator and pipeline tests.
    evidence_pack["doc_retrieval_queries"] = doc_retrieval_queries

    return evidence_pack