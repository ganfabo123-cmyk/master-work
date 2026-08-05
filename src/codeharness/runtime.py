from __future__ import annotations

from pathlib import Path

from .agents import Agent
from pydantic import BaseModel

from .models import AgentResult, Message, Task
from .trace import TraceRecorder


class AgentRuntime:
    """Schedules generic Agent.run calls and never calls an LLM directly."""

    def __init__(self, *, traces_root: Path = Path("traces"), max_turns: int = 8) -> None:
        self.trace = TraceRecorder(traces_root)
        self.max_turns = max_turns

    def run(self, *, agent: Agent, task: Task) -> AgentResult:
        session_id = self.start_session(agent=agent, task=task)
        try:
            output = self.run_turn(agent=agent, task=task, session_id=session_id)
            self.finish_session(session_id, "completed")
            return AgentResult("completed", output, None, session_id)
        except Exception as error:
            self.finish_session(session_id, "failed", str(error), agent_name=agent.name)
            return AgentResult("failed", None, str(error), session_id)

    def start_session(self, *, agent: Agent, task: Task) -> str:
        return self.trace.create_session(task.description, agent.name)

    def run_turn(
        self,
        *,
        agent: Agent,
        task: Task,
        session_id: str,
        messages: tuple[Message, ...] | list[Message] | None = None,
        record_initial_messages: bool = True,
    ) -> BaseModel:
        return agent.run(
            task,
            messages=messages,
            max_turns=self.max_turns,
            trace=self.trace,
            session_id=session_id,
            record_initial_messages=record_initial_messages,
        )

    def finish_session(self, session_id: str, status: str, error: str | None = None, *, agent_name: str | None = None) -> None:
        if error is not None and agent_name is not None:
            self.trace.record(session_id, agent_name, "error", error_type="RuntimeError", error_message=error)
        self.trace.finish_session(session_id, status, error)
