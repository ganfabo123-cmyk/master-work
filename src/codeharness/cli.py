"""Interactive terminal entry point for CodeHarness."""

from __future__ import annotations

import importlib
import os
import pkgutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from . import agents as agents_package
from .agents import Agent
from .llm import OpenAICompatibleClient
from .models import Message, Task
from .runtime import AgentRuntime


def main() -> None:
    agent = _select_agent()
    runtime = AgentRuntime(traces_root=Path("traces"))
    session_id = runtime.start_session(agent=agent, task=Task("Interactive CodeHarness session"))
    history: list[Message] = []
    is_first_turn = True

    print(f"CodeHarness · {agent.name}")
    print("输入问题开始对话；输入 exit 或 quit 退出。")
    try:
        while True:
            try:
                content = input("\nYou › ").strip()
            except EOFError:
                break
            if not content:
                continue
            if content.lower() in {"exit", "quit"}:
                break

            task = Task(content)
            if is_first_turn:
                history.extend(agent.initial_messages(task))
            else:
                history.append(_user_message(agent, task))
            try:
                output = runtime.run_turn(
                    agent=agent,
                    task=task,
                    session_id=session_id,
                    messages=history,
                    record_initial_messages=is_first_turn,
                )
            except Exception as error:
                print(f"\nError: {error}")
                continue

            answer = _render_output(output)
            history.append(Message("assistant", answer))
            print(f"\n{agent.name} › {answer}")
            is_first_turn = False
    except KeyboardInterrupt:
        print()
    finally:
        runtime.finish_session(session_id, "completed")
        print(f"Trace: traces/{session_id}")


def _select_agent() -> Agent:
    agent_types = _discover_agent_types()
    if not agent_types:
        raise RuntimeError("No Agent classes were discovered in codeharness.agents.")
    if len(agent_types) == 1:
        selected = agent_types[0]
    else:
        print("Available agents:")
        for index, agent_type in enumerate(agent_types, start=1):
            print(f"  {index}. {agent_type.__name__}")
        selected = agent_types[_read_agent_index(len(agent_types))]
    return selected(OpenAICompatibleClient.from_environment(), os.getenv("CODEHARNESS_MODEL", "deepseek-v4-flash"))


def _discover_agent_types() -> list[type[Agent]]:
    for module in pkgutil.iter_modules(agents_package.__path__, f"{agents_package.__name__}."):
        if not module.name.rsplit(".", 1)[-1].startswith("_"):
            importlib.import_module(module.name)
    return sorted(Agent.__subclasses__(), key=lambda agent_type: agent_type.__name__)


def _read_agent_index(count: int) -> int:
    while True:
        raw = input("Select agent › ").strip()
        if raw.isdigit() and 1 <= int(raw) <= count:
            return int(raw) - 1
        print(f"Enter a number from 1 to {count}.")


def _user_message(agent: Agent, task: Task) -> Message:
    messages = agent.initial_messages(task)
    user_messages = [message for message in messages if message.role == "user"]
    if len(user_messages) != 1:
        raise ValueError(f"Agent '{agent.name}' must build exactly one user message per interactive turn.")
    return user_messages[0]


def _render_output(output: BaseModel) -> str:
    values: dict[str, Any] = output.model_dump()
    if len(values) == 1:
        return str(next(iter(values.values())))
    return output.model_dump_json(indent=2)
