"""
Baseline comparison runner for SeismoSearch.

This script compares the current full SeismoSearch pipeline against several
simple deterministic ablation baselines on the same eval JSONL file.

Baselines included:
- full_system:
  current pipeline.py behavior.
- doc_only:
  simulates ordinary document-only RAG with safety_check + doc_retrieval.
- structured_only:
  simulates a database-only system with safety_check + event tools.
- no_safety_planner:
  simulates a planner without safety-first routing.

Important:
This is a first-stage baseline comparison runner. The non-full baselines are
component-ablation projections built from the full pipeline output structure.
They are intended to quantify expected failure modes before implementing
stronger independent baselines such as BM25, dense retrieval, or hybrid RAG.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


from run_eval import (  # noqa: E402
    check_doc_evidence,
    check_event_evidence,
    check_no_prediction_violation,
    check_parameter_accuracy,
    check_query_type,
    check_safety_refusal,
    check_tool_selection,
    check_unsafe_tool_call_free,
    get_tool_names,
    load_jsonl,
    summarize_results,
)

from seismosearch.pipeline import run_pipeline  # noqa: E402
from seismosearch.planner import (  # noqa: E402
    has_concept_intent,
    has_event_intent,
    infer_query_type,
    normalize_query,
    parse_min_magnitude,
)


BASELINE_VERSION = "baseline_comparison_0.1.0"


def make_tool_calls(tool_names: list[str]) -> list[dict[str, Any]]:
    """Create minimal tool_call records compatible with run_eval.py."""
    return [
        {
            "tool_name": tool_name,
            "status": "projected",
        }
        for tool_name in tool_names
    ]


def get_evidence_pack(result: dict[str, Any]) -> dict[str, Any]:
    """Extract evidence_pack safely from a pipeline result."""
    return result.get("evidence_pack", {}) or {}


def get_full_planner_output(full_result: dict[str, Any]) -> dict[str, Any]:
    """Extract full-system planner output from a pipeline result."""
    evidence_pack = get_evidence_pack(full_result)
    router_output = evidence_pack.get("router_output", {}) or {}

    return router_output.get("planner_output", {}) or {}


def get_event_parts(full_result: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    """Extract event evidence and computed evidence from a full-system result."""
    evidence_pack = get_evidence_pack(full_result)

    event_evidence = evidence_pack.get("event_evidence", []) or []
    computed_evidence = evidence_pack.get("computed_evidence", []) or []

    return event_evidence, computed_evidence


def get_doc_parts(full_result: dict[str, Any]) -> list[Any]:
    """Extract document evidence from a full-system result."""
    evidence_pack = get_evidence_pack(full_result)

    return evidence_pack.get("doc_evidence", []) or []


def build_projected_result(
    sample: dict[str, Any],
    baseline_name: str,
    pred_query_type: str,
    tool_names: list[str],
    event_evidence: list[Any] | None = None,
    computed_evidence: list[Any] | None = None,
    doc_evidence: list[Any] | None = None,
    planner_output: dict[str, Any] | None = None,
    answer_constraints: dict[str, Any] | None = None,
    answer: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal pipeline-like result for baseline evaluation."""
    event_evidence = event_evidence or []
    computed_evidence = computed_evidence or []
    doc_evidence = doc_evidence or []
    planner_output = planner_output or {}
    answer_constraints = answer_constraints or {}
    warnings = warnings or []

    if answer is None:
        answer = (
            f"[{baseline_name}] Projected baseline answer for query: "
            f"{sample.get('query', '')}"
        )

    evidence_pack = {
        "query_id": sample.get("query_id"),
        "query_type": pred_query_type,
        "tool_calls": make_tool_calls(tool_names),
        "event_evidence": event_evidence,
        "computed_evidence": computed_evidence,
        "doc_evidence": doc_evidence,
        "answer_constraints": answer_constraints,
        "warnings": warnings,
        "router_output": {
            "planner_output": planner_output,
        },
    }

    used_evidence_ids: list[str] = []

    for event in event_evidence:
        evidence_id = event.get("evidence_id") if isinstance(event, dict) else None

        if evidence_id is not None:
            used_evidence_ids.append(evidence_id)

    for doc in doc_evidence:
        evidence_id = doc.get("evidence_id") if isinstance(doc, dict) else None

        if evidence_id is not None:
            used_evidence_ids.append(evidence_id)

    for computed in computed_evidence:
        evidence_id = computed.get("evidence_id") if isinstance(computed, dict) else None

        if evidence_id is not None:
            used_evidence_ids.append(evidence_id)

    return {
        "status": "ok",
        "pipeline_version": BASELINE_VERSION,
        "baseline_name": baseline_name,
        "query_id": sample.get("query_id"),
        "user_query": sample.get("query"),
        "query_type": pred_query_type,
        "answer": answer,
        "used_evidence_ids": used_evidence_ids,
        "warnings": warnings,
        "answer_constraints": answer_constraints,
        "evidence_pack": evidence_pack,
    }


