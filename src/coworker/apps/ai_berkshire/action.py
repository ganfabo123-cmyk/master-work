"""Closed Action tools for AI Berkshire research."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from pydantic import Field

from ...core.base_action import Action, BaseAction, ToolAction
from ...infra.tools import BaseAgentTools


class InvestmentActionTools(BaseAgentTools):
    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        return (self.submit_analysis, self.submit_investment_memo)

    def submit_analysis(
        self,
        title: Annotated[str, Field(description="本维度研究报告标题。")],
        thesis: Annotated[str, Field(description="本维度一句话核心判断。")],
        content: Annotated[str, Field(description="完整 Markdown 分析，明确事实、推断、反证和资料缺口。")],
        score: Annotated[int, Field(ge=1, le=5, description="本维度评分，1 到 5。")],
        confidence: Annotated[int, Field(ge=0, le=100, description="结论置信度，0 到 100。")],
        citations: Annotated[list[str], Field(description="实际使用的来源或来源标识；没有可靠来源时传空列表。")],
    ) -> str:
        """生成分析师的 Research Artifact Action。"""
        return "Research Artifact Action 已生成，等待 Environment 执行。"

    def submit_investment_memo(
        self,
        recommendation: Annotated[str, Field(description="明确结论：买入、观察或回避。")],
        summary: Annotated[str, Field(description="最终一句话投资结论。")],
        content: Annotated[str, Field(description="综合四份研究产物形成的完整 Markdown 投资备忘录。")],
        score: Annotated[int, Field(ge=1, le=5, description="综合评分，1 到 5。")],
        confidence: Annotated[int, Field(ge=0, le=100, description="最终结论置信度，0 到 100。")],
        source_artifact_ids: Annotated[list[str], Field(description="综合时实际使用的四份研究产物 ID。")],
    ) -> str:
        """生成 team lead 的最终 Investment Memo Action。"""
        return "Investment Memo Action 已生成，等待 Environment 执行。"


class InvestmentAction(BaseAction):
    def __init__(self, *, agent_name: str) -> None:
        super().__init__(tools=InvestmentActionTools(agent_name))
        self.tool_action_map = {
            "submit_analysis": Action("submit_analysis", ToolAction),
            "submit_investment_memo": Action("submit_investment_memo", ToolAction),
        }
