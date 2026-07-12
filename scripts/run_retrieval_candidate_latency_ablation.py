"""
Benchmark SeismoSearch Hybrid and Hybrid + Reranker on the development set.

This script intentionally uses only:
    eval/retrieval_eval_60_corpus_v2.jsonl

It must not be pointed at the frozen holdout set for candidate_k tuning.

Outputs:
- retrieval quality metrics;
- warm per-query latency;
- first-call warm-up cost;
- candidate_k quality/cost comparison.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from run_retrieval_eval import (
    build_retrieval_queries,
    check_any_group_hit,
    check_exact_term_hit,
    check_source_hit,
    compute_reciprocal_rank,
    load_jsonl,
    summarize_records,
)
from seismosearch.hybrid_retriever import retrieve_docs_hybrid
from seismosearch.reranker import retrieve_docs_hybrid_rerank


DEFAULT_DEV_FILE = Path("eval/retrieval_eval_60_corpus_v2.jsonl")
DEFAULT_OUTPUT_FILE = Path(
    "eval/results/retrieval_candidate_latency_ablation_dev_v2.json"
)
FROZEN_HOLDOUT_NAME = "retrieval_holdout_26_v1.jsonl"


def percentile(values: list[float], percentile_value: float) -> float:
    """Calculate a percentile with linear interpolation."""
    if not values:
        return 0.0

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * percentile_value
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index

    return (
        ordered[lower_index] * (1.0 - fraction)
        + ordered[upper_index] * fraction
    )


def build_quality_record(
    sample: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Convert retrieved chunks into the existing retrieval-eval contract."""
    expected_source = sample.get("expected_source_path_contains")
    must_contain_terms = sample.get("must_contain_terms", [])
    must_contain_any_groups = sample.get(
        "must_contain_any_groups",
        [],
    )

    source_hit = check_source_hit(
        chunks=chunks,
        expected_source_path_contains=expected_source,
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
        expected_source_path_contains=expected_source,
        must_contain_terms=must_contain_terms,
        must_contain_any_groups=must_contain_any_groups,
    )

    failed_checks: list[str] = []

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
        "source_hit": source_hit,
        "exact_term_hit": exact_term_hit,
        "any_group_hit": any_group_hit,
        "term_hit": term_hit,
        "requirement_hit": requirement_hit,
        "reciprocal_rank": reciprocal_rank,
        "failed_checks": failed_checks,
    }


def run_configuration(
    samples: list[dict[str, Any]],
    config_name: str,
    retrieval_function: Callable[[list[str]], dict[str, Any]],
) -> dict[str, Any]:
    """Run one retriever configuration over all development samples."""
    quality_records: list[dict[str, Any]] = []
    latencies_seconds: list[float] = []
    query_variant_counts: list[int] = []

    for index, sample in enumerate(samples, start=1):
        retrieval_queries = build_retrieval_queries(
            sample=sample,
            query_mode="planner",
        )

        started_at = time.perf_counter()
        retrieval_result = retrieval_function(retrieval_queries)
        elapsed_seconds = time.perf_counter() - started_at

        chunks = retrieval_result.get("chunks", [])

        quality_records.append(
            build_quality_record(
                sample=sample,
                chunks=chunks,
            )
        )
        latencies_seconds.append(elapsed_seconds)
        query_variant_counts.append(len(retrieval_queries))

        print(
            f"[{config_name}] "
            f"{index:02d}/{len(samples)} "
            f"{sample['query_id']} "
            f"{elapsed_seconds:.4f}s"
        )

    quality_summary = summarize_records(quality_records)

    latency_summary = {
        "mean_seconds": statistics.fmean(latencies_seconds),
        "median_seconds": statistics.median(latencies_seconds),
        "p95_seconds": percentile(latencies_seconds, 0.95),
        "max_seconds": max(latencies_seconds, default=0.0),
        "min_seconds": min(latencies_seconds, default=0.0),
        "total_seconds": sum(latencies_seconds),
        "mean_query_variants": statistics.fmean(query_variant_counts),
    }

    failed_query_ids = [
        record["query_id"]
        for record in quality_records
        if record["failed_checks"]
    ]

    return {
        "config_name": config_name,
        "quality": quality_summary,
        "latency": latency_summary,
        "failed_query_ids": failed_query_ids,
    }


