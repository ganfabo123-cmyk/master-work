"""Authorized per-character observations for the murder-mystery workflow."""

from __future__ import annotations

import json

from ...core.base_observation import Observation
from ...core.models import Message
from ...infra.room import Room
from .state import ScriptMurderState


class ScriptMurderObservation(Observation):
    def __init__(self, *, state_message: Message, available_tool_names: tuple[str, ...], public_room: Room, private_room: Room, task_id: str, session_id: str) -> None:
        super().__init__("script-murder-observation", task_id, session_id)
        self.state_message = state_message
        self.available_tool_names = available_tool_names
        self.public_room = public_room
        self.private_room = private_room


def build_state_message(state: ScriptMurderState, player_name: str, available_actions: tuple[str, ...]) -> Message:
    payload = {
        "type": "script_murder.state",
        "case_id": state.case_id,
        "phase": state.phase.value,
        "player_name": player_name,
        "character_id": state.character_for(player_name),
        "alive_characters": sorted(state.alive_character_ids),
        "submitted": player_name in state.final_submissions,
        "available_actions": list(available_actions),
    }
    return Message("user", json.dumps(payload, ensure_ascii=False))
