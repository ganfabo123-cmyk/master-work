from __future__ import annotations

import json
from pathlib import Path

from coworker.core.models import Message, ToolCall
from coworker.infra.trace import TraceRecorder


def test_markdown_expands_native_tool_arguments_without_changing_jsonl(tmp_path: Path) -> None:
    recorder = TraceRecorder(tmp_path)
    session_id = recorder.create_session("task", "agent")
    message = Message(
        "assistant",
        "",
        tool_calls=(ToolCall("call-1", "send", json.dumps({"content": "first line\nsecond line"}, ensure_ascii=False)),),
    )
    recorder.record(session_id, "agent", "assistant", message=message.as_dict())

    directory = tmp_path / session_id / "agents"
    raw_jsonl = (directory / "agent.jsonl").read_text(encoding="utf-8")
    markdown = (directory / "agent.md").read_text(encoding="utf-8")

    assert '\\"content\\"' in raw_jsonl
    assert '"arguments": {' in markdown
    assert '\\"content\\"' not in markdown
