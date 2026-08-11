from __future__ import annotations

from collections.abc import Sequence
import json
import os
from time import perf_counter
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...core.models import Message, ModelResult, ToolCall


class LLMClient(Protocol):
    """Replace this boundary only when adopting a real model provider."""

    def generate(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        tools: list[dict],
        **kwargs: Any,
    ) -> ModelResult: ...


class DemoLLMClient:
    """Deterministic local client that demonstrates one tool round-trip."""

    def generate(self, *, model: str, messages: Sequence[Message], tools: list[dict], **kwargs: Any) -> ModelResult:
        if not any(message.role == "tool" for message in messages):
            task = next(message.content for message in messages if message.role == "user")
            return ModelResult(raw_content={"tool": "inspect_task"}, tool_calls=(ToolCall("demo-call-1", "inspect_task", {"task": task}),), model=model, finish_reason="tool_calls")
        observation = next(message.content for message in reversed(messages) if message.role == "tool")
        return ModelResult(
            raw_content={"content": f"Completed demo run. {observation}"},
            parsed_content=f"Completed demo run. {observation}",
            model=model,
            finish_reason="stop",
        )


class OpenAICompatibleClient:
    """Minimal sync adapter for OpenAI-compatible chat-completions endpoints."""

    def __init__(self, *, api_key: str, base_url: str, timeout_seconds: float = 60) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleClient":
        _load_dotenv_if_present()
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("PRO_API")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        if not api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY (or PRO_API). Copy .env.example to .env and set it.")
        return cls(api_key=api_key, base_url=base_url)

    def generate(self, *, model: str, messages: Sequence[Message], tools: list[dict], **kwargs: Any) -> ModelResult:
        wire_messages = []
        for message in messages:
            item = message.as_dict()
            # OpenAI-compatible endpoints commonly accept system but not developer.
            if item["role"] == "developer":
                item["role"] = "system"
            wire_messages.append(item)
        payload = {
            "model": model,
            "messages": wire_messages,
            "tools": [{"type": "function", "function": schema} for schema in tools],
            "thinking": {"type": "disabled"},
        }
        payload.update(kwargs)
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        started = perf_counter()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise RuntimeError(f"LLM network error: {error.reason}") from error
        choice = raw["choices"][0]
        message = choice["message"]
        calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            try:
                arguments = json.loads(call["function"]["arguments"])
            except json.JSONDecodeError as error:
                return ModelResult(raw_content=raw, parse_error=f"Invalid tool JSON: {error}", model=model)
            calls.append(ToolCall(call["id"], call["function"]["name"], arguments))
        usage = raw.get("usage", {})
        content = message.get("content")
        return ModelResult(
            raw_content=raw,
            parsed_content=content,
            tool_calls=tuple(calls),
            model=raw.get("model", model),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            duration_ms=round((perf_counter() - started) * 1000, 2),
            finish_reason=choice.get("finish_reason"),
        )


def _load_dotenv_if_present() -> None:
    """Tiny local .env reader; existing environment values always win."""
    path = os.getenv("COWORKER_ENV_FILE", ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
