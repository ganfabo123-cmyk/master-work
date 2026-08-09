"""File-backed Agent registration for one ROOM session."""

from __future__ import annotations

from pathlib import Path
import re
from time import sleep
from uuid import uuid4

from .models import AgentProfile


class RoomAgentRegistry:
    """Persist session-scoped Agent profiles under ``{session}/agents``."""

    def __init__(self, data_root: Path, session_id: str) -> None:
        self.data_root = data_root / _safe_identifier(session_id, "session_id") / "agents"
        self.session_id = _safe_identifier(session_id, "session_id")
        self.data_root.mkdir(parents=True, exist_ok=True)

    def save(self, profile: AgentProfile) -> None:
        path = self._profile_path(profile.name)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
            _replace_with_retry(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def load(self, name: str) -> AgentProfile:
        path = self._profile_path(name)
        if not path.exists():
            raise KeyError(f"Agent is not registered in session '{self.session_id}': {name}")
        return AgentProfile.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> tuple[AgentProfile, ...]:
        return tuple(
            AgentProfile.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.data_root.glob("*.json"))
        )

    def _profile_path(self, name: str) -> Path:
        return self.data_root / f"{_safe_identifier(name, 'agent name')}.json"


def _safe_identifier(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", normalized):
        raise ValueError(f"{label} must contain only letters, numbers, dot, underscore, or hyphen")
    return normalized


def _replace_with_retry(temporary: Path, destination: Path, *, attempts: int = 8) -> None:
    for attempt in range(attempts):
        try:
            temporary.replace(destination)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            sleep(0.025)
