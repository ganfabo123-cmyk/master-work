from codeharness.agents.customer_service import CustomerServiceAgent
from codeharness.llm import DemoLLMClient
from codeharness.tools import CustomerServiceTools
from codeharness.tools import search_customer_knowledge


def test_knowledge_tool_reads_markdown() -> None:
    assert "七天无理由退货" in search_customer_knowledge("退货政策")


def test_customer_service_agent_declares_its_own_capabilities() -> None:
    agent = CustomerServiceAgent(DemoLLMClient(), "test")
    assert agent.prompt_builder.__name__ == "build"
    assert len(agent.tools) == 1
    assert isinstance(agent.tools[0], CustomerServiceTools)
    assert agent.tools[0].agent_name == "customer-service"
    assert [function.__name__ for function in agent.tool_functions()] == ["search_customer_knowledge"]
    assert [skill.name for skill in agent.skills] == ["customer-service"]
