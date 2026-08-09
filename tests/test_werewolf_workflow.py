from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codeharness.client import LLMClient
from codeharness.models import ModelResult
from codeharness.models import Message, Task, ToolCall
from codeharness.environment.werewolf import WerewolfEnvironment, WerewolfWorkflowConfig, open_or_restore_session
from codeharness.session import SessionManager


class GameLLM(LLMClient):
    """Uses every current phase tool once, then ends its turn."""

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        assert {tool["name"] for tool in tools} >= {"think", "wolf_kill", "inspect", "vote", "shoot"}
        latest_state = next((message for message in reversed(messages) if message.role == "user" and '"type": "game_state"' in str(message.content)), None)
        names = set(json.loads(latest_state.content)["available_actions"]) if latest_state is not None else set()
        if "wolf_kill" in names:
            assert "night_wolf_kill" in str(latest_state.content)
        if messages[-1].role == "tool":
            if messages[-1].name != "think":
                return ModelResult(raw_content="action submitted", parsed_content="action submitted", model=model)
            return self._action_for(names)
        return self._call("think", {"strategy": "Review the visible messages and select the safest legal move."})

    def _action_for(self, names: set[str]) -> ModelResult:
        if "wolf_message" in names:
            return self._call("wolf_message", {"content": "agree on a target"})
        choices = {
            "wolf_kill": {"target": "player-3"},
            "inspect": {"target": "player-1"},
            "poison": {"target": "player-1"},
            "speak": {"content": "I will vote based on the public discussion."},
            "vote": {"target": "player-6"},
            "shoot": {"target": "player-2"},
        }
        for name, arguments in choices.items():
            if name in names:
                return self._call(name, arguments)
        return ModelResult(raw_content="abstain", parsed_content="abstain", model="game-test")

    @staticmethod
    def _call(name: str, arguments: dict[str, str]) -> ModelResult:
        return ModelResult(
            raw_content="",
            parsed_content="",
            tool_calls=(ToolCall("call-1", name, arguments),),
            model="game-test",
        )


def test_game_is_room_traceable_and_resumable(tmp_path: Path) -> None:
    traces = tmp_path / "traces"
    room = tmp_path / "room"
    environment = WerewolfEnvironment(SessionManager(traces_root=traces, room_data_root=room), llm=GameLLM(), model="game-test")

    result = environment.run(
        task=Task("开始一局经典狼人杀"),
        session_id=None,
        on_session_opened=None,
        config=WerewolfWorkflowConfig(max_game_rounds=4),
    )

    assert result.status == "completed"
    state_path = tmp_path / "state" / "data" / result.session_id / "werewolf.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    room_states = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (room / result.session_id / "rooms").glob("*.json")
    }
    assert len(room_states) == 2
    public = next(state for room_id, state in room_states.items() if "public" in room_id)
    wolves = next(state for room_id, state in room_states.items() if "wolves" in room_id)
    assert "game-engine" in public["participants"]
    assert len(public["participants"]) == 9
    assert "game-engine" in wolves["participants"]
    assert len(wolves["participants"]) == 3
    wolf_room_id = next(room_id for room_id in room_states if "wolves" in room_id)
    assert any(message.txt == "agree on a target" for message in environment.trace.room_messages(result.session_id, wolf_room_id))
    public_room_id = next(room_id for room_id in room_states if "public" in room_id)
    public_messages = environment.trace.room_messages(result.session_id, public_room_id)
    assert any("你已拿到身份" in message.txt and "list_experiences" in message.txt for message in public_messages)
    preparation_events = {
        player_name: [
            json.loads(message.content)
            for message in environment.trace.messages(result.session_id, player_name)
            if message.role == "user" and isinstance(message.content, str) and '"phase": "preparation"' in message.content
        ]
        for player_name in state["players"]
    }
    assert all(events for events in preparation_events.values())
    state_events = [
        json.loads(message.content)
        for player_name in state["players"]
        for message in environment.trace.messages(result.session_id, player_name)
        if message.role == "user" and isinstance(message.content, str) and '"type": "game_state"' in message.content
    ]
    assert state_events
    assert all(set(event) == {"type", "round_no", "phase", "alive_players", "available_actions"} for event in state_events)
    resumed = WerewolfEnvironment(SessionManager(traces_root=traces, room_data_root=room), llm=GameLLM(), model="game-test")
    # A finished session remains readable and can be reopened without rebuilding participants.
    restored = open_or_restore_session(resumed, task=Task("继续"), session_id=result.session_id)
    assert len(restored.agents) == 8
    assert {name: profile.role.value for name, profile in restored.state.players.items()} == {
        name: profile["role"] for name, profile in state["players"].items()
    }
