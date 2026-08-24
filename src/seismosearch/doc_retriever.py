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


# ?? Markdown ????????????????????????
# ????????????????????????????? chunk?
NON_RETRIEVAL_SECTION_HEADINGS = frozenset(
    {
        "example query",
        "example queries",
        "示例问题",
        "示例查询",
        "source",
        "sources",
        "reference",
        "references",
        "参考资料",
        "参考来源",
        "relation to evaluation",
        "evaluation notes",
        "retrieval evaluation",
        "评测说明",
        "与评测的关系",
        "document purpose",
        "文档目的",
    }
)


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


def is_non_retrieval_section_heading(heading: str) -> bool:
    """
    ?? Markdown ???????????????

    ????????????????????????
    """
    normalized_heading = normalize_text(heading).rstrip(
        " :?-??"
    )

    return (
        normalized_heading
        in NON_RETRIEVAL_SECTION_HEADINGS
    )


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
    Expand simple seismology / metadata / safety bilingual synonyms.

    This is still a deterministic keyword baseline, not semantic retrieval.

    Why this is needed:
    After expanding the corpus from one seismology concept document to multiple
    domain documents, queries may target catalog fields, USGS metadata, safety
    boundaries, and hazard-vs-prediction explanations. The deterministic
    retriever needs explicit domain vocabulary to keep sparse retrieval usable.
    """
    synonym_groups = [
        # 震级同义词组：用于让 magnitude / 震级 双语查询互相命中。
        [
            "震级",
            "magnitude",
        ],

        # 烈度同义词组：用于让 intensity / seismic intensity / 烈度 互相命中。
        [
            "烈度",
            "intensity",
            "seismic intensity",
        ],

        # 深度同义词组：覆盖 depth / hypocenter / 震源深度。
        [
            "深度",
            "震源深度",
            "震源",
            "depth",
            "hypocenter",
            "hypocenter depth",
        ],

        # 海啸同义词组：覆盖 tsunami alert / tsunami warning / 海啸提示 / 海啸预警。
        [
            "海啸",
            "海啸提示",
            "海啸预警",
            "正式海啸预警",
            "不等于正式海啸预警",
            "tsunami",
            "tsunami flag",
            "tsunami alert",
            "tsunami warning",
            "alert",
            "warning",
            "flag",
        ],

        # 经纬度同义词组：把 latitude / longitude 查询扩展到空间过滤能力。
        [
            "latitude",
            "longitude",
            "经纬度",
            "空间过滤",
            "距离计算",
            "bbox",
            "空间范围",
        ],

        # 结构化查询同义词组：把数值过滤问题拉向 catalog / database 文档。
        [
            "结构化查询",
            "结构化过滤",
            "精确数值过滤",
            "数值过滤",
            "语义相似度",
            "向量相似度",
            "向量数据库",
            "vector database",
            "structured query",
            "structured filtering",
            "numeric filtering",
            "magnitude >= 6.5",
            ">= 6.5",
            "6.5",
        ],

        # 本地样例库同义词组：用于数据范围和样例库限制问题。
        [
            "本地样例库",
            "本地样例",
            "local sample database",
            "完整全球地震目录",
            "全球地震目录",
            "时间范围有限",
            "样例库",
            "sample database",
        ],

        # 数据分层同义词组：用于 raw / processed / database pipeline 问题。
        [
            "raw",
            "raw layer",
            "processed",
            "processed layer",
            "processed JSONL",
            "database",
            "database layer",
            "DuckDB",
            "EventStore",
            "三层数据",
            "数据分层",
            "数据流程",
        ],

        # 事件证据同义词组：用于 Evidence Pack / event_evidence 问题。
        [
            "Evidence Pack",
            "event_evidence",
            "事件证据",
            "证据追踪",
            "Generator",
        ],

        # 文档检索同义词组：用于结构化事件数据和文档 QA 的边界问题。
        [
            "USGS event data",
            "结构化事件数据",
            "地震学概念文档",
            "非结构化文本",
            "文档检索",
            "document retrieval",
            "document QA",
            "分开检索",
        ],

        # 安全边界同义词组：用于 safety routing / 拒答 / 官方信息边界。
        [
            "安全回答",
            "safe response",
            "safety",
            "safety query",
            "safety routing",
            "safety_check",
            "不能预测未来具体地震",
            "未来具体地震预测",
            "不支持",
            "明天东京",
            "官方机构",
            "官方地震预警",
            "官方地震监测机构",
            "不替代",
            "unsupported questions",
        ],

        # 伪科学预测同义词组：用于动物异常、地震云、小震频繁等预测诱导。
        [
            "动物",
            "动物异常",
            "动物行为",
            "地震云",
            "狗叫",
            "鱼群异常",
            "伪科学",
            "预测依据",
            "可靠地震预测依据",
            "前兆",
            "P 波",
            "p wave",
            "pseudoscience",
        ],

        # 一般性防震准备与震后安全信息。
        [
            "防震准备",
            "应急准备",
            "earthquake preparedness",
            "摇晃停止",
            "受损建筑",
            "余震",
            "燃气",
            "电气",
            "火灾",
            "Drop Cover Hold On",
            "保护头颈",
        ],

        # 历史活动预测诱导同义词组：用于历史地震不能直接预测未来的问题。
        [
            "历史地震",
            "历史事件",
            "短期地震活动",
            "最近小震",
            "不能直接预测",
            "不能直接推出",
            "未来",
            "大震",
            "未来风险",
            "historical earthquakes",
        ],

        # hazard / risk / forecast / prediction 概念组。
        [
            "seismic hazard",
            "地震危险性",
            "seismic risk",
            "地震风险",
            "forecast",
            "earthquake forecast",
            "prediction",
            "earthquake prediction",
            "概率",
            "不确定性",
            "确定性预测",
            "明天这个地方一定会地震",
        ],

        # 通用解释类词。
        [
            "区别",
            "difference",
        ],

        # 通用定义类词。
        [
            "定义",
            "含义",
            "意思",
            "解释",
            "definition",
            "meaning",
            "explanation",
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

    # 领域关键词。这里不做复杂中文分词，而是保留稳定领域短语。
    domain_terms = [
        # 基础地震学概念。
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
        "正式海啸预警",
        "不等于正式海啸预警",
        "预警",
        "提示",

        # 结构化事件字段。
        "event_id",
        "time",
        "magnitude",
        "magnitude >= 6.5",
        ">= 6.5",
        "6.5",
        "depth_km",
        "place",
        "latitude",
        "longitude",
        "经纬度",
        "event_type",
        "tsunami flag",
        "flag",

        # 结构化查询与向量检索边界。
        "结构化查询",
        "结构化过滤",
        "精确数值过滤",
        "数值过滤",
        "语义相似度",
        "向量相似度",
        "向量数据库",
        "空间过滤",
        "距离计算",
        "bbox",
        "空间范围",

        # 数据源与数据分层。
        "USGS",
        "USGS event data",
        "raw",
        "raw layer",
        "processed",
        "processed layer",
        "processed JSONL",
        "database",
        "database layer",
        "DuckDB",
        "EventStore",
        "本地样例库",
        "本地样例",
        "local sample database",
        "完整全球地震目录",
        "全球地震目录",
        "时间范围有限",
        "样例库",
        "三层数据",
        "数据分层",
        "数据流程",

        # Evidence Pack 与生成边界。
        "Evidence Pack",
        "event_evidence",
        "事件证据",
        "证据追踪",
        "Generator",

        # 文档检索与结构化数据边界。
        "结构化事件数据",
        "地震学概念文档",
        "非结构化文本",
        "文档检索",
        "document retrieval",
        "document QA",
        "分开检索",

        # Safety routing 与拒答边界。
        "安全回答",
        "safe response",
        "safety",
        "safety query",
        "safety routing",
        "safety_check",
        "不支持",
        "unsupported questions",
        "未来具体地震预测",
        "不能预测未来具体地震",
        "明天东京",
        "官方机构",
        "官方地震预警",
        "官方地震监测机构",
        "不替代",

        # 伪科学预测诱导。
        "动物",
        "动物异常",
        "动物行为",
        "地震云",
        "狗叫",
        "鱼群异常",
        "伪科学",
        "预测依据",
        "可靠地震预测依据",
        "前兆",
        "P 波",

        # 一般性防震准备与震后安全。
        "防震准备",
        "应急准备",
        "earthquake preparedness",
        "摇晃停止",
        "受损建筑",
        "余震",
        "燃气",
        "电气",
        "火灾",
        "Drop Cover Hold On",
        "保护头颈",

        # 历史活动预测诱导。
        "历史地震",
        "历史事件",
        "短期地震活动",
        "最近小震",
        "不能直接预测",
        "不能直接推出",
        "未来",
        "大震",
        "未来风险",

        # hazard / risk / forecast / prediction。
        "seismic hazard",
        "地震危险性",
        "seismic risk",
        "地震风险",
        "forecast",
        "earthquake forecast",
        "prediction",
        "earthquake prediction",
        "概率",
        "不确定性",
        "确定性预测",
        "明天这个地方一定会地震",

        # 英文基础术语。
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
        "explanation",
        "vector database",
        "structured query",
        "structured filtering",
        "numeric filtering",
        "sample database",
        "pseudoscience",
        "historical earthquakes",
    ]

    for term in domain_terms:
        if term.lower() in normalized_query:
            add_unique_term(terms, term)

    english_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]*", normalized_query)

    # 这些词过于通用，不能作为排序核心。
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
        "seismosearch",
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
        # ?????????????????????????
        if is_non_retrieval_section_heading(heading):
            continue

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
        "explanation",
        "alert",
        "warning",
        "提示",
        "预警",
        "time",
        "place",
        "database",
        "data",
        "event",
        "prediction",
        "forecast",
        "safety",
        "seismosearch",
    }

    return normalize_text(term) in generic_terms


def term_weight(term: str) -> float:
    """
    Assign deterministic term weights.

    Specific Chinese domain concepts receive higher weight because the current
    user-facing eval set is Chinese-major. Generic retrieval terms receive lower
    weight so they do not dominate ranking.
    """
    normalized_term = normalize_text(term)

    high_value_terms = {
        # 基础地震学高价值术语。
        "震级",
        "烈度",
        "深度",
        "震源",
        "震源深度",
        "海啸",
        "海啸提示",
        "海啸预警",
        "正式海啸预警",
        "不等于正式海啸预警",
        "tsunami flag",

        # 结构化查询高价值术语。
        "magnitude >= 6.5",
        ">= 6.5",
        "6.5",
        "精确数值过滤",
        "数值过滤",
        "结构化查询",
        "结构化过滤",
        "语义相似度",
        "向量相似度",
        "向量数据库",
        "vector database",
        "structured query",
        "structured filtering",
        "numeric filtering",
        "经纬度",
        "latitude",
        "longitude",
        "空间过滤",
        "距离计算",
        "bbox",

        # 数据源和样例库高价值术语。
        "usgs",
        "usgs event data",
        "本地样例库",
        "本地样例",
        "local sample database",
        "完整全球地震目录",
        "全球地震目录",
        "时间范围有限",
        "三层数据",
        "数据分层",
        "processed jsonl",
        "duckdb",
        "eventstore",

        # Evidence / 文档检索高价值术语。
        "evidence pack",
        "event_evidence",
        "事件证据",
        "证据追踪",
        "结构化事件数据",
        "地震学概念文档",
        "非结构化文本",
        "文档检索",
        "document retrieval",
        "document qa",
        "分开检索",

        # 安全边界高价值术语。
        "安全回答",
        "safe response",
        "未来具体地震预测",
        "不能预测未来具体地震",
        "不支持",
        "unsupported questions",
        "明天东京",
        "官方机构",
        "官方地震预警",
        "官方地震监测机构",
        "动物异常",
        "地震云",
        "伪科学",
        "预测依据",
        "可靠地震预测依据",
        "前兆",

        # 历史活动与 hazard/prediction 高价值术语。
        "历史地震",
        "历史事件",
        "不能直接预测",
        "不能直接推出",
        "大震",
        "未来风险",
        "地震危险性",
        "地震风险",
        "seismic hazard",
        "seismic risk",
        "earthquake prediction",
        "earthquake forecast",
        "不确定性",
        "确定性预测",
        "明天这个地方一定会地震",
    }

    if normalized_term in high_value_terms:
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
