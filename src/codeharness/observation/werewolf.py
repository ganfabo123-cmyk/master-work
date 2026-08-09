"""Werewolf observation implementation."""

from __future__ import annotations

from ..base_class.base_observation.llm_observation import LLMObservation
from ..models import Message
import json


class WerewolfObservation(LLMObservation):
    """Build system signals used by the Werewolf runtime."""

    def __init__(self, observation_id: str = "werewolf-observation", task_id: str = "", session_id: str = "") -> None:
        super().__init__(observation_id, task_id, session_id)

    def game_state_message(self, state: object, available_tool_names: tuple[str, ...]) -> Message:
        return Message("user", json.dumps({"type": "game_state", "round_no": state.round_no, "phase": state.phase.value, "alive_players": state.alive_players(), "available_actions": available_tool_names}, ensure_ascii=False))
