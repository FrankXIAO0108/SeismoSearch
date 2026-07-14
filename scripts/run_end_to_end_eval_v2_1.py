"""
Independent SeismoSearch evaluation contract 2.1 runner.

Contract 2.1 keeps the frozen V1 and official V2 runners unchanged. It adds
bilingual required-term matching for both retrieved document evidence and
generated answers, then recomputes the final contract result.

The default paths are development-only paths. Official V1/V2 holdout inputs and
result files are explicitly rejected.
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

from seismosearch.evaluation_terms import (
    TERM_MATCH_CONTRACT_VERSION,
    find_missing_required_terms,
)


ROOT = Path(__file__).resolve().parents[1]
V2_RUNNER_PATH = (
    ROOT
    / "scripts"
    / "run_end_to_end_eval_v2.py"
)
DEFAULT_EVAL_FILE = Path(
    "eval/end_to_end_holdout_20_v2_1_dev.jsonl"
)
DEFAULT_OUTPUT_FILE = Path(
    "eval/results/"
    "end_to_end_holdout_20_v2_1_dev_results.json"
)
EVALUATION_CONTRACT_VERSION = "2.1.0"
SUPPORTED_MODES = {"deterministic", "llm"}

FORBIDDEN_ARTIFACT_NAMES = {
    "end_to_end_holdout_20_v1.jsonl",
    "end_to_end_holdout_20_v1_results.json",
    "end_to_end_holdout_20_v2.jsonl",
    "end_to_end_holdout_20_v2_results.json",
}


def load_v2_runner() -> ModuleType:
    """Load contract V2 without modifying its source file."""
    spec = importlib.util.spec_from_file_location(
        "_seismosearch_end_to_end_v2",
        V2_RUNNER_PATH,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load V2 runner: {V2_RUNNER_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V2 = load_v2_runner()


def assert_safe_paths(
    eval_file: Path,
    output_file: Path,
) -> None:
    """
    Reject all frozen V1 and official V2 artifact names.

    Contract 2.1 must use a fresh development set or a future separately frozen
    holdout. It must never overwrite the official V2 first-pass result.
    """
    selected_names = {
        eval_file.name.lower(),
        output_file.name.lower(),
    }
    collisions = sorted(
        FORBIDDEN_ARTIFACT_NAMES.intersection(
            selected_names
        )
    )

    if collisions:
        raise ValueError(
            "Evaluation contract 2.1 must not use frozen "
            "V1 or official V2 artifact paths: "
            + ", ".join(collisions)
        )


def _get_doc_requirements(
    sample: dict[str, Any],
) -> tuple[list[str], str | None]:
    """Extract normalized document requirements from one sample."""
    requirements = sample.get(
        "gold_doc_requirements",
        {},
    )

    if not isinstance(requirements, dict):
        return [], None

    raw_terms = requirements.get(
        "must_contain_terms",
        [],
    )
    required_terms = (
        [
            str(term)
            for term in raw_terms
            if str(term)
        ]
        if isinstance(raw_terms, list)
        else []
    )
    expected_source = requirements.get(
        "expected_source_path_contains"
    )

    return (
        required_terms,
        (
            expected_source
            if isinstance(expected_source, str)
            else None
        ),
    )


def _combine_doc_evidence_text(
    evidence_pack: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Combine retriever-visible document evidence for requirement checks."""
    raw_docs = evidence_pack.get(
        "doc_evidence",
        [],
    )
    docs = (
        [
            item
            for item in raw_docs
            if isinstance(item, dict)
        ]
        if isinstance(raw_docs, list)
        else []
    )
    parts: list[str] = []

    for doc in docs:
        parts.extend(
            [
                str(doc.get("doc_title", "")),
                str(doc.get("heading", "")),
                str(doc.get("text", "")),
                str(doc.get("source_path", "")),
            ]
        )

    return "\n".join(parts), docs


def check_doc_evidence_v2_1(
    sample: dict[str, Any],
    evidence_pack: dict[str, Any],
) -> tuple[bool | None, dict[str, Any]]:
    """
    Check retrieved document evidence with bilingual term equivalence.
    """
    if sample.get("gold_doc_required") is not True:
        return None, {
            "applicable": False,
            "required_terms": [],
            "missing_terms": [],
            "expected_source_path_contains": None,
            "source_path_match": None,
        }

    required_terms, expected_source = (
        _get_doc_requirements(sample)
    )
    combined_text, docs = (
        _combine_doc_evidence_text(
            evidence_pack
        )
    )
    missing_terms = find_missing_required_terms(
        combined_text,
        required_terms,
    )

    source_path_match: bool | None = None

    if expected_source is not None:
        source_path_match = any(
            expected_source
            in str(doc.get("source_path", ""))
            for doc in docs
        )

    valid = (
        bool(docs)
        and not missing_terms
        and source_path_match is not False
    )

    return valid, {
        "applicable": True,
        "required_terms": required_terms,
        "missing_terms": missing_terms,
        "expected_source_path_contains": (
            expected_source
        ),
        "source_path_match": source_path_match,
    }


