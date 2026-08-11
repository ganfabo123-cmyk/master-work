from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from coworker.apps.werewolf.agent import WerewolfPlayerAgent
from coworker.apps.werewolf.state import Phase, Role, WerewolfGameState
from coworker.core import Agent
from coworker.core.models import Message, ModelResult, Prompt, Task, ToolCall
from coworker.infra.client import LLMClient
from coworker.infra.room import AgentProfile, Room
from coworker.infra.runtimes import LLMRuntime


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
        raise AssertionError("An Action Tool Call must terminate the Agent turn")


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


def _register_players(room: Room, state: WerewolfGameState, *, wolves_only: bool = False) -> None:
    names = state.alive_wolves() if wolves_only else tuple(state.players)
    for name in (*names, "game-engine"):
        room.register(AgentProfile(name=name, introduction="participant", role="player"))
        room.invite(name)


def _player_agent(
    llm: LLMClient,
    *,
    room: Room,
    state: WerewolfGameState,
    name: str,
    wolf_room: Room | None = None,
) -> WerewolfPlayerAgent:
    return WerewolfPlayerAgent(
        llm,
        "test",
        name=name,
        role=state.role_of(name),
        public_room=room,
        state=state,
        wolf_room=wolf_room,
    )


def _registry_for(agent: WerewolfPlayerAgent):
    functions = agent.tool_functions()
    return LLMRuntime.build_tool_registry(functions), functions


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


def test_preparation_keeps_the_full_phase_invariant_tool_contract() -> None:
    with TemporaryDirectory() as directory:
        room = Room("werewolf", session_id="preparation-test", data_root=Path(directory))
        state = WerewolfGameState.classic_eight_players()
        state.phase = Phase.PREPARATION
        _register_players(room, state)

        functions = _player_agent(TemperatureRecordingLLM(), room=room, state=state, name="player-8").tool_functions()

        assert [function.__name__ for function in functions] == [
            "think",
            "save_experience",
            "list_experiences",
            "get_experience",
            "wolf_message",
            "speak",
            "wolf_kill",
            "inspect",
            "save",
            "poison",
            "vote",
            "shoot",
            "skip_shot",
        ]


def test_action_tool_schema_has_no_room_side_effect_when_invoked_directly() -> None:
    with TemporaryDirectory() as directory:
        room = Room("werewolf", session_id="thinking-test", data_root=Path(directory))
        state = WerewolfGameState.classic_eight_players()
        _register_players(room, state)
        registry, _ = _registry_for(_player_agent(TemperatureRecordingLLM(), room=room, state=state, name="player-1"))

        registry.invoke("wolf_message", {"content": "今晚处理 player-3"})

        assert room.history() == ()


def test_policy_tool_executes_before_action_tool_terminates_turn() -> None:
    with TemporaryDirectory() as directory:
        room = Room("werewolf", session_id="separate-think-test", data_root=Path(directory))
        state = WerewolfGameState.classic_eight_players()
        _register_players(room, state)
        llm = ThoughtThenActionLLM()
        agent = _player_agent(llm, room=room, state=state, name="player-1")

        result = agent.run(Task("test"))

        assert llm.calls == 1
        assert [call.name for call in result.tool_calls] == ["think", "wolf_message"]
        assert room.history() == ()


def test_wolf_message_action_does_not_write_either_room_before_environment_consumes_it() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        public_room = Room("public", session_id="private-room-test", data_root=root)
        wolf_room = Room("wolves", session_id="private-room-test", data_root=root)
        state = WerewolfGameState.classic_eight_players()
        _register_players(public_room, state)
        _register_players(wolf_room, state, wolves_only=True)

        registry, _ = _registry_for(_player_agent(TemperatureRecordingLLM(), room=public_room, wolf_room=wolf_room, state=state, name="player-1"))
        registry.invoke("think", {"strategy": "先与狼队友私下确认目标"})
        registry.invoke("wolf_message", {"content": "今晚处理 player-3"})

        assert public_room.history() == ()
        assert wolf_room.history() == ()
        assert wolf_room.participants() == ("game-engine", "player-1", "player-2")


def test_unavailable_witch_save_returns_feedback_and_allows_the_turn_to_finish() -> None:
    with TemporaryDirectory() as directory:
        room = Room("public", session_id="witch-feedback", data_root=Path(directory))
        state = WerewolfGameState.classic_eight_players()
        witch = next(name for name, player in state.players.items() if player.role is Role.WITCH)
        state.phase = Phase.NIGHT_WITCH
        state.witch_has_antidote = False
        _register_players(room, state)
        llm = InvalidSaveThenStopLLM()
        agent = _player_agent(llm, room=room, state=state, name=witch)
        functions = agent.tool_functions()
        assert {function.__name__ for function in functions} == {"think", "save_experience", "list_experiences", "get_experience", "poison"}

        result = agent.run(Task("witch turn"))

        assert result.content == "本回合不使用药物。"
        assert llm.calls == 3
