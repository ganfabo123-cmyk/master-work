from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codeharness.llm import LLMClient, ModelResult
from codeharness.agents import WerewolfPlayerAgent
from codeharness.models import Message, Task, ToolCall
from codeharness.orchestrator import Orchestrator
from codeharness.util.werewolf_state import Role


class GameLLM(LLMClient):
    """Uses every current phase tool once, then ends its turn."""

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        if messages[-1].role == "tool":
            names = {tool["name"] for tool in tools}
            if messages[-1].name != "think":
                return ModelResult(raw_content="action submitted", parsed_content="action submitted", model=model)
            return self._action_for(names)
        names = {tool["name"] for tool in tools}
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
        return ModelResult(raw_content="abstain", parsed_content="abstain", model=model)

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
    orchestrator = Orchestrator(traces_root=traces, room_data_root=room, llm=GameLLM(), model="game-test", max_game_rounds=4)

    result = orchestrator.run(task=Task("开始一局经典狼人杀"))

    assert result.status == "completed"
    state_path = traces / result.session_id / "werewolf_state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    room_state = next(room.glob("room_*.json")).read_text(encoding="utf-8")
    assert "game-engine" in room_state
    assert "player-1" in room_state
    assert "狼人请私下协商" in room_state
    resumed = Orchestrator(traces_root=traces, room_data_root=room, llm=GameLLM(), model="game-test", max_game_rounds=4)
    resumed.register_agent_factory(
        "werewolf-player",
        lambda profile: WerewolfPlayerAgent(GameLLM(), "game-test", name=profile.name, role=Role(profile.kwargs["identity"])),
    )
    # A finished session remains readable and can be reopened without rebuilding participants.
    restored = resumed._open_or_restore_werewolf_session(task=Task("继续"), session_id=result.session_id)
    assert len(restored.agents) == 8
    assert {name: profile.role.value for name, profile in restored.state.players.items()} == {
        name: profile["role"] for name, profile in state["players"].items()
    }
