"""Declarative Agent configuration. Runtime integration remains intentionally unchanged."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from ..llm import LLMClient, ModelResult
from ..models import Message, Prompt, Task, ToolCall
from ..tools import ToolRegistry, registry
from ..trace import TraceRecorder

PromptBuilder = Callable[[Task], Prompt]
ToolFunction = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class SkillSpec:
    """A Skill this Agent may use; it is not a global default."""

    name: str
    path: Path
    description: str


@dataclass(frozen=True, slots=True)
class Agent:
    """All domain-specific Agent choices belong in this class declaration."""

    name: str
    model: str
    llm: LLMClient
    prompt_builder: PromptBuilder
    temperature: float | None = None
    tools: tuple[ToolFunction, ...] = ()
    skills: tuple[SkillSpec, ...] = ()
    tool_registry: ToolRegistry = registry

    def __post_init__(self) -> None:
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")

    def initial_messages(self, task: Task) -> tuple[Message, ...]:
        return self.prompt_builder(task).messages

    def tool_schemas(self, tools: tuple[ToolFunction, ...] | None = None) -> list[dict[str, Any]]:
        return self.tool_registry.schemas_for(self.tools if tools is None else tools)

    def run(
        self,
        task: Task | None = None,
        *,
        messages: tuple[Message, ...] | list[Message] | None = None,
        tools: tuple[ToolFunction, ...] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        tool_registry: ToolRegistry | None = None,
        model: str | None = None,
        max_turns: int = 8,
        trace: TraceRecorder | None = None,
        session_id: str | None = None,
        record_initial_messages: bool = True,
        **llm_kwargs: Any,
    ) -> Message:
        """Run this Agent's complete LLM and tool loop, returning its final assistant message."""
        if messages is None:
            if task is None:
                raise ValueError("task is required when messages are not supplied")
            history = list(self.initial_messages(task))
        else:
            history = list(messages)
        selected_tools = self.tools if tools is None else tools
        active_registry = tool_registry or self.tool_registry
        schemas = active_registry.schemas_for(selected_tools) if tool_schemas is None else tool_schemas
        if record_initial_messages and trace is not None and session_id is not None:
            self._record_initial_trace(trace, session_id, history)

        for _ in range(max_turns):
            sent_messages = tuple(history)
            generation_options = {"temperature": self.temperature, **llm_kwargs} if self.temperature is not None else llm_kwargs
            result = self.llm.generate(
                model=model or self.model,
                messages=sent_messages,
                tools=schemas,
                **generation_options,
            )
            if result.parse_error:
                self._append_feedback(history, trace, session_id, f"Model parse error: {result.parse_error}")
                continue
            if not result.tool_calls:
                assistant_message = Message("assistant", result.parsed_content)
                history.append(assistant_message)
                self._record_assistant_message(trace, session_id, assistant_message, result)
                return assistant_message

            wire_tool_calls = tuple(
                ToolCall(call.id, call.name, json.dumps(call.arguments, ensure_ascii=False))
                for call in result.tool_calls
            )
            assistant_message = Message("assistant", result.parsed_content or "", tool_calls=wire_tool_calls)
            history.append(assistant_message)
            self._record_assistant_message(trace, session_id, assistant_message, result)
            defer_for_thought = any(call.name == "think" for call in result.tool_calls)
            for call in result.tool_calls:
                if call.name not in {tool.__name__ for tool in selected_tools}:
                    available = ", ".join(tool.__name__ for tool in selected_tools) or "无"
                    tool_message = Message(
                        "tool",
                        f"工具 '{call.name}' 当前不可用。可用工具：{available}。请根据当前状态重新选择；若无需行动，可直接结束本回合。",
                        name=call.name,
                        tool_call_id=call.id,
                    )
                    history.append(tool_message)
                    self._record_tool_message(trace, session_id, tool_message, duration_ms=0, success=False)
                    continue
                if defer_for_thought and call.name != "think":
                    tool_message = Message(
                        "tool",
                        "请先仅调用 think 并根据其返回结果继续；本次消息或动作调用未执行。",
                        name=call.name,
                        tool_call_id=call.id,
                    )
                    history.append(tool_message)
                    self._record_tool_message(trace, session_id, tool_message, duration_ms=0, success=False)
                    continue
                started = perf_counter()
                try:
                    value = active_registry.invoke(call.name, call.arguments)
                    tool_message = Message("tool", value, name=call.name, tool_call_id=call.id)
                    history.append(tool_message)
                    self._record_tool_message(trace, session_id, tool_message, duration_ms=round((perf_counter() - started) * 1000, 2))
                except Exception as error:
                    tool_message = Message("tool", str(error), name=call.name, tool_call_id=call.id)
                    history.append(tool_message)
                    self._record_tool_message(trace, session_id, tool_message, duration_ms=round((perf_counter() - started) * 1000, 2), success=False)
        raise RuntimeError(f"Agent '{self.name}' exceeded max_turns={max_turns} without a final assistant message")

    def _record_initial_trace(self, trace: TraceRecorder, session_id: str, messages: list[Message]) -> None:
        for message in messages:
            if message.role not in {"developer", "user"}:
                continue
            trace_message = message.as_dict()
            trace_message["role"] = "system" if message.role == "developer" else "user"
            trace.record(session_id, self.name, trace_message["role"], message=trace_message)

    def _record_assistant_message(self, trace: TraceRecorder | None, session_id: str | None, message: Message, result: ModelResult) -> None:
        if trace is not None and session_id is not None:
            trace.record(
                session_id,
                self.name,
                "assistant",
                message=message.as_dict(),
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                duration_ms=result.duration_ms,
                finish_reason=result.finish_reason,
            )

    def _record_tool_message(
        self,
        trace: TraceRecorder | None,
        session_id: str | None,
        message: Message,
        *,
        duration_ms: float,
        success: bool = True,
    ) -> None:
        if trace is not None and session_id is not None:
            trace.record(session_id, self.name, "tool", message=message.as_dict(), success=success, duration_ms=duration_ms)

    def _append_feedback(self, history: list[Message], trace: TraceRecorder | None, session_id: str | None, content: str) -> None:
        message = Message("user", content)
        history.append(message)
        if trace is not None and session_id is not None:
            trace.record(session_id, self.name, "user", message=message.as_dict())
