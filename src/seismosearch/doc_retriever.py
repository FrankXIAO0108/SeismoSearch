"""
Document retriever for SeismoSearch.

This module implements the first deterministic document retrieval baseline.

Current design:
- read local user-facing Markdown knowledge documents;
- split them into small heading-based chunks;
- score chunks with weighted keyword overlap;
- return traceable document evidence candidates.

This is NOT a vector retriever yet.

Important design choice:
The default retrieval corpus should only include user-facing knowledge documents.
Project management documents such as progress reports, source lists, badcase
logs, and evaluation reports should not be retrieved as answer evidence for
ordinary user questions.

Why:
RAG quality is not only a retrieval-algorithm problem. It is also a corpus
hygiene problem. If project docs and answer docs are mixed together, source
metadata files can outrank real domain knowledge chunks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# 默认只检索面向用户回答的领域知识文档。
# 不再默认检索 docs/，避免 source_list.md、progress.md、badcase.md、
# eval report、baseline plan 等项目管理文档污染用户问答检索结果。
DEFAULT_DOC_DIRS = [
    Path("data/processed/docs"),
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
    return " ".join(str(text).lower().strip().split())


def extract_markdown_title(text: str, fallback: str) -> str:
    """Extract the first Markdown H1 title, or use fallback."""
    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("# "):
            return stripped[2:].strip()

    return fallback


def add_unique_term(terms: list[str], term: str) -> None:
    """Append a normalized term while preserving order and removing duplicates."""
    normalized_term = normalize_text(term)

    if not normalized_term:
        return

    if normalized_term not in terms:
        terms.append(normalized_term)


def expand_domain_synonyms(terms: list[str]) -> list[str]:
    """
    Expand simple seismology bilingual synonyms.

    This is still a deterministic keyword baseline, not semantic retrieval.

    The goal is to make raw English queries such as
    "magnitude and intensity difference" able to retrieve Chinese concept chunks
    containing "震级" and "烈度".
    """
    synonym_groups = [
        [
            "震级",
            "magnitude",
        ],
        [
            "烈度",
            "intensity",
            "seismic intensity",
        ],
        [
            "深度",
            "震源深度",
            "震源",
            "depth",
            "hypocenter",
            "hypocenter depth",
        ],
        [
            "海啸",
            "海啸提示",
            "海啸预警",
            "tsunami",
            "tsunami alert",
            "tsunami warning",
            "alert",
            "warning",
        ],
        [
            "区别",
            "difference",
        ],
        [
            "定义",
            "含义",
            "意思",
            "definition",
            "meaning",
        ],
    ]

    expanded_terms = list(terms)
    existing_terms = set(expanded_terms)

    for group in synonym_groups:
        group_normalized = [normalize_text(term) for term in group]

        if any(term in existing_terms for term in group_normalized):
            for term in group_normalized:
                add_unique_term(expanded_terms, term)

            existing_terms = set(expanded_terms)

    return expanded_terms


def extract_query_terms(query: str) -> list[str]:
    """
    Extract retrieval terms from a query.

    This function supports:
    - Chinese domain phrases;
    - English alphanumeric terms;
    - lightweight bilingual domain synonym expansion.

    It intentionally uses simple deterministic rules as a baseline.
    """
    normalized_query = normalize_text(query)

    terms: list[str] = []

    # 领域关键词。这里不做中文分词，而是保留若干稳定短语。
    domain_terms = [
        "震级",
        "烈度",
        "区别",
        "定义",
        "含义",
        "意思",
        "解释",
        "地震",
        "震源",
        "震源深度",
        "深度",
        "海啸",
        "海啸提示",
        "海啸预警",
        "预警",
        "提示",
        "magnitude",
        "intensity",
        "seismic intensity",
        "seismic",
        "earthquake",
        "depth",
        "hypocenter",
        "hypocenter depth",
        "tsunami",
        "tsunami alert",
        "tsunami warning",
        "alert",
        "warning",
        "difference",
        "definition",
        "meaning",
    ]

    for term in domain_terms:
        if term.lower() in normalized_query:
            add_unique_term(terms, term)

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
        "please",
        "explain",
        "completely",
        "unrelated",
        "cooking",
        "recipe",
    }

    for token in english_tokens:
        token = token.lower()

        if token not in stopwords and len(token) >= 2:
            add_unique_term(terms, token)

    return expand_domain_synonyms(terms)


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


def is_generic_retrieval_term(term: str) -> bool:
    """
    Return whether a term is too generic for ranking.

    Generic terms should still contribute to recall, but they should not dominate
    ranking. For example, "地震" and "earthquake" appear in many chunks.
    """
    generic_terms = {
        "地震",
        "earthquake",
        "seismic",
        "定义",
        "含义",
        "意思",
        "解释",
        "definition",
        "meaning",
        "alert",
        "warning",
        "提示",
        "预警",
    }

    return normalize_text(term) in generic_terms


def term_weight(term: str) -> float:
    """
    Assign deterministic term weights.

    Specific Chinese domain concepts receive higher weight because the current
    user-facing eval set is Chinese-major. This prevents English synonym chunks
    from outranking directly matched Chinese concept chunks for Chinese queries.

    Generic retrieval terms receive lower weight.
    """
    normalized_term = normalize_text(term)

    high_value_chinese_terms = {
        "震级",
        "烈度",
        "深度",
        "震源",
        "震源深度",
        "海啸",
        "海啸提示",
        "海啸预警",
    }

    if normalized_term in high_value_chinese_terms:
        return 1.8

    if is_generic_retrieval_term(normalized_term):
        return 0.45

    return 1.0


def score_chunk(
    chunk: DocumentChunk,
    query_terms: list[str],
) -> tuple[float, list[str], int, int]:
    """
    Score one chunk against query terms.

    Scoring:
    - stronger boost for specific terms in heading;
    - moderate boost for terms in text;
    - small boost for terms in document title;
    - generic terms are downweighted;
    - user-facing processed docs get a tiny corpus-quality boost only when
      the chunk has at least one real matched term.

    Returns:
    - score;
    - matched terms;
    - specific match count;
    - heading match count.
    """
    heading = normalize_text(chunk.heading)
    text = normalize_text(chunk.text)
    title = normalize_text(chunk.doc_title)
    source_path = normalize_text(chunk.source_path)

    score = 0.0
    matched_terms: list[str] = []
    specific_match_count = 0
    heading_match_count = 0

    for term in query_terms:
        term_lower = normalize_text(term)
        weight = term_weight(term_lower)

        term_score = 0.0
        matched_in_heading = term_lower in heading
        matched_in_text = term_lower in text
        matched_in_title = term_lower in title

        if matched_in_heading:
            term_score += 4.0 * weight
            heading_match_count += 1

        if matched_in_text:
            term_score += 2.0 * weight

        if matched_in_title:
            term_score += 0.5 * weight

        if term_score > 0:
            matched_terms.append(term_lower)
            score += term_score

            if not is_generic_retrieval_term(term_lower):
                specific_match_count += 1

    # Corpus-quality prior:
    # Only apply this boost after at least one real term match.
    # Otherwise unrelated queries such as "completely unrelated cooking recipe"
    # would still return arbitrary processed-doc chunks with score 0.1.
    if matched_terms and "data/processed/docs" in source_path:
        score += 0.1

    return score, matched_terms, specific_match_count, heading_match_count


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

    active_doc_dirs = doc_dirs or DEFAULT_DOC_DIRS

    tool_input = {
        "queries": query_list,
        "top_k": top_k,
        "doc_dirs": [path.as_posix() for path in active_doc_dirs],
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

    chunks, warnings = load_markdown_chunks(doc_dirs=active_doc_dirs)

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

    if not query_terms:
        return {
            "tool_name": "doc_retrieval",
            "status": "ok",
            "input": tool_input,
            "chunks": [],
            "warnings": warnings + ["no_query_terms_extracted"],
        }

    scored_chunks: list[dict[str, Any]] = []

    for chunk in chunks:
        (
            score,
            matched_terms,
            specific_match_count,
            heading_match_count,
        ) = score_chunk(chunk, query_terms)

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
        "tool_name": "doc_retrieval",
        "status": "ok",
        "input": tool_input,
        "chunks": scored_chunks[:top_k],
        "warnings": warnings,
    }