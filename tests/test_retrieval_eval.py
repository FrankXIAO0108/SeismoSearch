"""
Tests for retrieval evaluation logic.

These tests focus on alias-aware evaluation requirements.

The goal is to avoid over-penalizing semantically correct bilingual evidence.
For example, a Chinese chunk containing "震级" and "烈度" should satisfy an
English requirement for "magnitude" and "intensity" when the eval sample defines
these as alias groups.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_retrieval_eval_runner() -> ModuleType:
    """Load scripts/run_retrieval_eval.py as a testable module."""
    script_path = Path("scripts/run_retrieval_eval.py").resolve()

    spec = importlib.util.spec_from_file_location(
        "run_retrieval_eval",
        script_path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


runner = load_retrieval_eval_runner()


def test_source_hit_accepts_equivalent_source_list() -> None:
    """A gold requirement may allow multiple equivalent source documents."""
    chunks = [
        {
            "source_path": "data/processed/docs/legacy_source.md",
        }
    ]

    assert runner.check_source_hit(
        chunks=chunks,
        expected_source_path_contains=[
            "new_official_source.md",
            "legacy_source.md",
        ],
    )


def test_any_group_hit_accepts_bilingual_aliases() -> None:
    """Alias groups should allow Chinese evidence for English concepts."""
    chunks = [
        {
            "source_path": "data/processed/docs/seismology_concepts.md",
            "doc_title": "Seismology Concepts Seed Document",
            "heading": "震级和烈度的区别",
            "text": "震级表示一次地震释放能量的大小。烈度表示某个地点受到地震影响或破坏的强弱。",
            "matched_terms": ["震级", "烈度"],
        }
    ]

    groups = [
        ["magnitude", "震级"],
        ["intensity", "烈度"],
    ]

    assert runner.check_any_group_hit(
        chunks=chunks,
        must_contain_any_groups=groups,
    )


def test_any_group_hit_requires_each_group_to_match() -> None:
    """
    Every alias group must have at least one matched item.

    This test intentionally uses a chunk that only contains magnitude/震级
    evidence and does not contain intensity/烈度 evidence in source_path,
    title, heading, text, or matched_terms.
    """
    chunks = [
        {
            "source_path": "data/processed/docs/seismology_concepts.md",
            "doc_title": "Seismology Concepts Seed Document",
            "heading": "震级定义",
            "text": "震级表示一次地震释放能量的大小。",
            "matched_terms": ["震级"],
        }
    ]

    groups = [
        ["magnitude", "震级"],
        ["intensity", "烈度"],
    ]

    assert not runner.check_any_group_hit(
        chunks=chunks,
        must_contain_any_groups=groups,
    )


def test_reciprocal_rank_uses_alias_groups() -> None:
    """MRR should treat a rank-1 bilingual alias match as correct."""
    chunks = [
        {
            "source_path": "data/processed/docs/seismology_concepts.md",
            "doc_title": "Seismology Concepts Seed Document",
            "heading": "震级和烈度的区别",
            "text": "震级表示一次地震释放能量的大小。烈度表示某个地点受到地震影响或破坏的强弱。",
            "matched_terms": ["震级", "烈度"],
        },
        {
            "source_path": "data/processed/docs/seismology_concepts.md",
            "doc_title": "Seismology Concepts Seed Document",
            "heading": "Magnitude and Intensity",
            "text": "Earthquake magnitude describes the size or energy release. Seismic intensity describes observed shaking effects.",
            "matched_terms": ["magnitude", "intensity"],
        },
    ]

    groups = [
        ["magnitude", "震级"],
        ["intensity", "烈度"],
    ]

    rr = runner.compute_reciprocal_rank(
        chunks=chunks,
        expected_source_path_contains="seismology_concepts.md",
        must_contain_terms=[],
        must_contain_any_groups=groups,
    )

    assert rr == 1.0


def test_exact_term_requirement_is_backward_compatible() -> None:
    """Old eval files using must_contain_terms should still work."""
    chunks = [
        {
            "source_path": "data/processed/docs/seismology_concepts.md",
            "doc_title": "Seismology Concepts Seed Document",
            "heading": "海啸提示 / Tsunami Alert",
            "text": "海啸提示可以对应 tsunami alert。",
            "matched_terms": ["海啸提示", "tsunami alert"],
        }
    ]

    assert runner.check_term_hit(
        chunks=chunks,
        must_contain_terms=["tsunami alert"],
        must_contain_any_groups=[],
    )
