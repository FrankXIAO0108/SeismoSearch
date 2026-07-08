"""
Retrieval evaluation runner for SeismoSearch.

This script evaluates document retrieval quality independently from the full
pipeline.

Why this exists:
The main run_eval.py checks whether doc_evidence exists inside the full
pipeline result. That is useful, but it does not isolate the retrieval layer.

This script focuses only on retrieval:

- Does the retriever return the expected source document?
- Does the returned top-k evidence contain required terms?
- At what rank does the first correct chunk appear?
- Does planner-based query rewriting improve retrieval compared with raw query?
- Does BM25 improve over the deterministic keyword-overlap baseline?
- Does dense retrieval improve semantic matching over sparse retrieval?
- Does hybrid retrieval improve over single retrievers?
- Does hybrid + reranker improve chunk-level ranking?

Supported retrievers:
- keyword: weighted keyword-overlap retriever from doc_retriever.py;
- bm25: lightweight deterministic BM25 retriever from bm25_retriever.py;
- dense: sentence-transformers dense retriever from dense_retriever.py;
- hybrid: BM25 + dense RRF retriever from hybrid_retriever.py;
- hybrid_rerank: hybrid retriever + cross-encoder reranker from reranker.py.

Evaluation requirements:
- expected_source_path_contains:
  require at least one returned chunk to come from the expected source path.
- must_contain_terms:
  exact terms that must all appear.
- must_contain_any_groups:
  alias-aware requirements. Each group means "at least one term in this group
  must appear". This is useful for bilingual retrieval evaluation, e.g.
  ["magnitude", "震级"] or ["intensity", "烈度"].
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from seismosearch.bm25_retriever import retrieve_docs_bm25
from seismosearch.dense_retriever import retrieve_docs_dense
from seismosearch.doc_retriever import retrieve_docs
from seismosearch.hybrid_retriever import retrieve_docs_hybrid
from seismosearch.planner import plan_query
from seismosearch.reranker import retrieve_docs_hybrid_rerank


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load retrieval eval samples from JSONL."""
    samples: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL at line {line_number}: {error}"
                ) from error

    return samples


def normalize_text(text: str) -> str:
    """Normalize text for deterministic matching."""
    return " ".join(str(text).lower().strip().split())


def build_retrieval_queries(
    sample: dict[str, Any],
    query_mode: str,
) -> list[str]:
    """
    Build retrieval queries for one sample.

    query_mode:
    - raw:
      use the original user query only.
    - planner:
      use planner-generated doc_retrieval_queries when available.
    """
    user_query = sample["query"]

    if query_mode == "raw":
        return [user_query]

    if query_mode == "planner":
        planner_output = plan_query(user_query)
        doc_queries = planner_output.get("doc_retrieval_queries", [])

        if doc_queries:
            return doc_queries

        return [user_query]

    raise ValueError(f"Unsupported query_mode: {query_mode}")


def run_retriever(
    retriever: str,
    retrieval_queries: list[str],
    top_k: int,
) -> dict[str, Any]:
    """Run the selected retriever."""
    if retriever == "keyword":
        return retrieve_docs(
            queries=retrieval_queries,
            top_k=top_k,
        )

    if retriever == "bm25":
        return retrieve_docs_bm25(
            queries=retrieval_queries,
            top_k=top_k,
        )

    if retriever == "dense":
        return retrieve_docs_dense(
            queries=retrieval_queries,
            top_k=top_k,
        )

    if retriever == "hybrid":
        return retrieve_docs_hybrid(
            queries=retrieval_queries,
            top_k=top_k,
        )

    if retriever == "hybrid_rerank":
        return retrieve_docs_hybrid_rerank(
            queries=retrieval_queries,
            top_k=top_k,
        )

    raise ValueError(f"Unsupported retriever: {retriever}")


def chunk_to_searchable_text(chunk: dict[str, Any]) -> str:
    """
    Combine chunk fields into a single string for requirement checks.

    matched_terms is included because the retriever may have matched aliases
    that do not always appear literally in the short displayed fields.
    """
    return "\n".join(
        [
            str(chunk.get("source_path", "")),
            str(chunk.get("doc_title", "")),
            str(chunk.get("heading", "")),
            str(chunk.get("text", "")),
            " ".join(chunk.get("matched_terms", [])),
        ]
    )


