"""Declarative configuration for LLM-backed Agents."""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..base_observation.llm_observation import LLMObservation
from ...protocol.base_agent import BaseAgent
from ...protocol.base_tool import BaseAgentTools
from ...tool_registry import ToolRegistry
from ...client import LLMClient
from ...models import Message, Prompt, Task
from ...runtimes.llm_runtime import LLMRuntime
from ...trace import TraceRecorder

PromptBuilder = Callable[[Task], Prompt]
ToolFunction = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class SkillSpec:
    """A Skill this Agent may use; it is not a global default."""

    name: str
    path: Path
    description: str


@dataclass(frozen=True, slots=True)
class LLMAgent(BaseAgent):
    """Generic LLM-backed Agent configuration."""

    name: str
    model: str
    llm: LLMClient
    prompt_builder: PromptBuilder | None = None
    policy: Any = None
    action: Any = None
    temperature: float | None = None
    policy_tools: tuple[BaseAgentTools, ...] = ()
    action_tools: tuple[BaseAgentTools, ...] = ()
    skills: tuple[SkillSpec, ...] = ()
    runtime: LLMRuntime = field(default_factory=LLMRuntime, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self.policy is not None:
            object.__setattr__(self, "prompt_builder", self.get_prompt_builder())
        if self.action is not None and not self.action_tools:
            object.__setattr__(self, "action_tools", self._resolve_tool_sets(self.action))

    def get_prompt_builder(self) -> PromptBuilder:
        """Resolve the Prompt Builder from the configured Policy."""
        if self.policy is not None:
            builder = getattr(self.policy, "build", None)
            if callable(builder):
                return builder
            if callable(self.policy):
                return self.policy
            raise TypeError("policy must expose build(task) or be callable")
        if self.prompt_builder is not None:
            return self.prompt_builder
        raise ValueError(f"Agent '{self.name}' has no policy or prompt_builder")

    def get_tools(self) -> tuple[BaseAgentTools, ...]:
        """Resolve and combine Policy-owned and Action-owned tool sets."""
        return (*self.policy_tools, *self.action_tools)

    @staticmethod
    def _resolve_tool_sets(configured: Any) -> tuple[BaseAgentTools, ...]:
        """Normalize one tool set or an iterable of tool sets."""
        if configured is None:
            return ()
        if isinstance(configured, BaseAgentTools):
            return (configured,)
        try:
            tool_sets = tuple(configured)
        except TypeError as error:
            raise TypeError("action must be a BaseAgentTools instance or an iterable of them") from error
        if not all(isinstance(tool_set, BaseAgentTools) for tool_set in tool_sets):
            raise TypeError("action must contain only BaseAgentTools instances")
        return tool_sets

    def initial_messages(self, task: Task) -> tuple[Message, ...]:
        if self.prompt_builder is None:
            raise ValueError(f"Agent '{self.name}' has no prompt_builder")
        return self.prompt_builder(task).messages

    def tool_functions(self) -> tuple[ToolFunction, ...]:
        """Return model-callable functions from Policy and Action tool sets."""
        return tuple(function for tool_set in self.get_tools() for function in tool_set.tool_functions())

    def tool_schemas(self, tools: tuple[ToolFunction, ...] | None = None) -> list[dict[str, Any]]:
        selected_tools = self.tool_functions() if tools is None else tools
        return self.runtime.build_tool_registry(selected_tools).schemas_for(selected_tools)

    def run(
        self,
        task: Task | None = None,
        *,
        messages: tuple[Message, ...] | list[Message] | None = None,
        tools: tuple[ToolFunction, ...] | None = None,
        available_tool_names: Collection[str] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        tool_registry: ToolRegistry | None = None,
        observation: LLMObservation | None = None,
        model: str | None = None,
        max_turns: int = 8,
        trace: TraceRecorder | None = None,
        session_id: str | None = None,
        record_initial_messages: bool = True,
        **llm_kwargs: Any,
    ) -> Message:
        """Delegate one complete LLM run to the configured runtime."""
        return self.runtime.run(
            agent_name=self.name,
            llm=self.llm,
            temperature=self.temperature,
            task=task,
            messages=messages,
            initial_messages=self.initial_messages,
            tool_functions=self.tool_functions,
            tools=tools,
            available_tool_names=available_tool_names,
            tool_schemas=tool_schemas,
            tool_registry=tool_registry,
            observation=observation,
            model=model or self.model,
            max_turns=max_turns,
            trace=trace,
            session_id=session_id,
            record_initial_messages=record_initial_messages,
            llm_kwargs=llm_kwargs,
        )
