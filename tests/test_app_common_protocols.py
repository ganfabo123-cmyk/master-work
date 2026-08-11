from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from coworker.core import ActionEnvelope, AppEvent, EventDelivery, Observation
from coworker.core.models import ToolCall
from coworker.infra.events import RoomEventDispatcher
from coworker.infra.runtimes import SynchronousAppRuntime


def test_action_envelope_keeps_protocol_metadata_separate_from_payload() -> None:
    observation = Observation("obs-1", "task-1", "session-1")
    action = ActionEnvelope(
        "agent-1:call-1", "agent-1", "submit", {"value": 3},
        ToolCall("call-1", "submit", {"value": 3}), observation,
    )

    assert action.message_id == action.action_id
    assert action.payload == {"value": 3}
    assert action.tool_call.name == action.name


class RecordingRoom:
    def __init__(self) -> None:
        self.messages = []

    def send(self, message: object) -> None:
        self.messages.append(message)


def test_room_event_dispatcher_separates_event_fact_from_delivery() -> None:
    room = RecordingRoom()
    event = AppEvent("event-1", "phase_changed", "engine", "next phase")
    delivery = EventDelivery("event-1", "public", "agent-2", private=True)

    RoomEventDispatcher().dispatch((event,), (delivery,), rooms={"public": room})

    assert len(room.messages) == 1
    assert room.messages[0].name == "engine"
    assert room.messages[0].at == "agent-2"
    assert room.messages[0].txt == "next phase"


@dataclass
class LoopState:
    value: int = 0

    @property
    def is_terminal(self) -> bool:
        return self.value == 1


class RecordingSession:
    def __init__(self) -> None:
        self.state = LoopState()
        self.persisted = 0

    def persist(self) -> None:
        self.persisted += 1


class MinimalEnvironment:
    def __init__(self) -> None:
        self.state = LoopState()
        self.events: list[str] = []

    def before_cycle(self, state: LoopState) -> tuple[str, ...]:
        return ("before",)

    def dispatch_events(self, events: tuple[str, ...]) -> None:
        self.events.extend(events)

    def select_agents(self, state: LoopState) -> tuple[object, ...]:
        return (SimpleNamespace(name="agent-1"),)

    def observe(self, state: LoopState, agent: object) -> object:
        return object()

    def act(self, agent: object, observation: object) -> object:
        return SimpleNamespace(actor="agent-1")

    def ready_to_step(self, state: LoopState, actions: object) -> bool:
        return actions == {"agent-1": actions["agent-1"]}

    def resolve_collected_actions(self, state: LoopState, actions: object) -> object:
        return actions

    def step(self, state: LoopState, actions: object) -> LoopState:
        return LoopState(1)

    def after_transition(self, old_state: LoopState, actions: object, new_state: LoopState) -> LoopState:
        return new_state

    def build_events(self, old_state: LoopState, actions: object, new_state: LoopState) -> tuple[str, ...]:
        return ("after",)


def test_synchronous_runtime_owns_collection_transition_events_and_persistence() -> None:
    environment = MinimalEnvironment()
    session = RecordingSession()

    state = SynchronousAppRuntime().run(environment, session)

    assert state.is_terminal
    assert session.state is state
    assert session.persisted == 1
    assert environment.events == ["before", "after"]
