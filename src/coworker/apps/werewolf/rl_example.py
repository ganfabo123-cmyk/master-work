"""正式狼人杀 RL 流程的最小调用示例。

具体职责已经分离到正式模块：

- ``state.py`` 保存 State；
- ``observation.py`` 定义 Agent 可见的 Observation；
- ``policy.py`` 和 ``agent.py`` 完成 Policy 决策；
- ``action.py`` 定义模型能够选择的 Action；
- ``environment.py`` 实现 ``observe()``、``act()``、``step()``并编排完整循环。

``WerewolfEnvironment.run()`` 中的核心过程现在是：

    while state.phase is not Phase.FINISHED:
        actions = {}
        for agent in actors:
            observation = environment.observe(state, agent)
            action = environment.act(agent, observation)
            if action is not None:
                actions[action.actor] = action
        state = environment.step(state, actions)

即：

    State → Observation → Policy → Action → Environment → New State
          → New Observation → Policy → Next Action → Environment → ...
"""

from __future__ import annotations

from ...core.models import AgentResult, Task
from ...infra.runtimes import SessionRuntime
from .environment import WerewolfEnvironment, WerewolfWorkflowConfig


def run_werewolf_rl(
    environment: WerewolfEnvironment,
    *,
    task: Task,
    session_id: str | None = None,
    config: WerewolfWorkflowConfig | None = None,
) -> AgentResult:
    """Run the formal Werewolf Environment through its standard RL loop."""
    return SessionRuntime(trace=environment.trace).run(
        environment,
        task=task,
        session_id=session_id,
        config=config,
    )


__all__ = ["run_werewolf_rl"]
