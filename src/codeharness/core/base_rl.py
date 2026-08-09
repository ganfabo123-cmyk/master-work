"""Standard reinforcement-learning-style execution flow.

Subclass implementation::

    class AppRL(BaseRL):
        def observe(self, state, agent):
            return app_environment.create_observation(state, agent)

        def act(self, agent, observation):
            return agent.run(observation=observation)

        def step(self, state, action):
            return app_environment.step(state, action)

Standard loop::

    rl = AppRL()
    state = initial_state
    while not state.is_terminal:
        agent = select_agent(state)
        observation = rl.observe(state, agent)
        action = rl.act(agent, observation)
        state = rl.step(state, action)

The resulting process is::

    State → Observation → Policy → Action → Environment → New State
          → New Observation → Policy → Next Action → Environment → ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .base_agent import Agent
from .base_observation import Observation
from .base_state import State


class BaseRL(ABC):
    """Connect State, Observation, Policy, Action, and the next State."""

    @abstractmethod
    def observe(self, state: State, agent: Agent) -> Observation:
        """Create the Agent-visible Observation from the current State."""
        raise NotImplementedError

    @abstractmethod
    def act(self, agent: Agent, observation: Observation) -> Any:
        """Apply the Agent's Policy to the Observation and return an Action."""
        raise NotImplementedError

    @abstractmethod
    def step(self, state: State, action: Any) -> State:
        """Apply the Action through the Environment and return the next State."""
        raise NotImplementedError

    def run_step(self, state: State, agent: Agent) -> State:
        """Run one State → Observation → Policy → Action → next State cycle."""
        observation = self.observe(state, agent)
        action = self.act(agent, observation)
        return self.step(state, action)
