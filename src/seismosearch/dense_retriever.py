"""
Dense document retriever for SeismoSearch.

This module implements the first dense retrieval baseline for the document
retrieval layer.

Why this exists:
The existing retrievers are sparse baselines:
- keyword-overlap retriever;
- BM25 retriever.

Those methods work well for exact terms such as "magnitude", "震级",
"tsunami alert", or "depth", but they struggle when the query requires
semantic matching, for example:
- "latitude 和 longitude 后续可以怎么用？"
- "为什么历史地震不能直接预测未来？"
- "catalog query 和 safety routing 的边界是什么？"

Dense retrieval is introduced here as a baseline to test whether sentence
embedding similarity can recover semantically relevant chunks that sparse
retrieval misses.

Important:
- This is NOT a vector database implementation.
- This is NOT hybrid retrieval.
- This is a local in-memory dense retrieval baseline over Markdown chunks.
- It is intended for evaluation and comparison, not production performance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from seismosearch.doc_retriever import (
    DEFAULT_DOC_DIRS,
    DEFAULT_TOP_K,
    DocumentChunk,
    load_markdown_chunks,
    normalize_text,
)


DEFAULT_DENSE_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def build_dense_text(chunk: DocumentChunk) -> str:
    """
    Build the text sent to the embedding model for one chunk.

    Design:
    - include document title;
    - repeat heading to strengthen section-level semantics;
    - include chunk body text.

    This mirrors the BM25 field-weighting idea, but for dense embeddings.
    """
    return "\n".join(
        [
            chunk.doc_title,
            chunk.heading,
            chunk.heading,
            chunk.text,
        ]
    )


@lru_cache(maxsize=2)
def load_embedding_model(model_name: str = DEFAULT_DENSE_MODEL_NAME):
    """
    Lazily load a sentence-transformers model.

    The import is inside the function so normal tests that do not use dense
    retrieval do not require importing sentence-transformers.
    """
    try:
        from sentence_transformers import SentenceTransformer
        from huggingface_hub import snapshot_download
    except ImportError as error:
        raise ImportError(
            "sentence-transformers is required for dense retrieval. "
            "Install it with: python -m pip install sentence-transformers"
        ) from error

    resolved_model_name = model_name

    # Passing a repository ID to recent Transformers versions can trigger a
    # remote metadata request even when all model files are already cached.
    # Resolve the cached snapshot to a local path first so warm/offline runs
    # are reproducible. Fall back to the repository ID for the first download.
    try:
        resolved_model_name = snapshot_download(
            repo_id=model_name,
            local_files_only=True,
        )
    except Exception:
        resolved_model_name = model_name

    return SentenceTransformer(resolved_model_name)


def encode_texts(
    texts: list[str],
    model_name: str = DEFAULT_DENSE_MODEL_NAME,
) -> np.ndarray:
    """
    Encode texts into L2-normalized numpy embeddings.

    Normalization makes cosine similarity equivalent to dot product.
    """
    model = load_embedding_model(model_name)

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return np.asarray(embeddings, dtype=np.float32)


def dense_similarity(
    query_embedding: np.ndarray,
    chunk_embeddings: np.ndarray,
) -> np.ndarray:
    """
    Compute cosine similarity between one query embedding and chunk embeddings.

    Because embeddings are normalized, dot product equals cosine similarity.
    """
    return chunk_embeddings @ query_embedding


def retrieve_docs_dense(
    queries: str | list[str],
    top_k: int = DEFAULT_TOP_K,
    doc_dirs: list[Path] | None = None,
    model_name: str = DEFAULT_DENSE_MODEL_NAME,
) -> dict[str, Any]:
    """
    Retrieve local Markdown chunks using dense embedding similarity.

    Parameters:
    - queries: a single query string or a list of rewritten retrieval queries;
    - top_k: number of chunks to return;
    - doc_dirs: optional local document directories;
    - model_name: sentence-transformers model name.

    Returns a tool-like retrieval result with the same interface as sparse
    retrievers.
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
        "doc_dirs": [path.as_posix() for path in active_doc_dirs],
        "retriever": "dense",
        "model_name": model_name,
    }

    if top_k <= 0:
        return {
            "tool_name": "doc_retrieval_dense",
            "status": "error",
            "input": tool_input,
            "chunks": [],
            "warnings": [],
            "error": "top_k must be positive.",
        }

    if not query_list:
        return {
            "tool_name": "doc_retrieval_dense",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": ["empty_retrieval_query"],
        }

    chunks, warnings = load_markdown_chunks(doc_dirs=active_doc_dirs)

    if not chunks:
        return {
            "tool_name": "doc_retrieval_dense",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": warnings,
        }

    dense_texts = [build_dense_text(chunk) for chunk in chunks]

    chunk_embeddings = encode_texts(
        texts=dense_texts,
        model_name=model_name,
    )

    query_embeddings = encode_texts(
        texts=query_list,
        model_name=model_name,
    )

    # Multiple retrieval queries may exist when planner query rewriting is used.
    # For each chunk, keep the maximum similarity over all query variants.
    all_scores = []

    for query_embedding in query_embeddings:
        scores = dense_similarity(
            query_embedding=query_embedding,
            chunk_embeddings=chunk_embeddings,
        )
        all_scores.append(scores)

    score_matrix = np.vstack(all_scores)
    max_scores = score_matrix.max(axis=0)

    scored_chunks: list[dict[str, Any]] = []

    for chunk, score in zip(chunks, max_scores):
        scored_chunks.append(
            {
                "chunk_id": chunk.chunk_id,
                "source_path": chunk.source_path,
                "source_type": chunk.source_type,
                "doc_title": chunk.doc_title,
                "heading": chunk.heading,
                "text": chunk.text,
                "score": float(score),
                # Dense retrieval does not rely on lexical matched terms.
                # Keep a trace marker so evaluation output remains readable.
                "matched_terms": ["dense_similarity"],
                "specific_match_count": 0,
                "heading_match_count": 0,
                "retriever": "dense",
                "model_name": model_name,
            }
        )

    scored_chunks.sort(
        key=lambda item: (
            item["score"],
            item["chunk_id"],
        ),
        reverse=True,
    )

    return {
        "tool_name": "doc_retrieval_dense",
        "status": "ok",
        "input": tool_input,
        "chunks": scored_chunks[:top_k],
        "warnings": warnings,
    }


def retrieve_docs_dense_debug(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    model_name: str = DEFAULT_DENSE_MODEL_NAME,
) -> list[dict[str, Any]]:
    """
    Convenience helper for manual debugging.

    This is not used by the pipeline. It is useful when inspecting why dense
    retrieval returns certain chunks.
    """
    result = retrieve_docs_dense(
        queries=query,
        top_k=top_k,
        model_name=model_name,
    )

    debug_rows = []

    for chunk in result.get("chunks", []):
        debug_rows.append(
            {
                "source_path": chunk.get("source_path"),
                "heading": chunk.get("heading"),
                "score": chunk.get("score"),
                "text_preview": normalize_text(chunk.get("text", ""))[:160],
            }
        )

    return debug_rows
