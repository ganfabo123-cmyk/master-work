from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from codeharness.agents import Agent
from codeharness.llm import LLMClient, ModelResult
from codeharness.models import Message, Prompt, Task, ToolCall
from codeharness.room import AgentProfile, Room
from codeharness.util.werewolf_state import Phase, Role, WerewolfGameState
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


class InvalidSaveThenStopLLM(LLMClient):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        self.calls += 1
        if self.calls == 1:
            return ModelResult(raw_content="", tool_calls=(ToolCall("think", "think", {"strategy": "确认药物状态"}),), model=model)
        if self.calls == 2:
            return ModelResult(raw_content="", tool_calls=(ToolCall("save", "save", {}),), model=model)
        assert any(message.name == "save" and "当前不可用" in str(message.content) for message in messages)
        return ModelResult(raw_content="本回合不使用药物。", parsed_content="本回合不使用药物。", model=model)


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


def test_wolf_message_is_written_only_to_the_private_wolf_room() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        public_room = Room("public", session_id="private-room-test", data_root=root)
        wolf_room = Room("wolves", session_id="private-room-test", data_root=root)
        state = WerewolfGameState.classic_eight_players()
        for name in (*state.players, "game-engine"):
            public_room.register(AgentProfile(name=name, introduction="participant", role="player"))
            public_room.invite(name)
        for name in (*state.alive_wolves(), "game-engine"):
            wolf_room.register(AgentProfile(name=name, introduction="participant", role="wolf"))
            wolf_room.invite(name)

        registry, _ = tools_for_player(room=public_room, wolf_room=wolf_room, actor="player-1", state=state)
        registry.invoke("think", {"strategy": "先与狼队友私下确认目标"})
        registry.invoke("wolf_message", {"content": "今晚处理 player-3"})

        assert public_room.history() == ()
        assert [message.txt for message in wolf_room.history()] == ["今晚处理 player-3"]
        assert wolf_room.participants() == ("game-engine", "player-1", "player-2", "player-6")


def test_unavailable_witch_save_returns_feedback_and_allows_the_turn_to_finish() -> None:
    with TemporaryDirectory() as directory:
        room = Room("public", session_id="witch-feedback", data_root=Path(directory))
        state = WerewolfGameState.classic_eight_players()
        witch = next(name for name, player in state.players.items() if player.role is Role.WITCH)
        state.phase = Phase.NIGHT_WITCH
        state.witch_has_antidote = False
        for name in (*state.players, "game-engine"):
            room.register(AgentProfile(name=name, introduction="participant", role="player"))
            room.invite(name)
        registry, tools = tools_for_player(room=room, actor=witch, state=state)
        assert {tool.__name__ for tool in tools} == {"think", "poison"}
        llm = InvalidSaveThenStopLLM()
        agent = Agent(name=witch, model="test", llm=llm, prompt_builder=lambda task: Prompt((Message("developer", "test"), Message("user", task.description))))

        result = agent.run(Task("witch turn"), tools=tools, tool_registry=registry)

        assert result.content == "本回合不使用药物。"
        assert llm.calls == 3
