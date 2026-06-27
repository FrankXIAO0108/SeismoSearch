"""
Document retriever for SeismoSearch.

This module implements the first deterministic document retrieval baseline.

Current design:
- read local Markdown documents;
- split them into small heading-based chunks;
- score chunks with keyword overlap;
- return traceable document evidence candidates.

This is NOT a vector retriever yet.

Reason for starting with deterministic retrieval:
- easy to test;
- easy to debug;
- provides a baseline before adding embeddings / vector DB;
- avoids hiding retrieval quality problems behind a black-box model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_DOC_DIRS = [
    Path("data/processed/docs"),
    Path("docs"),
]

DEFAULT_TOP_K = 5


@dataclass
class DocumentChunk:
    """A local document chunk used for retrieval."""

    chunk_id: str
    source_path: str
    source_type: str
    doc_title: str
    heading: str
    text: str


def normalize_text(text: str) -> str:
    """Normalize text for deterministic keyword matching."""
    return " ".join(text.lower().strip().split())


def extract_markdown_title(text: str, fallback: str) -> str:
    """Extract the first Markdown H1 title, or use fallback."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()

    return fallback


def extract_query_terms(query: str) -> list[str]:
    """
    Extract retrieval terms from a query.

    This function supports both:
    - Chinese domain phrases;
    - English alphanumeric terms.

    It intentionally uses simple rules as a deterministic baseline.
    """
    normalized_query = normalize_text(query)

    terms: list[str] = []

    domain_terms = [
        "震级",
        "烈度",
        "区别",
        "地震",
        "震源",
        "深度",
        "海啸",
        "预警",
        "magnitude",
        "intensity",
        "seismic",
        "earthquake",
        "depth",
        "tsunami",
        "warning",
        "difference",
        "definition",
    ]

    for term in domain_terms:
        if term.lower() in normalized_query:
            terms.append(term.lower())

    english_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]*", normalized_query)

    stopwords = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "is",
        "are",
        "what",
        "why",
        "how",
        "in",
        "for",
        "with",
        "vs",
    }

    for token in english_tokens:
        token = token.lower()
        if token not in stopwords and len(token) >= 2:
            terms.append(token)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(terms))


def split_markdown_into_chunks(
    text: str,
    source_path: Path,
    max_chars: int = 900,
) -> list[DocumentChunk]:
    """
    Split a Markdown document into heading-based chunks.

    Strategy:
    - H2 headings start a new semantic section;
    - long sections are further split by character length;
    - each chunk keeps title, heading, source path, and text.
    """
    doc_title = extract_markdown_title(text, fallback=source_path.stem)

    sections: list[tuple[str, list[str]]] = []
    current_heading = doc_title
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("## "):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = stripped[3:].strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    chunks: list[DocumentChunk] = []
    chunk_index = 1

    for heading, lines in sections:
        section_text = "\n".join(lines).strip()

        if not section_text:
            continue

        # Simple long-section splitting.
        start = 0
        while start < len(section_text):
            piece = section_text[start : start + max_chars].strip()
            start += max_chars

            if not piece:
                continue

            chunk = DocumentChunk(
                chunk_id=f"{source_path.stem}_{chunk_index:03d}",
                source_path=source_path.as_posix(),
                source_type="local_markdown",
                doc_title=doc_title,
                heading=heading,
                text=piece,
            )
            chunks.append(chunk)
            chunk_index += 1

    return chunks


def load_markdown_chunks(
    doc_dirs: list[Path] | None = None,
) -> tuple[list[DocumentChunk], list[str]]:
    """Load Markdown chunks from configured document directories."""
    doc_dirs = doc_dirs or DEFAULT_DOC_DIRS

    chunks: list[DocumentChunk] = []
    warnings: list[str] = []

    markdown_paths: list[Path] = []

    for doc_dir in doc_dirs:
        if not doc_dir.exists():
            warnings.append(f"doc_dir_not_found:{doc_dir.as_posix()}")
            continue

        markdown_paths.extend(sorted(doc_dir.glob("*.md")))

    if not markdown_paths:
        warnings.append("no_markdown_documents_found")

    for path in markdown_paths:
        try:
            text = path.read_text(encoding="utf-8")
            chunks.extend(split_markdown_into_chunks(text=text, source_path=path))
        except UnicodeDecodeError:
            warnings.append(f"failed_to_read_utf8:{path.as_posix()}")

    return chunks, warnings


def score_chunk(chunk: DocumentChunk, query_terms: list[str]) -> tuple[float, list[str]]:
    """
    Score one chunk against query terms.

    Scoring is intentionally simple:
    - +3 for term in heading;
    - +2 for term in chunk text;
    - +1 for term in document title.

    Returns:
    - score;
    - matched terms.
    """
    heading = normalize_text(chunk.heading)
    text = normalize_text(chunk.text)
    title = normalize_text(chunk.doc_title)

    score = 0.0
    matched_terms: list[str] = []

    for term in query_terms:
        term_lower = term.lower()

        term_score = 0.0

        if term_lower in heading:
            term_score += 3.0

        if term_lower in text:
            term_score += 2.0

        if term_lower in title:
            term_score += 1.0

        if term_score > 0:
            matched_terms.append(term_lower)
            score += term_score

    return score, matched_terms


def retrieve_docs(
    queries: str | list[str],
    top_k: int = DEFAULT_TOP_K,
    doc_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """
    Retrieve local Markdown chunks for one or more retrieval queries.

    Parameters:
    - queries: a single query string or a list of rewritten retrieval queries;
    - top_k: number of chunks to return;
    - doc_dirs: optional local document directories.

    Returns a tool-like retrieval result that can later be converted into
    doc_evidence by evidence_builder.py.
    """
    if isinstance(queries, str):
        query_list = [queries]
    else:
        query_list = queries

    query_list = [query for query in query_list if query and query.strip()]

    tool_input = {
        "queries": query_list,
        "top_k": top_k,
        "doc_dirs": [path.as_posix() for path in (doc_dirs or DEFAULT_DOC_DIRS)],
    }

    if top_k <= 0:
        return {
            "tool_name": "doc_retrieval",
            "status": "error",
            "input": tool_input,
            "chunks": [],
            "warnings": [],
            "error": "top_k must be positive.",
        }

    if not query_list:
        return {
            "tool_name": "doc_retrieval",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": ["empty_retrieval_query"],
        }

    chunks, warnings = load_markdown_chunks(doc_dirs=doc_dirs)

    if not chunks:
        return {
            "tool_name": "doc_retrieval",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": warnings,
        }

    all_terms: list[str] = []

    for query in query_list:
        all_terms.extend(extract_query_terms(query))

    query_terms = list(dict.fromkeys(all_terms))

    scored_chunks: list[dict[str, Any]] = []

    for chunk in chunks:
        score, matched_terms = score_chunk(chunk, query_terms)

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
            }
        )

    scored_chunks.sort(
        key=lambda item: (
            item["score"],
            len(item["matched_terms"]),
            item["chunk_id"],
        ),
        reverse=True,
    )

    return {
        "tool_name": "doc_retrieval",
        "status": "ok",
        "input": tool_input,
        "chunks": scored_chunks[:top_k],
        "warnings": warnings,
    }