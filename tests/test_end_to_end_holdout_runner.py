"""
Unit tests for frozen end-to-end holdout runner helpers.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT
    / "scripts"
    / "run_end_to_end_holdout_v1.py"
)


def load_runner() -> ModuleType:
    """Load the runner directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "run_end_to_end_holdout_v1",
        RUNNER_PATH,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load runner: {RUNNER_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def test_tool_and_parameter_checks() -> None:
    """Planner and tool checks should inspect Evidence Pack fields."""
    sample = {
        "gold_event_constraints": {
            "min_magnitude": 6.5,
        }
    }
    pack = {
        "tool_calls": [
            {"tool_name": "safety_check"},
            {"tool_name": "event_search"},
        ],
        "router_output": {
            "planner_output": {
                "event_search_params": {
                    "min_magnitude": 6.5,
                }
            }
        },
    }

    assert runner.get_tool_names(pack) == [
        "safety_check",
        "event_search",
    ]
    assert runner.check_parameter_accuracy(
        sample,
        pack,
    ) is True


def test_doc_evidence_contract() -> None:
    """Required terms and source path must exist in retrieved evidence."""
    sample = {
        "gold_doc_required": True,
        "gold_doc_requirements": {
            "must_contain_terms": [
                "gap",
                "depthError",
            ],
            "expected_source_path_contains": (
                "quality_and_uncertainty_fields.md"
            ),
        },
    }
    pack = {
        "doc_evidence": [
            {
                "heading": "gap and depthError",
                "text": "gap and depthError describe uncertainty.",
                "source_path": (
                    "data/processed/docs/"
                    "quality_and_uncertainty_fields.md"
                ),
            }
        ]
    }

    assert runner.check_doc_evidence(
        sample,
        pack,
    ) is True


def test_citation_contract_rejects_unknown_id() -> None:
    """Inline and declared citations must come from Evidence Pack."""
    assert runner.check_citation_validity(
        answer="事实。[doc_999]",
        used_evidence_ids=["doc_999"],
        available_ids={"doc_001"},
    ) is False
