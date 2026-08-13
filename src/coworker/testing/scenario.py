from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generic, TypeVar

from .scripted_llm import ScriptedLLMClient, ScriptedRequest, ScriptedTurn


ResultT = TypeVar("ResultT")
ScenarioExecution = Callable[[ScriptedLLMClient, Path], ResultT]
ScenarioVerification = Callable[[ResultT, ScriptedLLMClient, Path], None]


@dataclass(frozen=True, slots=True)
class ScenarioResult(Generic[ResultT]):
    name: str
    value: ResultT
    requests: tuple[ScriptedRequest, ...]

    @property
    def turn_count(self) -> int:
        return len(self.requests)


class ScenarioRunner:
    """Run an App-owned scenario against real infrastructure with one fake boundary."""

    @staticmethod
    def run(
        *,
        name: str,
        turns: Sequence[ScriptedTurn],
        execute: ScenarioExecution[ResultT],
        verify: ScenarioVerification[ResultT] | None = None,
        workspace: Path | None = None,
    ) -> ScenarioResult[ResultT]:
        if workspace is not None:
            workspace.mkdir(parents=True, exist_ok=True)
            return ScenarioRunner._run(name, turns, execute, verify, workspace)
        with TemporaryDirectory(prefix="coworker_scenario_") as temp_dir:
            return ScenarioRunner._run(name, turns, execute, verify, Path(temp_dir))

    @staticmethod
    def _run(
        name: str,
        turns: Sequence[ScriptedTurn],
        execute: ScenarioExecution[ResultT],
        verify: ScenarioVerification[ResultT] | None,
        workspace: Path,
    ) -> ScenarioResult[ResultT]:
        client = ScriptedLLMClient(turns)
        value = execute(client, workspace)
        client.assert_complete()
        if verify is not None:
            verify(value, client, workspace)
        return ScenarioResult(name=name, value=value, requests=client.requests)

