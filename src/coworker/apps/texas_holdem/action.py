"""Closed betting actions for Texas Hold'em players."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from pydantic import Field

from ...core.base_action import Action, BaseAction, ToolAction
from ...infra.tools import BaseAgentTools


ENGINE_NAME = "poker-engine"
ACTION_NAMES = ("fold", "check", "call", "raise_bet", "all_in")


class PokerActionTools(BaseAgentTools):
    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        return (self.fold, self.check, self.call, self.raise_bet, self.all_in)

    def fold(self) -> str:
        """弃牌并放弃本局已投入筹码。"""
        return "Fold Action 已生成，等待 Environment 结算。"

    def check(self) -> str:
        """无需补筹码时过牌。"""
        return "Check Action 已生成，等待 Environment 结算。"

    def call(self) -> str:
        """跟注到当前下注额；筹码不足时自动投入全部筹码。"""
        return "Call Action 已生成，等待 Environment 结算。"

    def raise_bet(self, amount: Annotated[int, Field(gt=0, description="本街加注后的总下注额，不是追加额。")]) -> str:
        """将本街总下注提高到指定筹码数。"""
        return f"Raise Action({amount}) 已生成，等待 Environment 结算。"

    def all_in(self) -> str:
        """投入剩余全部筹码。"""
        return "All-in Action 已生成，等待 Environment 结算。"


class PokerAction(BaseAction):
    def __init__(self, agent_name: str) -> None:
        super().__init__(tools=PokerActionTools(agent_name))
        self.tool_action_map = {name: Action(name, ToolAction) for name in ACTION_NAMES}
