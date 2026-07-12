"""
One-time patch for SeismoSearch LLM generation stability.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LLM_CLIENT_PATH = (
    PROJECT_ROOT / "src" / "seismosearch" / "llm_client.py"
)
LLM_GENERATOR_PATH = (
    PROJECT_ROOT / "src" / "seismosearch" / "llm_generator.py"
)
TEST_PATH = (
    PROJECT_ROOT / "tests" / "test_llm_generation_stability.py"
)

CLIENT_REPLACEMENTS = [('    temperature: float = 0.0\n    max_tokens: int = 1200\n', '    temperature: float = 0.0\n    max_tokens: int = 1200\n    json_mode: bool = True\n    thinking_mode: str | None = None\n'), ('        max_tokens = _read_int_env(\n            "SEISMOSEARCH_LLM_MAX_TOKENS",\n            default=1200,\n            minimum=1,\n        )\n\n        return cls(\n', '        max_tokens = _read_int_env(\n            "SEISMOSEARCH_LLM_MAX_TOKENS",\n            default=1200,\n            minimum=1,\n        )\n        json_mode = _read_bool_env(\n            "SEISMOSEARCH_LLM_JSON_MODE",\n            default=True,\n        )\n        thinking_mode = _read_optional_choice_env(\n            "SEISMOSEARCH_LLM_THINKING_MODE",\n            choices={"enabled", "disabled"},\n        )\n\n        return cls(\n'), ('            temperature=0.0,\n            max_tokens=max_tokens,\n        )\n', '            temperature=0.0,\n            max_tokens=max_tokens,\n            json_mode=json_mode,\n            thinking_mode=thinking_mode,\n        )\n'), ('def _read_int_env(\n    name: str,\n    default: int,\n    minimum: int,\n) -> int:\n', 'def _read_bool_env(\n    name: str,\n    default: bool,\n) -> bool:\n    """Read a boolean environment variable."""\n    raw_value = os.getenv(name)\n\n    if raw_value is None or not raw_value.strip():\n        return default\n\n    normalized_value = raw_value.strip().lower()\n\n    if normalized_value in {"1", "true", "yes", "on"}:\n        return True\n\n    if normalized_value in {"0", "false", "no", "off"}:\n        return False\n\n    raise LLMClientError(\n        f"{name} must be a boolean, got: {raw_value!r}"\n    )\n\n\ndef _read_optional_choice_env(\n    name: str,\n    choices: set[str],\n) -> str | None:\n    """Read an optional normalized choice environment variable."""\n    raw_value = os.getenv(name)\n\n    if raw_value is None or not raw_value.strip():\n        return None\n\n    normalized_value = raw_value.strip().lower()\n\n    if normalized_value not in choices:\n        choices_text = ", ".join(sorted(choices))\n        raise LLMClientError(\n            f"{name} must be one of: {choices_text}."\n        )\n\n    return normalized_value\n\n\ndef _read_int_env(\n    name: str,\n    default: int,\n    minimum: int,\n) -> int:\n'), ('        payload = {\n            "model": self.settings.model,\n            "messages": messages,\n            "temperature": self.settings.temperature,\n            "max_tokens": self.settings.max_tokens,\n            "stream": False,\n        }\n\n        request = Request(\n', '        payload = {\n            "model": self.settings.model,\n            "messages": messages,\n            "temperature": self.settings.temperature,\n            "max_tokens": self.settings.max_tokens,\n            "stream": False,\n        }\n\n        if self.settings.json_mode:\n            payload["response_format"] = {\n                "type": "json_object",\n            }\n\n        if self.settings.thinking_mode is not None:\n            payload["thinking"] = {\n                "type": self.settings.thinking_mode,\n            }\n\n        request = Request(\n'), ('    content = message.get("content")\n\n    if isinstance(content, str):\n        normalized_content = content.strip()\n\n        if not normalized_content:\n            raise LLMClientError(\n                "LLM response content is empty"\n            )\n\n        return normalized_content\n', '    content = message.get("content")\n    finish_reason = first_choice.get("finish_reason")\n    reasoning_content = message.get("reasoning_content")\n    reasoning_chars = (\n        len(reasoning_content)\n        if isinstance(reasoning_content, str)\n        else 0\n    )\n\n    if isinstance(content, str):\n        normalized_content = content.strip()\n\n        if not normalized_content:\n            raise LLMClientError(\n                "LLM response content is empty; "\n                f"finish_reason={finish_reason!r}; "\n                f"reasoning_content_chars={reasoning_chars}"\n            )\n\n        return normalized_content\n')]
GENERATOR_REPLACEMENTS = [('EVIDENCE_ID_PATTERN = re.compile(\n    r"\\[(event_\\d{3}|computed_\\d{3}|doc_\\d{3})\\]"\n)\n\n\nclass ChatCompletionClient(Protocol):\n', 'EVIDENCE_ID_PATTERN = re.compile(\n    r"\\[(event_\\d{3}|computed_\\d{3}|doc_\\d{3})\\]"\n)\n\nMAX_EVENT_EVIDENCE = 10\nMAX_COMPUTED_EVIDENCE = 3\nMAX_DOC_EVIDENCE = 5\n\n\nclass ChatCompletionClient(Protocol):\n'), ('    event_evidence = [\n        _select_keys(item, event_keys)\n        for item in evidence_pack.get("event_evidence", [])[:5]\n        if isinstance(item, dict)\n    ]\n    computed_evidence = [\n        _select_keys(item, computed_keys)\n        for item in evidence_pack.get("computed_evidence", [])[:3]\n        if isinstance(item, dict)\n    ]\n    doc_evidence = [\n        _select_keys(item, document_keys)\n        for item in evidence_pack.get("doc_evidence", [])[:5]\n        if isinstance(item, dict)\n    ]\n\n    return {\n', '    raw_event_evidence = [\n        item\n        for item in evidence_pack.get("event_evidence", [])\n        if isinstance(item, dict)\n    ]\n    raw_computed_evidence = [\n        item\n        for item in evidence_pack.get("computed_evidence", [])\n        if isinstance(item, dict)\n    ]\n    raw_doc_evidence = [\n        item\n        for item in evidence_pack.get("doc_evidence", [])\n        if isinstance(item, dict)\n    ]\n\n    event_evidence = [\n        _select_keys(item, event_keys)\n        for item in raw_event_evidence[:MAX_EVENT_EVIDENCE]\n    ]\n    computed_evidence = [\n        _select_keys(item, computed_keys)\n        for item in raw_computed_evidence[\n            :MAX_COMPUTED_EVIDENCE\n        ]\n    ]\n    doc_evidence = [\n        _select_keys(item, document_keys)\n        for item in raw_doc_evidence[:MAX_DOC_EVIDENCE]\n    ]\n\n    evidence_summary = {\n        "event_evidence": {\n            "total_count": len(raw_event_evidence),\n            "included_count": len(event_evidence),\n            "truncated": (\n                len(raw_event_evidence) > len(event_evidence)\n            ),\n        },\n        "computed_evidence": {\n            "total_count": len(raw_computed_evidence),\n            "included_count": len(computed_evidence),\n            "truncated": (\n                len(raw_computed_evidence)\n                > len(computed_evidence)\n            ),\n        },\n        "doc_evidence": {\n            "total_count": len(raw_doc_evidence),\n            "included_count": len(doc_evidence),\n            "truncated": (\n                len(raw_doc_evidence) > len(doc_evidence)\n            ),\n        },\n    }\n\n    return {\n'), ('        "doc_evidence": doc_evidence,\n        "safety_evidence": evidence_pack.get(\n', '        "doc_evidence": doc_evidence,\n        "evidence_summary": evidence_summary,\n        "safety_evidence": evidence_pack.get(\n'), ('9. 如果是本地样例库统计，必须明确它不代表完整全球目录。\n10. 只返回一个 JSON 对象，不要使用 Markdown 代码块，也不要输出额外解释。\n\n返回格式：\n', '9. 如果是本地样例库统计，必须明确它不代表完整全球目录。\n10. 检查 evidence_summary：如果 event_evidence.truncated=true，必须明确说明“共 total_count 条，本回答仅展示 included_count 条”，不得暗示已经列出全部结果。\n11. 回答应简洁；同一句事实优先引用最直接的一条证据，避免无必要地连续堆叠多个引用。\n12. 只返回一个 JSON 对象，不要使用 Markdown 代码块，也不要输出额外解释。\n\n返回格式：\n')]
TEST_CONTENT = '"""\nTests for LLM request stability and controlled evidence budgets.\n"""\n\nfrom __future__ import annotations\n\nimport json\nfrom typing import Any\n\nimport pytest\n\nimport seismosearch.llm_client as llm_client\nfrom seismosearch.llm_client import (\n    LLMClientError,\n    OpenAICompatibleChatClient,\n    OpenAICompatibleSettings,\n)\nfrom seismosearch.llm_generator import (\n    build_controlled_evidence_context,\n)\n\n\nclass FakeHttpResponse:\n    """Minimal context-manager response for urllib tests."""\n\n    def __init__(self, payload: dict[str, Any]) -> None:\n        self.payload = payload\n\n    def __enter__(self) -> "FakeHttpResponse":\n        return self\n\n    def __exit__(\n        self,\n        exc_type,\n        exc_value,\n        traceback,\n    ) -> None:\n        return None\n\n    def read(self) -> bytes:\n        return json.dumps(self.payload).encode("utf-8")\n\n\ndef test_client_sends_json_and_thinking_controls(\n    monkeypatch,\n) -> None:\n    """Configured request controls should reach the provider payload."""\n    captured_payload: dict[str, Any] = {}\n\n    def fake_urlopen(request, timeout):\n        del timeout\n        captured_payload.update(\n            json.loads(request.data.decode("utf-8"))\n        )\n        return FakeHttpResponse(\n            {\n                "choices": [\n                    {\n                        "finish_reason": "stop",\n                        "message": {\n                            "content": (\n                                \'{"answer":"ok",\'\n                                \'"used_evidence_ids":[],\'\n                                \'"grounding_notes":[]}\'\n                            )\n                        },\n                    }\n                ]\n            }\n        )\n\n    monkeypatch.setattr(\n        llm_client,\n        "urlopen",\n        fake_urlopen,\n    )\n\n    settings = OpenAICompatibleSettings(\n        base_url="https://api.deepseek.com",\n        api_key="test-key",\n        model="deepseek-v4-flash",\n        json_mode=True,\n        thinking_mode="disabled",\n    )\n    client = OpenAICompatibleChatClient(settings)\n\n    output = client.complete(\n        [{"role": "user", "content": "test"}]\n    )\n\n    assert \'"answer":"ok"\' in output\n    assert captured_payload["response_format"] == {\n        "type": "json_object"\n    }\n    assert captured_payload["thinking"] == {\n        "type": "disabled"\n    }\n\n\ndef test_empty_content_error_contains_diagnostics() -> None:\n    """Empty final content should retain finish and reasoning clues."""\n    with pytest.raises(\n        LLMClientError,\n        match="finish_reason=\'length\'",\n    ):\n        llm_client._extract_assistant_text(\n            {\n                "choices": [\n                    {\n                        "finish_reason": "length",\n                        "message": {\n                            "content": "",\n                            "reasoning_content": "thinking",\n                        },\n                    }\n                ]\n            }\n        )\n\n\ndef test_controlled_context_reports_event_truncation() -> None:\n    """The model must know when only part of a result list is included."""\n    events = [\n        {\n            "evidence_id": f"event_{index:03d}",\n            "event_id": f"event-{index}",\n            "magnitude": 6.0,\n        }\n        for index in range(1, 13)\n    ]\n\n    context = build_controlled_evidence_context(\n        {\n            "query_id": "test",\n            "user_query": "列出事件",\n            "query_type": "catalog",\n            "event_evidence": events,\n            "computed_evidence": [],\n            "doc_evidence": [],\n            "safety_evidence": {},\n            "answer_constraints": {},\n            "warnings": [],\n        }\n    )\n\n    assert len(context["event_evidence"]) == 10\n    assert context["evidence_summary"]["event_evidence"] == {\n        "total_count": 12,\n        "included_count": 10,\n        "truncated": True,\n    }\n'


def read_preserving_newlines(path: Path) -> tuple[str, str]:
    with path.open("r", encoding="utf-8", newline="") as file:
        text = file.read()

    newline = "\r\n" if "\r\n" in text else "\n"
    return text, newline


def normalize_block(block: str, newline: str) -> str:
    return block.replace("\n", newline)


def apply_replacements(
    path: Path,
    replacements: list[tuple[str, str]],
    already_applied_marker: str,
) -> None:
    text, newline = read_preserving_newlines(path)

    if already_applied_marker in text:
        raise RuntimeError(
            f"Patch already applied to {path}"
        )

    for index, (old, new) in enumerate(
        replacements,
        start=1,
    ):
        old_value = normalize_block(old, newline)
        new_value = normalize_block(new, newline)
        count = text.count(old_value)

        if count != 1:
            raise RuntimeError(
                f"{path.name} replacement {index}: "
                f"expected one match, found {count}"
            )

        text = text.replace(
            old_value,
            new_value,
            1,
        )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        file.write(text)


def main() -> None:
    if TEST_PATH.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing file: {TEST_PATH}"
        )

    apply_replacements(
        LLM_CLIENT_PATH,
        CLIENT_REPLACEMENTS,
        "thinking_mode: str | None",
    )
    apply_replacements(
        LLM_GENERATOR_PATH,
        GENERATOR_REPLACEMENTS,
        "MAX_EVENT_EVIDENCE = 10",
    )

    TEST_PATH.write_text(
        TEST_CONTENT,
        encoding="utf-8",
        newline="\n",
    )

    print("[PASS] LLM generation stability patch applied")
    print(f"  updated: {LLM_CLIENT_PATH}")
    print(f"  updated: {LLM_GENERATOR_PATH}")
    print(f"  created: {TEST_PATH}")


if __name__ == "__main__":
    main()
