"""Werewolf Action assembled from its executable tools."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
import json
from typing import Annotated

from pydantic import Field

from ...core.base_action import Action, BaseAction, RawContentAction, ToolAction
from ...infra.tools import BaseAgentTools
from ...infra.room import Room, RoomMessage
from .state import Phase, WerewolfGameState


class ActionName(StrEnum):
    WOLF_KILL = "wolf_kill"
    INSPECT = "inspect"
    SAVE = "save"
    POISON = "poison"
    VOTE = "vote"
    SHOOT = "shoot"
    SKIP_SHOT = "skip_shot"


def encode_action(
    *,
    action: ActionName,
    target: str | None,
    round_no: int,
    phase: Phase,
) -> str:
    return json.dumps(
        {
            "type": "werewolf.action",
            "action": action,
            "target": target,
            "round": round_no,
            "phase": phase,
        },
        ensure_ascii=False,
    )


class WerewolfActionTools(BaseAgentTools):
    """Build the model-callable game actions for one Werewolf player."""

    def __init__(
        self,
        agent_name: str,
        room: Room,
        state: WerewolfGameState,
        has_thought: Callable[[], bool],
    ) -> None:
        super().__init__(agent_name)
        self.room = room
        self.state = state
        self._has_thought = has_thought

    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        return tuple(self._build_action_tool(action) for action in ActionName)

    def _build_action_tool(self, action: ActionName) -> Callable[..., str]:
        if action in {ActionName.SAVE, ActionName.SKIP_SHOT}:

            def submit() -> str:
                """提交无需目标的游戏动作。"""
                self._require_thought()
                self._submit(action, None)
                return "动作已提交给规则引擎。"
        else:

            def submit(
                target: Annotated[str, Field(description="目标玩家名称，例如 player-3；必须是存活且合法的玩家。")],
            ) -> str:
                """提交一个有目标的游戏动作。"""
                self._require_thought()
                self._submit(action, target)
                return "动作已提交给规则引擎。"
        submit.__name__ = action.value
        return submit

    def _require_thought(self) -> None:
        if not self._has_thought():
            raise ValueError("请先调用 think(strategy) 完成私密思考，再发送 ROOM 消息或提交游戏动作。")

    def _submit(self, action: ActionName, target: str | None) -> None:
        self.room.send(
            RoomMessage(
                name=self.agent_name,
                at="game-engine",
                txt=encode_action(
                    action=action,
                    target=target,
                    round_no=self.state.round_no,
                    phase=self.state.phase,
                ),
            )
        )


class WerewolfAction(BaseAction):
    """Combine the Werewolf action tools with the Action base class."""

    def __init__(
        self,
        *,
        agent_name: str,
        room: Room,
        state: WerewolfGameState,
        has_thought: Callable[[], bool],
    ) -> None:
        super().__init__(
            tools=WerewolfActionTools(agent_name, room, state, has_thought),
        )
        self.tool_action_map = {
            "raw content": Action(
                name="raw content",
                type=RawContentAction,
            ),
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
