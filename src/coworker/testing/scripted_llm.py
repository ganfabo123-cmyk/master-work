from __future__ import annotations

from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from threading import Lock
from typing import Any

from ..core.models import Message, ModelResult


@dataclass(frozen=True, slots=True)
class ScriptedRequest:
    """Immutable evidence captured for one scripted model invocation."""

    model: str
    messages: tuple[Message, ...]
    tools: tuple[dict[str, Any], ...]
    options: dict[str, Any]

    @property
    def tool_names(self) -> tuple[str, ...]:
        names: list[str] = []
        for schema in self.tools:
            function = schema.get("function")
            name = schema.get("name")
            if name is None and isinstance(function, dict):
                name = function.get("name")
            if name is not None:
                names.append(str(name))
        return tuple(names)


RequestAssertion = Callable[[ScriptedRequest], None]


@dataclass(frozen=True, slots=True)
class ScriptedTurn:
    """One fixed model response and the generic expectations preceding it."""

    name: str
    response: ModelResult
    expected_model: str | None = None
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    assert_request: RequestAssertion | None = None


class ScriptedLLMError(AssertionError):
    """Raised when runtime behavior diverges from the supplied script."""


class ScriptedLLMClient:
    """Replay fixed model responses while auditing real runtime requests."""

    def __init__(self, turns: Sequence[ScriptedTurn]) -> None:
        self._turns = tuple(turns)
        self._requests: list[ScriptedRequest] = []
        self._lock = Lock()

    @property
    def requests(self) -> tuple[ScriptedRequest, ...]:
        with self._lock:
            return tuple(self._requests)

    @property
    def consumed(self) -> int:
        with self._lock:
            return len(self._requests)

    @property
    def remaining(self) -> int:
        return len(self._turns) - self.consumed

    def generate(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        tools: list[dict],
        **kwargs: Any,
    ) -> ModelResult:
        request = ScriptedRequest(
            model=model,
            messages=tuple(deepcopy(tuple(messages))),
            tools=tuple(deepcopy(tools)),
            options=deepcopy(kwargs),
        )
        with self._lock:
            index = len(self._requests)
            if index >= len(self._turns):
                raise ScriptedLLMError(
                    f"unexpected model call #{index + 1}; the script has only {len(self._turns)} turns"
                )
            turn = self._turns[index]
            self._requests.append(request)

        self._validate(turn, request, index)
        return turn.response

    def assert_complete(self) -> None:
        remaining = self.remaining
        if remaining:
            next_turn = self._turns[self.consumed]
            raise ScriptedLLMError(
                f"script stopped with {remaining} unconsumed turn(s); next turn is {next_turn.name!r}"
            )

    @staticmethod
    def _validate(turn: ScriptedTurn, request: ScriptedRequest, index: int) -> None:
        label = f"scripted turn #{index + 1} ({turn.name})"
        if turn.expected_model is not None and request.model != turn.expected_model:
            raise ScriptedLLMError(
                f"{label} expected model {turn.expected_model!r}, got {request.model!r}"
            )
        available = set(request.tool_names)
        missing = set(turn.required_tools) - available
        if missing:
            raise ScriptedLLMError(f"{label} is missing required tools: {sorted(missing)}")
        forbidden = set(turn.forbidden_tools) & available
        if forbidden:
            raise ScriptedLLMError(f"{label} exposed forbidden tools: {sorted(forbidden)}")
        if turn.assert_request is not None:
            try:
                turn.assert_request(request)
            except ScriptedLLMError:
                raise
            except AssertionError as error:
                raise ScriptedLLMError(f"{label} request assertion failed: {error}") from error

