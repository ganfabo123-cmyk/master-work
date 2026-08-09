"""One configurable Agent class for all werewolf players."""

from __future__ import annotations

from pathlib import Path

from ...core.base_agent import Agent, PromptBuilder, SkillSpec
from ...infra.client import LLMClient
from ...infra.room import Room
from .action import WerewolfAction
from .policy import WerewolfPolicy
from .state import Role, WerewolfGameState


_SKILLS_ROOT = Path(__file__).resolve().parents[4] / "skills" / "werewolf"


class WerewolfPlayerAgent(Agent):
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
        policy = WerewolfPolicy(
            player_name=name,
            role=role,
            room=public_room,
            state=state,
            wolf_room=wolf_room,
        )
        action = WerewolfAction(
            agent_name=name,
            room=public_room,
            state=state,
            has_thought=policy.tools.has_thought,
        )
        super().__init__(
            name=name,
            model=model,
            llm=llm,
            policy=policy,
            action=action,
            temperature=0.9,
            policy_tools=(policy.tools,),
            action_tools=(action.tools,),
            skills=(
                SkillSpec(
                    name=f"werewolf-{role.value}",
                    path=_SKILLS_ROOT / role.value / "SKILL.md",
                    description=f"Classic werewolf rules for the {role.value} role.",
                ),
            ),
        )

    def get_prompt_builder(self) -> PromptBuilder:
        """Resolve the Prompt Builder owned by the configured Policy."""
        return self.policy.prompt_builder.build
