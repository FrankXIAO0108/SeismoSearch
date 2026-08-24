"""
Hybrid document retriever for SeismoSearch.

This module implements a first hybrid retrieval baseline using Reciprocal Rank
Fusion (RRF).

Why this exists:
After adding retrieval_eval_60, we observed that:
- keyword / BM25 are strong for exact domain terms and structured field queries;
- dense retrieval can help semantic queries, but is less stable as a standalone
  retriever;
- no single retriever is clearly dominant across all query types.

Therefore, this module combines:
- BM25 sparse retrieval;
- dense embedding retrieval;

using RRF.

Important:
- This is NOT GraphRAG.
- This is NOT a vector database.
- This is NOT a production retrieval stack.
- This is a deterministic hybrid retrieval baseline for evaluation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seismosearch.bm25_retriever import retrieve_docs_bm25
from seismosearch.dense_retriever import retrieve_docs_dense
from seismosearch.doc_retriever import DEFAULT_DOC_DIRS, DEFAULT_TOP_K


DEFAULT_RRF_K = 60


def make_chunk_key(chunk: dict[str, Any]) -> str:
    """
    Build a stable key for merging chunks returned by different retrievers.

    chunk_id is usually stable because all retrievers use the same Markdown
    chunk loader. We still include source_path and heading to make the key more
    interpretable and robust.
    """
    return "|".join(
        [
            str(chunk.get("chunk_id", "")),
            str(chunk.get("source_path", "")),
            str(chunk.get("heading", "")),
        ]
    )


def rrf_score(
    rank: int,
    rrf_k: int = DEFAULT_RRF_K,
) -> float:
    """
    Compute Reciprocal Rank Fusion score for one rank.

    Formula:
        1 / (rrf_k + rank)

    Larger rrf_k makes scores smoother and reduces sensitivity to top-1 noise.
    """
    return 1.0 / (rrf_k + rank)


def add_ranked_chunks_to_fusion(
    fused: dict[str, dict[str, Any]],
    chunks: list[dict[str, Any]],
    retriever_name: str,
    weight: float,
    rrf_k: int,
) -> None:
    """
    Add ranked chunks from one retriever into the fusion table.

    For each chunk:
    - compute RRF contribution;
    - merge with existing entry if another retriever returned the same chunk;
    - keep per-retriever trace fields for debugging and evaluation.
    """
    for rank, chunk in enumerate(chunks, start=1):
        chunk_key = make_chunk_key(chunk)

        contribution = weight * rrf_score(
            rank=rank,
            rrf_k=rrf_k,
        )

        if chunk_key not in fused:
            fused[chunk_key] = {
                "chunk": dict(chunk),
                "hybrid_score": 0.0,
                "retriever_ranks": {},
                "retriever_scores": {},
                "retriever_contributions": {},
            }

        fused_entry = fused[chunk_key]
        fused_entry["hybrid_score"] += contribution
        fused_entry["retriever_ranks"][retriever_name] = rank
        fused_entry["retriever_scores"][retriever_name] = chunk.get("score")
        fused_entry["retriever_contributions"][retriever_name] = contribution


def retrieve_docs_hybrid(
    queries: str | list[str],
    top_k: int = DEFAULT_TOP_K,
    doc_dirs: list[Path] | None = None,
    candidate_k: int | None = None,
    rrf_k: int = DEFAULT_RRF_K,
    bm25_weight: float = 1.0,
    dense_weight: float = 1.0,
) -> dict[str, Any]:
    """
    Retrieve local Markdown chunks using BM25 + dense RRF fusion.

    Parameters:
    - queries: a single query string or a list of rewritten retrieval queries;
    - top_k: number of final chunks to return;
    - doc_dirs: optional local document directories;
    - candidate_k: number of candidates requested from each base retriever;
    - rrf_k: RRF smoothing constant;
    - bm25_weight: fusion weight for BM25;
    - dense_weight: fusion weight for dense retrieval.

    Returns a tool-like retrieval result with the same interface as other
    retrievers.
    """
    if isinstance(queries, str):
        query_list = [queries]
    else:
        query_list = queries

    query_list = [query for query in query_list if query and query.strip()]

    active_doc_dirs = doc_dirs or DEFAULT_DOC_DIRS

    if candidate_k is None:
        candidate_k = max(top_k * 4, 20)

    tool_input = {
        "queries": query_list,
        "top_k": top_k,
        "candidate_k": candidate_k,
        "doc_dirs": [path.as_posix() for path in active_doc_dirs],
        "retriever": "hybrid",
        "fusion": "rrf",
        "rrf_k": rrf_k,
        "bm25_weight": bm25_weight,
        "dense_weight": dense_weight,
    }

    if top_k <= 0:
        return {
            "tool_name": "doc_retrieval_hybrid",
            "status": "error",
            "input": tool_input,
            "chunks": [],
            "warnings": [],
            "error": "top_k must be positive.",
        }

    if not query_list:
        return {
            "tool_name": "doc_retrieval_hybrid",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": ["empty_retrieval_query"],
        }

    bm25_result = retrieve_docs_bm25(
        queries=query_list,
        top_k=candidate_k,
        doc_dirs=active_doc_dirs,
    )

    dense_result = retrieve_docs_dense(
        queries=query_list,
        top_k=candidate_k,
        doc_dirs=active_doc_dirs,
    )

    warnings = []
    warnings.extend(bm25_result.get("warnings", []))
    warnings.extend(dense_result.get("warnings", []))

    fused: dict[str, dict[str, Any]] = {}

    add_ranked_chunks_to_fusion(
        fused=fused,
        chunks=bm25_result.get("chunks", []),
        retriever_name="bm25",
        weight=bm25_weight,
        rrf_k=rrf_k,
    )

    add_ranked_chunks_to_fusion(
        fused=fused,
        chunks=dense_result.get("chunks", []),
        retriever_name="dense",
        weight=dense_weight,
        rrf_k=rrf_k,
    )

    fused_chunks: list[dict[str, Any]] = []

    for fused_entry in fused.values():
        chunk = dict(fused_entry["chunk"])

        chunk["score"] = fused_entry["hybrid_score"]
        chunk["retriever"] = "hybrid"
        chunk["fusion"] = "rrf"
        chunk["retriever_ranks"] = fused_entry["retriever_ranks"]
        chunk["retriever_scores"] = fused_entry["retriever_scores"]
        chunk["retriever_contributions"] = fused_entry["retriever_contributions"]

        matched_terms = chunk.get("matched_terms", [])

        if not matched_terms:
            matched_terms = ["hybrid_rrf"]

        chunk["matched_terms"] = matched_terms

        fused_chunks.append(chunk)

    fused_chunks.sort(
        key=lambda item: (
            item["score"],
            item.get("chunk_id", ""),
        ),
        reverse=True,
    )

    return {
        "tool_name": "doc_retrieval_hybrid",
        "status": "ok",
        "input": tool_input,
        "chunks": fused_chunks[:top_k],
        "warnings": warnings,
    }


def retrieve_docs_hybrid_debug(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """
    Convenience helper for manually inspecting hybrid retrieval behavior.
    """
    result = retrieve_docs_hybrid(
        queries=query,
        top_k=top_k,
    )

    debug_rows = []

    for chunk in result.get("chunks", []):
        debug_rows.append(
            {
                "source_path": chunk.get("source_path"),
                "heading": chunk.get("heading"),
                "score": chunk.get("score"),
                "retriever_ranks": chunk.get("retriever_ranks"),
                "retriever_scores": chunk.get("retriever_scores"),
            }
        )

    return debug_rows
