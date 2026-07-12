"""
Tests for SeismoSearch BM25 document retriever.

These tests verify that the BM25 retriever follows the same interface and basic
behavior contract as the keyword-overlap retriever.

The purpose is not to prove BM25 is better yet.
The purpose is to make BM25 a controlled retrieval baseline that can be compared
against keyword retrieval in retrieval_eval.
"""

from __future__ import annotations

from pathlib import Path

from seismosearch.bm25_retriever import (
    compute_idf,
    retrieve_docs_bm25,
)


DOC_DIRS = [
    Path("data/processed/docs"),
]


def test_compute_idf_is_positive_for_rare_terms() -> None:
    """BM25 IDF should be positive and higher for rarer terms."""
    rare_idf = compute_idf(
        document_frequency=1,
        num_documents=10,
    )

    common_idf = compute_idf(
        document_frequency=8,
        num_documents=10,
    )

    assert rare_idf > 0
    assert common_idf > 0
    assert rare_idf > common_idf


def test_retrieve_docs_bm25_returns_relevant_magnitude_intensity_chunk() -> None:
    """BM25 retriever should return magnitude/intensity concept evidence."""
    result = retrieve_docs_bm25(
        queries=[
            "震级 烈度 区别",
            "seismic magnitude vs intensity",
        ],
        top_k=3,
        doc_dirs=DOC_DIRS,
    )

    assert result["status"] == "ok"
    assert result["tool_name"] == "doc_retrieval_bm25"

    chunks = result["chunks"]

    assert len(chunks) >= 1

    top_chunk = chunks[0]

    assert top_chunk["score"] > 0
    assert top_chunk["source_type"] == "local_markdown"
    assert top_chunk["source_path"].endswith(
        "seismology_concepts.md"
    )
    assert top_chunk["retriever"] == "bm25"

    combined_text = (
        top_chunk["heading"]
        + "\n"
        + top_chunk["text"]
        + "\n"
        + " ".join(
            top_chunk["matched_terms"]
        )
    )

    assert "震级" in combined_text
    assert "烈度" in combined_text


def test_retrieve_docs_bm25_returns_relevant_tsunami_alert_chunk() -> None:
    """
    BM25 should return usable tsunami evidence.

    The test validates semantic evidence coverage instead of locking the result
    to one historical document or a fixed Top-1 ranking.
    """
    result = retrieve_docs_bm25(
        queries=[
            "地震中的 tsunami alert 是什么意思？",
            "海啸提示 tsunami alert",
        ],
        top_k=3,
        doc_dirs=DOC_DIRS,
    )

    assert result["status"] == "ok"

    chunks = result["chunks"]

    assert len(chunks) >= 1

    accepted_sources = {
        "seismology_concepts.md",
        "impact_and_review_fields.md",
    }

    assert any(
        any(
            chunk["source_path"].endswith(
                source_name
            )
            for source_name in accepted_sources
        )
        for chunk in chunks
    )

    combined_text = "\n".join(
        (
            chunk["heading"]
            + "\n"
            + chunk["text"]
            + "\n"
            + " ".join(
                chunk["matched_terms"]
            )
        )
        for chunk in chunks
    )

    assert (
        "海啸" in combined_text
        or "tsunami" in combined_text.lower()
    )

    assert any(
        term in combined_text
        for term in [
            "预警",
            "警报",
            "提示",
            "alert",
            "warning",
        ]
    )


def test_retrieve_docs_bm25_returns_empty_for_unmatched_query() -> None:
    """BM25 retriever should return empty chunks for unrelated queries."""
    result = retrieve_docs_bm25(
        queries=[
            "completely unrelated cooking recipe"
        ],
        top_k=3,
        doc_dirs=DOC_DIRS,
    )

    assert result["status"] == "ok"
    assert result["chunks"] == []


def test_retrieve_docs_bm25_rejects_invalid_top_k() -> None:
    """BM25 retriever should return structured error for invalid top_k."""
    result = retrieve_docs_bm25(
        queries=[
            "震级 烈度"
        ],
        top_k=0,
        doc_dirs=DOC_DIRS,
    )

    assert result["status"] == "error"
    assert result["chunks"] == []
    assert (
        "top_k must be positive"
        in result["error"]
    )