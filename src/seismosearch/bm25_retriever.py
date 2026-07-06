"""
BM25 document retriever for SeismoSearch.

This module implements a lightweight deterministic BM25 baseline.

Why this exists:
The original doc_retriever.py is a weighted keyword-overlap baseline.
That baseline is easy to debug, but it is not a standard IR baseline.

BM25 is a stronger classic sparse retrieval baseline. Adding it allows us to
compare:

- keyword_overlap retriever;
- BM25 retriever;
- future dense retriever;
- future hybrid retriever.

Important:
This implementation does not add an external dependency. It uses the same
local Markdown chunk loading and query-term extraction logic as doc_retriever.py,
then applies a simple BM25 scoring formula.

This is still not dense retrieval and not hybrid retrieval.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from seismosearch.doc_retriever import (
    DEFAULT_DOC_DIRS,
    DEFAULT_TOP_K,
    DocumentChunk,
    extract_query_terms,
    is_generic_retrieval_term,
    load_markdown_chunks,
    normalize_text,
    term_weight,
)


def count_chinese_chars(text: str) -> int:
    """Count Chinese characters as rough retrieval units."""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def count_english_tokens(text: str) -> int:
    """Count English / numeric tokens as rough retrieval units."""
    return len(re.findall(r"[a-zA-Z0-9_+-]+", text))


def estimate_document_length(text: str) -> int:
    """
    Estimate document length for BM25 length normalization.

    This is intentionally simple:
    - Chinese text is approximated by character count;
    - English text is approximated by token count.

    We avoid depending on jieba or other tokenizers in this baseline.
    """
    normalized_text = normalize_text(text)

    length = count_chinese_chars(normalized_text) + count_english_tokens(normalized_text)

    return max(length, 1)


def build_bm25_text(chunk: DocumentChunk) -> str:
    """
    Build searchable text for one chunk.

    Heading is repeated to give section titles stronger retrieval influence.
    This roughly mimics field weighting while keeping the implementation simple.
    """
    return "\n".join(
        [
            chunk.heading,
            chunk.heading,
            chunk.heading,
            chunk.doc_title,
            chunk.text,
        ]
    )


def term_frequency(term: str, text: str) -> int:
    """
    Count deterministic phrase-level term frequency.

    For Chinese phrases, substring count works well enough for this small
    deterministic baseline.

    For English terms, this also works because text is normalized to lowercase.
    """
    normalized_term = normalize_text(term)
    normalized_text = normalize_text(text)

    if not normalized_term:
        return 0

    return normalized_text.count(normalized_term)


def compute_document_frequency(
    query_terms: list[str],
    chunk_texts: list[str],
) -> dict[str, int]:
    """Compute document frequency for each query term."""
    document_frequency: dict[str, int] = {}

    for term in query_terms:
        normalized_term = normalize_text(term)
        df = 0

        for text in chunk_texts:
            if term_frequency(normalized_term, text) > 0:
                df += 1

        document_frequency[normalized_term] = df

    return document_frequency


def compute_idf(
    document_frequency: int,
    num_documents: int,
) -> float:
    """
    Compute BM25 IDF with smoothing.

    Formula:
    log(1 + (N - df + 0.5) / (df + 0.5))

    This keeps IDF non-negative and stable for small corpora.
    """
    return math.log(
        1.0
        + (num_documents - document_frequency + 0.5)
        / (document_frequency + 0.5)
    )


def bm25_term_score(
    term_frequency_value: int,
    idf: float,
    document_length: int,
    average_document_length: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Compute BM25 score contribution for one term."""
    if term_frequency_value <= 0:
        return 0.0

    denominator = (
        term_frequency_value
        + k1
        * (
            1.0
            - b
            + b
            * document_length
            / max(average_document_length, 1.0)
        )
    )

    return idf * (
        term_frequency_value
        * (k1 + 1.0)
        / denominator
    )