def warm_up(
    sample: dict[str, Any],
    max_candidate_k: int,
    top_k: int,
) -> dict[str, float]:
    """Measure first-call model initialization before warm benchmarks."""
    retrieval_queries = build_retrieval_queries(
        sample=sample,
        query_mode="planner",
    )

    hybrid_started_at = time.perf_counter()
    retrieve_docs_hybrid(
        queries=retrieval_queries,
        top_k=top_k,
    )
    hybrid_first_call_seconds = (
        time.perf_counter() - hybrid_started_at
    )

    reranker_started_at = time.perf_counter()
    retrieve_docs_hybrid_rerank(
        queries=retrieval_queries,
        top_k=top_k,
        candidate_k=max_candidate_k,
    )
    reranker_first_call_seconds = (
        time.perf_counter() - reranker_started_at
    )

    return {
        "hybrid_first_call_seconds": hybrid_first_call_seconds,
        "reranker_first_call_seconds_after_hybrid": (
            reranker_first_call_seconds
        ),
    }


def print_comparison(
    results: list[dict[str, Any]],
) -> None:
    """Print a compact quality and latency comparison table."""
    print("")
    print("=" * 118)
    print(
        f"{'configuration':<28}"
        f"{'req_hit@5':>12}"
        f"{'MRR':>10}"
        f"{'failed':>10}"
        f"{'mean_s':>12}"
        f"{'median_s':>12}"
        f"{'p95_s':>12}"
        f"{'total_s':>12}"
    )
    print("-" * 118)

    for result in results:
        quality = result["quality"]
        latency = result["latency"]

        print(
            f"{result['config_name']:<28}"
            f"{quality['requirement_hit_at_k']:>12.4f}"
            f"{quality['mrr']:>10.4f}"
            f"{quality['failed_records']:>10}"
            f"{latency['mean_seconds']:>12.4f}"
            f"{latency['median_seconds']:>12.4f}"
            f"{latency['p95_seconds']:>12.4f}"
            f"{latency['total_seconds']:>12.2f}"
        )

    print("=" * 118)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--eval-file",
        type=Path,
        default=DEFAULT_DEV_FILE,
        help="Development retrieval evaluation JSONL.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="JSON output path.",
    )
    parser.add_argument(
        "--candidate-k",
        type=int,
        nargs="+",
        default=[10, 20, 30, 40],
        help="Reranker candidate sizes to compare.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Final number of chunks returned.",
    )

    return parser.parse_args()


def main() -> None:
    """Run development-set candidate size and latency ablation."""
    args = parse_args()

    if args.eval_file.name == FROZEN_HOLDOUT_NAME:
        raise ValueError(
            "Refusing to tune candidate_k on the frozen holdout set. "
            "Use eval/retrieval_eval_60_corpus_v2.jsonl."
        )

    if args.top_k <= 0:
        raise ValueError("--top-k must be positive.")

    candidate_values = sorted(set(args.candidate_k))

    if not candidate_values:
        raise ValueError("At least one --candidate-k value is required.")

    if any(value < args.top_k for value in candidate_values):
        raise ValueError(
            "Every candidate_k value must be greater than or equal to top_k."
        )

    samples = load_jsonl(args.eval_file)

    if not samples:
        raise ValueError(f"No samples found in {args.eval_file}")

    print(
        f"[INFO] development samples: {len(samples)}"
    )
    print(
        f"[INFO] candidate_k values: {candidate_values}"
    )
    print(
        "[INFO] warming models before latency measurement..."
    )

    warmup = warm_up(
        sample=samples[0],
        max_candidate_k=max(candidate_values),
        top_k=args.top_k,
    )

    print(
        "[INFO] hybrid first call: "
        f"{warmup['hybrid_first_call_seconds']:.4f}s"
    )
    print(
        "[INFO] reranker first call after hybrid: "
        f"{warmup['reranker_first_call_seconds_after_hybrid']:.4f}s"
    )

    results: list[dict[str, Any]] = []

    results.append(
        run_configuration(
            samples=samples,
            config_name="hybrid",
            retrieval_function=lambda queries: retrieve_docs_hybrid(
                queries=queries,
                top_k=args.top_k,
            ),
        )
    )

    for candidate_k in candidate_values:
        results.append(
            run_configuration(
                samples=samples,
                config_name=f"hybrid_rerank_k{candidate_k}",
                retrieval_function=(
                    lambda queries, active_candidate_k=candidate_k:
                    retrieve_docs_hybrid_rerank(
                        queries=queries,
                        top_k=args.top_k,
                        candidate_k=active_candidate_k,
                    )
                ),
            )
        )

    output = {
        "eval_file": str(args.eval_file),
        "query_mode": "planner",
        "top_k": args.top_k,
        "candidate_k_values": candidate_values,
        "warmup": warmup,
        "results": results,
    }

    args.output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output_file.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print_comparison(results)
    print(
        f"[PASS] saved: {args.output_file}"
    )


if __name__ == "__main__":
    main()
