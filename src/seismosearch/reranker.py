"""
Hybrid + reranker retrieval module for SeismoSearch.

This module adds a cross-encoder reranker on top of hybrid retrieval.

Why this exists:
The previous hybrid retriever combines BM25 and dense retrieval through RRF.
It improves recall and becomes the best retrieval configuration so far, but
the remaining failures are mostly chunk-level ranking errors.

Typical remaining failures:
- the correct source document is retrieved, but the wrong chunk is ranked higher;
- field explanation chunks are confused with concept explanation chunks;
- implicit queries such as "latitude 和 longitude 后续可以怎么用？" need better
  query-chunk relevance scoring.

Design:
1. Use hybrid retrieval to recall a candidate set.
2. Use a cross-encoder reranker to score each query-chunk pair.
3. Sort candidates by reranker score.
4. Return the final top-k chunks.

Important boundaries:
- This is not a vector database.
- This is not training or fine-tuning.
- This is an inference-only reranking baseline.
- This module is used for evaluation before deciding whether reranking is worth
  adding to the main pipeline.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from seismosearch.doc_retriever import (
    DEFAULT_DOC_DIRS,
    DEFAULT_TOP_K,
    normalize_text,
)
from seismosearch.hybrid_retriever import retrieve_docs_hybrid


DEFAULT_RERANK_MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
DEFAULT_RERANK_CANDIDATE_K = 10


def build_rerank_text(chunk: dict[str, Any]) -> str:
    """
    Build the chunk text used by the cross-encoder reranker.

    The reranker receives query-chunk pairs. To make the chunk more informative,
    we include:
    - document title;
    - section heading;
    - chunk body text.

    Heading is repeated once because section title often contains the strongest
    semantic signal.
    """
    return "\n".join(
        [
            str(chunk.get("doc_title", "")),
            str(chunk.get("heading", "")),
            str(chunk.get("heading", "")),
            str(chunk.get("text", "")),
        ]
    )


@lru_cache(maxsize=2)
def load_reranker_model(model_name: str = DEFAULT_RERANK_MODEL_NAME):
    """
    Lazily load the cross-encoder reranker model.

    The import is kept inside the function so importing this module does not
    force sentence-transformers to load unless reranking is actually used.
    """
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as error:
        raise ImportError(
            "sentence-transformers is required for reranking. "
            "Install it with: python -m pip install sentence-transformers"
        ) from error

    return CrossEncoder(model_name)


def score_candidates_with_reranker(
    queries: list[str],
    chunks: list[dict[str, Any]],
    model_name: str = DEFAULT_RERANK_MODEL_NAME,
) -> np.ndarray:
    """
    Score candidate chunks with a cross-encoder reranker.

    Multiple retrieval queries may exist when planner query rewriting is used.
    For each chunk, we compute scores against all query variants and keep the
    maximum score.

    This keeps the interface compatible with:
    - raw query mode;
    - planner query mode.
    """
    if not queries or not chunks:
        return np.asarray([], dtype=np.float32)

    model = load_reranker_model(model_name)

    pairs: list[tuple[str, str]] = []

    for query in queries:
        for chunk in chunks:
            pairs.append(
                (
                    query,
                    build_rerank_text(chunk),
                )
            )

    raw_scores = model.predict(
        pairs,
        show_progress_bar=False,
    )

    score_array = np.asarray(raw_scores, dtype=np.float32)
    score_matrix = score_array.reshape(len(queries), len(chunks))

    return score_matrix.max(axis=0)


def retrieve_docs_hybrid_rerank(
    queries: str | list[str],
    top_k: int = DEFAULT_TOP_K,
    doc_dirs: list[Path] | None = None,
    candidate_k: int = DEFAULT_RERANK_CANDIDATE_K,
    model_name: str = DEFAULT_RERANK_MODEL_NAME,
) -> dict[str, Any]:
    """
    Retrieve documents with hybrid retrieval and rerank the candidates.

    Parameters:
    - queries:
      raw query or planner-generated retrieval queries.
    - top_k:
      number of final chunks returned after reranking.
    - doc_dirs:
      optional document directories.
    - candidate_k:
      number of hybrid candidates to send into the reranker.
    - model_name:
      cross-encoder reranker model name.

    Returns:
    A retrieval result with the same shape as other retrievers.
    """
    if isinstance(queries, str):
        query_list = [queries]
    else:
        query_list = queries

    query_list = [query for query in query_list if query and query.strip()]

    active_doc_dirs = doc_dirs or DEFAULT_DOC_DIRS

    tool_input = {
        "queries": query_list,
        "top_k": top_k,
        "candidate_k": candidate_k,
        "doc_dirs": [path.as_posix() for path in active_doc_dirs],
        "retriever": "hybrid_rerank",
        "base_retriever": "hybrid",
        "reranker_model_name": model_name,
    }

    if top_k <= 0:
        return {
            "tool_name": "doc_retrieval_hybrid_rerank",
            "status": "error",
            "input": tool_input,
            "chunks": [],
            "warnings": [],
            "error": "top_k must be positive.",
        }

    if not query_list:
        return {
            "tool_name": "doc_retrieval_hybrid_rerank",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": ["empty_retrieval_query"],
        }

    candidate_result = retrieve_docs_hybrid(
        queries=query_list,
        top_k=candidate_k,
        doc_dirs=active_doc_dirs,
    )

    candidate_chunks = candidate_result.get("chunks", [])

    if not candidate_chunks:
        return {
            "tool_name": "doc_retrieval_hybrid_rerank",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": candidate_result.get("warnings", []),
        }

    rerank_scores = score_candidates_with_reranker(
        queries=query_list,
        chunks=candidate_chunks,
        model_name=model_name,
    )

    reranked_chunks: list[dict[str, Any]] = []

    for original_rank, (chunk, rerank_score) in enumerate(
        zip(candidate_chunks, rerank_scores),
        start=1,
    ):
        reranked_chunk = dict(chunk)

        reranked_chunk["score"] = float(rerank_score)
        reranked_chunk["rerank_score"] = float(rerank_score)
        reranked_chunk["hybrid_rank"] = original_rank
        reranked_chunk["hybrid_score"] = chunk.get("score")
        reranked_chunk["retriever"] = "hybrid_rerank"
        reranked_chunk["reranker_model_name"] = model_name

        matched_terms = list(reranked_chunk.get("matched_terms", []))

        if "cross_encoder_rerank" not in matched_terms:
            matched_terms.append("cross_encoder_rerank")

        reranked_chunk["matched_terms"] = matched_terms

        reranked_chunks.append(reranked_chunk)

    reranked_chunks.sort(
        key=lambda item: (
            item["rerank_score"],
            -item["hybrid_rank"],
        ),
        reverse=True,
    )

    return {
        "tool_name": "doc_retrieval_hybrid_rerank",
        "status": "ok",
        "input": tool_input,
        "chunks": reranked_chunks[:top_k],
        "warnings": candidate_result.get("warnings", []),
    }


def retrieve_docs_hybrid_rerank_debug(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    candidate_k: int = DEFAULT_RERANK_CANDIDATE_K,
) -> list[dict[str, Any]]:
    """
    Debug helper for inspecting reranked results.
    """
    result = retrieve_docs_hybrid_rerank(
        queries=query,
        top_k=top_k,
        candidate_k=candidate_k,
    )

    debug_rows = []

    for chunk in result.get("chunks", []):
        debug_rows.append(
            {
                "source_path": chunk.get("source_path"),
                "heading": chunk.get("heading"),
                "rerank_score": chunk.get("rerank_score"),
                "hybrid_rank": chunk.get("hybrid_rank"),
                "hybrid_score": chunk.get("hybrid_score"),
                "text_preview": normalize_text(chunk.get("text", ""))[:160],
            }
        )

    return debug_rows