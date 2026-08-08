"""Werewolf observation implementation."""

from __future__ import annotations

from typing import Any

from ..core.base_observation import BaseObservation, SystemSignal


class WerewolfObservation(BaseObservation):
    """Build system signals used by the Werewolf runtime."""

    def system_signal(self, **kwargs: Any) -> SystemSignal:
        """Wrap a developer-defined Werewolf runtime signal payload."""
        return SystemSignal(**kwargs)
