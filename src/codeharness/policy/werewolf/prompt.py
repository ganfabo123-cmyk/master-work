"""Prompt construction for one player in the deterministic werewolf workflow."""

from __future__ import annotations

from pathlib import Path

from ..models import Message, Prompt, Task
from ..util.werewolf_state import Phase, Role
from .base import BasePromptBuilder


_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills" / "werewolf"


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
