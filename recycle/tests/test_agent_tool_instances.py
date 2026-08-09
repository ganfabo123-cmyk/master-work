from typing import Annotated, Any, Callable

from pydantic import Field

from codeharness.agents.base import Agent
from codeharness.llm import DemoLLMClient
from codeharness.models import Message, ModelResult, Prompt, Task, ToolCall
from codeharness.tools.base import BaseAgentTools


class FirstTools(BaseAgentTools):
    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        return (self.first,)

    def first(self, value: Annotated[str, Field(description="First tool input.")]) -> str:
        """Return the first tool result."""
        return f"{self.agent_name}:first:{value}"


class SecondTools(BaseAgentTools):
    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        return (self.second,)

    def second(self, value: Annotated[str, Field(description="Second tool input.")]) -> str:
        """Return the second tool result."""
        return f"{self.agent_name}:second:{value}"


class CallingFirstLLM:
    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        assert [tool["name"] for tool in tools] == ["first", "second"]
        if not any(message.role == "tool" for message in messages):
            return ModelResult(raw_content={}, tool_calls=(ToolCall("call-1", "first", {"value": "x"}),))
        return ModelResult(raw_content={}, parsed_content=messages[-1].content)


class CallingSecondLLM:
    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        assert [tool["name"] for tool in tools] == ["first", "second"]
        if not any(message.role == "tool" for message in messages):
            return ModelResult(raw_content={}, tool_calls=(ToolCall("call-1", "second", {"value": "x"}),))
        return ModelResult(raw_content={}, parsed_content=messages[-1].content)


def test_agent_aggregates_bound_functions_from_multiple_tool_instances() -> None:
    agent = Agent(
        name="player-1",
        model="test",
        llm=DemoLLMClient(),
        prompt_builder=lambda task: Prompt((Message("developer", "test"), Message("user", task.description))),
        policy_tools=(FirstTools("player-1"), SecondTools("player-1")),
    )

    assert [function.__name__ for function in agent.tool_functions()] == ["first", "second"]
    assert agent.tool_schemas() == [
        {
            "name": "first",
            "description": "Return the first tool result.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"description": "First tool input.", "type": "string"}},
                "required": ["value"],
            },
        },
        {
            "name": "second",
            "description": "Return the second tool result.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"description": "Second tool input.", "type": "string"}},
                "required": ["value"],
            },
        },
    ]
    registry = agent._build_tool_registry(agent.tool_functions())
    assert registry.invoke("first", {"value": "x"}) == "player-1:first:x"
    assert registry.invoke("second", {"value": "y"}) == "player-1:second:y"


def test_agent_run_invokes_function_bound_to_its_tool_instance() -> None:
    agent = Agent(
        name="player-1",
        model="test",
        llm=CallingFirstLLM(),
        prompt_builder=lambda task: Prompt((Message("developer", "test"), Message("user", task.description))),
        policy_tools=(FirstTools("player-1"), SecondTools("player-1")),
    )

    result = agent.run(Task("test"))

    assert result.content == "player-1:first:x"


def test_agent_run_rejects_a_tool_outside_the_available_names_without_changing_schema() -> None:
    agent = Agent(
        name="player-1",
        model="test",
        llm=CallingSecondLLM(),
        prompt_builder=lambda task: Prompt((Message("developer", "test"), Message("user", task.description))),
        policy_tools=(FirstTools("player-1"), SecondTools("player-1")),
    )

    result = agent.run(Task("test"), available_tool_names=("first",))

    assert result.content == "当前 second 工具不可用，只可用：first。"