def chunks_to_combined_text(chunks: list[dict[str, Any]]) -> str:
    """Combine all top-k chunks into normalized searchable text."""
    return normalize_text(
        "\n".join(chunk_to_searchable_text(chunk) for chunk in chunks)
    )


def check_source_hit(
    chunks: list[dict[str, Any]],
    expected_source_path_contains: str | None,
) -> bool:
    """
    Check whether any returned chunk comes from the expected source path.

    If the sample does not specify expected_source_path_contains, return True.
    """
    if expected_source_path_contains is None:
        return True

    for chunk in chunks:
        source_path = str(chunk.get("source_path", ""))

        if expected_source_path_contains in source_path:
            return True

    return False


def check_exact_terms_in_text(
    searchable_text: str,
    must_contain_terms: list[str],
) -> bool:
    """
    Check exact term requirements against one searchable text string.

    Every term in must_contain_terms must appear.
    """
    if not must_contain_terms:
        return True

    for term in must_contain_terms:
        if normalize_text(term) not in searchable_text:
            return False

    return True


def check_any_groups_in_text(
    searchable_text: str,
    must_contain_any_groups: list[list[str]],
) -> bool:
    """
    Check alias-aware term groups against one searchable text string.

    Each group means:
    - at least one item in this group must appear.
    """
    if not must_contain_any_groups:
        return True

    for group in must_contain_any_groups:
        normalized_group = [
            normalize_text(term)
            for term in group
            if normalize_text(term)
        ]

        if not normalized_group:
            continue

        if not any(term in searchable_text for term in normalized_group):
            return False

    return True


def check_exact_term_hit(
    chunks: list[dict[str, Any]],
    must_contain_terms: list[str],
) -> bool:
    """Check exact term requirements over combined top-k retrieved text."""
    combined_text = chunks_to_combined_text(chunks)

    return check_exact_terms_in_text(
        searchable_text=combined_text,
        must_contain_terms=must_contain_terms,
    )


def check_any_group_hit(
    chunks: list[dict[str, Any]],
    must_contain_any_groups: list[list[str]],
) -> bool:
    """Check alias-aware requirements over combined top-k retrieved text."""
    combined_text = chunks_to_combined_text(chunks)

    return check_any_groups_in_text(
        searchable_text=combined_text,
        must_contain_any_groups=must_contain_any_groups,
    )


def check_term_hit(
    chunks: list[dict[str, Any]],
    must_contain_terms: list[str],
    must_contain_any_groups: list[list[str]],
) -> bool:
    """
    Check all term requirements.

    Backward compatibility:
    - old eval files can still use must_contain_terms;
    - new eval files can use must_contain_any_groups;
    - samples may use both.
    """
    exact_term_hit = check_exact_term_hit(
        chunks=chunks,
        must_contain_terms=must_contain_terms,
    )

    any_group_hit = check_any_group_hit(
        chunks=chunks,
        must_contain_any_groups=must_contain_any_groups,
    )

    return exact_term_hit and any_group_hit


def chunk_satisfies_requirements(
    chunk: dict[str, Any],
    expected_source_path_contains: str | None,
    must_contain_terms: list[str],
    must_contain_any_groups: list[list[str]],
) -> bool:
    """
    Check whether one chunk satisfies source, exact term, and alias-group
    requirements.

    This is used for MRR calculation.
    """
    searchable_text = normalize_text(chunk_to_searchable_text(chunk))

    if expected_source_path_contains is not None:
        source_path = str(chunk.get("source_path", ""))

        if expected_source_path_contains not in source_path:
            return False

    if not check_exact_terms_in_text(
        searchable_text=searchable_text,
        must_contain_terms=must_contain_terms,
    ):
        return False

    if not check_any_groups_in_text(
        searchable_text=searchable_text,
        must_contain_any_groups=must_contain_any_groups,
    ):
        return False

    return True


