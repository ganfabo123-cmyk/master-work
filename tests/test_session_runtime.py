from __future__ import annotations

import json
from pathlib import Path

from coworker.core import SessionContext
from coworker.core.models import AgentResult, Message, Task
from coworker.infra.runtimes import SessionRuntime
from coworker.infra.trace import TraceRecorder


class StubEnvironment:
    session_mode = "stub-workflow"
    entry_agent = "stub-agent"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.contexts: list[SessionContext] = []

    def run_session(self, *, task: Task, context: SessionContext, **options: object) -> AgentResult:
        self.contexts.append(context)
        if self.fail:
            raise RuntimeError("stub failure")
        return AgentResult("completed", Message("assistant", task.description), None, context.session_id)


def _metadata(root: Path, session_id: str) -> dict:
    return json.loads((root / session_id / "session.json").read_text(encoding="utf-8"))


def test_session_runtime_owns_create_callback_and_finish(tmp_path: Path) -> None:
    trace = TraceRecorder(tmp_path / "traces")
    runtime = SessionRuntime(trace=trace)
    environment = StubEnvironment()
    opened: list[str] = []

    result = runtime.run(environment, task=Task("diagnose"), on_session_opened=opened.append)

    assert result.status == "completed"
    assert opened == [result.session_id]
    assert environment.contexts == [SessionContext(result.session_id, False)]
    metadata = _metadata(trace.root, result.session_id)
    assert metadata["status"] == "completed"
    assert metadata["mode"] == environment.session_mode
    assert metadata["entry_agent"] == environment.entry_agent


def test_session_runtime_resumes_before_environment_execution(tmp_path: Path) -> None:
    trace = TraceRecorder(tmp_path / "traces")
    session_id = trace.create_session("first", "stub-agent", mode="stub-workflow")
    trace.finish_session(session_id, "completed")
    environment = StubEnvironment()

    result = SessionRuntime(trace=trace).run(environment, task=Task("continue"), session_id=session_id)

    assert result.status == "completed"
    assert environment.contexts == [SessionContext(session_id, True)]
    assert _metadata(trace.root, session_id)["resume_count"] == 1


def test_session_runtime_records_environment_failure(tmp_path: Path) -> None:
    trace = TraceRecorder(tmp_path / "traces")
    result = SessionRuntime(trace=trace).run(StubEnvironment(fail=True), task=Task("fail"))

    assert result.status == "failed"
    assert result.error == "stub failure"
    assert _metadata(trace.root, result.session_id)["status"] == "failed"