def build_doc_only_result(
    sample: dict[str, Any],
    full_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Build Doc-only RAG baseline result.

    This baseline keeps safety_check + doc_retrieval for every query.
    It never calls event_search or event_statistics.
    """
    doc_evidence = get_doc_parts(full_result)

    planner_output = {
        "planner_version": BASELINE_VERSION,
        "original_query": sample.get("query"),
        "normalized_query": normalize_query(sample.get("query", "")),
        "query_type": "concept",
        "event_search_params": None,
        "event_statistics_params": None,
        "doc_retrieval_queries": [sample.get("query", "")],
        "safety_intent": None,
        "rewrite_notes": [
            "Doc-only baseline: all queries are projected to document retrieval."
        ],
        "warnings": [],
    }

    return build_projected_result(
        sample=sample,
        baseline_name="doc_only",
        pred_query_type="concept",
        tool_names=["safety_check", "doc_retrieval"],
        event_evidence=[],
        computed_evidence=[],
        doc_evidence=doc_evidence,
        planner_output=planner_output,
        answer_constraints={},
        answer=(
            "Doc-only baseline answer. This baseline only uses document evidence "
            "and does not query structured earthquake events."
        ),
        warnings=[],
    )


def build_structured_only_result(
    sample: dict[str, Any],
    full_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Build Structured-only baseline result.

    This baseline keeps safety_check + event_search + event_statistics for
    every query. It never calls doc_retrieval.
    """
    event_evidence, computed_evidence = get_event_parts(full_result)
    full_planner_output = get_full_planner_output(full_result)

    event_search_params = full_planner_output.get("event_search_params")
    event_statistics_params = full_planner_output.get("event_statistics_params")

    planner_output = {
        "planner_version": BASELINE_VERSION,
        "original_query": sample.get("query"),
        "normalized_query": normalize_query(sample.get("query", "")),
        "query_type": "catalog",
        "event_search_params": event_search_params,
        "event_statistics_params": event_statistics_params,
        "doc_retrieval_queries": [],
        "safety_intent": None,
        "rewrite_notes": [
            "Structured-only baseline: all queries are projected to event tools."
        ],
        "warnings": [],
    }

    return build_projected_result(
        sample=sample,
        baseline_name="structured_only",
        pred_query_type="catalog",
        tool_names=["safety_check", "event_search", "event_statistics"],
        event_evidence=event_evidence,
        computed_evidence=computed_evidence,
        doc_evidence=[],
        planner_output=planner_output,
        answer_constraints={},
        answer=(
            "Structured-only baseline answer. This baseline only uses structured "
            "earthquake event tools and does not retrieve concept documents."
        ),
        warnings=[],
    )


def infer_no_safety_query_type(user_query: str) -> tuple[str, dict[str, Any]]:
    """
    Infer query type without safety-first routing.

    This intentionally removes detect_safety_intent() to simulate an ablation
    baseline where safety intent does not override event / concept intent.
    """
    normalized_query = normalize_query(user_query)

    min_magnitude, magnitude_notes = parse_min_magnitude(normalized_query)

    event_intent = has_event_intent(
        user_query=normalized_query,
        min_magnitude=min_magnitude,
    )

    concept_intent = has_concept_intent(normalized_query)

    query_type = infer_query_type(
        safety_intent=None,
        event_intent=event_intent,
        concept_intent=concept_intent,
    )

    planner_output = {
        "planner_version": BASELINE_VERSION,
        "original_query": user_query,
        "normalized_query": normalized_query,
        "query_type": query_type,
        "event_search_params": None,
        "event_statistics_params": None,
        "doc_retrieval_queries": [],
        "safety_intent": None,
        "rewrite_notes": [
            "No-safety planner baseline: safety intent detection is disabled.",
            *magnitude_notes,
        ],
        "warnings": [],
    }

    return query_type, planner_output


def tool_names_for_query_type(query_type: str) -> list[str]:
    """Map projected query_type to tool names."""
    if query_type == "catalog":
        return [
            "safety_check",
            "event_search",
            "event_statistics",
        ]

    if query_type == "concept":
        return [
            "safety_check",
            "doc_retrieval",
        ]

    if query_type == "mixed":
        return [
            "safety_check",
            "event_search",
            "event_statistics",
            "doc_retrieval",
        ]

    if query_type == "safety":
        return [
            "safety_check",
        ]

    return [
        "safety_check",
        "doc_retrieval",
    ]


def build_no_safety_planner_result(
    sample: dict[str, Any],
    full_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Build No-safety Planner baseline result.

    This baseline keeps catalog / concept / mixed routing, but disables
    safety-first intent detection.
    """
    user_query = sample.get("query", "")
    pred_query_type, planner_output = infer_no_safety_query_type(user_query)

    tool_names = tool_names_for_query_type(pred_query_type)

    full_planner_output = get_full_planner_output(full_result)

    if "event_search" in tool_names:
        planner_output["event_search_params"] = full_planner_output.get(
            "event_search_params"
        )
        planner_output["event_statistics_params"] = full_planner_output.get(
            "event_statistics_params"
        )

    if "doc_retrieval" in tool_names:
        planner_output["doc_retrieval_queries"] = [user_query]

    event_evidence: list[Any] = []
    computed_evidence: list[Any] = []
    doc_evidence: list[Any] = []

    if "event_search" in tool_names:
        event_evidence, computed_evidence = get_event_parts(full_result)

    if "doc_retrieval" in tool_names:
        doc_evidence = get_doc_parts(full_result)

    return build_projected_result(
        sample=sample,
        baseline_name="no_safety_planner",
        pred_query_type=pred_query_type,
        tool_names=tool_names,
        event_evidence=event_evidence,
        computed_evidence=computed_evidence,
        doc_evidence=doc_evidence,
        planner_output=planner_output,
        answer_constraints={},
        answer=(
            "No-safety Planner baseline answer. This baseline disables "
            "safety-first routing and therefore may route unsafe prediction "
            "queries into catalog or concept paths."
        ),
        warnings=[],
    )


def build_full_system_result(
    sample: dict[str, Any],
) -> dict[str, Any]:
    """Run the actual full SeismoSearch pipeline."""
    return run_pipeline(
        user_query=sample["query"],
        query_id=sample.get("query_id"),
        include_evidence_pack=True,
    )


def build_baseline_result(
    baseline_name: str,
    sample: dict[str, Any],
    full_result: dict[str, Any],
) -> dict[str, Any]:
    """Build a result for one baseline."""
    if baseline_name == "full_system":
        return full_result

    if baseline_name == "doc_only":
        return build_doc_only_result(sample, full_result)

    if baseline_name == "structured_only":
        return build_structured_only_result(sample, full_result)

    if baseline_name == "no_safety_planner":
        return build_no_safety_planner_result(sample, full_result)

    raise ValueError(f"Unsupported baseline: {baseline_name}")


def evaluate_result(
    sample: dict[str, Any],
    result: dict[str, Any],
    baseline_name: str,
    include_answers: bool = False,
) -> dict[str, Any]:
    """Evaluate one already-built result with existing run_eval checks."""
    checks = {
        "query_type_correct": check_query_type(sample, result),
        "tool_selection_correct": check_tool_selection(sample, result),
        "unsafe_tool_call_free": check_unsafe_tool_call_free(sample, result),
        "event_evidence_correct": check_event_evidence(sample, result),
        "doc_evidence_correct": check_doc_evidence(sample, result),
        "safety_refusal_correct": check_safety_refusal(sample, result),
        "parameter_correct": check_parameter_accuracy(sample, result),
        "no_prediction_violation": check_no_prediction_violation(sample, result),
    }

    failed_checks = [
        check_name
        for check_name, check_value in checks.items()
        if check_value is False
    ]

    answer = result.get("answer", "") or ""

    record = {
        "baseline_name": baseline_name,
        "query_id": sample.get("query_id"),
        "query": sample.get("query"),
        "gold_query_type": sample.get("gold_query_type"),
        "pred_query_type": result.get("query_type"),
        "gold_tools": sample.get("gold_tools", []),
        "actual_tools": get_tool_names(result),
        "checks": checks,
        "failed_checks": failed_checks,
        "used_evidence_ids": result.get("used_evidence_ids", []),
        "warnings": result.get("warnings", []),
        "answer_preview": answer[:300],
    }

    if include_answers:
        record["answer"] = answer

    return record


def evaluate_baselines(
    samples: list[dict[str, Any]],
    baseline_names: list[str],
    include_answers: bool = False,
) -> dict[str, Any]:
    """Evaluate all baselines on the same samples."""
    baseline_records: dict[str, list[dict[str, Any]]] = {
        baseline_name: []
        for baseline_name in baseline_names
    }

    for sample in samples:
        full_result = build_full_system_result(sample)

        for baseline_name in baseline_names:
            baseline_result = build_baseline_result(
                baseline_name=baseline_name,
                sample=sample,
                full_result=full_result,
            )

            record = evaluate_result(
                sample=sample,
                result=baseline_result,
                baseline_name=baseline_name,
                include_answers=include_answers,
            )

            baseline_records[baseline_name].append(record)

    baseline_outputs: dict[str, Any] = {}

    for baseline_name, records in baseline_records.items():
        baseline_outputs[baseline_name] = {
            "summary": summarize_results(records),
            "records": records,
        }

    return baseline_outputs


def print_summary_table(baseline_outputs: dict[str, Any]) -> None:
    """Print a compact summary table."""
    metrics = [
        "query_type_accuracy",
        "tool_selection_accuracy",
        "unsafe_tool_call_free_rate",
        "event_evidence_hit_rate",
        "doc_evidence_hit_rate",
        "safety_refusal_accuracy",
        "parameter_accuracy",
        "no_prediction_violation_rate",
    ]

    baseline_names = list(baseline_outputs.keys())

    print("\nBaseline comparison summary")
    print("=" * 120)

    header = ["metric", *baseline_names]
    print(" | ".join(header))
    print("-" * 120)

    for metric in metrics:
        row = [metric]

        for baseline_name in baseline_names:
            value = baseline_outputs[baseline_name]["summary"].get(metric)
            row.append(f"{value:.3f}" if isinstance(value, float) else str(value))

        print(" | ".join(row))

    print("=" * 120)


def print_failed_record_overview(baseline_outputs: dict[str, Any]) -> None:
    """Print compact failed-record overview for each baseline."""
    print("\nFailed record overview")
    print("=" * 120)

    for baseline_name, baseline_output in baseline_outputs.items():
        records = baseline_output["records"]
        failed_records = [
            record
            for record in records
            if record.get("failed_checks")
        ]

        print(f"\n[{baseline_name}] failed_records={len(failed_records)}")

        for record in failed_records[:20]:
            print(
                f"- {record['query_id']} | "
                f"gold={record['gold_query_type']} | "
                f"pred={record['pred_query_type']} | "
                f"tools={record['actual_tools']} | "
                f"failed={record['failed_checks']}"
            )

        if len(failed_records) > 20:
            remaining = len(failed_records) - 20
            print(f"... {remaining} more failed records omitted in console output")


def main() -> None:
    """Run baseline comparison from CLI."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--eval-file",
        type=Path,
        default=Path("eval/eval_40.jsonl"),
        help="Path to evaluation JSONL file.",
    )

    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("eval/results/baseline_comparison_eval_40.json"),
        help="Path to save baseline comparison results.",
    )

    parser.add_argument(
        "--include-answers",
        action="store_true",
        help="Whether to include full answers in output JSON.",
    )

    args = parser.parse_args()

    baseline_names = [
        "full_system",
        "doc_only",
        "structured_only",
        "no_safety_planner",
    ]

    samples = load_jsonl(args.eval_file)

    baseline_outputs = evaluate_baselines(
        samples=samples,
        baseline_names=baseline_names,
        include_answers=args.include_answers,
    )

    output = {
        "baseline_version": BASELINE_VERSION,
        "comparison_mode": "component_ablation_projection",
        "eval_file": str(args.eval_file),
        "baseline_names": baseline_names,
        "note": (
            "Non-full baselines are first-stage component-ablation projections "
            "built from the full pipeline output structure. They are designed "
            "to quantify expected failure modes before implementing stronger "
            "independent baselines such as BM25, dense retrieval, or hybrid RAG."
        ),
        "baselines": baseline_outputs,
    }

    args.output_file.parent.mkdir(parents=True, exist_ok=True)

    with args.output_file.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print_summary_table(baseline_outputs)
    print_failed_record_overview(baseline_outputs)

    print(f"\nSaved detailed baseline comparison to: {args.output_file}")


if __name__ == "__main__":
    main()