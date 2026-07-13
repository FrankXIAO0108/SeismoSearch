"""
Deterministic citation-support checks for SeismoSearch evaluation.

This module deliberately separates two concepts:

1. Citation validity:
   Does the answer cite evidence IDs that exist in the Evidence Pack?

2. Citation support:
   Do the cited evidence items satisfy the reference evidence requirements
   for the evaluation sample?

The second check is not a general natural-language-inference model. It is a
deterministic, inspectable evaluation contract that catches cases where an
answer cites a valid but irrelevant document chunk.
"""

from __future__ import annotations

import re
from typing import Any


CITATION_PATTERN = re.compile(
    r"\[(event_\d{3}|computed_\d{3}|doc_\d{3})\]"
)

EVIDENCE_FIELDS = (
    "event_evidence",
    "computed_evidence",
    "doc_evidence",
)


def extract_inline_citation_ids(answer: str) -> list[str]:
    """Extract unique inline citation IDs in appearance order."""
    citation_ids: list[str] = []

    for evidence_id in CITATION_PATTERN.findall(answer):
        if evidence_id not in citation_ids:
            citation_ids.append(evidence_id)

    return citation_ids


def build_evidence_index(
    evidence_pack: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Index Evidence Pack items by evidence_id."""
    index: dict[str, dict[str, Any]] = {}

    for field_name in EVIDENCE_FIELDS:
        items = evidence_pack.get(field_name, [])

        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            evidence_id = item.get("evidence_id")

            if not isinstance(evidence_id, str):
                continue

            if not evidence_id:
                continue

            index[evidence_id] = item

    return index


def _combine_cited_doc_text(
    cited_doc_items: list[dict[str, Any]],
) -> str:
    """Combine only cited document evidence for requirement checks."""
    parts: list[str] = []

    for item in cited_doc_items:
        parts.extend(
            [
                str(item.get("doc_title", "")),
                str(item.get("heading", "")),
                str(item.get("text", "")),
                str(item.get("source_path", "")),
            ]
        )

    return "\n".join(parts)


def check_reference_citation_support(
    sample: dict[str, Any],
    answer: str,
    evidence_pack: dict[str, Any],
) -> dict[str, Any]:
    """
    Check whether cited evidence satisfies reference requirements.

    Evaluation rules:
    - unknown inline citation IDs fail;
    - gold_event_required requires at least one cited event evidence item;
    - gold_doc_required requires at least one cited document evidence item;
    - document terms and expected source path are checked against cited
      document evidence only, not against every retrieved chunk;
    - samples without event or document requirements are not applicable.

    The returned diagnostics are intentionally explicit so failure analysis
    can distinguish structural citation errors from evidence-support errors.
    """
    event_required = sample.get("gold_event_required") is True
    doc_required = sample.get("gold_doc_required") is True
    applicable = event_required or doc_required

    citation_ids = extract_inline_citation_ids(answer)
    evidence_index = build_evidence_index(evidence_pack)

    unknown_citation_ids = [
        evidence_id
        for evidence_id in citation_ids
        if evidence_id not in evidence_index
    ]

    cited_event_ids = [
        evidence_id
        for evidence_id in citation_ids
        if evidence_id.startswith("event_")
        and evidence_id in evidence_index
    ]

    cited_doc_ids = [
        evidence_id
        for evidence_id in citation_ids
        if evidence_id.startswith("doc_")
        and evidence_id in evidence_index
    ]

    cited_doc_items = [
        evidence_index[evidence_id]
        for evidence_id in cited_doc_ids
    ]

    missing_event_citation = (
        event_required and not cited_event_ids
    )
    missing_doc_citation = (
        doc_required and not cited_doc_ids
    )

    requirements = sample.get(
        "gold_doc_requirements",
        {},
    )

    if not isinstance(requirements, dict):
        requirements = {}

    required_terms = requirements.get(
        "must_contain_terms",
        [],
    )

    if not isinstance(required_terms, list):
        required_terms = []

    normalized_required_terms = [
        str(term)
        for term in required_terms
        if str(term)
    ]

    expected_source = requirements.get(
        "expected_source_path_contains"
    )

    cited_doc_text = _combine_cited_doc_text(
        cited_doc_items
    )
    normalized_cited_doc_text = cited_doc_text.lower()

    missing_doc_terms: list[str] = []

    if doc_required:
        missing_doc_terms = [
            term
            for term in normalized_required_terms
            if term.lower() not in normalized_cited_doc_text
        ]

    source_path_match: bool | None = None

    if doc_required and isinstance(expected_source, str):
        source_path_match = any(
            expected_source
            in str(item.get("source_path", ""))
            for item in cited_doc_items
        )

    valid: bool | None

    if not applicable:
        valid = None
    else:
        valid = (
            not unknown_citation_ids
            and not missing_event_citation
            and not missing_doc_citation
            and not missing_doc_terms
            and source_path_match is not False
        )

    return {
        "applicable": applicable,
        "valid": valid,
        "citation_ids": citation_ids,
        "unknown_citation_ids": unknown_citation_ids,
        "cited_event_ids": cited_event_ids,
        "cited_doc_ids": cited_doc_ids,
        "missing_event_citation": missing_event_citation,
        "missing_doc_citation": missing_doc_citation,
        "required_doc_terms": normalized_required_terms,
        "missing_doc_terms": missing_doc_terms,
        "expected_source_path_contains": expected_source,
        "source_path_match": source_path_match,
    }
