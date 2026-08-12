from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from coworker.apps.ai_berkshire.environment import AIBerkshireEnvironment, InvestmentWorkflowConfig
from coworker.apps.ai_berkshire.policy import InvestmentPromptBuilder
from coworker.apps.ai_berkshire.state import InvestmentRole, InvestmentState
from coworker.apps.ai_berkshire.web_search import SearchRecency
from coworker.core.models import Message, ModelResult, Task, ToolCall
from coworker.infra.client import LLMClient
from coworker.infra.session import SessionManager

from tool_message_assertions import assert_tool_calls_are_paired


class InvestmentLLM(LLMClient):
    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        assert_tool_calls_are_paired(messages)
        state_message = next(message for message in reversed(messages) if message.role == "user" and '"type": "ai_berkshire_state"' in str(message.content))
        state = json.loads(state_message.content)
        if state["role"] == "lead":
            artifact_ids = [item["artifact_id"] for item in state["artifacts"]]
            return self._call("submit_investment_memo", {
                "recommendation": "观察", "summary": "生意质量尚可，但数据不足以确认安全边际。",
                "content": "# 最终报告\n\n综合四维研究，当前保持观察。", "score": 3,
                "confidence": 68, "source_artifact_ids": artifact_ids,
            }, model)
        state_index = max(index for index, message in enumerate(messages) if message is state_message)
        search_result = next(
            (message for message in messages[state_index + 1:] if message.role == "tool" and message.name == "search_web"),
            None,
        )
        if search_result is None:
            return self._call("search_web", {
                "query": f"Example Corp {state['role']} latest filing",
                "top_k": 3,
                "recency": "year",
                "sites": ["example.com"],
            }, model)
        source_url = json.loads(str(search_result.content))["references"][0]["url"]
        return self._call("submit_analysis", {
            "title": f"{state['role']} 分析", "thesis": f"{state['role']} 维度需要继续验证。",
            "content": f"# {state['role']}\n\n基于给定资料完成分析并标注缺口。", "score": 3,
            "confidence": 65, "citations": [source_url],
        }, model)

    @staticmethod
    def _call(name: str, arguments: dict[str, object], model: str) -> ModelResult:
        return ModelResult(raw_content="", tool_calls=(ToolCall(f"{name}-call", name, arguments),), model=model)


class FakeSearchClient:
    def search(self, *, query: str, top_k: int, recency: SearchRecency, sites: tuple[str, ...]) -> dict[str, object]:
        return {
            "query": query,
            "request_id": "fake-request",
            "references": [{
                "id": 1,
                "title": "Example Corp filing",
                "url": f"https://example.com/{query.split()[-3]}",
                "website": "example.com",
                "date": "2026-08-11",
                "content": "verified source excerpt",
                "rerank_score": 0.9,
                "authority_score": 0.8,
            }],
        }


class MalformedOnceInvestmentLLM(InvestmentLLM):
    def __init__(self) -> None:
        self.malformed_sent = False

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **kwargs: Any) -> ModelResult:
        result = super().generate(model=model, messages=messages, tools=tools, **kwargs)
        if self.malformed_sent or not result.tool_calls or result.tool_calls[0].name != "submit_analysis":
            return result
        state_message = next(message for message in reversed(messages) if message.role == "user" and '"type": "ai_berkshire_state"' in str(message.content))
        if json.loads(state_message.content)["role"] != "industry":
            return result
        arguments = dict(result.tool_calls[0].arguments)
        arguments.pop("content")
        self.malformed_sent = True
        return self._call("submit_analysis", arguments, model)


class InvalidRecommendationOnceLLM(InvestmentLLM):
    def __init__(self) -> None:
        self.invalid_sent = False

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **kwargs: Any) -> ModelResult:
        result = super().generate(model=model, messages=messages, tools=tools, **kwargs)
        if self.invalid_sent or not result.tool_calls or result.tool_calls[0].name != "submit_investment_memo":
            return result
        arguments = dict(result.tool_calls[0].arguments)
        arguments["recommendation"] = "观察（结构性再平衡）"
        self.invalid_sent = True
        return self._call("submit_investment_memo", arguments, model)


def test_investment_prompt_includes_runtime_date_and_timezone() -> None:
    before = datetime.now().astimezone()
    prompt = InvestmentPromptBuilder(agent_name="financial-analyst", role=InvestmentRole.FINANCIAL).build(Task("研究8月持仓"))
    after = datetime.now().astimezone()

    system = str(prompt.messages[0].content)
    assert "# 运行时间" in system
    assert "当前日期时间：" in system
    assert "当前时区：" in system
    assert "不得自行猜测年份" in system
    assert before.date().isoformat() in system or after.date().isoformat() in system


