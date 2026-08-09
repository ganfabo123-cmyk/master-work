"""Game-action tools owned by one Werewolf player."""

from __future__ import annotations

from typing import Annotated, Callable

from pydantic import Field

from ...protocol.base_tool import BaseAgentTools
from ...room import Room
from ...room.models import RoomMessage
from ...state.werewolf import WerewolfGameState
from .actions import ActionName, encode_action


class WerewolfActionTools(BaseAgentTools):
    """Build the model-callable game actions for one Werewolf player."""

    def __init__(self, agent_name: str, room: Room, state: WerewolfGameState, has_thought: Callable[[], bool]) -> None:
        super().__init__(agent_name)
        self.room = room
        self.state = state
        self._has_thought = has_thought

    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        return tuple(
            self._build_action_tool(action)
            for action in ActionName
        )

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