def check_answer_required_terms_v2_1(
    sample: dict[str, Any],
    answer: str,
) -> tuple[bool | None, dict[str, Any]]:
    """Check generated-answer terminology with bilingual equivalence."""
    required_terms, _ = _get_doc_requirements(
        sample
    )

    if not required_terms:
        return None, {
            "applicable": False,
            "required_terms": [],
            "missing_terms": [],
        }

    missing_terms = find_missing_required_terms(
        answer,
        required_terms,
    )

    return not missing_terms, {
        "applicable": True,
        "required_terms": required_terms,
        "missing_terms": missing_terms,
    }


def recompute_contract_pass(
    checks: dict[str, Any],
) -> bool:
    """
    Recompute contract_pass after replacing V2.0 term checks.

    None means not applicable and is excluded from the denominator.
    """
    applicable_values = [
        bool(value)
        for check_name, value in checks.items()
        if check_name != "contract_pass"
        and value is not None
    ]
    return all(applicable_values)


def evaluate_mode(
    sample: dict[str, Any],
    evidence_pack: dict[str, Any],
    generation_result: dict[str, Any],
    requested_mode: str,
    generation_seconds: float,
    end_to_end_seconds: float,
) -> dict[str, Any]:
    """Evaluate one result under independent contract 2.1."""
    record = V2.evaluate_mode(
        sample=sample,
        evidence_pack=evidence_pack,
        generation_result=generation_result,
        requested_mode=requested_mode,
        generation_seconds=generation_seconds,
        end_to_end_seconds=end_to_end_seconds,
    )
    answer = str(record.get("answer", ""))

    doc_check, doc_diagnostics = (
        check_doc_evidence_v2_1(
            sample,
            evidence_pack,
        )
    )
    answer_check, answer_diagnostics = (
        check_answer_required_terms_v2_1(
            sample,
            answer,
        )
    )

    checks = record["checks"]
    checks["doc_evidence_correct"] = doc_check
    checks["required_terms_correct"] = (
        answer_check
    )
    checks["contract_pass"] = (
        recompute_contract_pass(checks)
    )

    record["evaluation_contract_version"] = (
        EVALUATION_CONTRACT_VERSION
    )
    record["term_match_contract_version"] = (
        TERM_MATCH_CONTRACT_VERSION
    )
    record["evaluation_v2_1_diagnostics"] = {
        "doc_evidence_terms": doc_diagnostics,
        "answer_terms": answer_diagnostics,
    }

    return record


def summarize_mode(
    records: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    """Reuse V2 summary logic after contract 2.1 checks are installed."""
    summary = V2.summarize_mode(
        records=records,
        mode=mode,
    )
    summary["evaluation_contract_version"] = (
        EVALUATION_CONTRACT_VERSION
    )
    summary["term_match_contract_version"] = (
        TERM_MATCH_CONTRACT_VERSION
    )
    return summary


def print_summary(
    summaries: list[dict[str, Any]],
    evidence_latency: dict[str, float],
) -> None:
    """Reuse the stable V2 console summary."""
    V2.print_summary(
        summaries=summaries,
        evidence_latency=evidence_latency,
    )


def parse_args() -> argparse.Namespace:
    """Parse development or fresh-holdout runner options."""
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
    """Run contract 2.1 on a fresh development set or future holdout."""
    args = parse_args()
    assert_safe_paths(
        eval_file=args.eval_file,
        output_file=args.output_file,
    )

    modes = list(dict.fromkeys(args.modes))

    if "llm" in modes:
        V2.V1.validate_llm_environment()

    samples = V2.V1.load_jsonl(args.eval_file)

    if not samples:
        raise ValueError("No evaluation samples loaded")

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
        evidence_pack = V2.V1.build_evidence_pack(
            user_query=query,
            query_id=query_id,
            doc_retriever_mode=(
                args.doc_retriever_mode
            ),
        )
        evidence_seconds = (
            time.perf_counter()
            - evidence_started
        )
        evidence_latencies.append(
            evidence_seconds
        )

        evidence_records.append(
            {
                "query_id": query_id,
                "pred_query_type": (
                    evidence_pack.get(
                        "query_type"
                    )
                ),
                "actual_tools": (
                    V2.V1.get_tool_names(
                        evidence_pack
                    )
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
                    V2.V1.generate_answer_with_llm(
                        evidence_pack=evidence_pack,
                        fallback_on_error=True,
                    )
                )
            else:
                generation_result = dict(
                    V2.V1.generate_answer(
                        evidence_pack
                    )
                )
                generation_result[
                    "generator_mode"
                ] = "deterministic"
                generation_result[
                    "model_name"
                ] = None

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
                generation_result=(
                    generation_result
                ),
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
                and sample.get(
                    "gold_query_type"
                )
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
    evidence_latency = (
        V2.V1.summarize_latency(
            evidence_latencies
        )
    )

    output = {
        "evaluation_contract_version": (
            EVALUATION_CONTRACT_VERSION
        ),
        "term_match_contract_version": (
            TERM_MATCH_CONTRACT_VERSION
        ),
        "eval_file": str(args.eval_file),
        "num_samples": len(samples),
        "doc_retriever_mode": (
            args.doc_retriever_mode
        ),
        "modes": modes,
        "llm_model": os.getenv(
            "SEISMOSEARCH_LLM_MODEL"
        ),
        "official_first_pass_holdout": False,
        "official_v2_result_untouched": True,
        "base_v2_runner_reused": str(
            V2_RUNNER_PATH
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
