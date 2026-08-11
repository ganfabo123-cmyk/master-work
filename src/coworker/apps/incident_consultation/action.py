"""Closed Action space for incident consultation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from pydantic import Field

from ...core.base_action import Action, BaseAction, ToolAction
from ...infra.room import Room
from ...infra.tools import BaseAgentTools


class IncidentActionTools(BaseAgentTools):
    def __init__(self, agent_name: str, room: Room) -> None:
        super().__init__(agent_name)

    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        return (self.submit_finding, self.submit_final_diagnosis)

    def submit_finding(
        self,
        component: Annotated[str, Field(description="疑似异常服务或组件名。")],
        summary: Annotated[str, Field(description="基于可见证据形成的简短发现。")],
        evidence_ids: Annotated[list[str], Field(description="Observation 中真实存在的证据 ID。")],
        confidence: Annotated[int, Field(ge=0, le=100, description="置信度，0 到 100。")],
    ) -> str:
        """生成本证据专家的结构化 Finding Action。"""
        return "Finding Action 已生成，等待 Environment 执行。"

    def submit_final_diagnosis(
        self,
        component: Annotated[str, Field(description="最终认定的根因服务或组件。")],
        root_cause: Annotated[str, Field(description="最终根因说明，必须区分证据和推断。")],
        evidence_ids: Annotated[list[str], Field(description="专家 Findings 中已经引用的证据 ID。")],
        confidence: Annotated[int, Field(ge=0, le=100, description="置信度，0 到 100。")],
    ) -> str:
        """生成主诊断专家的最终诊断 Action。"""
        return "Final Diagnosis Action 已生成，等待 Environment 执行。"


class IncidentAction(BaseAction):
    def __init__(self, *, agent_name: str, room: Room) -> None:
        super().__init__(tools=IncidentActionTools(agent_name, room))
        self.tool_action_map = {
            "submit_finding": Action("submit_finding", ToolAction),
            "submit_final_diagnosis": Action("submit_final_diagnosis", ToolAction),
        }