def score_chunk_bm25(
    chunk: DocumentChunk,
    chunk_text: str,
    query_terms: list[str],
    document_frequency: dict[str, int],
    num_documents: int,
    document_length: int,
    average_document_length: float,
) -> tuple[float, list[str], int, int]:
    """
    Score one chunk with BM25.

    Returns:
    - score;
    - matched terms;
    - specific match count;
    - heading match count.
    """
    score = 0.0
    matched_terms: list[str] = []
    specific_match_count = 0
    heading_match_count = 0

    heading = normalize_text(chunk.heading)

    for term in query_terms:
        normalized_term = normalize_text(term)

        tf = term_frequency(normalized_term, chunk_text)

        if tf <= 0:
            continue

        df = document_frequency.get(normalized_term, 0)
        idf = compute_idf(
            document_frequency=df,
            num_documents=num_documents,
        )

        base_score = bm25_term_score(
            term_frequency_value=tf,
            idf=idf,
            document_length=document_length,
            average_document_length=average_document_length,
        )

        weighted_score = base_score * term_weight(normalized_term)

        score += weighted_score
        matched_terms.append(normalized_term)

        if not is_generic_retrieval_term(normalized_term):
            specific_match_count += 1

        if normalized_term in heading:
            heading_match_count += 1

    # Tiny corpus prior.
    # Only apply after at least one real term match.
    if matched_terms and "data/processed/docs" in normalize_text(chunk.source_path):
        score += 0.1

    return score, matched_terms, specific_match_count, heading_match_count


def retrieve_docs_bm25(
    queries: str | list[str],
    top_k: int = DEFAULT_TOP_K,
    doc_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """
    Retrieve local Markdown chunks using BM25.

    Parameters:
    - queries: a single query string or a list of rewritten retrieval queries;
    - top_k: number of chunks to return;
    - doc_dirs: optional local document directories.

    Returns a tool-like retrieval result with the same interface as retrieve_docs.
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
        "retriever": "bm25",
    }

    if top_k <= 0:
        return {
            "tool_name": "doc_retrieval_bm25",
            "status": "error",
            "input": tool_input,
            "chunks": [],
            "warnings": [],
            "error": "top_k must be positive.",
        }

    if not query_list:
        return {
            "tool_name": "doc_retrieval_bm25",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": ["empty_retrieval_query"],
        }

    chunks, warnings = load_markdown_chunks(doc_dirs=active_doc_dirs)

    if not chunks:
        return {
            "tool_name": "doc_retrieval_bm25",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": warnings,
        }

    all_terms: list[str] = []

    for query in query_list:
        all_terms.extend(extract_query_terms(query))

    query_terms = list(dict.fromkeys(all_terms))

    if not query_terms:
        return {
            "tool_name": "doc_retrieval_bm25",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": warnings + ["no_query_terms_extracted"],
        }

    chunk_texts = [build_bm25_text(chunk) for chunk in chunks]
    document_lengths = [estimate_document_length(text) for text in chunk_texts]

    average_document_length = (
        sum(document_lengths) / len(document_lengths)
        if document_lengths
        else 1.0
    )

    document_frequency = compute_document_frequency(
        query_terms=query_terms,
        chunk_texts=chunk_texts,
    )

    scored_chunks: list[dict[str, Any]] = []

    for chunk, chunk_text, document_length in zip(
        chunks,
        chunk_texts,
        document_lengths,
    ):
        (
            score,
            matched_terms,
            specific_match_count,
            heading_match_count,
        ) = score_chunk_bm25(
            chunk=chunk,
            chunk_text=chunk_text,
            query_terms=query_terms,
            document_frequency=document_frequency,
            num_documents=len(chunks),
            document_length=document_length,
            average_document_length=average_document_length,
        )

        if score <= 0:
            continue

        scored_chunks.append(
            {
                "chunk_id": chunk.chunk_id,
                "source_path": chunk.source_path,
                "source_type": chunk.source_type,
                "doc_title": chunk.doc_title,
                "heading": chunk.heading,
                "text": chunk.text,
                "score": score,
                "matched_terms": matched_terms,
                "specific_match_count": specific_match_count,
                "heading_match_count": heading_match_count,
                "retriever": "bm25",
            }
        )

    scored_chunks.sort(
        key=lambda item: (
            item["score"],
            item["specific_match_count"],
            item["heading_match_count"],
            len(item["matched_terms"]),
            item["chunk_id"],
        ),
        reverse=True,
    )

    return {
        "tool_name": "doc_retrieval_bm25",
        "status": "ok",
        "input": tool_input,
        "chunks": scored_chunks[:top_k],
        "warnings": warnings,
    }