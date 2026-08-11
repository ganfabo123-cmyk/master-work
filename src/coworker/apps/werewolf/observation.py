"""Werewolf observation implementation."""

from __future__ import annotations

import json

from ...core.base_observation import Observation
from ...core.models import Message
from ...infra.room import Room


class WerewolfObservation(Observation):
    """Build system signals used by the Werewolf runtime."""

    def __init__(self, observation_id: str = "werewolf-observation", task_id: str = "", session_id: str = "") -> None:
        super().__init__(observation_id, task_id, session_id)

    def game_state_message(self, state: object, available_tool_names: tuple[str, ...]) -> Message:
        return Message("user", json.dumps({"type": "game_state", "round_no": state.round_no, "phase": state.phase.value, "alive_players": state.alive_players(), "available_actions": available_tool_names}, ensure_ascii=False))


class WerewolfTurnObservation(Observation):
    """All information exposed to one player for one RL decision."""

    def __init__(
        self,
        *,
        state_message: Message,
        available_tool_names: tuple[str, ...],
        public_room: Room,
        additional_rooms: tuple[Room, ...],
        task_id: str,
        session_id: str,
    ) -> None:
        super().__init__("werewolf-turn-observation", task_id, session_id)
        self.state_message = state_message
        self.available_tool_names = available_tool_names
        self.public_room = public_room
        self.additional_rooms = additional_rooms
