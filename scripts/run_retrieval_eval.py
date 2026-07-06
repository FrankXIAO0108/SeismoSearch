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

Current retriever:
- keyword overlap retriever from src/seismosearch/doc_retriever.py

Future retrievers:
- BM25;
- dense retrieval;
- hybrid retrieval;
- rerank.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from seismosearch.doc_retriever import retrieve_docs
from seismosearch.planner import plan_query


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
    """Normalize text for simple deterministic matching."""
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


def chunk_to_searchable_text(chunk: dict[str, Any]) -> str:
    """Combine chunk fields into a single string for requirement checks."""
    return "\n".join(
        [
            str(chunk.get("source_path", "")),
            str(chunk.get("doc_title", "")),
            str(chunk.get("heading", "")),
            str(chunk.get("text", "")),
            " ".join(chunk.get("matched_terms", [])),
        ]
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


def check_term_hit(
    chunks: list[dict[str, Any]],
    must_contain_terms: list[str],
) -> bool:
    """
    Check whether returned chunks contain all required terms.

    The check is performed over the combined top-k retrieved text.
    """
    if not must_contain_terms:
        return True

    combined_text = normalize_text(
        "\n".join(chunk_to_searchable_text(chunk) for chunk in chunks)
    )

    for term in must_contain_terms:
        if normalize_text(term) not in combined_text:
            return False

    return True


def chunk_satisfies_requirements(
    chunk: dict[str, Any],
    expected_source_path_contains: str | None,
    must_contain_terms: list[str],
) -> bool:
    """
    Check whether one chunk satisfies both source and term requirements.

    This is used for MRR calculation.
    """
    searchable_text = normalize_text(chunk_to_searchable_text(chunk))

    if expected_source_path_contains is not None:
        source_path = str(chunk.get("source_path", ""))

        if expected_source_path_contains not in source_path:
            return False

    for term in must_contain_terms:
        if normalize_text(term) not in searchable_text:
            return False

    return True


def compute_reciprocal_rank(
    chunks: list[dict[str, Any]],
    expected_source_path_contains: str | None,
    must_contain_terms: list[str],
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
        ):
            return 1.0 / rank

    return 0.0


def evaluate_sample(
    sample: dict[str, Any],
    query_mode: str,
    top_k: int,
) -> dict[str, Any]:
    """Evaluate one retrieval sample."""
    retrieval_queries = build_retrieval_queries(
        sample=sample,
        query_mode=query_mode,
    )

    retrieval_result = retrieve_docs(
        queries=retrieval_queries,
        top_k=top_k,
    )

    chunks = retrieval_result.get("chunks", [])

    expected_source_path_contains = sample.get("expected_source_path_contains")
    must_contain_terms = sample.get("must_contain_terms", [])

    source_hit = check_source_hit(
        chunks=chunks,
        expected_source_path_contains=expected_source_path_contains,
    )

    term_hit = check_term_hit(
        chunks=chunks,
        must_contain_terms=must_contain_terms,
    )

    requirement_hit = source_hit and term_hit

    reciprocal_rank = compute_reciprocal_rank(
        chunks=chunks,
        expected_source_path_contains=expected_source_path_contains,
        must_contain_terms=must_contain_terms,
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
            }
        )

    failed_checks = []

    if not source_hit:
        failed_checks.append("source_hit")

    if not term_hit:
        failed_checks.append("term_hit")

    if not requirement_hit:
        failed_checks.append("requirement_hit")

    return {
        "query_id": sample.get("query_id"),
        "query": sample.get("query"),
        "query_mode": query_mode,
        "retrieval_queries": retrieval_queries,
        "expected_source_path_contains": expected_source_path_contains,
        "must_contain_terms": must_contain_terms,
        "source_hit": source_hit,
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
        "term_hit_at_k": safe_ratio(term_hit_values),
        "requirement_hit_at_k": safe_ratio(requirement_hit_values),
        "mrr": mrr,
        "failed_records": len(failed_records),
    }


def print_summary(summary: dict[str, Any], query_mode: str, top_k: int) -> None:
    """Print retrieval eval summary."""
    print("\nRetrieval evaluation summary")
    print("=" * 80)
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
                f"matched={chunk['matched_terms']}"
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
            top_k=args.top_k,
        )
        for sample in samples
    ]

    summary = summarize_records(records)

    output = {
        "retriever": "keyword_overlap",
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
        top_k=args.top_k,
    )

    print_failed_records(records)

    print(f"\nSaved detailed retrieval evaluation to: {args.output_file}")


if __name__ == "__main__":
    main()