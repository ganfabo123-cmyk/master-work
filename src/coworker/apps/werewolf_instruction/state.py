"""State for the eight-player werewolf instruction discussion."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ...core.base_state import State

PARTICIPANTS = tuple(f"player-{index}" for index in range(1, 9))


class InstructionPhase(StrEnum):
    DISCUSSION = "discussion"
    FINISHED = "finished"


@dataclass
class WerewolfInstructionState(State):
    phase: InstructionPhase = InstructionPhase.DISCUSSION
    discussion_round: int = 1
    spoken: set[str] = field(default_factory=set)
    instructions: dict[str, str] = field(default_factory=dict)
    consumed_action_ids: set[str] = field(default_factory=set)
    tutorial: str = ""

    @classmethod
    def initial(cls, task_id: str, session_id: str) -> "WerewolfInstructionState":
        return cls(task_id=task_id, session_id=session_id)

    @property
    def is_terminal(self) -> bool:
        return self.phase is InstructionPhase.FINISHED

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "phase": self.phase.value,
            "discussion_round": self.discussion_round,
            "spoken": sorted(self.spoken),
            "instructions": dict(self.instructions),
            "consumed_action_ids": sorted(self.consumed_action_ids),
            "tutorial": self.tutorial,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "WerewolfInstructionState":
        return cls(
            task_id=str(data["task_id"]),
            session_id=str(data["session_id"]),
            phase=InstructionPhase(str(data.get("phase", InstructionPhase.DISCUSSION.value))),
            discussion_round=int(data.get("discussion_round", 1)),
            spoken={str(item) for item in data.get("spoken", [])},
            instructions={str(name): str(content) for name, content in dict(data.get("instructions") or {}).items()},
            consumed_action_ids={str(item) for item in data.get("consumed_action_ids", [])},
            tutorial=str(data.get("tutorial", "")),
        )
