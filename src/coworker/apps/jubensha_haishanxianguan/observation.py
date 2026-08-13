from __future__ import annotations

import json

from ...core.base_observation import Observation
from ...core.models import Message
from ...infra.room import Room
from .action import HaishanActionManager
from .data_loader import HaishanMaterialLoader
from .state import GamePhase, HaishanXianguanState


class HaishanObservation(Observation):
    def __init__(
        self,
        *,
        observation_id: str,
        task_id: str,
        session_id: str,
        actor_id: str,
        state_message: Message,
        available_tool_names: tuple[str, ...],
        rooms: tuple[Room, ...],
    ) -> None:
        super().__init__(observation_id, task_id, session_id)
        self.actor_id = actor_id
        self.messages = (state_message,)
        self.available_tool_names = available_tool_names
        self.rooms = rooms


def build_visible_payload(
    state: HaishanXianguanState,
    actor_id: str,
    loader: HaishanMaterialLoader,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "actor_id": actor_id,
        "phase": state.phase.value,
        "role_order": list(state.role_order),
        "public_role_cards": loader.public_role_cards().content,
        "private_script": loader.role_script(actor_id).content,
        "introductions": dict(state.introductions),
        "public_discussion": {
            phase: dict(messages)
            for phase, messages in state.discussion_rounds.items()
        },
        "available_action": HaishanActionManager.PHASE_ACTION.get(state.phase),
    }
    person = loader.clues("person")
    scene = loader.clues("scene")
    if state.phase is GamePhase.INTRO:
        owned_ids: set[str] = set()
        allowed_ids: set[str] = set()
    elif state.phase in (GamePhase.PERSON_SEARCH, GamePhase.PERSON_DISCUSS):
        owned_ids = set(state.person_clue_assignments[actor_id])
        allowed_ids = set(person)
    else:
        owned_ids = set(state.person_clue_assignments[actor_id]) | set(
            state.scene_clue_assignments[actor_id]
        )
        allowed_ids = set(person) | set(scene)
    visible_ids = (owned_ids | state.revealed_clues) & allowed_ids
    records = person | scene
    payload["visible_clues"] = {
        clue_id: records[clue_id].content for clue_id in sorted(visible_ids)
    }
    payload["private_clue_ids"] = sorted(owned_ids - state.revealed_clues)
    if actor_id in state.votes:
        payload["own_vote"] = dict(state.votes[actor_id])
    if state.phase in (GamePhase.REVEAL, GamePhase.SCORE, GamePhase.FINISHED):
        payload["truth"] = loader.truth().content
    if state.phase is GamePhase.FINISHED:
        payload["terminal_result"] = state.terminal_result
    return payload


def state_message(payload: dict[str, object]) -> Message:
    return Message("user", json.dumps(payload, ensure_ascii=False, sort_keys=True))
