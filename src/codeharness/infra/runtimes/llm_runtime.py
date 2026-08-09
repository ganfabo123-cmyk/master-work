"""Runtime loop for LLM-backed Agents."""

from __future__ import annotations

from collections.abc import Callable, Collection
import json
from time import perf_counter
from typing import Any

from ..client import LLMClient
from ...core.base_observation import Observation
from ...core.models import Message, ModelResult, Task, ToolCall
from ..tool_registry import ToolRegistry
from ..trace import TraceRecorder

ToolFunction = Callable[..., Any]


class LLMRuntime:
    """Execute one complete LLM and tool-call loop."""

    def run(
        self,
        *,
        agent_name: str,
        llm: LLMClient,
        temperature: float | None,
        task: Task | None,
        messages: tuple[Message, ...] | list[Message] | None,
        initial_messages: Callable[[Task], tuple[Message, ...]],
        tool_functions: Callable[[], tuple[ToolFunction, ...]],
        tools: tuple[ToolFunction, ...] | None,
        available_tool_names: Collection[str] | None,
        tool_schemas: list[dict[str, Any]] | None,
        tool_registry: ToolRegistry | None,
        observation: Observation | None,
        model: str | None,
        max_turns: int,
        trace: TraceRecorder | None,
        session_id: str | None,
        record_initial_messages: bool,
        llm_kwargs: dict[str, Any],
    ) -> Message:
        if messages is None:
            if task is None:
                raise ValueError("task is required when messages are not supplied")
            history = list(initial_messages(task))
        else:
            history = list(messages)

        selected_tools = tool_functions() if tools is None else tools
        active_registry = self.build_tool_registry(selected_tools) if tool_registry is None else tool_registry
        active_observation = observation or Observation(
            observation_id=f"{agent_name}-observation",
            task_id=task.description if task is not None else "",
            session_id=session_id or "",
        )
        schemas = active_registry.schemas_for(selected_tools) if tool_schemas is None else tool_schemas
        selected_tool_names = tuple(tool.__name__ for tool in selected_tools)
        allowed_tool_names = frozenset(selected_tool_names if available_tool_names is None else available_tool_names)
        available_names = tuple(name for name in selected_tool_names if name in allowed_tool_names)
        if record_initial_messages and trace is not None and session_id is not None:
            self._record_initial_trace(trace, session_id, agent_name, history)

        for _ in range(max_turns):
            sent_messages = tuple(history)
            generation_options = {"temperature": temperature, **llm_kwargs} if temperature is not None else llm_kwargs
            result = llm.generate(
                model=model or "",
                messages=sent_messages,
                tools=schemas,
                **generation_options,
            )
            if result.parse_error:
                self._append_feedback(history, trace, session_id, agent_name, f"Model parse error: {result.parse_error}")
                continue
            if not result.tool_calls:
                assistant_message = Message("assistant", result.parsed_content)
                history.append(assistant_message)
                self._record_assistant_message(trace, session_id, agent_name, assistant_message, result)
                return assistant_message

            assistant_message = Message(
                "assistant",
                result.parsed_content or "",
                tool_calls=self._wire_tool_calls(result.tool_calls),
            )
            history.append(assistant_message)
            self._record_assistant_message(trace, session_id, agent_name, assistant_message, result)
            defer_for_thought = any(call.name == "think" for call in result.tool_calls)
            for call in result.tool_calls:
                history.append(
                    self._handle_tool_call(
                        agent_name=agent_name,
                        call=call,
                        selected_tool_names=selected_tool_names,
                        allowed_tool_names=allowed_tool_names,
                        available_names=available_names,
                        defer_for_thought=defer_for_thought,
                        tool_registry=active_registry,
                        observation=active_observation,
                        trace=trace,
                        session_id=session_id,
                    )
                )
        raise RuntimeError(f"Agent '{agent_name}' exceeded max_turns={max_turns} without a final assistant message")

    @staticmethod
    def build_tool_registry(tools: tuple[ToolFunction, ...]) -> ToolRegistry:
        """Build one isolated registry for the functions available in one run."""
        active_registry = ToolRegistry()
        for tool_function in tools:
            active_registry.register(tool_function)
        return active_registry

    @staticmethod
    def _wire_tool_calls(tool_calls: tuple[ToolCall, ...]) -> tuple[ToolCall, ...]:
        return tuple(
            ToolCall(call.id, call.name, json.dumps(call.arguments, ensure_ascii=False))
            for call in tool_calls
        )

    def _handle_tool_call(
        self,
        *,
        agent_name: str,
        call: ToolCall,
        selected_tool_names: tuple[str, ...],
        allowed_tool_names: frozenset[str],
        available_names: tuple[str, ...],
        defer_for_thought: bool,
        tool_registry: ToolRegistry,
        observation: Observation,
        trace: TraceRecorder | None,
        session_id: str | None,
    ) -> Message:
        if call.name not in selected_tool_names or call.name not in allowed_tool_names:
            available = ", ".join(available_names) or "无"
            tool_message = Message("tool", f"当前 {call.name} 工具不可用，只可用：{available}。", name=call.name, tool_call_id=call.id)
            self._record_tool_message(trace, session_id, agent_name, tool_message, duration_ms=0, success=False)
            return tool_message

        if defer_for_thought and call.name != "think":
            tool_message = Message("tool", "请先仅调用 think 并根据其返回结果继续；本次消息或动作调用未执行。", name=call.name, tool_call_id=call.id)
            self._record_tool_message(trace, session_id, agent_name, tool_message, duration_ms=0, success=False)
            return tool_message

        started = perf_counter()
        execution_error: Exception | None = None

        def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
            nonlocal execution_error
            try:
                return tool_registry.invoke(name, arguments)
            except Exception as error:
                execution_error = error
                raise

        try:
            tool_message = observation.feedback("tool_result", (call,), execute_tool)[0]
            self._record_tool_message(
                trace,
                session_id,
                agent_name,
                tool_message,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                success=execution_error is None,
            )
            return tool_message
        except Exception as error:
            tool_message = Message("tool", str(error), name=call.name, tool_call_id=call.id)
            self._record_tool_message(trace, session_id, agent_name, tool_message, duration_ms=round((perf_counter() - started) * 1000, 2), success=False)
            return tool_message

    @staticmethod
    def _record_initial_trace(trace: TraceRecorder, session_id: str, agent_name: str, messages: list[Message]) -> None:
        trace.record_initial_messages(session_id, agent_name, messages)

    @staticmethod
    def _record_assistant_message(trace: TraceRecorder | None, session_id: str | None, agent_name: str, message: Message, result: ModelResult) -> None:
        if trace is not None and session_id is not None:
            trace.record_assistant_message(session_id, agent_name, message, model=result.model, input_tokens=result.input_tokens, output_tokens=result.output_tokens, total_tokens=result.total_tokens, duration_ms=result.duration_ms, finish_reason=result.finish_reason)

    @staticmethod
    def _record_tool_message(trace: TraceRecorder | None, session_id: str | None, agent_name: str, message: Message, *, duration_ms: float, success: bool = True) -> None:
        if trace is not None and session_id is not None:
            trace.record_tool_message(session_id, agent_name, message, success=success, duration_ms=duration_ms)

    @staticmethod
    def _append_feedback(history: list[Message], trace: TraceRecorder | None, session_id: str | None, agent_name: str, content: str) -> None:
        message = Message("user", content)
        history.append(message)
        if trace is not None and session_id is not None:
            trace.record_feedback(session_id, agent_name, message)
