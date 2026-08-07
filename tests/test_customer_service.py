from codeharness.agents.customer_service import CustomerServiceAgent
from codeharness.tools import search_customer_knowledge


def test_knowledge_tool_reads_markdown() -> None:
    assert "七天无理由退货" in search_customer_knowledge("退货政策")


def test_customer_service_agent_declares_its_own_capabilities() -> None:
    agent = CustomerServiceAgent("test")
    assert agent.prompt_builder.__name__ == "build_customer_service_prompt"
    assert agent.tools == (search_customer_knowledge,)
    assert [skill.name for skill in agent.skills] == ["customer-service"]
