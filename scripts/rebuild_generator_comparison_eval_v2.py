"""
Rebuild generator comparison evaluation v2 while reusing successful LLM records
from v1.

Only v1 LLM fallback records are sent to the API again. Deterministic records
are regenerated locally after the citation metadata fix.
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

from seismosearch.evidence_builder import build_evidence_pack
from seismosearch.generator import generate_answer
from seismosearch.llm_generator import generate_answer_with_llm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "run_generator_comparison_eval.py"
)


def load_runner_module() -> ModuleType:
    """Load comparison helpers directly from the runner path."""
    spec = importlib.util.spec_from_file_location(
        "run_generator_comparison_eval",
        RUNNER_PATH,
    )

    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load runner: {RUNNER_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner_module()


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object."""
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")

    return data


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input-v1",
        type=Path,
        default=Path(
            "eval/results/generator_comparison_eval_40_v1.json"
        ),
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=Path("eval/eval_40.jsonl"),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path(
            "eval/results/generator_comparison_eval_40_v2.json"
        ),
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
    )

    return parser.parse_args()


def validate_llm_environment() -> None:
    """Fail early if a retry cannot call the configured model."""
    required_names = (
        "SEISMOSEARCH_LLM_BASE_URL",
        "SEISMOSEARCH_LLM_API_KEY",
        "SEISMOSEARCH_LLM_MODEL",
    )
    missing = [
        name
        for name in required_names
        if not os.getenv(name, "").strip()
    ]

    if missing:
        raise RuntimeError(
            "Missing LLM environment variables: "
            + ", ".join(missing)
        )


def main() -> None:
    """Regenerate deterministic records and retry only v1 fallbacks."""
    args = parse_args()
    validate_llm_environment()

    original = load_json(args.input_v1)
    samples = runner.load_jsonl(args.eval_file)

    original_llm_records = {
        str(record["query_id"]): record
        for record in original["records_by_mode"]["llm"]
    }

    deterministic_records: list[dict[str, Any]] = []
    llm_records: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    evidence_latencies: list[float] = []
    retried_ids: list[str] = []
    reused_ids: list[str] = []

    doc_retriever_mode = original.get(
        "doc_retriever_mode",
        "hybrid_rerank",
    )

    for index, sample in enumerate(samples, start=1):
        query_id = str(sample["query_id"])
        query = str(sample["query"])

        evidence_started = time.perf_counter()
        evidence_pack = build_evidence_pack(
            user_query=query,
            query_id=query_id,
            doc_retriever_mode=doc_retriever_mode,
        )
        evidence_seconds = time.perf_counter() - evidence_started
        evidence_latencies.append(evidence_seconds)

        evidence_records.append(
            {
                "query_id": query_id,
                "query_type": evidence_pack.get("query_type"),
                "doc_retriever_mode": evidence_pack.get(
                    "doc_retriever_mode"
                ),
                "event_evidence_count": len(
                    evidence_pack.get("event_evidence", [])
                ),
                "computed_evidence_count": len(
                    evidence_pack.get("computed_evidence", [])
                ),
                "doc_evidence_count": len(
                    evidence_pack.get("doc_evidence", [])
                ),
                "evidence_build_seconds": evidence_seconds,
                "warnings": evidence_pack.get("warnings", []),
            }
        )

        deterministic_started = time.perf_counter()
        deterministic_result = dict(
            generate_answer(evidence_pack)
        )
        deterministic_result["generator_mode"] = "deterministic"
        deterministic_result["model_name"] = None
        deterministic_seconds = (
            time.perf_counter() - deterministic_started
        )

        deterministic_record = runner.evaluate_generation(
            sample=sample,
            evidence_pack=evidence_pack,
            generation_result=deterministic_result,
            requested_mode="deterministic",
            generation_seconds=deterministic_seconds,
        )
        deterministic_records.append(deterministic_record)

        original_llm = original_llm_records.get(query_id)

        if original_llm is None:
            raise KeyError(
                f"Missing original LLM record: {query_id}"
            )

        if (
            original_llm.get("actual_generator_mode")
            == "deterministic_fallback"
        ):
            llm_started = time.perf_counter()
            llm_result = generate_answer_with_llm(
                evidence_pack=evidence_pack,
                fallback_on_error=True,
            )
            llm_seconds = time.perf_counter() - llm_started

            llm_record = runner.evaluate_generation(
                sample=sample,
                evidence_pack=evidence_pack,
                generation_result=llm_result,
                requested_mode="llm",
                generation_seconds=llm_seconds,
            )
            llm_records.append(llm_record)
            retried_ids.append(query_id)

            if (
                sample.get("gold_query_type") != "safety"
                and args.sleep_seconds > 0
            ):
                time.sleep(args.sleep_seconds)

            source_label = "retried"
        else:
            llm_records.append(original_llm)
            reused_ids.append(query_id)
            source_label = "reused"

        print(
            f"[{index:02d}/{len(samples)}] {query_id} | "
            f"det_contract="
            f"{deterministic_record['checks']['contract_pass']} | "
            f"llm={source_label}"
        )

    summaries = [
        runner.summarize_mode(
            deterministic_records,
            "deterministic",
        ),
        runner.summarize_mode(
            llm_records,
            "llm",
        ),
    ]
    evidence_latency = runner.summarize_evidence_latency(
        evidence_latencies
    )

    output = {
        "eval_file": str(args.eval_file),
        "source_eval_v1": str(args.input_v1),
        "num_samples": len(samples),
        "doc_retriever_mode": doc_retriever_mode,
        "modes": ["deterministic", "llm"],
        "llm_model": os.getenv("SEISMOSEARCH_LLM_MODEL"),
        "reuse_policy": {
            "reused_successful_llm_records": len(reused_ids),
            "retried_llm_fallback_records": len(retried_ids),
            "reused_query_ids": reused_ids,
            "retried_query_ids": retried_ids,
        },
        "evidence_build_latency": evidence_latency,
        "summaries": summaries,
        "evidence_records": evidence_records,
        "records_by_mode": {
            "deterministic": deterministic_records,
            "llm": llm_records,
        },
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

    runner.print_summary(
        summaries=summaries,
        evidence_latency=evidence_latency,
    )
    print(
        "[PASS] retried LLM query IDs: "
        + ", ".join(retried_ids)
    )
    print(f"[PASS] saved: {args.output_file}")


if __name__ == "__main__":
    main()
