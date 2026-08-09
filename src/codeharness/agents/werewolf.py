"""One configurable Agent class for all werewolf players."""

from __future__ import annotations

from pathlib import Path

from ..action.werewolf import WerewolfActionTools
from ..base_class.base_agent import LLMAgent, SkillSpec
from ..client import LLMClient
from ..room import Room
from ..policy.werewolf.prompt import WerewolfPromptBuilder
from ..policy.werewolf.tool import WerewolfPlayerTools
from ..state.werewolf import Role, WerewolfGameState


_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills" / "werewolf"


class WerewolfPlayerAgent(LLMAgent):
    def __init__(
        self,
        llm: LLMClient,
        model: str,
        *,
        name: str,
        role: Role,
        public_room: Room,
        state: WerewolfGameState,
        wolf_room: Room | None = None,
    ) -> None:
        policy_tools = WerewolfPlayerTools(name, public_room, state, wolf_room)
        action_tools = WerewolfActionTools(name, public_room, state, policy_tools.has_thought)
        super().__init__(
            name=name,
            model=model,
            llm=llm,
            policy=WerewolfPromptBuilder(player_name=name, role=role),
            temperature=0.9,
            policy_tools=(policy_tools,),
            action_tools=(action_tools,),
            skills=(
                SkillSpec(
                    name=f"werewolf-{role.value}",
                    path=_SKILLS_ROOT / role.value / "SKILL.md",
                    description=f"Classic werewolf rules for the {role.value} role.",
                ),
            ),
        )
