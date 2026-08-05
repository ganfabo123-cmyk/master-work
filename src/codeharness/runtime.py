from __future__ import annotations

from pathlib import Path

from .agents import Agent
from .models import AgentResult, Task
from .trace import TraceRecorder


class AgentRuntime:
    """Schedules generic Agent.run calls and never calls an LLM directly."""

    def __init__(self, *, traces_root: Path = Path("traces"), max_turns: int = 8) -> None:
        self.trace = TraceRecorder(traces_root)
        self.max_turns = max_turns

    def run(self, *, agent: Agent, task: Task) -> AgentResult:
        session_id = self.trace.create_session(task.description, agent.name)
        try:
            output = agent.run(task, max_turns=self.max_turns, trace=self.trace, session_id=session_id)
            self.trace.finish_session(session_id, "completed")
            return AgentResult("completed", output, None, session_id)
        except Exception as error:
            self.trace.record(session_id, agent.name, "error", error_type=type(error).__name__, error_message=str(error))
            self.trace.finish_session(session_id, "failed", str(error))
            return AgentResult("failed", None, str(error), session_id)
