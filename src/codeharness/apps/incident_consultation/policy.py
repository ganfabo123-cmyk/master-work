"""Policies for the incident-consultation experts."""

from __future__ import annotations

from ...core.base_policy import BasePolicy
from ...core.models import Message, Prompt, Task
from ...infra.prompt import BasePromptBuilder
from ...infra.tools import BaseAgentTools
from .state import ExpertRole


class IncidentPromptBuilder(BasePromptBuilder):
    def __init__(self, *, expert_name: str, role: ExpertRole) -> None:
        self.expert_name = expert_name
        self.role = role

    def build(self, task: Task) -> Prompt:
        if self.role is ExpertRole.LEAD:
            duty = "综合三位证据专家已经提交的 Findings，给出一个最终根因诊断。"
            action_rule = "必须调用 submit_final_diagnosis；只能引用 Findings 中出现过的 evidence_id。"
        else:
            duty = f"你是 {self.role.value} 证据专家，只分析当前 Observation 提供的本类证据。"
            action_rule = "必须调用 submit_finding；不得声称看过其他证据类型或伪造证据 ID。"
        system = f"""# 软件故障多专家会诊

你是 {self.expert_name}。
{duty}

# 规则

- 只依据当前 Observation 中的结构化事实。
- 数据集没有显式官方 ground truth，不得把猜测表述成已确认事实。
- {action_rule}
- confidence 必须是 0 到 100 的整数。
- 工具提交后，用一句话结束本回合。
"""
        return Prompt((Message("developer", system), Message("user", task.description)))


class IncidentPolicy(BasePolicy):
    def __init__(self, *, expert_name: str, role: ExpertRole) -> None:
        super().__init__(prompt_builder=IncidentPromptBuilder(expert_name=expert_name, role=role), tools=BaseAgentTools(expert_name))
