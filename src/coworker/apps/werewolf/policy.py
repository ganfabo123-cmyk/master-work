"""Werewolf Policy, Prompt Builder, and Policy-owned tools."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Callable, Literal

from pydantic import Field

from ...core.base_policy import BasePolicy
from ...infra.prompt import BasePromptBuilder
from ...infra.tools import BaseAgentTools
from ...infra.memory import LongTermMemoryEntry, LongTermMemoryManager
from ...core.models import Message, Prompt, Task
from ...infra.room import Room
from .state import Role, WerewolfGameState


_SKILLS_ROOT = Path(__file__).resolve().parents[4] / "skills" / "werewolf"


class WerewolfPromptBuilder(BasePromptBuilder):
    def __init__(self, *, player_name: str, role: Role) -> None:
        self.player_name = player_name
        self.role = role

    def build(self, task: Task) -> Prompt:
        role_skill = (_SKILLS_ROOT / self.role.value / "SKILL.md").read_text(encoding="utf-8")
        system = f"""# 你的身份

你是 {self.player_name}，真实身份是：{self.role.value}。这是私密信息，绝不能向其他玩家直接透露。

# 身份技能

{role_skill}

# 强制规则

- 只能依据此 Prompt、自己的私有收件箱和所提供工具行动。
- 任何会改变游戏局面的行为必须调用对应工具；自然语言不能代替投票、击杀、查验、用药或开枪。
- 每个回合必须先单独调用 `think(strategy)`，完成私密策略推理并收到工具确认；只有之后才允许调用公开发言、狼队私聊或游戏动作工具。
- `think` 的内容不会发到 ROOM，其他玩家不可见；不要把完整私密思考写进公开发言或狼队私聊。
- 当需要思考时，可以调用 `list_experiences` 查看自己的历史经验摘要，再调用 `get_experience` 读取某条完整经验，以辅助本回合的私密策略判断；这些经验仅供你本人参考，不得当作当前对局已经发生的事实。
- 没有可用工具时，只能等待或做简短推理，不得伪造规则引擎结果。
- 不得猜测、读取或声称知道其他玩家的 Profile 或身份。
- 公共 ROOM 信息对所有玩家可见；仅当你是狼人且收到狼队私聊 ROOM 时，才可把其中内容用于协商。
- 后续会以增量事件提供当前阶段、可用工具和新收到的 ROOM 消息；仅依据最新事件行动。
- `save` 表示消耗解药救人，不表示跳过行动；若事件中没有 `save`，说明解药已不可用。
"""
        user = f"用户发起的请求：{task.description}"
        return Prompt((Message("developer", system), Message("user", user)))


class WerewolfPlayerTools(BaseAgentTools):
    def __init__(
        self,
        agent_name: str,
        room: Room,
        state: WerewolfGameState,
        wolf_room: Room | None = None,
    ) -> None:
        super().__init__(agent_name)

    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        return (
            self.think,
            self.save_experience,
            self.list_experiences,
            self.get_experience,
        )

    def think(
        self,
        strategy: Annotated[str, Field(description="本回合的私密策略推理，包括线索、风险和下一步行动依据；不会发送到 ROOM。")],
    ) -> str:
        """记录本回合的私密策略推理。"""
        return "思考已记录。"

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

class WerewolfPolicy(BasePolicy):
    """Combine the Werewolf Prompt Builder and Policy tools."""

    def __init__(
        self,
        *,
        player_name: str,
        role: Role,
        room: Room,
        state: WerewolfGameState,
        wolf_room: Room | None = None,
    ) -> None:
        super().__init__(
            prompt_builder=WerewolfPromptBuilder(player_name=player_name, role=role),
            tools=WerewolfPlayerTools(player_name, room, state, wolf_room),
        )
