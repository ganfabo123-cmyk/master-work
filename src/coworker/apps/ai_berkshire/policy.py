"""AI Berkshire analyst and team-lead Policies."""

from __future__ import annotations

from datetime import datetime

from ...core.base_policy import BasePolicy
from ...core.models import Message, Prompt, Task
from ...infra.prompt import BasePromptBuilder
from ...infra.tools import BaseAgentTools
from .state import InvestmentRole


ROLE_GUIDANCE = {
    InvestmentRole.BUSINESS: "以段永平视角研究商业模式、用户价值、收入结构、护城河和可持续竞争优势，并主动寻找商业模式失效的反证。",
    InvestmentRole.FINANCIAL: "以巴菲特视角研究近年财务质量、现金流、资产负债表、估值和安全边际；不得心算或编造缺失数据。",
    InvestmentRole.INDUSTRY: "以芒格视角研究行业结构、竞争格局、产业链价值分配、替代威胁和非共识风险。",
    InvestmentRole.RISK: "以李录视角研究管理层、治理、资本配置、监管、周期风险和十年后的长期确定性。",
}


class InvestmentPromptBuilder(BasePromptBuilder):
    def __init__(self, *, agent_name: str, role: InvestmentRole) -> None:
        self.agent_name = agent_name
        self.role = role

    def build(self, task: Task) -> Prompt:
        now = datetime.now().astimezone()
        current_time = now.isoformat(timespec="seconds")
        timezone_name = now.tzname() or str(now.utcoffset() or "unknown")
        if self.role is InvestmentRole.LEAD:
            duty = "综合 Observation 中四份研究产物，形成最终投资备忘录。必须比较观点冲突，不能只是拼接报告。"
            action_rule = "必须调用 submit_investment_memo，并完整引用四个 source_artifact_ids。"
        else:
            duty = ROLE_GUIDANCE[self.role]
            action_rule = "调用 3 到 4 次 search_web 获取最新资料后立即调用 submit_analysis；必须填写 title、thesis、content、score、confidence、citations 全部字段，citations 只能填写搜索结果中真实出现过的 URL。"
        system = f"""# AI Berkshire 多 Agent 投研团队

你是 {self.agent_name}。{duty}

# 运行时间

- 当前日期时间：{current_time}
- 当前时区：{timezone_name}
- 用户使用“今天、本月、8月”等相对时间时，必须以上述运行时间解释；不得自行猜测年份。

# 研究纪律

- 只把 Observation 和 Task 中提供的资料视为已知事实；不得伪造实时行情、财报数字或来源。
- 明确区分事实、推断与未知；资料不足时降低 confidence 并直接说明缺口。
- 信息丰富度评级影响研究策略：A 级重视反面检验，B 级标注推算置信度，C 级聚焦第一性原理问题。
- 报告应包含关键判断、支持证据、反方观点、风险和结论。
- 优先搜索公司公告、交易所披露和公司官网，再使用高质量行业与新闻来源；注明资料日期。
- 本系统输出仅供研究，不构成投资建议。
- {action_rule}
"""
        return Prompt((Message("developer", system), Message("user", task.description)))


class InvestmentPolicy(BasePolicy):
    def __init__(self, *, agent_name: str, role: InvestmentRole) -> None:
        super().__init__(prompt_builder=InvestmentPromptBuilder(agent_name=agent_name, role=role), tools=BaseAgentTools(agent_name))
