"""
End-to-end evaluation runner for SeismoSearch evaluation contract v2.

This runner reuses the frozen V1 runner's stable helper functions, but adds
citation-support evaluation. It is intentionally separated from the V1 runner
and refuses to read or overwrite the frozen V1 holdout paths.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import time
from pathlib import Path
from types import ModuleType
from typing import Any

from seismosearch.citation_support import (
    check_reference_citation_support,
)


ROOT = Path(__file__).resolve().parents[1]
V1_RUNNER_PATH = (
    ROOT
    / "scripts"
    / "run_end_to_end_holdout_v1.py"
)
DEFAULT_EVAL_FILE = Path(
    "eval/end_to_end_holdout_20_v2.jsonl"
)
DEFAULT_OUTPUT_FILE = Path(
    "eval/results/end_to_end_holdout_20_v2_results.json"
)
SUPPORTED_MODES = {"deterministic", "llm"}


def load_v1_runner() -> ModuleType:
    """Load the frozen V1 runner without modifying it."""
    spec = importlib.util.spec_from_file_location(
        "_seismosearch_end_to_end_v1",
        V1_RUNNER_PATH,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load V1 runner: {V1_RUNNER_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V1 = load_v1_runner()


def assert_not_v1_paths(
    eval_file: Path,
    output_file: Path,
) -> None:
    """Refuse to consume or overwrite the frozen V1 holdout artifacts."""
    forbidden_names = {
        "end_to_end_holdout_20_v1.jsonl",
        "end_to_end_holdout_20_v1_results.json",
    }

    selected_names = {
        eval_file.name.lower(),
        output_file.name.lower(),
    }

    collisions = sorted(
        forbidden_names.intersection(selected_names)
    )

    if collisions:
        raise ValueError(
            "Evaluation contract v2 must not use frozen V1 paths: "
            + ", ".join(collisions)
        )


def evaluate_mode(
    sample: dict[str, Any],
    evidence_pack: dict[str, Any],
    generation_result: dict[str, Any],
    requested_mode: str,
    generation_seconds: float,
    end_to_end_seconds: float,
) -> dict[str, Any]:
    """
    Evaluate one result with the V1 contract plus citation support.

    Citation validity answers whether IDs exist and match the answer metadata.
    Citation support answers whether the cited evidence satisfies the reference
    event/document requirements for this sample.
    """
    record = V1.evaluate_mode(
        sample=sample,
        evidence_pack=evidence_pack,
        generation_result=generation_result,
        requested_mode=requested_mode,
        generation_seconds=generation_seconds,
        end_to_end_seconds=end_to_end_seconds,
    )

    support = check_reference_citation_support(
        sample=sample,
        answer=str(record.get("answer", "")),
        evidence_pack=evidence_pack,
    )
    support_valid = support.get("valid")

    checks = record["checks"]
    checks["citation_support_valid"] = (
        support_valid
    )

    if support_valid is not None:
        checks["contract_pass"] = (
            bool(checks["contract_pass"])
            and bool(support_valid)
        )

    record["citation_support"] = support
    record["evaluation_contract_version"] = "2.0.0"

    return record


def summarize_mode(
    records: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    """Summarize V1 metrics plus citation-support coverage."""
    summary = V1.summarize_mode(
        records=records,
        mode=mode,
    )

    applicable_values = [
        bool(
            record["checks"][
                "citation_support_valid"
            ]
        )
        for record in records
        if record["checks"].get(
            "citation_support_valid"
        )
        is not None
    ]

    summary["citation_support_valid_rate"] = (
        V1.safe_ratio(applicable_values)
    )
    summary["citation_support_num_applicable"] = (
        len(applicable_values)
    )
    summary[
        "citation_support_failed_query_ids"
    ] = [
        record["query_id"]
        for record in records
        if record["checks"].get(
            "citation_support_valid"
        )
        is False
    ]

    return summary


def print_summary(
    summaries: list[dict[str, Any]],
    evidence_latency: dict[str, float],
) -> None:
    """Print the original table and the new support metric."""
    V1.print_summary(
        summaries=summaries,
        evidence_latency=evidence_latency,
    )

    print()
    print("=" * 76)
    print(
        f"{'mode':<20}"
        f"{'citation_support':>22}"
        f"{'applicable':>14}"
        f"{'support_failures':>20}"
    )
    print("-" * 76)

    for summary in summaries:
        failed_ids = summary[
            "citation_support_failed_query_ids"
        ]
        failed_text = (
            "-"
            if not failed_ids
            else ",".join(failed_ids)
        )

        print(
            f"{summary['generator_mode']:<20}"
            f"{summary['citation_support_valid_rate']:>22.4f}"
            f"{summary['citation_support_num_applicable']:>14}"
            f"{failed_text:>20}"
        )

    print("=" * 76)


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the V2 evaluation contract."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--eval-file",
        type=Path,
        default=DEFAULT_EVAL_FILE,
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=sorted(SUPPORTED_MODES),
        default=["deterministic", "llm"],
    )
    parser.add_argument(
        "--doc-retriever-mode",
        choices=[
            "keyword",
            "hybrid",
            "hybrid_rerank",
        ],
        default="hybrid_rerank",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
    )

    return parser.parse_args()


def main() -> None:
    """Run a V2 holdout and save citation-support diagnostics."""
    args = parse_args()
    assert_not_v1_paths(
        eval_file=args.eval_file,
        output_file=args.output_file,
    )

    modes = list(dict.fromkeys(args.modes))

    if "llm" in modes:
        V1.validate_llm_environment()

    samples = V1.load_jsonl(args.eval_file)

    if not samples:
        raise ValueError("No holdout samples loaded")

    records_by_mode: dict[
        str,
        list[dict[str, Any]],
    ] = {
        mode: []
        for mode in modes
    }
    evidence_records: list[dict[str, Any]] = []
    evidence_latencies: list[float] = []

    for index, sample in enumerate(
        samples,
        start=1,
    ):
        query_id = str(sample["query_id"])
        query = str(sample["query"])

        evidence_started = time.perf_counter()
        evidence_pack = V1.build_evidence_pack(
            user_query=query,
            query_id=query_id,
            doc_retriever_mode=(
                args.doc_retriever_mode
            ),
        )
        evidence_seconds = (
            time.perf_counter() - evidence_started
        )
        evidence_latencies.append(
            evidence_seconds
        )

        evidence_records.append(
            {
                "query_id": query_id,
                "pred_query_type": (
                    evidence_pack.get("query_type")
                ),
                "actual_tools": V1.get_tool_names(
                    evidence_pack
                ),
                "doc_retriever_mode": (
                    evidence_pack.get(
                        "doc_retriever_mode"
                    )
                ),
                "event_evidence_count": len(
                    evidence_pack.get(
                        "event_evidence",
                        [],
                    )
                ),
                "computed_evidence_count": len(
                    evidence_pack.get(
                        "computed_evidence",
                        [],
                    )
                ),
                "doc_evidence_count": len(
                    evidence_pack.get(
                        "doc_evidence",
                        [],
                    )
                ),
                "evidence_build_seconds": (
                    evidence_seconds
                ),
                "warnings": evidence_pack.get(
                    "warnings",
                    [],
                ),
            }
        )

        for mode in modes:
            generation_started = (
                time.perf_counter()
            )

            if mode == "llm":
                generation_result = (
                    V1.generate_answer_with_llm(
                        evidence_pack=evidence_pack,
                        fallback_on_error=True,
                    )
                )
            else:
                generation_result = dict(
                    V1.generate_answer(
                        evidence_pack
                    )
                )
                generation_result[
                    "generator_mode"
                ] = "deterministic"
                generation_result["model_name"] = None

            generation_seconds = (
                time.perf_counter()
                - generation_started
            )
            end_to_end_seconds = (
                evidence_seconds
                + generation_seconds
            )

            record = evaluate_mode(
                sample=sample,
                evidence_pack=evidence_pack,
                generation_result=generation_result,
                requested_mode=mode,
                generation_seconds=(
                    generation_seconds
                ),
                end_to_end_seconds=(
                    end_to_end_seconds
                ),
            )
            records_by_mode[mode].append(
                record
            )

            print(
                f"[{index:02d}/{len(samples)}] "
                f"{query_id} | {mode} | "
                f"actual="
                f"{record['actual_generator_mode']} | "
                f"contract="
                f"{record['checks']['contract_pass']} | "
                f"citation_support="
                f"{record['checks']['citation_support_valid']} | "
                f"e2e={end_to_end_seconds:.3f}s"
            )

            if (
                mode == "llm"
                and sample.get("gold_query_type")
                != "safety"
                and args.sleep_seconds > 0
            ):
                time.sleep(
                    args.sleep_seconds
                )

    summaries = [
        summarize_mode(
            records_by_mode[mode],
            mode,
        )
        for mode in modes
    ]
    evidence_latency = V1.summarize_latency(
        evidence_latencies
    )

    output = {
        "evaluation_contract_version": "2.0.0",
        "eval_file": str(args.eval_file),
        "num_samples": len(samples),
        "doc_retriever_mode": (
            args.doc_retriever_mode
        ),
        "modes": modes,
        "llm_model": os.getenv(
            "SEISMOSEARCH_LLM_MODEL"
        ),
        "first_pass_holdout": True,
        "frozen_v1_runner_reused": str(
            V1_RUNNER_PATH
        ),
        "evidence_build_latency": (
            evidence_latency
        ),
        "summaries": summaries,
        "evidence_records": evidence_records,
        "records_by_mode": records_by_mode,
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
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print_summary(
        summaries=summaries,
        evidence_latency=evidence_latency,
    )
    print(
        f"[PASS] saved: {args.output_file}"
    )


if __name__ == "__main__":
    main()
