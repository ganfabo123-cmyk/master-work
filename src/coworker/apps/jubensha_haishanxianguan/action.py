from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Annotated, Any

from pydantic import Field

from ...core.action_envelope import ActionEnvelope
from ...core.base_action import Action, BaseAction, ToolAction
from ...core.base_environment import ActionManager
from ...core.models import ToolCall
from ...infra.tools import BaseAgentTools
from .state import GamePhase, HaishanXianguanState, ROLE_ORDER


LOCATION_VALUES = (
    "study",
    "wenhai_tower",
    "opera_stage",
    "water_boat_beside_zhuyun_tower",
    "unknown",
)
MOTIVE_VALUES = (
    "family_medical_cost_and_freedom",
    "protect_pan_family",
    "foreign_diplomatic_interest",
    "unknown",
)


class HaishanActionTools(BaseAgentTools):
    def __init__(self, agent_name: str = "unassigned") -> None:
        super().__init__(agent_name)

    def introduce_character(
        self,
        content: Annotated[str, Field(description="公开的角色自我介绍全文")],
    ) -> str:
        return "自我介绍已接收，等待 Environment 结算。"

    def handle_clues(
        self,
        decisions: Annotated[
            list[dict[str, object]],
            Field(description="本轮每条线索的 clue_id 与 reveal 决定"),
        ],
    ) -> str:
        return f"已接收 {len(decisions)} 条线索决定，等待 Environment 结算。"

    def discuss_publicly(
        self,
        content: Annotated[str, Field(description="本轮公开讨论发言全文")],
    ) -> str:
        return "公开发言已接收，等待 Environment 结算。"

    def submit_vote(
        self,
        suspect_id: Annotated[str, Field(description="最后调包者的角色 ID")],
        image_location: Annotated[str, Field(description="画像最终地点枚举")],
        motive: Annotated[str, Field(description="真凶动机枚举")],
        self_is_culprit: Annotated[bool, Field(description="自己是否为最后调包者")],
        task_claims: Annotated[dict[str, object], Field(description="角色任务复盘陈述")],
    ) -> str:
        return "保密投票已接收，等待 Environment 结算。"

    def tool_functions(self) -> tuple[object, ...]:
        return (
            self.introduce_character,
            self.handle_clues,
            self.discuss_publicly,
            self.submit_vote,
        )


class HaishanAction(BaseAction):
    def __init__(self, tools: HaishanActionTools | None = None) -> None:
        active_tools = tools or HaishanActionTools()
        super().__init__(tools=active_tools)
        self.tool_action_map = {
            "introduce_character": Action("introduce_character", ToolAction),
            "handle_clues": Action("handle_clues", ToolAction),
            "discuss_publicly": Action("discuss_publicly", ToolAction),
            "submit_vote": Action("submit_vote", ToolAction),
        }


@dataclass(frozen=True)
class HaishanActionPayload:
    actor_id: str
    name: str
    arguments: dict[str, object]


