"""
Main pipeline for SeismoSearch.

Unified flow:

user_query
-> planner.py
-> evidence_builder.py
-> deterministic or LLM-backed generator
-> structured pipeline result
"""

from __future__ import annotations

from typing import Any

from seismosearch.evidence_builder import build_evidence_pack
from seismosearch.generator import generate_answer
from seismosearch.llm_generator import (
    ChatCompletionClient,
    generate_answer_with_llm,
)


PIPELINE_VERSION = "generator_modes_0.2.0"
SUPPORTED_GENERATOR_MODES = {
    "deterministic",
    "llm",
}


def _build_error_result(
    *,
    user_query: Any,
    query_id: str | None,
    generator_mode: Any,
    warning: str,
    error: str,
) -> dict[str, Any]:
    """Build one stable pipeline error response."""
    return {
        "status": "error",
        "pipeline_version": PIPELINE_VERSION,
        "query_id": query_id,
        "user_query": user_query,
        "query_type": None,
        "answer": "",
        "used_evidence_ids": [],
        "warnings": [warning],
        "requested_generator_mode": generator_mode,
        "generator_mode": None,
        "error": error,
    }


def _run_generator(
    evidence_pack: dict[str, Any],
    generator_mode: str,
    llm_client: ChatCompletionClient | None,
) -> dict[str, Any]:
    """Run the requested generator."""
    if generator_mode == "llm":
        return generate_answer_with_llm(
            evidence_pack=evidence_pack,
            client=llm_client,
            fallback_on_error=True,
        )

    result = dict(generate_answer(evidence_pack))
    result["generator_mode"] = "deterministic"
    result["model_name"] = None
    return result


def run_pipeline(
    user_query: str,
    query_id: str | None = None,
    include_evidence_pack: bool = True,
    generator_mode: str = "deterministic",
    llm_client: ChatCompletionClient | None = None,
    doc_retriever_mode: str = "keyword",
) -> dict[str, Any]:
    """
    Run SeismoSearch for one natural-language query.

    generator_mode:
    - deterministic
    - llm

    doc_retriever_mode:
    - keyword
    - hybrid
    - hybrid_rerank
    """
    if not isinstance(user_query, str):
        return _build_error_result(
            user_query=user_query,
            query_id=query_id,
            generator_mode=generator_mode,
            warning="user_query_must_be_a_string",
            error="user_query must be a string.",
        )

    if not isinstance(generator_mode, str):
        return _build_error_result(
            user_query=user_query,
            query_id=query_id,
            generator_mode=generator_mode,
            warning="generator_mode_must_be_a_string",
            error="generator_mode must be a string.",
        )

    normalized_generator_mode = generator_mode.strip().lower()

    if normalized_generator_mode not in SUPPORTED_GENERATOR_MODES:
        supported_text = ", ".join(
            sorted(SUPPORTED_GENERATOR_MODES)
        )

        return _build_error_result(
            user_query=user_query,
            query_id=query_id,
            generator_mode=generator_mode,
            warning="unsupported_generator_mode",
            error=(
                "generator_mode must be one of: "
                f"{supported_text}."
            ),
        )

    try:
        evidence_pack = build_evidence_pack(
            user_query=user_query,
            query_id=query_id,
            doc_retriever_mode=doc_retriever_mode,
        )

        generation_result = _run_generator(
            evidence_pack=evidence_pack,
            generator_mode=normalized_generator_mode,
            llm_client=llm_client,
        )

        actual_generator_mode = generation_result.get(
            "generator_mode",
            normalized_generator_mode,
        )
        generation_warnings = list(
            generation_result.get(
                "warnings",
                evidence_pack.get("warnings", []),
            )
        )

        generation_metadata = {
            "status": generation_result.get("status"),
            "query_type": generation_result.get("query_type"),
            "requested_generator_mode": normalized_generator_mode,
            "generator_mode": actual_generator_mode,
            "model_name": generation_result.get("model_name"),
            "warnings": generation_warnings,
        }

        generation_error = generation_result.get("generation_error")
        if generation_error is not None:
            generation_metadata["generation_error"] = generation_error

        result = {
            "status": "ok",
            "pipeline_version": PIPELINE_VERSION,
            "query_id": evidence_pack.get("query_id"),
            "user_query": user_query,
            "query_type": evidence_pack.get("query_type"),
            "answer": generation_result.get("answer"),
            "used_evidence_ids": generation_result.get(
                "used_evidence_ids",
                [],
            ),
            "warnings": generation_warnings,
            "answer_constraints": evidence_pack.get(
                "answer_constraints",
                {},
            ),
            "requested_generator_mode": normalized_generator_mode,
            "generator_mode": actual_generator_mode,
            "doc_retriever_mode": evidence_pack.get(
                "doc_retriever_mode"
            ),
            "generation": generation_metadata,
        }

        if include_evidence_pack:
            result["evidence_pack"] = evidence_pack

        return result
    except Exception as exc:
        return _build_error_result(
            user_query=user_query,
            query_id=query_id,
            generator_mode=normalized_generator_mode,
            warning="pipeline_execution_failed",
            error=str(exc),
        )
