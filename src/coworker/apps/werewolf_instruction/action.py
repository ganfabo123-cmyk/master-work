"""Closed tools for discussion and final instruction submission."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from pydantic import Field

from ...core.base_action import Action, BaseAction, ToolAction
from ...infra.room import Room
from ...infra.tools import BaseAgentTools

ENGINE_NAME = "instruction-engine"


class WerewolfInstructionTools(BaseAgentTools):
    def __init__(self, agent_name: str, room: Room) -> None:
        super().__init__(agent_name)

    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        return (self.speak, self.submit_my_instruction)

    def speak(self, content: Annotated[str, Field(description="发送到公共讨论 ROOM 的狼人杀策略或经验。")]) -> str:
        """生成向全部参与者发言的 Action。"""
        return "Speak Action 已生成，等待 Environment 执行。"

    def submit_my_instruction(self, instruction: Annotated[str, Field(description="可直接拼入最终教程的正文，不要包含署名或心得标题。")]) -> str:
        """生成当前参与者的最终教程提交 Action。"""
        return "Instruction Action 已生成，等待 Environment 执行。"


class WerewolfInstructionAction(BaseAction):
    def __init__(self, *, agent_name: str, room: Room) -> None:
        super().__init__(tools=WerewolfInstructionTools(agent_name, room))
        self.tool_action_map = {
            "speak": Action("speak", ToolAction),
            "submit_my_instruction": Action("submit_my_instruction", ToolAction),
        }
