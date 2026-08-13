from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Self

from ...core.base_state import State


class GamePhase(StrEnum):
    INTRO = "intro"
    PERSON_SEARCH = "person_search"
    PERSON_DISCUSS = "person_discuss"
    SCENE_SEARCH = "scene_search"
    SCENE_DISCUSS = "scene_discuss"
    VOTE = "vote"
    REVEAL = "reveal"
    SCORE = "score"
    FINISHED = "finished"


ROLE_ORDER = ("pan", "ivan", "li", "maid", "butler", "he")


@dataclass
class HaishanXianguanState(State):
    phase: GamePhase = GamePhase.INTRO
    role_order: tuple[str, ...] = ROLE_ORDER
    script_refs: dict[str, str] = field(default_factory=dict)
    person_clue_assignments: dict[str, tuple[str, ...]] = field(default_factory=dict)
    scene_clue_assignments: dict[str, tuple[str, ...]] = field(default_factory=dict)
    handled_clues: dict[str, set[str]] = field(default_factory=dict)
    revealed_clues: set[str] = field(default_factory=set)
    introductions: dict[str, str] = field(default_factory=dict)
    discussion_rounds: dict[str, dict[str, str]] = field(default_factory=dict)
    votes: dict[str, dict[str, object]] = field(default_factory=dict)
    vote_tally: dict[str, int] = field(default_factory=dict)
    collective_result: dict[str, object] | None = None
    truth_revealed: bool = False
    scores: dict[str, dict[str, object]] = field(default_factory=dict)
    winner_ids: tuple[str, ...] = ()
    consumed_action_ids: set[str] = field(default_factory=set)
    emitted_event_ids: set[str] = field(default_factory=set)
    terminal_result: dict[str, object] | None = None

    @classmethod
    def initial(cls, task_id: str, session_id: str) -> Self:
        person_ids = tuple(f"person-{index:02d}" for index in range(1, 13))
        scene_ids = tuple(f"scene-{index:02d}" for index in range(1, 15))
        person = {
            role: person_ids[index * 2 : index * 2 + 2]
            for index, role in enumerate(ROLE_ORDER)
        }
        scene_counts = (3, 3, 2, 2, 2, 2)
        scene: dict[str, tuple[str, ...]] = {}
        offset = 0
        for role, count in zip(ROLE_ORDER, scene_counts, strict=True):
            scene[role] = scene_ids[offset : offset + count]
            offset += count
        return cls(
            task_id=task_id,
            session_id=session_id,
            script_refs={role: f"script:{role}" for role in ROLE_ORDER},
            person_clue_assignments=person,
            scene_clue_assignments=scene,
            handled_clues={role: set() for role in ROLE_ORDER},
            discussion_rounds={
                GamePhase.PERSON_DISCUSS.value: {},
                GamePhase.SCENE_DISCUSS.value: {},
            },
        )

    @property
    def is_terminal(self) -> bool:
        return self.phase is GamePhase.FINISHED and self.terminal_result is not None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["phase"] = self.phase.value
        for key in ("revealed_clues", "consumed_action_ids", "emitted_event_ids"):
            data[key] = sorted(data[key])
        data["handled_clues"] = {
            role: sorted(values) for role, values in self.handled_clues.items()
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        values = dict(data)
        values["phase"] = GamePhase(str(values["phase"]))
        values["role_order"] = tuple(values.get("role_order", ROLE_ORDER))
        for key in ("revealed_clues", "consumed_action_ids", "emitted_event_ids"):
            values[key] = set(values.get(key, []))
        values["handled_clues"] = {
            str(role): set(items)
            for role, items in dict(values.get("handled_clues", {})).items()
        }
        values["person_clue_assignments"] = {
            str(role): tuple(items)
            for role, items in dict(values.get("person_clue_assignments", {})).items()
        }
        values["scene_clue_assignments"] = {
            str(role): tuple(items)
            for role, items in dict(values.get("scene_clue_assignments", {})).items()
        }
        values["winner_ids"] = tuple(values.get("winner_ids", ()))
        return cls(**values)
