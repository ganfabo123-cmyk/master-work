from __future__ import annotations

from ...core.base_policy import BasePolicy
from ...core.models import Message, Prompt, Task
from ...infra.prompt import BasePromptBuilder


class HaishanPromptBuilder(BasePromptBuilder):
    def __init__(self, role_name: str) -> None:
        self.role_name = role_name

    def build(self, task: Task) -> Prompt:
        return Prompt(
            messages=(Message("developer", (
                f"你扮演《海山仙馆之寻》中的{self.role_name}。"
                "只根据当前 Observation 中授权的信息行动。"
                "必须选择当前唯一可用的 Action Tool；工具只表达意图。"
                "不得声称看到了其他角色的私密剧本、未公开线索或未公开投票。"
            )), Message("user", str(getattr(task, "description", task)))),
        )


class HaishanPolicy(BasePolicy):
    """App-local policy marker; model execution remains owned by the public runtime."""

    def build(self, task: Task) -> Prompt:
        return self.prompt_builder.build(task)
