"""Werewolf Action assembled from its executable tools."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Annotated

from pydantic import Field

from ...core.base_action import Action, BaseAction, RawContentAction, ToolAction
from ...infra.tools import BaseAgentTools
from ...infra.room import Room
from .state import Phase, WerewolfGameState


class ActionName(StrEnum):
    WOLF_MESSAGE = "wolf_message"
    SPEAK = "speak"
    WOLF_KILL = "wolf_kill"
    INSPECT = "inspect"
    SAVE = "save"
    POISON = "poison"
    VOTE = "vote"
    SHOOT = "shoot"
    SKIP_SHOT = "skip_shot"


class WerewolfActionTools(BaseAgentTools):
    """Build the model-callable game actions for one Werewolf player."""

    def __init__(
        self,
        agent_name: str,
        room: Room,
        state: WerewolfGameState,
    ) -> None:
        super().__init__(agent_name)

    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        game_actions = tuple(action for action in ActionName if action not in {ActionName.WOLF_MESSAGE, ActionName.SPEAK})
        return (self.wolf_message, self.speak, *(self._build_action_tool(action) for action in game_actions))

    def wolf_message(self, content: Annotated[str, Field(description="发给全部存活狼队友的私下协商内容。")]) -> str:
        """生成狼队私下协商 Action。"""
        return "Wolf Message Action 已生成，等待 Environment 执行。"

    def speak(self, content: Annotated[str, Field(description="公开发言内容，应基于当前可见线索进行推理。")]) -> str:
        """生成面向全体玩家的公开发言 Action。"""
        return "Speak Action 已生成，等待 Environment 执行。"

    def _build_action_tool(self, action: ActionName) -> Callable[..., str]:
        if action in {ActionName.SAVE, ActionName.SKIP_SHOT}:

            def submit() -> str:
                """生成一个无需目标的游戏 Action。"""
                return "游戏 Action 已生成，等待 Environment 执行。"
        else:

            def submit(
                target: Annotated[str, Field(description="目标玩家名称，例如 player-3；必须是存活且合法的玩家。")],
            ) -> str:
                """生成一个有目标的游戏 Action。"""
                return "游戏 Action 已生成，等待 Environment 执行。"
        submit.__name__ = action.value
        return submit

class WerewolfAction(BaseAction):
    """Combine the Werewolf action tools with the Action base class."""

    def __init__(
        self,
        *,
        agent_name: str,
        room: Room,
        state: WerewolfGameState,
    ) -> None:
        super().__init__(
            tools=WerewolfActionTools(agent_name, room, state),
        )
        self.tool_action_map = {
            "raw content": Action(
                name="raw content",
                type=RawContentAction,
            ),
            "wolf_message": Action(name=ActionName.WOLF_MESSAGE.value, type=ToolAction),
            "speak": Action(name=ActionName.SPEAK.value, type=ToolAction),
            "wolf_kill": Action(
                name=ActionName.WOLF_KILL.value,
                type=ToolAction,
            ),
            "inspect": Action(
                name=ActionName.INSPECT.value,
                type=ToolAction,
            ),
            "save": Action(
                name=ActionName.SAVE.value,
                type=ToolAction,
            ),
            "poison": Action(
                name=ActionName.POISON.value,
                type=ToolAction,
            ),
            "vote": Action(
                name=ActionName.VOTE.value,
                type=ToolAction,
            ),
            "shoot": Action(
                name=ActionName.SHOOT.value,
                type=ToolAction,
            ),
            "skip_shot": Action(
                name=ActionName.SKIP_SHOT.value,
                type=ToolAction,
            ),
        }
