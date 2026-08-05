"""Interactive terminal entry point for CodeHarness."""

from __future__ import annotations

import argparse
import importlib
import os
import pkgutil
from pathlib import Path
from . import agents as agents_package
from .agents import Agent
from .llm import OpenAICompatibleClient
from .models import Message, Task
from .orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(prefix_chars="-/")
    parser.add_argument("/resume", "--resume", dest="resume", metavar="SESSION_ID", help="Resume an existing trace session.")
    args = parser.parse_args()
    orchestrator = Orchestrator(traces_root=Path("traces"))
    if args.resume:
        session_agents = orchestrator.session_agents(args.resume)
        if len(session_agents) != 1:
            raise RuntimeError(f"CLI can resume exactly one-Agent sessions; found: {session_agents}")
        agent = _select_agent(expected_name=session_agents[0])
        session_id = args.resume
        history = list(orchestrator.resume_session(session_id=session_id, agent=agent))
        is_first_turn = False
    else:
        agent = _select_agent()
        session_id = orchestrator.start_session(agent=agent, task=Task("Interactive CodeHarness session"))
        history = []
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
                output = orchestrator.run_turn(
                    agent=agent,
                    task=task,
                    session_id=session_id,
                    messages=history,
                    record_initial_messages=is_first_turn,
                )
            except Exception as error:
                print(f"\nError: {error}")
                continue

            answer = str(output.content or "")
            history.append(Message("assistant", answer))
            print(f"\n{agent.name} › {answer}")
            is_first_turn = False
    except KeyboardInterrupt:
        print()
    finally:
        orchestrator.finish_session(session_id, "completed")
        print(f"Trace: traces/{session_id}")


def _select_agent(expected_name: str | None = None) -> Agent:
    agent_types = _discover_agent_types()
    if not agent_types:
        raise RuntimeError("No Agent classes were discovered in codeharness.agents.")
    client = OpenAICompatibleClient.from_environment()
    model = os.getenv("CODEHARNESS_MODEL", "deepseek-v4-flash")
    candidates = [agent_type(client, model) for agent_type in agent_types]
    if expected_name is not None:
        for candidate in candidates:
            if candidate.name == expected_name:
                return candidate
        raise RuntimeError(f"No installed Agent matches resumed session agent: {expected_name}")
    if len(candidates) == 1:
        return candidates[0]
    else:
        print("Available agents:")
        for index, candidate in enumerate(candidates, start=1):
            print(f"  {index}. {candidate.name}")
        return candidates[_read_agent_index(len(candidates))]


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
