"""Agent-isolated persistence for reusable long-term experience memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class LongTermMemoryEntry:
    """One experience record using the collaboration-experience template."""

    experience_name: str
    happened_at: datetime
    thing_done: str
    outcome: Literal["成功", "失败"]
    feedback_basis: str
    approach: str
    reason_and_principle: str

    def __post_init__(self) -> None:
        for field_name in (
            "experience_name",
            "thing_done",
            "feedback_basis",
            "approach",
            "reason_and_principle",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be empty")

    def render(self) -> str:
        """Render exactly the initial long-term-memory experience template."""
        happened_at = self.happened_at.strftime("%Y-%m-%d %H:%M")
        return (
            f"经验名称：{self.experience_name}\n\n"
            f"在 {happened_at}，我做了 {self.thing_done}。\n"
            f"反馈为 {self.outcome}（根据 {self.feedback_basis}）。\n\n"
            "当时我的做法是：\n"
            f"{self.approach}\n\n"
            "我需要深刻思考一下这次成功/失败背后的原因：\n"
            "为什么我成功/失败，我认为原因是：\n"
            f"{self.reason_and_principle}"
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "experience_name": self.experience_name,
            "happened_at": self.happened_at.isoformat(),
            "thing_done": self.thing_done,
            "outcome": self.outcome,
            "feedback_basis": self.feedback_basis,
            "approach": self.approach,
            "reason_and_principle": self.reason_and_principle,
        }

    @classmethod
    def from_dict(cls, data: object) -> "LongTermMemoryEntry":
        if not isinstance(data, dict):
            raise ValueError("memory entry must be an object")
        try:
            outcome = data["outcome"]
            if outcome not in {"成功", "失败"}:
                raise ValueError("outcome must be 成功 or 失败")
            return cls(
                experience_name=str(data["experience_name"]),
                happened_at=datetime.fromisoformat(str(data["happened_at"])),
                thing_done=str(data["thing_done"]),
                outcome=outcome,
                feedback_basis=str(data["feedback_basis"]),
                approach=str(data["approach"]),
                reason_and_principle=str(data["reason_and_principle"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid long-term memory entry") from error


class AgentLongTermMemory:
    """The persistence API for one already-bound Agent namespace."""

    def __init__(self, data_root: Path, agent_name: str) -> None:
        if not agent_name.strip():
            raise ValueError("agent_name cannot be empty")
        self.data_root = data_root
        self.agent_name = agent_name

    @property
    def path(self) -> Path:
        return self.data_root / f"{quote(self.agent_name, safe='._-')}.json"

    def ensure(self) -> Path:
        """Create the Agent's empty memory file if it does not yet exist."""
        if not self.path.exists():
            self._save(())
        return self.path

    def list(self) -> tuple[LongTermMemoryEntry, ...]:
        return self._load()

    def get(self, experience_name: str) -> LongTermMemoryEntry | None:
        return next((entry for entry in self._load() if entry.experience_name == experience_name), None)

    def add(self, entry: LongTermMemoryEntry) -> None:
        entries = self._load()
        if any(item.experience_name == entry.experience_name for item in entries):
            raise ValueError(f"duplicate experience_name for Agent '{self.agent_name}': {entry.experience_name}")
        self._save((*entries, entry))

    def _load(self) -> tuple[LongTermMemoryEntry, ...]:
        if not self.path.exists():
            return ()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid long-term memory file: {self.path}") from error
        if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("agent_name") != self.agent_name:
            raise ValueError(f"invalid long-term memory file: {self.path}")
        entries = data.get("entries")
        if not isinstance(entries, list):
            raise ValueError(f"invalid long-term memory entries: {self.path}")
        return tuple(LongTermMemoryEntry.from_dict(entry) for entry in entries)

    def _save(self, entries: tuple[LongTermMemoryEntry, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": 1,
            "agent_name": self.agent_name,
            "entries": [entry.as_dict() for entry in entries],
        }
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()


class LongTermMemoryManager:
    """Create Agent-owned memory APIs below one configurable persistence root."""

    def __init__(self, data_root: Path = Path("memory/data")) -> None:
        self.data_root = data_root

    def for_agent(self, agent_name: str) -> AgentLongTermMemory:
        memory = AgentLongTermMemory(self.data_root, agent_name)
        memory.ensure()
        return memory
