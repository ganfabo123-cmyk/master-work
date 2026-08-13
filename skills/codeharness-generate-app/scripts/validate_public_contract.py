from __future__ import annotations

import argparse
import inspect
from pathlib import Path
import sys


EXPECTED_SIGNATURES = {
    "BaseAgentTools.__init__": ("self", "agent_name"),
    "BaseAction.__init__": ("self", "tools"),
    "BasePolicy.__init__": ("self", "prompt_builder", "tools"),
    "Environment.__init__": ("self", "agents", "state", "observation", "trace"),
    "Environment.execute_tool_action": (
        "self",
        "agent",
        "observation",
        "tool_call",
        "message_sink",
    ),
    "Environment.reject_tool_action": (
        "self",
        "agent",
        "observation",
        "tool_call",
        "reason",
        "message_sink",
    ),
    "SessionRuntime.run": (
        "self",
        "environment",
        "task",
        "session_id",
        "on_session_opened",
        "environment_options",
    ),
    "SynchronousAppRuntime.run": ("self", "environment", "session"),
    "RoomEventDispatcher.dispatch": ("self", "events", "deliveries", "rooms"),
}


def parameter_names(target: object) -> tuple[str, ...]:
    return tuple(inspect.signature(target).parameters)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the source-free CodeHarness public App generation contract."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()

    from coworker.core.base_action import BaseAction
    from coworker.core.base_environment import Environment
    from coworker.core.base_policy import BasePolicy
    from coworker.infra.events import RoomEventDispatcher
    from coworker.infra.runtimes import SessionRuntime, SynchronousAppRuntime
    from coworker.infra.tools import BaseAgentTools

    targets = {
        "BaseAgentTools.__init__": BaseAgentTools.__init__,
        "BaseAction.__init__": BaseAction.__init__,
        "BasePolicy.__init__": BasePolicy.__init__,
        "Environment.__init__": Environment.__init__,
        "Environment.execute_tool_action": Environment.execute_tool_action,
        "Environment.reject_tool_action": Environment.reject_tool_action,
        "SessionRuntime.run": SessionRuntime.run,
        "SynchronousAppRuntime.run": SynchronousAppRuntime.run,
        "RoomEventDispatcher.dispatch": RoomEventDispatcher.dispatch,
    }
    errors: list[str] = []
    for label, expected in EXPECTED_SIGNATURES.items():
        actual = parameter_names(targets[label])
        if actual != expected:
            errors.append(f"{label}: expected {expected}, got {actual}")

    env_example = args.repo.resolve() / ".env.example"
    if not env_example.exists():
        errors.append(f"missing required public configuration contract: {env_example}")
    else:
        text = env_example.read_text(encoding="utf-8")
        required = ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL")
        missing = tuple(name for name in required if f"{name}=" not in text)
        if missing:
            errors.append(f".env.example is missing required names: {missing}")

    if errors:
        print("Public App contract validation failed:")
        for error in errors:
            print(f"- {error}")
        print("Stop generation and update this Skill contract; do not inspect implementation source.")
        return 1
    print("Public App contract validation passed.")
    print("Model configuration source: .env.example (DEEPSEEK_*; PRO_API/PRO_MODEL aliases if declared).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
