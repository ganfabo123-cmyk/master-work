"""Synchronous lifecycle runtime for session-backed Environments."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...core.models import AgentResult, Task
from ...core.session import SessionContext, SessionEnvironment
from ..trace import TraceRecorder


class SessionRuntime:
    """Open, resume, execute, and close one Environment session."""

    def __init__(self, *, trace: TraceRecorder) -> None:
        self.trace = trace

    def run(
        self,
        environment: SessionEnvironment,
        *,
        task: Task,
        session_id: str | None = None,
        on_session_opened: Callable[[str], None] | None = None,
        **environment_options: Any,
    ) -> AgentResult:
        active_session_id = session_id
        lifecycle_opened = False
        try:
            resumed = active_session_id is not None
            if resumed:
                self._resume(environment, active_session_id)
            else:
                active_session_id = self.trace.create_session(
                    task.description,
                    environment.entry_agent,
                    mode=environment.session_mode,
                )
            lifecycle_opened = True

            if on_session_opened is not None:
                on_session_opened(active_session_id)

            result = environment.run_session(
                task=task,
                context=SessionContext(active_session_id, resumed),
                **environment_options,
            )
            if result.session_id != active_session_id:
                raise ValueError(
                    "Environment returned a different session_id: "
                    f"{result.session_id!r} != {active_session_id!r}"
                )
            self.trace.finish_session(active_session_id, result.status, result.error)
            return result
        except Exception as error:
            if lifecycle_opened and active_session_id is not None:
                self.trace.finish_session(active_session_id, "failed", str(error))
            return AgentResult("failed", None, str(error), active_session_id or "")

    def _resume(self, environment: SessionEnvironment, session_id: str) -> None:
        metadata = self.trace.session_data(session_id)
        if metadata.get("mode") != environment.session_mode:
            raise ValueError(
                f"Session mode does not match Environment: {metadata.get('mode')!r} != {environment.session_mode!r}"
            )
        if metadata.get("entry_agent") != environment.entry_agent:
            raise ValueError(
                "Session entry_agent does not match Environment: "
                f"{metadata.get('entry_agent')!r} != {environment.entry_agent!r}"
            )
        self.trace.resume_session_state(session_id)
