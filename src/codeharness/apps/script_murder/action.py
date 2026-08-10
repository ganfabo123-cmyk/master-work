"""Closed domain actions exposed to murder-mystery characters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import Field

from ...core.base_action import Action, BaseAction, ToolAction
from ...infra.room import Room
from ...infra.tools import BaseAgentTools


ENGINE_NAME = "script-murder-engine"


class ScriptMurderActionTools(BaseAgentTools):
    def __init__(self, agent_name: str, public_room: Room, private_room: Room) -> None:
        super().__init__(agent_name)

    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        return (self.speak, self.pass_turn, self.submit_resolution)

    def speak(self, message: Annotated[str, Field(min_length=1, description="发送到公共 ROOM 的角色发言。")]) -> str:
        """生成向所有参与者公开发言的 Action。"""
        return "Speak Action 已生成，等待 Environment 执行。"

    def pass_turn(self) -> str:
        """生成保持沉默并结束发言机会的 Action。"""
        return "Pass Action 已生成，等待 Environment 执行。"

    def submit_resolution(
        self,
        declarations: Annotated[list[str], Field(description="结算时公开的声明，可为空列表。")],
        decisive_action: Annotated[Literal["murder", "guard", "investigate", "pass"], Field(description="至多一个决定性行动。")],
        target: Annotated[str | None, Field(description="行动目标的角色 ID；pass 时必须为空。")],
        leader_vote: Annotated[str, Field(description="党魁选票目标的角色 ID。")],
    ) -> str:
        """生成不可修改的最终声明、行动和党魁选票 Action。"""
        return "Resolution Action 已生成，等待 Environment 执行。"


class ScriptMurderAction(BaseAction):
    def __init__(self, *, agent_name: str, public_room: Room, private_room: Room) -> None:
        super().__init__(tools=ScriptMurderActionTools(agent_name, public_room, private_room))
        self.tool_action_map = {name: Action(name, ToolAction) for name in ("speak", "pass_turn", "submit_resolution")}
