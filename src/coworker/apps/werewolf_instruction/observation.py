"""Per-participant Observation for instruction discussion."""

from __future__ import annotations

import json

from ...core.base_observation import Observation
from ...core.models import Message
from ...infra.room import Room
from .state import PARTICIPANTS, WerewolfInstructionState


class WerewolfInstructionObservation(Observation):
    def __init__(self, *, state_message: Message, available_tool_names: tuple[str, ...], room: Room, task_id: str, session_id: str) -> None:
        super().__init__("werewolf-instruction-observation", task_id, session_id)
        self.state_message = state_message
        self.available_tool_names = available_tool_names
        self.room = room


def build_state_message(state: WerewolfInstructionState, agent_name: str) -> Message:
    return Message(
        "user",
        json.dumps(
            {
                "type": "werewolf_instruction_state",
                "discussion_round": state.discussion_round,
                "participant": agent_name,
                "participants": PARTICIPANTS,
                "submitted": [name for name in PARTICIPANTS if name in state.instructions],
                "self_submitted": agent_name in state.instructions,
            },
            ensure_ascii=False,
        ),
    )
