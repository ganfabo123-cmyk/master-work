"""Serializable domain state for the synchronous murder-mystery workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ...core.base_state import State


PLAYERS = tuple(f"player-{index}" for index in range(1, 6))


class ScriptMurderPhase(StrEnum):
    ROUND_1_DISCUSSION = "round_1_discussion"
    ROUND_2_DISCUSSION = "round_2_discussion"
    FINAL_SUBMISSION = "final_submission"
    RESOLUTION = "resolution"
    FINISHED = "finished"


@dataclass(frozen=True, slots=True)
class FinalSubmission:
    declarations: tuple[str, ...]
    decisive_action: str
    target: str | None
    leader_vote: str

    def to_dict(self) -> dict[str, object]:
        return {"declarations": list(self.declarations), "decisive_action": self.decisive_action, "target": self.target, "leader_vote": self.leader_vote}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FinalSubmission":
        return cls(tuple(str(item) for item in data.get("declarations", [])), str(data["decisive_action"]), None if data.get("target") is None else str(data["target"]), str(data["leader_vote"]))


@dataclass
class ScriptMurderState(State):
    case_id: str = ""
    phase: ScriptMurderPhase = ScriptMurderPhase.ROUND_1_DISCUSSION
    speaker_index: int = 0
    character_assignments: dict[str, str] = field(default_factory=dict)
    alive_character_ids: set[str] = field(default_factory=set)
    delivered_document_ids: set[str] = field(default_factory=set)
    final_submissions: dict[str, FinalSubmission] = field(default_factory=dict)
    consumed_action_ids: set[str] = field(default_factory=set)
    resolution: dict[str, object] = field(default_factory=dict)
    ending_report: str = ""

    @classmethod
    def initial(cls, task_id: str, session_id: str, *, case_id: str = "", assignments: dict[str, str] | None = None) -> "ScriptMurderState":
        mapped = dict(assignments or {})
        return cls(task_id=task_id, session_id=session_id, case_id=case_id, character_assignments=mapped, alive_character_ids=set(mapped.values()))

    @property
    def is_terminal(self) -> bool:
        return self.phase is ScriptMurderPhase.FINISHED

    def character_for(self, player_name: str) -> str:
        return self.character_assignments[player_name]

    def player_for(self, character_id: str) -> str:
        return next(player for player, assigned in self.character_assignments.items() if assigned == character_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id, "session_id": self.session_id, "case_id": self.case_id,
            "phase": self.phase.value, "speaker_index": self.speaker_index,
            "character_assignments": dict(self.character_assignments),
            "alive_character_ids": sorted(self.alive_character_ids),
            "delivered_document_ids": sorted(self.delivered_document_ids),
            "final_submissions": {key: value.to_dict() for key, value in self.final_submissions.items()},
            "consumed_action_ids": sorted(self.consumed_action_ids),
            "resolution": self.resolution, "ending_report": self.ending_report,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ScriptMurderState":
        return cls(
            task_id=str(data["task_id"]), session_id=str(data["session_id"]), case_id=str(data.get("case_id", "")),
            phase=ScriptMurderPhase(str(data.get("phase", ScriptMurderPhase.ROUND_1_DISCUSSION.value))),
            speaker_index=int(data.get("speaker_index", 0)),
            character_assignments={str(k): str(v) for k, v in dict(data.get("character_assignments") or {}).items()},
            alive_character_ids={str(item) for item in data.get("alive_character_ids", [])},
            delivered_document_ids={str(item) for item in data.get("delivered_document_ids", [])},
            final_submissions={str(k): FinalSubmission.from_dict(v) for k, v in dict(data.get("final_submissions") or {}).items()},
            consumed_action_ids={str(item) for item in data.get("consumed_action_ids", [])},
            resolution=dict(data.get("resolution") or {}), ending_report=str(data.get("ending_report", "")),
        )
