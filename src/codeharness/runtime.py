from __future__ import annotations

from pathlib import Path

from .context import ContextBuilder
from .llm import LLMClient
from .models import AgentResult, AgentSpec, AgentState, Message, Task
from .prompts import build_task_prompt
from .tools import ToolError, ToolRegistry, registry
from .trace import TraceRecorder


class AgentRuntime:
    """The only execution loop; domain code supplies agent, task, tools and client."""

    def __init__(self, llm: LLMClient, *, tools: ToolRegistry = registry, traces_root: Path = Path("traces"), max_turns: int = 8) -> None:
        self.llm, self.tools, self.trace = llm, tools, TraceRecorder(traces_root)
        self.context, self.max_turns = ContextBuilder(), max_turns

    def run(self, *, agent: AgentSpec, task: Task) -> AgentResult:
        state, session_id = AgentState(task), self.trace.create_session(task.description, agent.name)
        self.trace.record(session_id, agent.name, "system_prompt", raw_content=agent.system_prompt)
        self.trace.record(session_id, agent.name, "user_prompt", raw_content=task.description)
        try:
            while state.turn_count < self.max_turns:
                messages = self.context.build(prompt=build_task_prompt(task, agent.system_prompt), state=state, skill_content=self._load_skill(agent.skill_path))
                model_result = self.llm.generate(model=agent.model, messages=messages, tools=self.tools.schemas())
                self.trace.record(session_id, agent.name, "model_response", messages=[m.as_dict() for m in messages], result=model_result)
                state.turn_count += 1
                if model_result.parse_error:
                    state.messages.append(Message("user", f"Model parse error: {model_result.parse_error}"))
                    continue
                if model_result.tool_calls:
                    for call in model_result.tool_calls:
                        self.trace.record(session_id, agent.name, "tool_call", tool_call=call)
                        try:
                            value = self.tools.invoke(call.name, call.arguments)
                            state.messages.append(Message("tool", value, name=call.name, tool_call_id=call.id))
                            self.trace.record(session_id, agent.name, "tool_result", tool_call_id=call.id, tool_name=call.name, success=True, result=value)
                        except ToolError as error:
                            state.messages.append(Message("tool", str(error), name=call.name, tool_call_id=call.id))
                            self.trace.record(session_id, agent.name, "tool_result", tool_call_id=call.id, tool_name=call.name, success=False, result=str(error))
                    continue
                state.status, state.final_result = "completed", model_result.parsed_content
                self.trace.finish_session(session_id, state.status)
                return AgentResult("completed", state.final_result, None, session_id)
            raise RuntimeError(f"maximum turns exceeded ({self.max_turns})")
        except Exception as error:
            self.trace.record(session_id, agent.name, "error", error_type=type(error).__name__, error_message=str(error))
            self.trace.finish_session(session_id, "failed", str(error))
            return AgentResult("failed", None, str(error), session_id)

    @staticmethod
    def _load_skill(path: str | None) -> str | None:
        return Path(path).read_text(encoding="utf-8") if path else None
