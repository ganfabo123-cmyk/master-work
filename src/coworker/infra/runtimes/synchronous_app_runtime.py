"""Domain-neutral synchronous multi-Agent State transition loop."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...core.base_environment import Environment
    from ...core.base_state import State
    from ..session.app_session import AppSession


class SynchronousAppRuntime:
    """Execute one complete synchronous App without knowing its domain."""

    def run(self, environment: Environment, session: AppSession[Any]) -> State:
        state = session.state
        while not state.is_terminal:
            environment.dispatch_events(environment.before_cycle(state))
            actions: dict[str, Any] = {}
            for agent in environment.select_agents(state):
                action = environment.act(agent, environment.observe(state, agent))
                if action is not None:
                    actions[action.actor] = action
            if not environment.ready_to_step(state, actions):
                raise RuntimeError("Collected Actions are not ready for a synchronous State transition")
            resolved = environment.resolve_collected_actions(state, actions)
            old_state = deepcopy(state)
            state = environment.step(state, resolved)
            state = environment.after_transition(old_state, resolved, state)
            session.state = state
            environment.state = state
            environment.dispatch_events(environment.build_events(old_state, resolved, state))
            session.persist()
        return state