def test_ai_berkshire_parallel_research_then_lead_synthesis(tmp_path: Path) -> None:
    environment = AIBerkshireEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=InvestmentLLM(), model="test", search_client=FakeSearchClient(),
    )
    config = InvestmentWorkflowConfig(
        company_name="Example Corp", ticker="EXM", information_grade="B",
        data_cutoff="2026-08-11", research_context="provided company brief",
    )

    result = environment.run(task=Task("研究 Example Corp 的长期投资价值"), config=config)

    assert result.status == "completed", result.error
    state_path = tmp_path / "state" / "data" / result.session_id / "ai_berkshire.json"
    state = InvestmentState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
    assert state.is_terminal
    assert set(state.artifacts) == {"business-analyst", "financial-analyst", "industry-researcher", "risk-assessor"}
    assert state.final_memo is not None
    assert state.final_memo.recommendation == "观察"
    assert set(state.final_memo.source_artifact_ids) == {item.artifact_id for item in state.artifacts.values()}
    assert environment._active is not None
    room_messages = environment.trace.room_messages(result.session_id, environment._active.room("research").room_id)
    for artifact in state.artifacts.values():
        assert any(message.name == artifact.author and artifact.content in message.txt for message in room_messages)
    assert any(
        message.name == "team-lead" and state.final_memo.content in message.txt
        for message in room_messages
    )
    for context in environment._active.contexts.values():
        assert_tool_calls_are_paired(context.history())

    resumed = AIBerkshireEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=InvestmentLLM(), model="test", search_client=FakeSearchClient(),
    )
    resumed_result = resumed.run(task=Task("继续研究"), config=config, session_id=result.session_id)
    assert resumed_result.status == "completed"
    assert resumed.state.is_terminal
    assert resumed.trace.session_data(result.session_id)["resume_count"] == 1


def test_investment_config_rejects_missing_company_and_invalid_grade() -> None:
    for kwargs in ({"company_name": ""}, {"company_name": "Example", "information_grade": "D"}):
        try:
            InvestmentWorkflowConfig(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid investment workflow config was accepted")


def test_generic_runtime_can_derive_config_from_task_inputs(tmp_path: Path) -> None:
    environment = AIBerkshireEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=InvestmentLLM(), model="test", search_client=FakeSearchClient(),
    )
    result = environment.run(task=Task("研究 Example Corp", {
        "company_name": "Example Corp", "ticker": "EXM", "information_grade": "C",
        "research_context": "limited provided evidence", "data_cutoff": "2026-08-11",
    }))

    assert result.status == "completed", result.error
    assert environment.state.company_name == "Example Corp"
    assert environment.state.information_grade == "C"


def test_invalid_action_is_rejected_and_corrected_in_same_agent_context(tmp_path: Path) -> None:
    environment = AIBerkshireEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=MalformedOnceInvestmentLLM(), model="test", search_client=FakeSearchClient(),
    )

    result = environment.run(
        task=Task("研究 Example Corp"),
        config=InvestmentWorkflowConfig(company_name="Example Corp"),
    )

    assert result.status == "completed", result.error
    assert environment._active is not None
    industry_context = environment._active.contexts["industry-researcher"].history()
    rejected = [message for message in industry_context if message.role == "tool" and message.name == "submit_analysis"]
    assert len(rejected) == 2
    assert "参数无法解析" in str(rejected[0].content)
    assert_tool_calls_are_paired(industry_context)


def test_team_lead_receives_precise_recommendation_correction(tmp_path: Path) -> None:
    environment = AIBerkshireEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=InvalidRecommendationOnceLLM(), model="test", search_client=FakeSearchClient(),
    )

    result = environment.run(task=Task("研究 Example Corp"), config=InvestmentWorkflowConfig(company_name="Example Corp"))

    assert result.status == "completed", result.error
    assert environment.state.final_memo is not None
    assert environment.state.final_memo.recommendation == "观察"
    assert environment._active is not None
    lead_context = environment._active.contexts["team-lead"].history()
    rejected = [message for message in lead_context if message.role == "tool" and message.name == "submit_investment_memo"]
    assert "必须精确填写“买入”“观察”或“回避”" in str(rejected[0].content)
    assert_tool_calls_are_paired(lead_context)
