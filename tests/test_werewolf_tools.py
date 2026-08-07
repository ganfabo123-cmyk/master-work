from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from codeharness.agents import Agent
from codeharness.llm import LLMClient, ModelResult
from codeharness.models import Message, Prompt, Task, ToolCall
from codeharness.room import AgentProfile, Room
from codeharness.util.werewolf_state import WerewolfGameState
from codeharness.util.werewolf_tools import tools_for_player


class TemperatureRecordingLLM(LLMClient):
    def __init__(self) -> None:
        self.temperature: float | None = None

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **kwargs: Any) -> ModelResult:
        self.temperature = kwargs.get("temperature")
        return ModelResult(raw_content="done", parsed_content="done", model=model)


class ThoughtThenActionLLM(LLMClient):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **kwargs: Any) -> ModelResult:
        self.calls += 1
        if self.calls == 1:
            return ModelResult(
                raw_content="",
                tool_calls=(
                    ToolCall("think-call", "think", {"strategy": "先判断预言家可能性"}),
                    ToolCall("message-call", "wolf_message", {"content": "今晚处理 player-3"}),
                ),
                model=model,
            )
        if self.calls == 2:
            assert any(message.name == "wolf_message" and "未执行" in str(message.content) for message in messages)
            return ModelResult(raw_content="", tool_calls=(ToolCall("message-retry", "wolf_message", {"content": "今晚处理 player-3"}),), model=model)
        return ModelResult(raw_content="done", parsed_content="done", model=model)


def test_temperature_is_forwarded_to_model() -> None:
    llm = TemperatureRecordingLLM()
    agent = Agent(
        name="temperature-agent",
        model="test",
        llm=llm,
        prompt_builder=lambda task: Prompt((Message("developer", "test"), Message("user", task.description))),
        temperature=1.15,
    )

    agent.run(Task("test"))

    assert llm.temperature == 1.15


def test_think_is_private_and_required_before_room_message() -> None:
    with TemporaryDirectory() as directory:
        room = Room("werewolf", session_id="thinking-test", data_root=Path(directory))
        state = WerewolfGameState.classic_eight_players()
        for name in (*state.players, "game-engine"):
            room.register(AgentProfile(name=name, introduction="participant", role="player"))
            room.invite(name)
        registry, _ = tools_for_player(room=room, actor="player-1", state=state)

        try:
            registry.invoke("wolf_message", {"content": "今晚处理 player-3"})
        except Exception as error:
            assert "先调用 think" in str(error)
        else:
            raise AssertionError("ROOM message should require think first")
        registry.invoke("think", {"strategy": "player-3 的发言最像预言家"})
        registry.invoke("wolf_message", {"content": "今晚处理 player-3"})

        message = room.history()[0]
        assert message.txt == "今晚处理 player-3"
        assert "预言家" not in message.txt
        assert message.at == ("player-1", "player-2", "player-6")


def test_think_must_finish_in_a_separate_model_turn_before_message() -> None:
    with TemporaryDirectory() as directory:
        room = Room("werewolf", session_id="separate-think-test", data_root=Path(directory))
        state = WerewolfGameState.classic_eight_players()
        for name in (*state.players, "game-engine"):
            room.register(AgentProfile(name=name, introduction="participant", role="player"))
            room.invite(name)
        registry, tools = tools_for_player(room=room, actor="player-1", state=state)
        llm = ThoughtThenActionLLM()
        agent = Agent(
            name="player-1",
            model="test",
            llm=llm,
            prompt_builder=lambda task: Prompt((Message("developer", "test"), Message("user", task.description))),
        )

        agent.run(Task("test"), tools=tools, tool_registry=registry)

        assert llm.calls == 3
        assert [message.txt for message in room.history()] == ["今晚处理 player-3"]
