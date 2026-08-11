from __future__ import annotations

from collections.abc import Callable
from typing import Any

from coworker.core import Agent
from coworker.core.models import Message, ModelResult, Prompt, Task, ToolCall
from coworker.infra.client import LLMClient
from coworker.infra.runtimes import IncrementalContext
from coworker.infra.tools import BaseAgentTools


class PolicyThenActionLLM(LLMClient):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        self.calls += 1
        return ModelResult(
            raw_content="",
            tool_calls=(
                ToolCall("think-call", "think", {}),
                ToolCall("vote-call", "vote", {"target": "player-3"}),
            ),
            model=model,
        )


class RecordingPolicyTools(BaseAgentTools):
    def __init__(self) -> None:
        super().__init__("agent")
        self.calls = 0

    def tool_functions(self) -> tuple[Callable[[], str], ...]:
        return (self.think,)

    def think(self) -> str:
        self.calls += 1
        return "policy tool executed"


class RecordingActionTools(BaseAgentTools):
    def __init__(self) -> None:
        super().__init__("agent")
        self.calls = 0

    def tool_functions(self) -> tuple[Callable[[str], str], ...]:
        return (self.vote,)

    def vote(self, target: str) -> str:
        self.calls += 1
        return f"action tool unexpectedly executed for {target}"


def test_action_tool_call_ends_turn_without_execution_or_raw_content() -> None:
    llm = PolicyThenActionLLM()
    policy_tools = RecordingPolicyTools()
    action_tools = RecordingActionTools()
    agent = Agent(
        name="agent", model="test", llm=llm,
        prompt_builder=lambda task: Prompt((Message("developer", "test"), Message("user", task.description))),
        policy_tools=(policy_tools,), action_tools=(action_tools,),
    )

    context = IncrementalContext()
    result = agent.run(Task("产生一个动作"), message_sink=context.append_turn_messages)

    assert llm.calls == 1
    assert policy_tools.calls == 1
    assert action_tools.calls == 0
    assert [call.name for call in result.tool_calls] == ["think", "vote"]
    assert context.messages[0] == result
    assert context.messages[1].role == "tool"
    assert context.messages[1].tool_call_id == "think-call"
