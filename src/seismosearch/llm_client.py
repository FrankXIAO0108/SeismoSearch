"""
OpenAI-compatible chat client for SeismoSearch.

This module is deliberately provider-neutral. Any service exposing a compatible
``/chat/completions`` endpoint can be configured through environment variables.

Required environment variables:
- SEISMOSEARCH_LLM_BASE_URL
- SEISMOSEARCH_LLM_API_KEY
- SEISMOSEARCH_LLM_MODEL

No network request is made when this module is imported.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMClientError(RuntimeError):
    """Raised when the configured LLM endpoint cannot return usable text."""


@dataclass(frozen=True)
class OpenAICompatibleSettings:
    """Runtime settings for an OpenAI-compatible chat endpoint."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0
    temperature: float = 0.0
    max_tokens: int = 1200
    json_mode: bool = True
    thinking_mode: str | None = None

    @classmethod
    def from_env(cls) -> "OpenAICompatibleSettings":
        """Load and validate LLM settings from environment variables."""
        base_url = os.getenv("SEISMOSEARCH_LLM_BASE_URL", "").strip()
        api_key = os.getenv("SEISMOSEARCH_LLM_API_KEY", "").strip()
        model = os.getenv("SEISMOSEARCH_LLM_MODEL", "").strip()

        missing_names = []

        if not base_url:
            missing_names.append("SEISMOSEARCH_LLM_BASE_URL")

        if not api_key:
            missing_names.append("SEISMOSEARCH_LLM_API_KEY")

        if not model:
            missing_names.append("SEISMOSEARCH_LLM_MODEL")

        if missing_names:
            missing_text = ", ".join(missing_names)
            raise LLMClientError(
                f"Missing required LLM environment variables: {missing_text}"
            )

        timeout_seconds = _read_float_env(
            "SEISMOSEARCH_LLM_TIMEOUT_SECONDS",
            default=60.0,
            minimum=1.0,
        )
        max_tokens = _read_int_env(
            "SEISMOSEARCH_LLM_MAX_TOKENS",
            default=1200,
            minimum=1,
        )
        json_mode = _read_bool_env(
            "SEISMOSEARCH_LLM_JSON_MODE",
            default=True,
        )
        thinking_mode = _read_optional_choice_env(
            "SEISMOSEARCH_LLM_THINKING_MODE",
            choices={"enabled", "disabled"},
        )

        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            temperature=0.0,
            max_tokens=max_tokens,
            json_mode=json_mode,
            thinking_mode=thinking_mode,
        )


def _read_float_env(
    name: str,
    default: float,
    minimum: float,
) -> float:
    """Read one positive floating-point environment variable."""
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        parsed_value = float(raw_value)
    except ValueError as error:
        raise LLMClientError(
            f"{name} must be a number, got: {raw_value!r}"
        ) from error

    if parsed_value < minimum:
        raise LLMClientError(
            f"{name} must be at least {minimum}, got: {parsed_value}"
        )

    return parsed_value


def _read_bool_env(
    name: str,
    default: bool,
) -> bool:
    """Read a boolean environment variable."""
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    normalized_value = raw_value.strip().lower()

    if normalized_value in {"1", "true", "yes", "on"}:
        return True

    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise LLMClientError(
        f"{name} must be a boolean, got: {raw_value!r}"
    )


def _read_optional_choice_env(
    name: str,
    choices: set[str],
) -> str | None:
    """Read an optional normalized choice environment variable."""
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return None

    normalized_value = raw_value.strip().lower()

    if normalized_value not in choices:
        choices_text = ", ".join(sorted(choices))
        raise LLMClientError(
            f"{name} must be one of: {choices_text}."
        )

    return normalized_value


def _read_int_env(
    name: str,
    default: int,
    minimum: int,
) -> int:
    """Read one positive integer environment variable."""
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        parsed_value = int(raw_value)
    except ValueError as error:
        raise LLMClientError(
            f"{name} must be an integer, got: {raw_value!r}"
        ) from error

    if parsed_value < minimum:
        raise LLMClientError(
            f"{name} must be at least {minimum}, got: {parsed_value}"
        )

    return parsed_value


class OpenAICompatibleChatClient:
    """Minimal synchronous client for a compatible chat-completions endpoint."""

    def __init__(
        self,
        settings: OpenAICompatibleSettings,
    ) -> None:
        self.settings = settings

    @classmethod
    def from_env(cls) -> "OpenAICompatibleChatClient":
        """Create a client from the SeismoSearch LLM environment variables."""
        return cls(OpenAICompatibleSettings.from_env())

    @property
    def model_name(self) -> str:
        """Return the configured model name for traces and evaluation."""
        return self.settings.model

    def _endpoint_url(self) -> str:
        """Resolve the final chat-completions endpoint URL."""
        normalized_url = self.settings.base_url.rstrip("/")

        if normalized_url.endswith("/chat/completions"):
            return normalized_url

        return f"{normalized_url}/chat/completions"

    def complete(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Send one non-streaming chat request and return assistant text."""
        if not messages:
            raise LLMClientError("messages must not be empty")

        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "stream": False,
        }

        if self.settings.json_mode:
            payload["response_format"] = {
                "type": "json_object",
            }

        if self.settings.thinking_mode is not None:
            payload["thinking"] = {
                "type": self.settings.thinking_mode,
            }

        request = Request(
            url=self._endpoint_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "SeismoSearch/llm-generator-v1",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.settings.timeout_seconds,
            ) as response:
                response_bytes = response.read()
        except HTTPError as error:
            error_body = error.read().decode(
                "utf-8",
                errors="replace",
            )
            raise LLMClientError(
                f"LLM endpoint returned HTTP {error.code}: "
                f"{error_body[:500]}"
            ) from error
        except URLError as error:
            raise LLMClientError(
                f"Unable to reach LLM endpoint: {error.reason}"
            ) from error
        except TimeoutError as error:
            raise LLMClientError(
                "LLM request timed out"
            ) from error

        try:
            response_data = json.loads(
                response_bytes.decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LLMClientError(
                "LLM endpoint returned invalid JSON"
            ) from error

        return _extract_assistant_text(response_data)


def _extract_assistant_text(
    response_data: dict[str, Any],
) -> str:
    """Extract assistant text from a compatible chat response."""
    choices = response_data.get("choices")

    if not isinstance(choices, list) or not choices:
        raise LLMClientError(
            "LLM response does not contain choices"
        )

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        raise LLMClientError(
            "LLM response choice has an invalid shape"
        )

    message = first_choice.get("message")

    if not isinstance(message, dict):
        raise LLMClientError(
            "LLM response does not contain a message"
        )

    content = message.get("content")
    finish_reason = first_choice.get("finish_reason")
    reasoning_content = message.get("reasoning_content")
    reasoning_chars = (
        len(reasoning_content)
        if isinstance(reasoning_content, str)
        else 0
    )

    if isinstance(content, str):
        normalized_content = content.strip()

        if not normalized_content:
            raise LLMClientError(
                "LLM response content is empty; "
                f"finish_reason={finish_reason!r}; "
                f"reasoning_content_chars={reasoning_chars}"
            )

        return normalized_content

    # Some compatible endpoints return a list of typed content blocks.
    if isinstance(content, list):
        text_parts = []

        for item in content:
            if not isinstance(item, dict):
                continue

            text_value = item.get("text")

            if isinstance(text_value, str) and text_value.strip():
                text_parts.append(text_value.strip())

        joined_text = "\n".join(text_parts).strip()

        if joined_text:
            return joined_text

    raise LLMClientError(
        "LLM response message does not contain usable text"
    )
