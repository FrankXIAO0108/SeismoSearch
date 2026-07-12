"""
Tests for LLM request stability and controlled evidence budgets.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import seismosearch.llm_client as llm_client
from seismosearch.llm_client import (
    LLMClientError,
    OpenAICompatibleChatClient,
    OpenAICompatibleSettings,
)
from seismosearch.llm_generator import (
    build_controlled_evidence_context,
)


class FakeHttpResponse:
    """Minimal context-manager response for urllib tests."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_client_sends_json_and_thinking_controls(
    monkeypatch,
) -> None:
    """Configured request controls should reach the provider payload."""
    captured_payload: dict[str, Any] = {}

    def fake_urlopen(request, timeout):
        del timeout
        captured_payload.update(
            json.loads(request.data.decode("utf-8"))
        )
        return FakeHttpResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"answer":"ok",'
                                '"used_evidence_ids":[],'
                                '"grounding_notes":[]}'
                            )
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr(
        llm_client,
        "urlopen",
        fake_urlopen,
    )

    settings = OpenAICompatibleSettings(
        base_url="https://api.deepseek.com",
        api_key="test-key",
        model="deepseek-v4-flash",
        json_mode=True,
        thinking_mode="disabled",
    )
    client = OpenAICompatibleChatClient(settings)

    output = client.complete(
        [{"role": "user", "content": "test"}]
    )

    assert '"answer":"ok"' in output
    assert captured_payload["response_format"] == {
        "type": "json_object"
    }
    assert captured_payload["thinking"] == {
        "type": "disabled"
    }


def test_empty_content_error_contains_diagnostics() -> None:
    """Empty final content should retain finish and reasoning clues."""
    with pytest.raises(
        LLMClientError,
        match="finish_reason='length'",
    ):
        llm_client._extract_assistant_text(
            {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "content": "",
                            "reasoning_content": "thinking",
                        },
                    }
                ]
            }
        )


def test_controlled_context_reports_event_truncation() -> None:
    """The model must know when only part of a result list is included."""
    events = [
        {
            "evidence_id": f"event_{index:03d}",
            "event_id": f"event-{index}",
            "magnitude": 6.0,
        }
        for index in range(1, 13)
    ]

    context = build_controlled_evidence_context(
        {
            "query_id": "test",
            "user_query": "列出事件",
            "query_type": "catalog",
            "event_evidence": events,
            "computed_evidence": [],
            "doc_evidence": [],
            "safety_evidence": {},
            "answer_constraints": {},
            "warnings": [],
        }
    )

    assert len(context["event_evidence"]) == 10
    assert context["evidence_summary"]["event_evidence"] == {
        "total_count": 12,
        "included_count": 10,
        "truncated": True,
    }
