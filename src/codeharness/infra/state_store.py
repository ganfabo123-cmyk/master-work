"""Small JSON-backed state store used by concrete environments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar


StateT = TypeVar("StateT")


class StateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str, kind: str) -> Path:
        return self.root / session_id / f"{kind}.json"

    def update(self, session_id: str, kind: str, state: Any) -> None:
        path = self._path(session_id, kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def restore(self, session_id: str, kind: str, state_type: type[StateT]) -> StateT:
        path = self._path(session_id, kind)
        if not path.exists():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return state_type.from_dict(payload)
