"""Replayable deterministic random operations for App-owned resources."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import TypeVar


ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True)
class DeterministicRandomSource:
    seed: int

    def shuffled(self, items: tuple[ItemT, ...]) -> tuple[ItemT, ...]:
        """Return the same permutation for the same seed and input sequence."""
        values = list(items)
        Random(self.seed).shuffle(values)
        return tuple(values)