class HaishanActionManager(ActionManager):
    PHASE_ACTION = {
        GamePhase.INTRO: "introduce_character",
        GamePhase.PERSON_SEARCH: "handle_clues",
        GamePhase.PERSON_DISCUSS: "discuss_publicly",
        GamePhase.SCENE_SEARCH: "handle_clues",
        GamePhase.SCENE_DISCUSS: "discuss_publicly",
        GamePhase.VOTE: "submit_vote",
    }

    @staticmethod
    def _agent_id(agent: object) -> str:
        return str(getattr(agent, "name", agent))

    @staticmethod
    def _tool_value(tool_call: ToolCall, key: str) -> Any:
        value = getattr(tool_call, key, None)
        if value is not None:
            return value
        function = getattr(tool_call, "function", None)
        return getattr(function, key, None)

    def resolve_action(self, response: object) -> ActionEnvelope[HaishanActionPayload] | None:
        try:
            actor_name, assistant_message, observation = response
            tool_calls = tuple(getattr(assistant_message, "tool_calls", ()) or ())
            if not tool_calls:
                return None
            tool_call = tool_calls[0]
            name = str(self._tool_value(tool_call, "name"))
            raw_arguments = self._tool_value(tool_call, "arguments")
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            if not isinstance(arguments, dict) or name not in self.PHASE_ACTION.values():
                return None
            call_id = str(getattr(tool_call, "id"))
            actor = str(actor_name)
            return ActionEnvelope(
                action_id=f"{actor}:{call_id}",
                actor=actor,
                name=name,
                payload=HaishanActionPayload(actor, name, arguments),
                tool_call=tool_call,
                observation=observation,
            )
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def current_actor(state: HaishanXianguanState) -> str | None:
        if state.phase is GamePhase.INTRO:
            completed = set(state.introductions)
        elif state.phase in (GamePhase.PERSON_SEARCH, GamePhase.SCENE_SEARCH):
            assignments = (
                state.person_clue_assignments
                if state.phase is GamePhase.PERSON_SEARCH
                else state.scene_clue_assignments
            )
            completed = {
                role
                for role, clues in assignments.items()
                if set(clues).issubset(state.handled_clues.get(role, set()))
            }
        elif state.phase in (GamePhase.PERSON_DISCUSS, GamePhase.SCENE_DISCUSS):
            completed = set(state.discussion_rounds[state.phase.value])
        elif state.phase is GamePhase.VOTE:
            completed = set(state.votes)
        else:
            return None
        return next((role for role in state.role_order if role not in completed), None)

    def validate_action(
        self,
        action: ActionEnvelope[HaishanActionPayload],
        state: HaishanXianguanState,
    ) -> tuple[bool, str]:
        if action.action_id in state.consumed_action_ids:
            return False, f"Action {action.action_id} 已消费，不能重复提交。"
        expected_name = self.PHASE_ACTION.get(state.phase)
        if expected_name is None or action.name != expected_name:
            return False, f"阶段 {state.phase.value} 只允许 {expected_name or '自动结算'}。"
        expected_actor = self.current_actor(state)
        if action.actor != expected_actor:
            return False, f"当前应由 {expected_actor} 行动，而不是 {action.actor}。"
        args = action.payload.arguments
        if action.name in ("introduce_character", "discuss_publicly"):
            if not str(args.get("content", "")).strip():
                return False, "公开内容不能为空。"
        elif action.name == "handle_clues":
            decisions = args.get("decisions")
            if not isinstance(decisions, list):
                return False, "decisions 必须是线索决定列表。"
            assignments = (
                state.person_clue_assignments
                if state.phase is GamePhase.PERSON_SEARCH
                else state.scene_clue_assignments
            )
            expected = set(assignments[action.actor]) - state.handled_clues[action.actor]
            submitted: list[str] = []
            for decision in decisions:
                if not isinstance(decision, dict):
                    return False, "每条线索决定必须是对象。"
                clue_id = str(decision.get("clue_id", ""))
                if not isinstance(decision.get("reveal"), bool):
                    return False, f"线索 {clue_id} 的 reveal 必须是布尔值。"
                submitted.append(clue_id)
            if len(submitted) != len(set(submitted)):
                return False, "同一 clue_id 不能重复提交。"
            unknown = set(submitted) - expected
            if unknown:
                clue_id = sorted(unknown)[0]
                return False, f"线索 {clue_id} 不属于 {action.actor} 的本轮未处理线索。"
            missing = expected - set(submitted)
            if missing:
                return False, f"缺少本轮线索：{', '.join(sorted(missing))}。"
        elif action.name == "submit_vote":
            suspect = str(args.get("suspect_id", ""))
            if suspect not in ROLE_ORDER:
                return False, f"嫌疑人 {suspect or '<empty>'} 不在六名角色中。"
            if args.get("image_location") not in LOCATION_VALUES:
                return False, "image_location 不是声明的地点枚举。"
            if args.get("motive") not in MOTIVE_VALUES:
                return False, "motive 不是声明的动机枚举。"
            if not isinstance(args.get("self_is_culprit"), bool):
                return False, "self_is_culprit 必须是布尔值。"
            if not isinstance(args.get("task_claims"), dict):
                return False, "task_claims 必须是对象。"
        return True, ""

    def available_actions(
        self, state: HaishanXianguanState, agent: object
    ) -> tuple[str, ...]:
        name = self.PHASE_ACTION.get(state.phase)
        if name and self._agent_id(agent) == self.current_actor(state):
            return (name,)
        return ()

    def resolve_actions(
        self,
        state: HaishanXianguanState,
        actions: object,
    ) -> ActionEnvelope[HaishanActionPayload] | None:
        if isinstance(actions, ActionEnvelope):
            return actions
        if isinstance(actions, dict):
            actor = self.current_actor(state)
            return actions.get(actor) if actor else None
        if isinstance(actions, (tuple, list)):
            return actions[0] if actions else None
        return None
