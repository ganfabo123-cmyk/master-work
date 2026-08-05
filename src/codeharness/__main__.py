from pathlib import Path

from .agents import Agent
from .llm import DemoLLMClient
from .models import Task
from .prompts.learning import LearningPromptBuilder
from .runtime import AgentRuntime


def main() -> None:
    agent = Agent(
        name="learning-agent",
        model="demo-model",
        llm=DemoLLMClient(),
        prompt_builder=LearningPromptBuilder().build,
    )
    result = AgentRuntime(traces_root=Path("traces")).run(
        agent=agent,
        task=Task("Explain the task after inspecting it."),
    )
    print(f"{result.status}: {result.content}\ntrace: traces/{result.session_id}")


if __name__ == "__main__":
    main()
