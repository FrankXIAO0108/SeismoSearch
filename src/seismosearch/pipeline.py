"""
Main pipeline for SeismoSearch.

This module provides a unified entry point for the current SeismoSearch flow:

user_query
-> planner.py
-> evidence_builder.py
-> generator.py
-> pipeline result

The pipeline is intentionally deterministic at this stage.
It does not call an external LLM yet.

Current responsibility:
- accept a natural-language user query;
- build an Evidence Pack;
- generate a constrained answer;
- return a structured result for debugging, evaluation, and future API usage.
"""

from __future__ import annotations

from typing import Any

from seismosearch.evidence_builder import build_evidence_pack
from seismosearch.generator import generate_answer


PIPELINE_VERSION = "deterministic_0.1.0"


def run_pipeline(
    user_query: str,
    query_id: str | None = None,
    include_evidence_pack: bool = True,
) -> dict[str, Any]:
    """
    Run the current SeismoSearch pipeline for one user query.

    Parameters:
    - user_query: natural-language user question;
    - query_id: optional external query ID;
    - include_evidence_pack: whether to include the full Evidence Pack in result.

    Returns:
    - status;
    - pipeline_version;
    - query_id;
    - user_query;
    - query_type;
    - answer;
    - used_evidence_ids;
    - warnings;
    - evidence_pack, optionally.

    This function is the current main entry point for integration testing.
    """
    if not isinstance(user_query, str):
        return {
            "status": "error",
            "pipeline_version": PIPELINE_VERSION,
            "query_id": query_id,
            "user_query": user_query,
            "query_type": None,
            "answer": "",
            "used_evidence_ids": [],
            "warnings": ["user_query_must_be_a_string"],
            "error": "user_query must be a string.",
        }

    try:
        evidence_pack = build_evidence_pack(
            user_query=user_query,
            query_id=query_id,
        )

        generation_result = generate_answer(evidence_pack)

        result = {
            "status": "ok",
            "pipeline_version": PIPELINE_VERSION,
            "query_id": evidence_pack.get("query_id"),
            "user_query": user_query,
            "query_type": evidence_pack.get("query_type"),
            "answer": generation_result.get("answer"),
            "used_evidence_ids": generation_result.get("used_evidence_ids", []),
            "warnings": evidence_pack.get("warnings", []),
            "answer_constraints": evidence_pack.get("answer_constraints", {}),
            "generation": {
                "status": generation_result.get("status"),
                "query_type": generation_result.get("query_type"),
                "warnings": generation_result.get("warnings", []),
            },
        }

        if include_evidence_pack:
            result["evidence_pack"] = evidence_pack

        return result

    except Exception as exc:
        return {
            "status": "error",
            "pipeline_version": PIPELINE_VERSION,
            "query_id": query_id,
            "user_query": user_query,
            "query_type": None,
            "answer": "",
            "used_evidence_ids": [],
            "warnings": [],
            "error": str(exc),
        }