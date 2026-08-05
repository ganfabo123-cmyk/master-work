from pathlib import Path

from codeharness.llm import DemoLLMClient
from codeharness.models import AgentSpec, Task
from codeharness.runtime import AgentRuntime
from codeharness.tools import registry


def test_demo_runtime_writes_trace(tmp_path: Path) -> None:
    result = AgentRuntime(DemoLLMClient(), traces_root=tmp_path).run(
        agent=AgentSpec("test-agent", "demo", "Follow the task."),
        task=Task("Inspect this task."),
    )
    assert result.status == "completed"
    assert "Task received" in result.content
    assert (tmp_path / result.session_id / "test-agent.jsonl").exists()
    assert any(schema["name"] == "inspect_task" for schema in registry.schemas())
