"""Tests for selectable document retriever modes."""

from __future__ import annotations

from typing import Any

import seismosearch.evidence_builder as evidence_builder
from seismosearch.pipeline import run_pipeline


def fake_result(mode: str) -> dict[str, Any]:
    return {
        "tool_name": "doc_retrieval",
        "status": "ok",
        "input": {"queries": ["test"], "top_k": 5, "retriever": mode},
        "chunks": [
            {
                "chunk_id": "fake_001",
                "source_path": "data/processed/docs/seismology_concepts.md",
                "source_type": "local_markdown",
                "doc_title": "Seismology Concepts",
                "heading": "震级和烈度的区别",
                "text": "震级描述能量，烈度描述地点影响。",
                "score": 4.2,
                "matched_terms": ["震级", "烈度"],
                "retriever": mode,
                "hybrid_rank": 2,
                "hybrid_score": 0.03,
                "rerank_score": 4.2,
                "reranker_model_name": "fake-reranker",
            }
        ],
        "warnings": [],
    }


def test_default_mode_is_keyword() -> None:
    result = run_pipeline(
        "震级和烈度有什么区别？",
        include_evidence_pack=True,
    )
    assert result["status"] == "ok"
    assert result["doc_retriever_mode"] == "keyword"


def test_hybrid_rerank_mode_reaches_evidence_pack(monkeypatch) -> None:
    captured: list[str] = []

    def fake_run(
        queries: str | list[str],
        top_k: int,
        mode: str,
    ) -> dict[str, Any]:
        captured.append(mode)
        return fake_result(mode)

    monkeypatch.setattr(evidence_builder, "run_doc_retrieval", fake_run)

    result = run_pipeline(
        "震级和烈度有什么区别？",
        doc_retriever_mode="hybrid_rerank",
        include_evidence_pack=True,
    )

    assert result["status"] == "ok"
    assert captured == ["hybrid_rerank"]
    assert result["doc_retriever_mode"] == "hybrid_rerank"

    doc = result["evidence_pack"]["doc_evidence"][0]
    assert doc["retriever"] == "hybrid_rerank"
    assert doc["hybrid_rank"] == 2
    assert doc["rerank_score"] == 4.2


def test_unknown_mode_is_rejected() -> None:
    result = run_pipeline(
        "震级和烈度有什么区别？",
        doc_retriever_mode="unknown",
        include_evidence_pack=False,
    )
    assert result["status"] == "error"
    assert "doc_retriever_mode must be one of" in result["error"]