def compute_reciprocal_rank(
    chunks: list[dict[str, Any]],
    expected_source_path_contains: str | None,
    must_contain_terms: list[str],
    must_contain_any_groups: list[list[str]],
) -> float:
    """
    Compute reciprocal rank of the first chunk satisfying requirements.

    Return 0.0 when no retrieved chunk satisfies requirements.
    """
    for rank, chunk in enumerate(chunks, start=1):
        if chunk_satisfies_requirements(
            chunk=chunk,
            expected_source_path_contains=expected_source_path_contains,
            must_contain_terms=must_contain_terms,
            must_contain_any_groups=must_contain_any_groups,
        ):
            return 1.0 / rank

    return 0.0


def evaluate_sample(
    sample: dict[str, Any],
    query_mode: str,
    retriever: str,
    top_k: int,
) -> dict[str, Any]:
    """Evaluate one retrieval sample."""
    retrieval_queries = build_retrieval_queries(
        sample=sample,
        query_mode=query_mode,
    )

    retrieval_result = run_retriever(
        retriever=retriever,
        retrieval_queries=retrieval_queries,
        top_k=top_k,
    )

    chunks = retrieval_result.get("chunks", [])

    expected_source_path_contains = sample.get("expected_source_path_contains")
    must_contain_terms = sample.get("must_contain_terms", [])
    must_contain_any_groups = sample.get("must_contain_any_groups", [])

    source_hit = check_source_hit(
        chunks=chunks,
        expected_source_path_contains=expected_source_path_contains,
    )

    exact_term_hit = check_exact_term_hit(
        chunks=chunks,
        must_contain_terms=must_contain_terms,
    )

    any_group_hit = check_any_group_hit(
        chunks=chunks,
        must_contain_any_groups=must_contain_any_groups,
    )

    term_hit = exact_term_hit and any_group_hit

    requirement_hit = source_hit and term_hit

    reciprocal_rank = compute_reciprocal_rank(
        chunks=chunks,
        expected_source_path_contains=expected_source_path_contains,
        must_contain_terms=must_contain_terms,
        must_contain_any_groups=must_contain_any_groups,
    )

    top_chunks = []

    for rank, chunk in enumerate(chunks, start=1):
        top_chunks.append(
            {
                "rank": rank,
                "chunk_id": chunk.get("chunk_id"),
                "source_path": chunk.get("source_path"),
                "heading": chunk.get("heading"),
                "score": chunk.get("score"),
                "matched_terms": chunk.get("matched_terms", []),
                "retriever": chunk.get("retriever", retriever),
                "retriever_ranks": chunk.get("retriever_ranks", {}),
                "hybrid_rank": chunk.get("hybrid_rank"),
                "hybrid_score": chunk.get("hybrid_score"),
                "rerank_score": chunk.get("rerank_score"),
                "reranker_model_name": chunk.get("reranker_model_name"),
            }
        )

    failed_checks = []

    if not source_hit:
        failed_checks.append("source_hit")

    if not exact_term_hit:
        failed_checks.append("exact_term_hit")

    if not any_group_hit:
        failed_checks.append("any_group_hit")

    if not requirement_hit:
        failed_checks.append("requirement_hit")

    return {
        "query_id": sample.get("query_id"),
        "query": sample.get("query"),
        "query_mode": query_mode,
        "retriever": retriever,
        "retrieval_queries": retrieval_queries,
        "expected_source_path_contains": expected_source_path_contains,
        "must_contain_terms": must_contain_terms,
        "must_contain_any_groups": must_contain_any_groups,
        "source_hit": source_hit,
        "exact_term_hit": exact_term_hit,
        "any_group_hit": any_group_hit,
        "term_hit": term_hit,
        "requirement_hit": requirement_hit,
        "reciprocal_rank": reciprocal_rank,
        "failed_checks": failed_checks,
        "top_chunks": top_chunks,
        "warnings": retrieval_result.get("warnings", []),
    }


