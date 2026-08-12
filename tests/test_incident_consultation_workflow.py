from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from coworker.apps.incident_consultation.environment import IncidentConsultationEnvironment, IncidentWorkflowConfig
from coworker.apps.incident_consultation.state import IncidentState
from coworker.core.models import Message, ModelResult, Task, ToolCall
from coworker.infra.client import LLMClient
from coworker.infra.runtimes import SessionRuntime
from coworker.infra.session import SessionManager

from test_incident_case_loader import write_case
from tool_message_assertions import assert_tool_calls_are_paired


class ConsultationLLM(LLMClient):
    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        assert_tool_calls_are_paired(messages)
        if messages[-1].role == "tool":
            return ModelResult(raw_content="submitted", parsed_content="submitted", model=model)
        state_message = next(message for message in reversed(messages) if message.role == "user" and '"type": "incident_consultation_state"' in str(message.content))
        state = json.loads(state_message.content)
        if state["role"] == "lead":
            evidence_ids = [item for finding in state["findings"] for item in finding["evidence_ids"]]
            return self._call("submit_final_diagnosis", {"component": "checkoutservice", "root_cause": "多源证据共同指向 checkoutservice 附近异常；数据集未提供官方真值。", "evidence_ids": evidence_ids, "confidence": 75}, model)
        evidence = state["evidence"][0]
        return self._call("submit_finding", {"component": "checkoutservice", "summary": evidence["summary"], "evidence_ids": [evidence["evidence_id"]], "confidence": 70}, model)

    @staticmethod
    def _call(name: str, arguments: dict[str, object], model: str) -> ModelResult:
        return ModelResult(raw_content="", tool_calls=(ToolCall(f"{name}-call", name, arguments),), model=model)


class InterruptBeforeLeadLLM(ConsultationLLM):
    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **kwargs: Any) -> ModelResult:
        state_message = next(
            message
            for message in reversed(messages)
            if message.role == "user" and '"type": "incident_consultation_state"' in str(message.content)
        )
        if json.loads(state_message.content)["role"] == "lead":
            raise RuntimeError("intentional interruption before final diagnosis")
        return super().generate(model=model, messages=messages, tools=tools, **kwargs)


def test_complete_incident_consultation_uses_room_state_store_and_trace(tmp_path: Path) -> None:
    case_root = write_case(tmp_path / "case")
    environment = IncidentConsultationEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=ConsultationLLM(),
        model="test",
    )

    result = SessionRuntime(trace=environment.session.trace).run(
        environment,
        task=Task("分析这个软件故障案例"),
        config=IncidentWorkflowConfig(case_root=case_root),
    )

    assert result.status == "completed", result.error
    state_path = tmp_path / "state" / "data" / result.session_id / "incident_consultation.json"
    state = IncidentState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
    assert state.is_terminal
    assert set(state.findings) == {"metrics-expert", "logs-expert", "traces-expert"}
    assert state.final_diagnosis is not None
    assert state.final_diagnosis.component == "checkoutservice"
    session = environment.trace.session_data(result.session_id)
    assert session["mode"] == "incident-consultation"
    room_id = session["incident_room_id"]
    room_messages = environment.trace.room_messages(result.session_id, room_id)
    for finding in state.findings.values():
        assert any(message.name == finding.expert and finding.summary in str(message.txt) and finding.component in str(message.txt) for message in room_messages)
    assert any(message.name == "lead-expert" and state.final_diagnosis.root_cause in str(message.txt) for message in room_messages)
    assert environment._active is not None
    for context in environment._active.contexts.values():
        assert_tool_calls_are_paired(context.history())

    resumed = IncidentConsultationEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=ConsultationLLM(),
        model="test",
    )
    resumed_result = SessionRuntime(trace=resumed.session.trace).run(
        resumed,
        task=Task("继续分析"),
        session_id=result.session_id,
    )
    assert resumed_result.status == "completed"
    assert resumed.state.is_terminal
    assert resumed.trace.session_data(result.session_id)["resume_count"] == 1
    assert resumed._active is not None
    for context in resumed._active.contexts.values():
        assert_tool_calls_are_paired(context.history())


def test_incident_consultation_resumes_from_final_diagnosis_boundary(tmp_path: Path) -> None:
    case_root = write_case(tmp_path / "case")
    session = SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room")
    interrupted = IncidentConsultationEnvironment(session, llm=InterruptBeforeLeadLLM(), model="test")

    failed = SessionRuntime(trace=session.trace).run(
        interrupted,
        task=Task("分析这个软件故障案例"),
        config=IncidentWorkflowConfig(case_root=case_root),
    )

    assert failed.status == "failed"
    assert "intentional interruption" in str(failed.error)
    state_path = tmp_path / "state" / "data" / failed.session_id / "incident_consultation.json"
    interrupted_state = IncidentState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
    assert interrupted_state.phase.value == "final_diagnosis"
    assert set(interrupted_state.findings) == {"metrics-expert", "logs-expert", "traces-expert"}
    assert interrupted_state.final_diagnosis is None
    room_id = session.trace.session_data(failed.session_id)["incident_room_id"]
    findings_before_resume = [
        message.message_id
        for message in session.trace.room_messages(failed.session_id, room_id)
        if message.name in interrupted_state.findings
    ]
    assert len(findings_before_resume) == 3

    resumed_session = SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room")
    resumed = IncidentConsultationEnvironment(resumed_session, llm=ConsultationLLM(), model="test")
    completed = SessionRuntime(trace=resumed_session.trace).run(
        resumed,
        task=Task("继续分析"),
        session_id=failed.session_id,
    )

    assert completed.status == "completed", completed.error
    assert resumed.state.is_terminal
    assert resumed.state.final_diagnosis is not None
    findings_after_resume = [
        message.message_id
        for message in resumed_session.trace.room_messages(failed.session_id, room_id)
        if message.name in interrupted_state.findings
    ]
    assert findings_after_resume == findings_before_resume
    assert resumed_session.trace.session_data(failed.session_id)["resume_count"] == 1
    assert resumed._active is not None
    for context in resumed._active.contexts.values():
        assert_tool_calls_are_paired(context.history())
