from pathlib import Path

from .llm import DemoLLMClient
from .models import AgentSpec, Task
from .runtime import AgentRuntime


def main() -> None:
    result = AgentRuntime(DemoLLMClient(), traces_root=Path("traces")).run(
        agent=AgentSpec("learning-agent", "demo-model", "You are a careful learning assistant."),
        task=Task("Explain the task after inspecting it."),
    )
    print(f"{result.status}: {result.content}\ntrace: traces/{result.session_id}")


if __name__ == "__main__":
    main()
