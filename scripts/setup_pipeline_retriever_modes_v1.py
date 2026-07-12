"""One-time setup for selectable SeismoSearch document retrievers."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "src" / "seismosearch" / "evidence_builder.py"
PIPELINE = ROOT / "src" / "seismosearch" / "pipeline.py"
TEST = ROOT / "tests" / "test_pipeline_retriever_modes.py"


def read_text(path: Path) -> tuple[str, str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        text = f.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    return text, newline


def adapt(value: str, newline: str) -> str:
    return value.replace("\n", newline)


def replace_once(text: str, old: str, new: str, newline: str, label: str) -> str:
    old_value = adapt(old, newline)
    new_value = adapt(new, newline)
    count = text.count(old_value)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old_value, new_value, 1)


def write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def patch_evidence_builder() -> None:
    text, nl = read_text(EVIDENCE)
    if "SUPPORTED_DOC_RETRIEVER_MODES" in text:
        raise RuntimeError("evidence_builder.py already patched")

    text = replace_once(
        text,
        "from seismosearch.doc_retriever import retrieve_docs\nfrom seismosearch.planner import plan_query\n",
        "from seismosearch.doc_retriever import retrieve_docs\nfrom seismosearch.hybrid_retriever import retrieve_docs_hybrid\nfrom seismosearch.planner import plan_query\nfrom seismosearch.reranker import retrieve_docs_hybrid_rerank\n",
        nl,
        "imports",
    )

    text = replace_once(
        text,
        'SCHEMA_VERSION = "0.1.0"\n\n\ndef utc_now_iso() -> str:\n',
        '''SCHEMA_VERSION = "0.2.0"\nSUPPORTED_DOC_RETRIEVER_MODES = {\n    "keyword",\n    "hybrid",\n    "hybrid_rerank",\n}\n\n\ndef normalize_doc_retriever_mode(mode: str) -> str:\n    """Validate one document retriever mode."""\n    if not isinstance(mode, str):\n        raise TypeError("doc_retriever_mode must be a string")\n\n    normalized = mode.strip().lower()\n\n    if normalized not in SUPPORTED_DOC_RETRIEVER_MODES:\n        supported = ", ".join(sorted(SUPPORTED_DOC_RETRIEVER_MODES))\n        raise ValueError(\n            "doc_retriever_mode must be one of: "\n            f"{supported}."\n        )\n\n    return normalized\n\n\ndef run_doc_retrieval(\n    queries: str | list[str],\n    top_k: int,\n    mode: str,\n) -> dict[str, Any]:\n    """Run keyword, hybrid, or hybrid-rerank retrieval."""\n    normalized = normalize_doc_retriever_mode(mode)\n\n    if normalized == "hybrid_rerank":\n        result = retrieve_docs_hybrid_rerank(\n            queries=queries,\n            top_k=top_k,\n        )\n    elif normalized == "hybrid":\n        result = retrieve_docs_hybrid(\n            queries=queries,\n            top_k=top_k,\n        )\n    else:\n        result = retrieve_docs(\n            queries=queries,\n            top_k=top_k,\n        )\n\n    result = dict(result)\n    tool_input = dict(result.get("input", {}))\n    tool_input["retriever"] = normalized\n    result["input"] = tool_input\n    return result\n\n\ndef utc_now_iso() -> str:\n''',
        nl,
        "retriever router",
    )

    text = replace_once(
        text,
        '''            "score": chunk.get("score"),\n            "matched_terms": chunk.get("matched_terms", []),\n        }\n''',
        '''            "score": chunk.get("score"),\n            "matched_terms": chunk.get("matched_terms", []),\n            "retriever": chunk.get(\n                "retriever",\n                doc_result.get("input", {}).get("retriever"),\n            ),\n            "hybrid_rank": chunk.get("hybrid_rank"),\n            "hybrid_score": chunk.get("hybrid_score"),\n            "rerank_score": chunk.get("rerank_score"),\n            "reranker_model_name": chunk.get(\n                "reranker_model_name"\n            ),\n        }\n''',
        nl,
        "doc evidence metadata",
    )

    text = replace_once(
        text,
        '''    planner_output: dict[str, Any] | None = None,\n    use_planner: bool = True,\n) -> dict[str, Any]:\n''',
        '''    planner_output: dict[str, Any] | None = None,\n    use_planner: bool = True,\n    doc_retriever_mode: str = "keyword",\n) -> dict[str, Any]:\n''',
        nl,
        "signature",
    )

    text = replace_once(
        text,
        '''    - planner_output: optional precomputed planner output;\n    - use_planner: whether to call planner.py automatically.\n    """\n''',
        '''    - planner_output: optional precomputed planner output;\n    - use_planner: whether to call planner.py automatically;\n    - doc_retriever_mode: keyword, hybrid, or hybrid_rerank.\n    """\n''',
        nl,
        "docstring",
    )

    text = replace_once(
        text,
        '''    query_id = query_id or make_query_id()\n\n    resolved_planner_output = resolve_planner_output(\n''',
        '''    query_id = query_id or make_query_id()\n    resolved_doc_retriever_mode = normalize_doc_retriever_mode(\n        doc_retriever_mode\n    )\n\n    resolved_planner_output = resolve_planner_output(\n''',
        nl,
        "mode normalization",
    )

    text = replace_once(
        text,
        '''        doc_result = retrieve_docs(\n            queries=doc_retrieval_queries or [user_query],\n            top_k=5,\n        )\n''',
        '''        doc_result = run_doc_retrieval(\n            queries=doc_retrieval_queries or [user_query],\n            top_k=5,\n            mode=resolved_doc_retriever_mode,\n        )\n''',
        nl,
        "retrieval call",
    )

    text = replace_once(
        text,
        '''        "query_type": resolved_query_type,\n        "created_at_utc": utc_now_iso(),\n''',
        '''        "query_type": resolved_query_type,\n        "doc_retriever_mode": resolved_doc_retriever_mode,\n        "created_at_utc": utc_now_iso(),\n''',
        nl,
        "pack metadata",
    )

    write_text(EVIDENCE, text)


def patch_pipeline() -> None:
    text, nl = read_text(PIPELINE)
    if 'doc_retriever_mode: str = "keyword"' in text:
        raise RuntimeError("pipeline.py already patched")

    text = replace_once(
        text,
        '''    generator_mode: str = "deterministic",\n    llm_client: ChatCompletionClient | None = None,\n) -> dict[str, Any]:\n''',
        '''    generator_mode: str = "deterministic",\n    llm_client: ChatCompletionClient | None = None,\n    doc_retriever_mode: str = "keyword",\n) -> dict[str, Any]:\n''',
        nl,
        "pipeline signature",
    )

    text = replace_once(
        text,
        '''    generator_mode:\n    - deterministic\n    - llm\n    """\n''',
        '''    generator_mode:\n    - deterministic\n    - llm\n\n    doc_retriever_mode:\n    - keyword\n    - hybrid\n    - hybrid_rerank\n    """\n''',
        nl,
        "pipeline docstring",
    )

    text = replace_once(
        text,
        '''        evidence_pack = build_evidence_pack(\n            user_query=user_query,\n            query_id=query_id,\n        )\n''',
        '''        evidence_pack = build_evidence_pack(\n            user_query=user_query,\n            query_id=query_id,\n            doc_retriever_mode=doc_retriever_mode,\n        )\n''',
        nl,
        "builder call",
    )

    text = replace_once(
        text,
        '''            "generator_mode": actual_generator_mode,\n            "generation": generation_metadata,\n        }\n''',
        '''            "generator_mode": actual_generator_mode,\n            "doc_retriever_mode": evidence_pack.get(\n                "doc_retriever_mode"\n            ),\n            "generation": generation_metadata,\n        }\n''',
        nl,
        "result metadata",
    )

    write_text(PIPELINE, text)


def create_test() -> None:
    if TEST.exists():
        raise RuntimeError(f"Refusing to overwrite {TEST}")

    TEST.write_text(
        '''"""Tests for selectable document retriever modes."""\n\nfrom __future__ import annotations\n\nfrom typing import Any\n\nimport seismosearch.evidence_builder as evidence_builder\nfrom seismosearch.pipeline import run_pipeline\n\n\ndef fake_result(mode: str) -> dict[str, Any]:\n    return {\n        "tool_name": "doc_retrieval",\n        "status": "ok",\n        "input": {"queries": ["test"], "top_k": 5, "retriever": mode},\n        "chunks": [\n            {\n                "chunk_id": "fake_001",\n                "source_path": "data/processed/docs/seismology_concepts.md",\n                "source_type": "local_markdown",\n                "doc_title": "Seismology Concepts",\n                "heading": "震级和烈度的区别",\n                "text": "震级描述能量，烈度描述地点影响。",\n                "score": 4.2,\n                "matched_terms": ["震级", "烈度"],\n                "retriever": mode,\n                "hybrid_rank": 2,\n                "hybrid_score": 0.03,\n                "rerank_score": 4.2,\n                "reranker_model_name": "fake-reranker",\n            }\n        ],\n        "warnings": [],\n    }\n\n\ndef test_default_mode_is_keyword() -> None:\n    result = run_pipeline(\n        "震级和烈度有什么区别？",\n        include_evidence_pack=True,\n    )\n    assert result["status"] == "ok"\n    assert result["doc_retriever_mode"] == "keyword"\n\n\ndef test_hybrid_rerank_mode_reaches_evidence_pack(monkeypatch) -> None:\n    captured: list[str] = []\n\n    def fake_run(\n        queries: str | list[str],\n        top_k: int,\n        mode: str,\n    ) -> dict[str, Any]:\n        captured.append(mode)\n        return fake_result(mode)\n\n    monkeypatch.setattr(evidence_builder, "run_doc_retrieval", fake_run)\n\n    result = run_pipeline(\n        "震级和烈度有什么区别？",\n        doc_retriever_mode="hybrid_rerank",\n        include_evidence_pack=True,\n    )\n\n    assert result["status"] == "ok"\n    assert captured == ["hybrid_rerank"]\n    assert result["doc_retriever_mode"] == "hybrid_rerank"\n\n    doc = result["evidence_pack"]["doc_evidence"][0]\n    assert doc["retriever"] == "hybrid_rerank"\n    assert doc["hybrid_rank"] == 2\n    assert doc["rerank_score"] == 4.2\n\n\ndef test_unknown_mode_is_rejected() -> None:\n    result = run_pipeline(\n        "震级和烈度有什么区别？",\n        doc_retriever_mode="unknown",\n        include_evidence_pack=False,\n    )\n    assert result["status"] == "error"\n    assert "doc_retriever_mode must be one of" in result["error"]\n''',
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    patch_evidence_builder()
    patch_pipeline()
    create_test()
    print("[PASS] pipeline retriever modes installed")
    print(EVIDENCE)
    print(PIPELINE)
    print(TEST)


if __name__ == "__main__":
    main()