def safe_ratio(values: list[bool]) -> float:
    """Compute ratio safely."""
    if not values:
        return 0.0

    return sum(1 for value in values if value) / len(values)


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize retrieval evaluation records."""
    source_hit_values = [record["source_hit"] for record in records]
    exact_term_hit_values = [record["exact_term_hit"] for record in records]
    any_group_hit_values = [record["any_group_hit"] for record in records]
    term_hit_values = [record["term_hit"] for record in records]
    requirement_hit_values = [record["requirement_hit"] for record in records]
    reciprocal_ranks = [record["reciprocal_rank"] for record in records]

    if reciprocal_ranks:
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
    else:
        mrr = 0.0

    failed_records = [
        record
        for record in records
        if record["failed_checks"]
    ]

    return {
        "num_samples": len(records),
        "source_hit_at_k": safe_ratio(source_hit_values),
        "exact_term_hit_at_k": safe_ratio(exact_term_hit_values),
        "any_group_hit_at_k": safe_ratio(any_group_hit_values),
        "term_hit_at_k": safe_ratio(term_hit_values),
        "requirement_hit_at_k": safe_ratio(requirement_hit_values),
        "mrr": mrr,
        "failed_records": len(failed_records),
    }


def print_summary(
    summary: dict[str, Any],
    query_mode: str,
    retriever: str,
    top_k: int,
) -> None:
    """Print retrieval eval summary."""
    print("\nRetrieval evaluation summary")
    print("=" * 80)
    print(f"retriever: {retriever}")
    print(f"query_mode: {query_mode}")
    print(f"top_k: {top_k}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("=" * 80)


def print_failed_records(records: list[dict[str, Any]]) -> None:
    """Print compact failed retrieval cases."""
    failed_records = [
        record
        for record in records
        if record["failed_checks"]
    ]

    print("\nFailed retrieval records")
    print("=" * 80)

    if not failed_records:
        print("No failed retrieval records.")
        return

    for record in failed_records:
        print(
            f"- {record['query_id']} | "
            f"failed={record['failed_checks']} | "
            f"query={record['query']}"
        )

        for chunk in record["top_chunks"][:3]:
            print(
                f"  rank={chunk['rank']} | "
                f"source={chunk['source_path']} | "
                f"heading={chunk['heading']} | "
                f"score={chunk['score']} | "
                f"matched={chunk['matched_terms']} | "
                f"retriever_ranks={chunk.get('retriever_ranks', {})} | "
                f"hybrid_rank={chunk.get('hybrid_rank')} | "
                f"rerank_score={chunk.get('rerank_score')}"
            )


def main() -> None:
    """Run retrieval evaluation from CLI."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--eval-file",
        type=Path,
        default=Path("eval/retrieval_eval_20.jsonl"),
        help="Path to retrieval evaluation JSONL file.",
    )

    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("eval/results/retrieval_eval_keyword_planner_top5.json"),
        help="Path to save retrieval evaluation result.",
    )

    parser.add_argument(
        "--query-mode",
        choices=["raw", "planner"],
        default="planner",
        help="Whether to use raw user query or planner-generated retrieval queries.",
    )

    parser.add_argument(
        "--retriever",
        choices=[
            "keyword",
            "bm25",
            "dense",
            "hybrid",
            "hybrid_rerank",
        ],
        default="keyword",
        help="Retriever to evaluate.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved chunks to evaluate.",
    )

    args = parser.parse_args()

    samples = load_jsonl(args.eval_file)

    records = [
        evaluate_sample(
            sample=sample,
            query_mode=args.query_mode,
            retriever=args.retriever,
            top_k=args.top_k,
        )
        for sample in samples
    ]

    summary = summarize_records(records)

    output = {
        "retriever": args.retriever,
        "query_mode": args.query_mode,
        "top_k": args.top_k,
        "eval_file": str(args.eval_file),
        "summary": summary,
        "records": records,
    }

    args.output_file.parent.mkdir(parents=True, exist_ok=True)

    with args.output_file.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print_summary(
        summary=summary,
        query_mode=args.query_mode,
        retriever=args.retriever,
        top_k=args.top_k,
    )

    print_failed_records(records)

    print(f"\nSaved detailed retrieval evaluation to: {args.output_file}")


if __name__ == "__main__":
    main()