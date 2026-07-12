"""
Tests for the evidence-constrained LLM generator.

These tests use a fake client and never call an external model.
"""

from __future__ import annotations

from typing import Any

from seismosearch.llm_generator import (
    build_controlled_evidence_context,
    build_llm_messages,
    generate_answer_with_llm,
)


class FakeChatClient:
    """Small deterministic client used by unit tests."""

    def __init__(
        self,
        response_text: str,
    ) -> None:
        self.response_text = response_text
        self.call_count = 0
        self.last_messages: list[dict[str, str]] = []

    @property
    def model_name(self) -> str:
        """Return a stable fake model identifier."""
        return "fake-grounded-model"

    def complete(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Record the request and return the configured response."""
        self.call_count += 1
        self.last_messages = messages
        return self.response_text


def _concept_pack() -> dict[str, Any]:
    """Build a compact concept Evidence Pack for unit tests."""
    return {
        "query_id": "query_test_001",
        "user_query": "震级和烈度有什么区别？",
        "query_type": "concept",
        "event_evidence": [],
        "computed_evidence": [],
        "doc_evidence": [
            {
                "evidence_id": "doc_001",
                "chunk_id": "concepts::magnitude-intensity",
                "source_path": (
                    "data/processed/docs/"
                    "seismology_concepts.md"
                ),
                "source_type": "markdown",
                "doc_title": "Seismology Concepts",
                "heading": "Magnitude and Intensity",
                "text": (
                    "震级描述地震释放能量的大小；"
                    "烈度描述某地点感受到的震动及影响。"
                ),
                "score": 0.95,
            }
        ],
        "safety_evidence": {},
        "warnings": [],
        "answer_constraints": {
            "must_use_evidence_pack": True,
            "must_not_predict_future_earthquakes": False,
            "must_cite_doc_evidence_when_using_document_facts": True,
            "response_mode": "concept_answer",
        },
    }


def _safety_pack() -> dict[str, Any]:
    """Build a compact safety Evidence Pack for unit tests."""
    return {
        "query_id": "query_test_safety",
        "user_query": "明天东京会不会发生大地震？",
        "query_type": "safety",
        "event_evidence": [],
        "computed_evidence": [],
        "doc_evidence": [],
        "safety_evidence": {
            "safety_labels": {
                "prediction_inducement": True,
                "matched_keywords": ["明天"],
            }
        },
        "warnings": [],
        "answer_constraints": {
            "must_use_evidence_pack": True,
            "must_not_predict_future_earthquakes": True,
            "should_offer_safe_alternatives": True,
            "response_mode": (
                "safe_refusal_with_alternatives"
            ),
        },
    }


def test_controlled_context_excludes_raw_traces() -> None:
    """The LLM context should exclude raw planner and tool traces."""
    pack = _concept_pack()
    pack["router_output"] = {
        "private_debug_value": "must_not_reach_model"
    }
    pack["tool_calls"] = [
        {
            "private_raw_tool_output": (
                "must_not_reach_model"
            )
        }
    ]

    context = build_controlled_evidence_context(pack)
    serialized_context = str(context)

    assert "router_output" not in context
    assert "tool_calls" not in context
    assert "must_not_reach_model" not in serialized_context


def test_llm_generator_accepts_grounded_json() -> None:
    """A valid grounded answer should pass without fallback."""
    client = FakeChatClient(
        response_text=(
            '{"answer":"震级描述释放能量，'
            '烈度描述地点影响。[doc_001]",'
            '"used_evidence_ids":["doc_001"],'
            '"grounding_notes":[]}'
        )
    )

    result = generate_answer_with_llm(
        evidence_pack=_concept_pack(),
        client=client,
    )

    assert result["status"] == "ok"
    assert result["generator_mode"] == "llm"
    assert result["model_name"] == (
        "fake-grounded-model"
    )
    assert result["used_evidence_ids"] == [
        "doc_001"
    ]
    assert "[doc_001]" in result["answer"]
    assert client.call_count == 1

    messages = build_llm_messages(_concept_pack())

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "CONTROLLED_EVIDENCE_CONTEXT" in (
        messages[1]["content"]
    )


def test_unknown_evidence_id_triggers_fallback() -> None:
    """Unavailable evidence IDs must not escape validation."""
    client = FakeChatClient(
        response_text=(
            '{"answer":"这是没有证据的说法。[doc_999]",'
            '"used_evidence_ids":["doc_999"],'
            '"grounding_notes":[]}'
        )
    )

    result = generate_answer_with_llm(
        evidence_pack=_concept_pack(),
        client=client,
    )

    assert result["status"] == "ok"
    assert result["generator_mode"] == (
        "deterministic_fallback"
    )
    assert result["model_name"] is None
    assert "llm_generation_failed" in (
        result["warnings"]
    )
    assert "doc_999" in result["generation_error"]
    assert "[doc_001]" in result["answer"]


def test_safety_query_never_calls_llm_v1() -> None:
    """Version 1 keeps safety generation deterministic."""
    client = FakeChatClient(
        response_text=(
            '{"answer":"不应被使用",'
            '"used_evidence_ids":[],'
            '"grounding_notes":[]}'
        )
    )

    result = generate_answer_with_llm(
        evidence_pack=_safety_pack(),
        client=client,
    )

    assert result["status"] == "ok"
    assert result["generator_mode"] == (
        "deterministic_safety"
    )
    assert client.call_count == 0
    assert "不能预测" in result["answer"]
    assert "llm_skipped_for_safety_query" in (
        result["warnings"]
    )
