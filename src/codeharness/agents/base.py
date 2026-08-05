"""Declarative Agent configuration. Runtime integration remains intentionally unchanged."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..llm import LLMClient
from ..models import Message, Prompt, Task
from ..tools import ToolRegistry, registry
from ..trace import TraceRecorder

PromptBuilder = Callable[[Task], Prompt]
ToolFunction = Callable[..., Any]


class TextOutput(BaseModel):
    content: str


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
    tools: tuple[ToolFunction, ...] = ()
    skills: tuple[SkillSpec, ...] = ()
    output_format: type[BaseModel] = TextOutput
    tool_registry: ToolRegistry = registry

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
        model: str | None = None,
        output_format: type[BaseModel] | None = None,
        max_turns: int = 8,
        trace: TraceRecorder | None = None,
        session_id: str | None = None,
        **llm_kwargs: Any,
    ) -> BaseModel:
        """Run this Agent's complete LLM and tool loop, returning only its typed output."""
        if messages is None:
            if task is None:
                raise ValueError("task is required when messages are not supplied")
            history = list(self.initial_messages(task))
        else:
            history = list(messages)
        selected_tools = self.tools if tools is None else tools
        selected_format = self.output_format if output_format is None else output_format
        submission_name, submission_schema = self._submission_tool(selected_format)
        if not self._has_submission_instruction(history, submission_name):
            history = self._append_submission_instruction(history, submission_name, selected_format)
        schemas = [*(self.tool_schemas(selected_tools) if tool_schemas is None else tool_schemas), submission_schema]
        if trace is not None and session_id is not None:
            self._record_initial_trace(trace, session_id, history, task)

        for _ in range(max_turns):
            sent_messages = tuple(history)
            result = self.llm.generate(
                model=model or self.model,
                messages=sent_messages,
                tools=schemas,
                **llm_kwargs,
            )
            if trace is not None and session_id is not None:
                trace.record(session_id, self.name, "model_response", messages=[message.as_dict() for message in sent_messages], result=result)
            if result.parse_error:
                history.append(Message("user", f"Model parse error: {result.parse_error}"))
                continue
            if not result.tool_calls:
                history.append(Message("assistant", result.parsed_content))
                history.append(Message("user", f"Final output must call {submission_name}."))
                continue

            history.append(Message("assistant", result.parsed_content or "", tool_calls=result.tool_calls))
            if any(call.name == submission_name for call in result.tool_calls):
                if len(result.tool_calls) != 1:
                    raise ValueError("a final submission cannot be combined with other tool calls")
                call = result.tool_calls[0]
                output = selected_format.model_validate(call.arguments)
                history.append(Message("tool", output.model_dump_json(), name=call.name, tool_call_id=call.id))
                if trace is not None and session_id is not None:
                    trace.record(session_id, self.name, "tool_call", tool_call=call)
                    trace.record(
                        session_id,
                        self.name,
                        "tool_result",
                        tool_call_id=call.id,
                        tool_name=call.name,
                        success=True,
                        result=output,
                        messages=[message.as_dict() for message in history],
                    )
                return output

            for call in result.tool_calls:
                if call.name not in {tool.__name__ for tool in selected_tools}:
                    raise ValueError(f"tool is not allowed for agent '{self.name}': {call.name}")
                if trace is not None and session_id is not None:
                    trace.record(session_id, self.name, "tool_call", tool_call=call)
                try:
                    value = self.tool_registry.invoke(call.name, call.arguments)
                    history.append(Message("tool", value, name=call.name, tool_call_id=call.id))
                    if trace is not None and session_id is not None:
                        trace.record(session_id, self.name, "tool_result", tool_call_id=call.id, tool_name=call.name, success=True, result=value)
                except Exception as error:
                    history.append(Message("tool", str(error), name=call.name, tool_call_id=call.id))
                    if trace is not None and session_id is not None:
                        trace.record(session_id, self.name, "tool_result", tool_call_id=call.id, tool_name=call.name, success=False, result=str(error))
        raise RuntimeError(f"Agent '{self.name}' exceeded max_turns={max_turns} without submitting output")

    def _submission_tool(self, output_format: type[BaseModel]) -> tuple[str, dict[str, Any]]:
        import re

        format_name = re.sub(r"(?<!^)(?=[A-Z])", "_", output_format.__name__).lower()
        name = f"submit_{format_name}"
        if name in {tool.__name__ for tool in self.tools}:
            raise ValueError(f"submission tool conflicts with agent tool: {name}")
        return name, {
            "name": name,
            "description": "Submit the final result and finish this Agent task.",
            "parameters": output_format.model_json_schema(),
        }

    @staticmethod
    def _has_submission_instruction(messages: list[Message], submission_name: str) -> bool:
        return any(message.role == "developer" and submission_name in str(message.content) for message in messages)

    @staticmethod
    def _append_submission_instruction(messages: list[Message], submission_name: str, output_format: type[BaseModel]) -> list[Message]:
        instruction = Message(
            "developer",
            f"When the task is complete, call `{submission_name}` with arguments matching the {output_format.__name__} schema. "
            "This tool call is the final result; do not provide a final answer as plain text.",
        )
        developer_indexes = [index for index, message in enumerate(messages) if message.role == "developer"]
        messages.insert(developer_indexes[-1] + 1 if developer_indexes else 0, instruction)
        return messages

    def _record_initial_trace(self, trace: TraceRecorder, session_id: str, messages: list[Message], task: Task | None) -> None:
        system_prompt = "\n\n".join(str(message.content) for message in messages if message.role == "developer")
        trace.record(session_id, self.name, "system_prompt", raw_content=system_prompt)
        trace.record(session_id, self.name, "user_prompt", raw_content=task.description if task is not None else "explicit messages")
