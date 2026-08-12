"""Player-specific poker Observation projection."""

from __future__ import annotations

import json

from ...core.base_observation import Observation
from ...core.models import Message
from ...infra.room import Room
from .state import TexasHoldemState


class PokerObservation(Observation):
    def __init__(self, *, state_message: Message, available_tool_names: tuple[str, ...], room: Room, task_id: str, session_id: str) -> None:
        super().__init__(f"poker:{session_id}", task_id, session_id)
        self.state_message = state_message
        self.available_tool_names = available_tool_names
        self.room = room


def build_state_message(state: TexasHoldemState, player: str, available: tuple[str, ...]) -> Message:
    payload = {
        "type": "texas_holdem.state", "phase": state.phase.value, "player_name": player,
        "hole_cards": list(state.hole_cards[player]), "community_cards": list(state.community_cards),
        "pot": state.pot, "stacks": state.stacks, "street_bets": state.street_bets,
        "current_bet": state.current_bet, "amount_to_call": max(0, state.current_bet - state.street_bets[player]),
        "folded": sorted(state.folded), "all_in": sorted(state.all_in),
        "available_actions": list(available),
    }
    return Message("user", json.dumps(payload, ensure_ascii=False, sort_keys=True))
