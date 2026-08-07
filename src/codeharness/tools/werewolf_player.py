"""Tools owned by one WerewolfPlayerAgent instance."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Callable, Literal

from pydantic import Field

from ..memory import LongTermMemoryEntry, LongTermMemoryManager
from ..room import Room
from ..util.werewolf_actions import ActionName
from ..util.werewolf_state import Phase, Role, WerewolfGameState
from .base import BaseAgentTools
from .utils import build_werewolf_action_tool, send_public_werewolf_message, send_wolf_message


class WerewolfPlayerTools(BaseAgentTools):
    def __init__(self, agent_name: str, room: Room, state: WerewolfGameState, wolf_room: Room | None = None) -> None:
        super().__init__(agent_name)
        self.room = room
        self.state = state
        self.wolf_room = wolf_room
        self._has_thought = False

    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        """Return this player's complete, phase-invariant tool contract."""
        self._has_thought = False
        return (
            self.think,
            self.save_experience,
            self.list_experiences,
            self.get_experience,
            self.wolf_message,
            self.speak,
            *(build_werewolf_action_tool(self.room, self.agent_name, self.state, action, lambda: self._has_thought) for action in ActionName),
        )

    def think(
        self,
        strategy: Annotated[str, Field(description="本回合的私密策略推理，包括线索、风险和下一步行动依据；不会发送到 ROOM。")],
    ) -> str:
        """记录本回合私密思考；必须先调用，之后才能发送 ROOM 消息或提交游戏动作。"""
        self._has_thought = True
        return "思考已记录。现在可以调用公开发言、私聊或游戏动作工具。"

    def save_experience(
        self,
        experience_name: Annotated[str, Field(description="经验名称，在当前 Agent 的长期记忆中必须唯一。")],
        happened_at: Annotated[str, Field(description="经验发生时间，格式为 YYYY-MM-DD HH:mm。")],
        thing_done: Annotated[str, Field(description="当时做了什么。")],
        outcome: Annotated[Literal["成功", "失败"], Field(description="经验结果，只能是 成功 或 失败。")],
        feedback_basis: Annotated[str, Field(description="判断结果的反馈、裁定或可追溯依据。")],
        approach: Annotated[str, Field(description="当时采取的具体做法。")],
        reason_and_principle: Annotated[str, Field(description="成功或失败的原因分析，以及可迁移原则。")],
    ) -> str:
        """为当前狼人杀玩家存储一条完整的长期经验。"""
        try:
            LongTermMemoryManager().for_agent(self.agent_name).add(
                LongTermMemoryEntry(
                    experience_name=experience_name,
                    happened_at=datetime.strptime(happened_at, "%Y-%m-%d %H:%M"),
                    thing_done=thing_done,
                    outcome=outcome,
                    feedback_basis=feedback_basis,
                    approach=approach,
                    reason_and_principle=reason_and_principle,
                )
            )
        except ValueError as error:
            return f"存储长期经验失败：{error}"
        return f"已为 {self.agent_name} 存储长期经验：{experience_name}。"

    def list_experiences(self) -> str:
        """列出当前狼人杀玩家已有的长期经验名称、发生时间和结果摘要。"""
        entries = LongTermMemoryManager().for_agent(self.agent_name).list()
        if not entries:
            return "当前没有已沉淀的长期经验。"
        return "\n".join(
            f"- {entry.experience_name}（{entry.happened_at.strftime('%Y-%m-%d %H:%M')}，{entry.outcome}）"
            for entry in entries
        )

    def get_experience(
        self,
        experience_name: Annotated[str, Field(description="要读取的当前狼人杀玩家长期经验名称。")],
    ) -> str:
        """返回当前狼人杀玩家某条长期经验的完整模板内容。"""
        entry = LongTermMemoryManager().for_agent(self.agent_name).get(experience_name)
        if entry is None:
            return f"没有找到名称为“{experience_name}”的长期经验。"
        return entry.render()

    def wolf_message(
        self,
        content: Annotated[str, Field(description="发给全部存活狼队友的私下协商内容。")],
    ) -> str:
        """向全部存活狼人发送私下协商消息。"""
        return send_wolf_message(self.room, self.wolf_room, self.state, self.agent_name, content, self._has_thought)

    def speak(
        self,
        content: Annotated[str, Field(description="公开发言内容，应基于当前可见线索进行推理。")],
    ) -> str:
        """向全体玩家公开发言。"""
        return send_public_werewolf_message(self.room, self.agent_name, content, self._has_thought)
