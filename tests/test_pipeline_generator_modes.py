"""
Integration tests for SeismoSearch pipeline generator modes.

External LLM services are never called.
"""

from __future__ import annotations

from seismosearch.pipeline import run_pipeline


class FakePipelineChatClient:
    """Deterministic fake client for pipeline tests."""

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.call_count = 0

    @property
    def model_name(self) -> str:
        return "fake-pipeline-model"

    def complete(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        self.call_count += 1
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        return self.response_text


def test_pipeline_default_mode_remains_deterministic() -> None:
    result = run_pipeline(
        "震级和烈度有什么区别？",
        include_evidence_pack=False,
    )

    assert result["status"] == "ok"
    assert result["requested_generator_mode"] == "deterministic"
    assert result["generator_mode"] == "deterministic"
    assert result["generation"]["generator_mode"] == "deterministic"
    assert result["generation"]["model_name"] is None
    assert "[doc_001]" in result["answer"]


def test_pipeline_llm_mode_uses_injected_client() -> None:
    client = FakePipelineChatClient(
        '{"answer":"震级描述地震释放能量，烈度描述特定地点的震动与影响。[doc_001]",'
        '"used_evidence_ids":["doc_001"],"grounding_notes":[]}'
    )

    result = run_pipeline(
        "震级和烈度有什么区别？",
        generator_mode="llm",
        llm_client=client,
        include_evidence_pack=False,
    )

    assert result["status"] == "ok"
    assert result["requested_generator_mode"] == "llm"
    assert result["generator_mode"] == "llm"
    assert result["generation"]["model_name"] == "fake-pipeline-model"
    assert result["used_evidence_ids"] == ["doc_001"]
    assert client.call_count == 1


def test_pipeline_llm_validation_failure_falls_back() -> None:
    client = FakePipelineChatClient(
        '{"answer":"无效证据。[doc_999]",'
        '"used_evidence_ids":["doc_999"],"grounding_notes":[]}'
    )

    result = run_pipeline(
        "震级和烈度有什么区别？",
        generator_mode="llm",
        llm_client=client,
        include_evidence_pack=False,
    )

    assert result["status"] == "ok"
    assert result["generator_mode"] == "deterministic_fallback"
    assert "llm_generation_failed" in result["warnings"]
    assert "generation_error" in result["generation"]
    assert "[doc_001]" in result["answer"]
    assert client.call_count == 1


def test_pipeline_llm_mode_keeps_safety_deterministic() -> None:
    client = FakePipelineChatClient(
        '{"answer":"不应返回","used_evidence_ids":[],"grounding_notes":[]}'
    )

    result = run_pipeline(
        "明天东京会不会发生大地震？",
        generator_mode="llm",
        llm_client=client,
        include_evidence_pack=False,
    )

    assert result["status"] == "ok"
    assert result["query_type"] == "safety"
    assert result["generator_mode"] == "deterministic_safety"
    assert "不能预测" in result["answer"]
    assert "llm_skipped_for_safety_query" in result["warnings"]
    assert client.call_count == 0


def test_pipeline_rejects_unknown_generator_mode() -> None:
    result = run_pipeline(
        "震级和烈度有什么区别？",
        generator_mode="unknown",
        include_evidence_pack=False,
    )

    assert result["status"] == "error"
    assert result["generator_mode"] is None
    assert result["requested_generator_mode"] == "unknown"
    assert "unsupported_generator_mode" in result["warnings"]
