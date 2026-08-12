"""Prompt and private reasoning policy for poker players."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from pydantic import Field

from ...core.base_policy import BasePolicy
from ...core.models import Message, Prompt, Task
from ...infra.prompt import BasePromptBuilder
from ...infra.tools import BaseAgentTools


class PokerPromptBuilder(BasePromptBuilder):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def build(self, task: Task) -> Prompt:
        return Prompt((
            Message("developer", f"""你是四人德州扑克中的 {self.player_name}。

- 只依据自己的手牌、公共牌和公开下注信息决策。
- 其他玩家看不到你的手牌，你也不能声称知道其他人的手牌。
- 每回合只能调用一个当前开放的下注 Action。
- `raise_bet.amount` 表示本街加注后的总下注额。
- `think` 是私密推理，不改变牌局状态。"""),
            Message("user", task.description),
        ))


class PokerPolicyTools(BaseAgentTools):
    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        return (self.think,)

    def think(self, strategy: Annotated[str, Field(description="私密的牌力、赔率和对手范围判断。")]) -> str:
        """记录不会发送到公共 ROOM 的策略判断。"""
        return "私密牌局分析已记录。"


class PokerPolicy(BasePolicy):
    def __init__(self, player_name: str) -> None:
        builder = PokerPromptBuilder(player_name)
        super().__init__(prompt_builder=builder, tools=PokerPolicyTools(player_name))
