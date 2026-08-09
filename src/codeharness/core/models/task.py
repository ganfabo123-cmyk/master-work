from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Task:
    description: str
    inputs: dict[str, Any] = field(default_factory=dict)
