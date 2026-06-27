"""
Tests for SeismoSearch document retriever.

These tests verify the deterministic Markdown retrieval baseline.

The retriever should:
- load local Markdown documents;
- split them into traceable chunks;
- retrieve relevant chunks for concept queries;
- return structured chunk evidence candidates.
"""

from __future__ import annotations

from pathlib import Path

from seismosearch.doc_retriever import (
    extract_query_terms,
    retrieve_docs,
)


DOC_DIRS = [Path("data/processed/docs")]


def test_extract_query_terms_supports_chinese_and_english_terms() -> None:
    """Query term extraction should support Chinese and English domain terms."""
    terms = extract_query_terms("震级和烈度有什么区别？ magnitude vs intensity")

    assert "震级" in terms
    assert "烈度" in terms
    assert "区别" in terms
    assert "magnitude" in terms
    assert "intensity" in terms


def test_retrieve_docs_returns_relevant_magnitude_intensity_chunk() -> None:
    """Retriever should return magnitude/intensity concept chunk."""
    result = retrieve_docs(
        queries=[
            "震级 烈度 区别",
            "seismic magnitude vs intensity",
        ],
        top_k=3,
        doc_dirs=DOC_DIRS,
    )

    assert result["status"] == "ok"

    chunks = result["chunks"]

    assert len(chunks) >= 1

    top_chunk = chunks[0]

    assert top_chunk["score"] > 0
    assert top_chunk["source_type"] == "local_markdown"
    assert top_chunk["source_path"].endswith("seismology_concepts.md")

    combined_text = (
        top_chunk["heading"]
        + "\n"
        + top_chunk["text"]
        + "\n"
        + " ".join(top_chunk["matched_terms"])
    )

    assert "震级" in combined_text
    assert "烈度" in combined_text


def test_retrieve_docs_returns_empty_for_unmatched_query() -> None:
    """Retriever should return empty chunks for unrelated queries."""
    result = retrieve_docs(
        queries=["completely unrelated cooking recipe"],
        top_k=3,
        doc_dirs=DOC_DIRS,
    )

    assert result["status"] == "ok"
    assert result["chunks"] == []


def test_retrieve_docs_rejects_invalid_top_k() -> None:
    """Retriever should return structured error for invalid top_k."""
    result = retrieve_docs(
        queries=["震级 烈度"],
        top_k=0,
        doc_dirs=DOC_DIRS,
    )

    assert result["status"] == "error"
    assert result["chunks"] == []
    assert "top_k must be positive" in result["error"]