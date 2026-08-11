from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from coworker.apps.script_murder.environment import ScriptMurderEnvironment
from coworker.apps.script_murder.state import PLAYERS, ScriptMurderState
from coworker.core.models import Message, ModelResult, Task, ToolCall
from coworker.infra.client import LLMClient
from coworker.infra.runtimes import SessionRuntime
from coworker.infra.session import SessionManager
from tool_message_assertions import assert_tool_calls_are_paired


class ScriptMurderLLM(LLMClient):
    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        assert_tool_calls_are_paired(messages)
        if messages[-1].role == "tool":
            return ModelResult(raw_content="done", parsed_content="done", model=model)
        state_message = next(message for message in reversed(messages) if message.role == "user" and '"type": "script_murder.state"' in str(message.content))
        state = json.loads(state_message.content)
        player = state["player_name"]
        if state["phase"] in {"round_1_discussion", "round_2_discussion"}:
            return self._call(f"{player}-{state['phase']}", "speak", {"message": f"{player} 在 {state['phase']} 依据自己掌握的信息发言。"}, model)
        character = state["character_id"]
        return self._call(
            f"{player}-submit", "submit_resolution",
            {"declarations": [f"{player} 保留自己的最终判断。"], "decisive_action": "pass", "target": None, "leader_vote": character},
            model,
        )

    @staticmethod
    def _call(call_id: str, name: str, arguments: dict[str, object], model: str) -> ModelResult:
        return ModelResult(raw_content="", tool_calls=(ToolCall(call_id, name, arguments),), model=model)


def test_complete_workflow_is_private_deterministic_and_resumable(tmp_path: Path) -> None:
    environment = ScriptMurderEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=ScriptMurderLLM(), model="test",
    )
    result = SessionRuntime(trace=environment.session.trace).run(environment, task=Task("开始案件"))

    assert result.status == "completed", result.error
    state_path = tmp_path / "state" / "data" / result.session_id / "script_murder.json"
    state = ScriptMurderState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
    assert state.is_terminal
    assert len(state.final_submissions) == len(PLAYERS)
    assert state.resolution["elected_leader"] == "andre_robespierre"
    assert state.resolution["tie_break_rule"] == "case_character_order"
    assert "安德烈·罗伯斯庇尔是潜伏自由党" in state.ending_report

    session = environment.trace.session_data(result.session_id)
    private_ids = session["script_murder_private_room_ids"]
    player_one_private = environment.trace.room_messages(result.session_id, private_ids["player-1"])
    player_two_private = environment.trace.room_messages(result.session_id, private_ids["player-2"])
    assert any("目击证词" in str(message.txt) for message in player_one_private)
    assert not any("目击证词" in str(message.txt) for message in player_two_private)
    assert any("卧底家庭线索" in str(message.txt) for message in player_two_private)

    public_messages = environment.trace.room_messages(result.session_id, session["script_murder_public_room_id"])
    assert sum(message.name in PLAYERS and "依据自己掌握的信息发言" in str(message.txt) for message in public_messages) == 10
    assert not any('"action": "submit_resolution"' in str(message.txt) for message in public_messages)
    assert environment._active is not None
    for context in environment._active.contexts.values():
        assert_tool_calls_are_paired(context.history())

    resumed = ScriptMurderEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=ScriptMurderLLM(), model="test",
    )
    resumed_result = SessionRuntime(trace=resumed.session.trace).run(resumed, task=Task("继续"), session_id=result.session_id)
    assert resumed_result.status == "completed"
    assert resumed.state.is_terminal
    assert resumed.trace.session_data(result.session_id)["resume_count"] == 1
    assert resumed._active is not None
    for context in resumed._active.contexts.values():
        assert_tool_calls_are_paired(context.history())
