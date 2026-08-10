"""Policy for werewolf instruction discussion participants."""

from __future__ import annotations

from ...core.base_policy import BasePolicy
from ...core.models import Message, Prompt, Task
from ...infra.prompt import BasePromptBuilder
from ...infra.tools import BaseAgentTools


class WerewolfInstructionPromptBuilder(BasePromptBuilder):
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    def build(self, task: Task) -> Prompt:
        system = f"""# 狼人杀专家讨论会

你是 {self.agent_name}，与另外七名参与者共同编写一份实用、连贯的狼人杀教程。

# 工作要求

- 先阅读公共讨论，并调用 speak 与其他参与者交流策略、经验、分歧和改进建议。
- 综合公共讨论后，调用 submit_my_instruction 提交你负责的教程内容。
- instruction 本身必须像教程正文，不能带“{self.agent_name} 的心得”、章节署名或其他参与者标签。
- 内容应当可以和其他参与者的正文直接拼接，避免开场寒暄和提交说明。
- 提交后用一句话结束本回合。
"""
        return Prompt((Message("developer", system), Message("user", task.description)))


class WerewolfInstructionPolicy(BasePolicy):
    def __init__(self, agent_name: str) -> None:
        super().__init__(prompt_builder=WerewolfInstructionPromptBuilder(agent_name), tools=BaseAgentTools(agent_name))
