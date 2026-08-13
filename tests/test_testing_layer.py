from pathlib import Path
from tempfile import TemporaryDirectory

from coworker.core.models import Message, ModelResult, ToolCall
from coworker.testing import ScenarioRunner, ScriptedLLMClient, ScriptedLLMError, ScriptedTurn


def fixed_result(call_id: str, tool: str) -> ModelResult:
    return ModelResult(
        raw_content="",
        tool_calls=(ToolCall(call_id, tool, {"value": call_id}),),
        model="scripted",
        finish_reason="tool_calls",
    )


def test_scripted_client_replays_and_records_fixed_responses() -> None:
    turns = (
        ScriptedTurn("first", fixed_result("call-1", "act"), "scripted", ("act",)),
        ScriptedTurn("second", fixed_result("call-2", "finish"), required_tools=("finish",)),
    )
    client = ScriptedLLMClient(turns)
    first = client.generate(
        model="scripted",
        messages=(Message("user", "one"),),
        tools=[{"name": "act", "parameters": {}}],
    )
    second = client.generate(
        model="scripted",
        messages=(Message("user", "two"),),
        tools=[{"type": "function", "function": {"name": "finish"}}],
    )
    client.assert_complete()
    assert first.tool_calls[0].id == "call-1"
    assert second.tool_calls[0].id == "call-2"
    assert tuple(request.tool_names for request in client.requests) == (("act",), ("finish",))


def test_scripted_client_reports_divergence_and_unconsumed_turns() -> None:
    client = ScriptedLLMClient(
        (ScriptedTurn("expected", fixed_result("call-1", "act"), required_tools=("act",)),)
    )
    try:
        client.generate(model="scripted", messages=(), tools=[])
    except ScriptedLLMError as error:
        assert "missing required tools" in str(error)
    else:
        raise AssertionError("tool divergence must fail")

    untouched = ScriptedLLMClient(
        (ScriptedTurn("remaining", fixed_result("call-2", "finish")),)
    )
    try:
        untouched.assert_complete()
    except ScriptedLLMError as error:
        assert "remaining" in str(error)
    else:
        raise AssertionError("unconsumed script must fail")


def test_scenario_runner_owns_workspace_and_only_injects_client() -> None:
    seen: dict[str, object] = {}

    def execute(client: ScriptedLLMClient, workspace: Path) -> str:
        seen["client"] = client
        seen["workspace_exists"] = workspace.is_dir()
        result = client.generate(
            model="scripted",
            messages=(Message("user", "scenario"),),
            tools=[{"name": "finish"}],
        )
        return result.tool_calls[0].name

    def verify(value: str, client: ScriptedLLMClient, workspace: Path) -> None:
        assert value == "finish"
        assert client.consumed == 1
        assert workspace.is_dir()

    result = ScenarioRunner.run(
        name="minimal",
        turns=(ScriptedTurn("finish", fixed_result("call", "finish")),),
        execute=execute,
        verify=verify,
    )
    assert result.name == "minimal"
    assert result.value == "finish"
    assert result.turn_count == 1
    assert seen == {"client": seen["client"], "workspace_exists": True}


def test_scenario_runner_can_preserve_an_explicit_workspace() -> None:
    with TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "artifacts"
        result = ScenarioRunner.run(
            name="preserved",
            turns=(),
            execute=lambda _client, path: path,
            workspace=workspace,
        )
        assert result.value == workspace
        assert workspace.is_dir()
