from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from coworker.apps.texas_holdem.environment import TexasHoldemEnvironment, TexasHoldemWorkflowConfig
from coworker.apps.texas_holdem.state import PLAYERS, PokerPhase, TexasHoldemState
from coworker.core.models import Message, ModelResult, Task, ToolCall
from coworker.infra.client import LLMClient
from coworker.infra.runtimes import SessionRuntime
from coworker.infra.session import SessionManager
from tool_message_assertions import assert_tool_calls_are_paired


class CallingPokerLLM(LLMClient):
    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        assert_tool_calls_are_paired(messages)
        state_message = next(message for message in reversed(messages) if message.role == "user" and '"type": "texas_holdem.state"' in str(message.content))
        state = json.loads(state_message.content)
        name = "call" if state["amount_to_call"] > 0 else "check"
        call_id = f"{state['phase']}-{state['player_name']}-{state['street_bets'][state['player_name']]}"
        return ModelResult(raw_content="", tool_calls=(ToolCall(call_id, name, {}),), model=model)


def test_complete_hand_is_deterministic_private_and_resumable(tmp_path: Path) -> None:
    environment = TexasHoldemEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=CallingPokerLLM(), model="test",
    )
    result = SessionRuntime(trace=environment.session.trace).run(
        environment, task=Task("完成一局德州扑克"), config=TexasHoldemWorkflowConfig(seed=23),
    )

    assert result.status == "completed", result.error
    state_path = tmp_path / "state" / "data" / result.session_id / "texas_holdem.json"
    state = TexasHoldemState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
    assert state.phase is PokerPhase.FINISHED
    assert len(state.community_cards) == 5
    assert sum(state.stacks.values()) == 400
    assert state.seed == 23

    metadata = environment.session.trace.session_data(result.session_id)
    public_messages = environment.session.trace.room_messages(result.session_id, metadata["poker_public_room_id"])
    public_text = "\n".join(str(message.txt) for message in public_messages)
    for player in PLAYERS:
        private_messages = environment.session.trace.room_messages(result.session_id, metadata["poker_private_room_ids"][player])
        cards = " ".join(state.hole_cards[player])
        assert any(cards in str(message.txt) for message in private_messages)
        if player in state.folded or len(state.active_players()) == 1:
            assert cards not in public_text
        else:
            assert cards in public_text
    assert state.ending_report in public_text
    assert "累计投入" in public_text
    assert "派奖" in public_text
    assert environment._active is not None
    for context in environment._active.contexts.values():
        assert_tool_calls_are_paired(context.history())

    resumed = TexasHoldemEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=CallingPokerLLM(), model="test",
    )
    resumed_result = SessionRuntime(trace=resumed.session.trace).run(resumed, task=Task("继续"), session_id=result.session_id)
    assert resumed_result.status == "completed"
    assert resumed.state.is_terminal
    assert resumed.state.deck == state.deck
