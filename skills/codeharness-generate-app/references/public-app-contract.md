# CodeHarness first-stage public App contract

This document is the source contract for generation. Do not inspect platform implementations to supplement it.

Run `scripts/validate_public_contract.py --repo <repository-root>` before using this contract. A failing probe means this reference is stale; stop instead of guessing or opening implementation source.

## Model configuration

Read repository-root `.env.example`, never `.env`. Use exactly the names declared there. The current contract is:

```text
DEEPSEEK_API_KEY       required credential
DEEPSEEK_MODEL         model name
DEEPSEEK_BASE_URL      OpenAI-compatible base URL
PRO_API                optional API-key alias
PRO_MODEL              optional model-name alias
```

Resolve `DEEPSEEK_API_KEY` before `PRO_API` and `DEEPSEEK_MODEL` before `PRO_MODEL`. Do not invent `OPENAI_API_KEY`, `OPENAI_BASE_URL`, or `COWORKER_MODEL` unless a future `.env.example` declares them. Accept explicit `llm=` and `model=` runtime injection for tests and embedding. Never log or persist credential values.

## Imports

Use only these public paths for platform types:

```python
from ...core.action_envelope import ActionEnvelope
from ...core.base_action import Action, BaseAction, ToolAction
from ...core.base_agent import Agent, PromptBuilder
from ...core.base_environment import ActionManager, Environment
from ...core.base_observation import Observation
from ...core.base_policy import BasePolicy
from ...core.base_state import State
from ...core.events import AppEvent, EventDelivery
from ...core.models import AgentResult, Message, Prompt, Task, ToolCall
from ...core.session import SessionContext
from ...infra.client import LLMClient, OpenAICompatibleClient
from ...infra.events import RoomEventDispatcher
from ...infra.prompt import BasePromptBuilder
from ...infra.room import AgentProfile, Room
from ...infra.runtimes import SessionRuntime, SynchronousAppRuntime
from ...infra.runtimes.room_runtime import RoomRuntime
from ...infra.session import AppSession, SessionManager
from ...infra.tools import BaseAgentTools
```

Use `StateStore` from `...infra` when opening or restoring App State.

## State

Subclass dataclass `State(task_id: str, session_id: str)`. Implement:

```python
@classmethod
def initial(cls, task_id: str, session_id: str, ...) -> Self: ...

@property
def is_terminal(self) -> bool: ...

def to_dict(self) -> dict[str, object]: ...

@classmethod
def from_dict(cls, data: dict[str, object]) -> Self: ...
```

Persist JSON-compatible values. Preserve `consumed_action_ids` and terminal result. Transition using a copied or deserialized State, never the input instance.

## Observation

Subclass `Observation(observation_id, task_id, session_id)` and store:

- one `Message("user", json_payload)` containing only the actor-visible State projection;
- `available_tool_names: tuple[str, ...]`;
- the actor's authorized `Room` resources.

## Action

Subclass `BaseAgentTools`; call `super().__init__(agent_name)`, and expose `tool_functions()`. Tool functions use typed parameters and `Annotated[..., pydantic.Field(description=...)]`. They return acknowledgement text only and have no side effects.

Subclass `BaseAction`, initialize it with `super().__init__(tools=tools)`, and map every tool name to `Action(name, ToolAction)` in `tool_action_map`.

Create an App payload dataclass and use `ActionEnvelope[Payload]` with:

```text
action_id = actor + ":" + tool_call.id
actor
name
payload
tool_call
observation
```

## ActionManager

Implement all methods:

```python
resolve_action(response) -> ActionEnvelope | None
validate_action(action, state) -> tuple[bool, str]
available_actions(state, agent) -> tuple[str, ...]
resolve_actions(state, actions) -> app_step_input
```

`resolve_action` parses `(actor_name, assistant_message, observation)`, selects an allowed Tool Call, parses JSON arguments, and returns `None` on malformed input. Validation returns `(True, "")` or `(False, specific corrective reason)` and checks phase, actor, parameters, visibility/ownership, and consumed ID.

## Environment and synchronous runtime

Subclass `Environment`. Declare unique `session_mode` and `entry_agent`. Provide:

```python
@classmethod
def from_environment(cls, *, traces_root=Path("traces"), room_data_root=Path("room/data"), max_turns=5): ...

def run(self, *, task, session_id=None, on_session_opened=None, **options) -> AgentResult:
    return SessionRuntime(trace=self.session.trace).run(...)

def run_session(self, *, task: Task, context: SessionContext, **options) -> AgentResult: ...
def select_agents(self, state: State) -> tuple[Agent, ...]: ...
def observe(self, state: State, agent: Agent) -> Observation: ...
def act(self, agent: Agent, observation: Observation) -> ActionEnvelope | None: ...
def ready_to_step(self, state: State, actions: object) -> bool: ...
def step(self, state: State, action: object) -> State: ...
def build_events(self, old_state: State, actions: object, new_state: State) -> tuple[AppEvent, ...]: ...
def dispatch_events(self, events: tuple[AppEvent, ...]) -> None: ...
def orchestrate_agents(self) -> AgentResult: ...
```

Initialize base Environment with `super().__init__(agents, state, observation, trace=trace)`. A lazy `from_environment()` may use a harmless bootstrap State/Observation, but it must replace them with the active AppSession resources before execution. Own `RoomRuntime`, `SynchronousAppRuntime`, `RoomEventDispatcher`, the active `AppSession`, current Task, and ActionManager.

Use these exact runtime calls:

```python
result = SessionRuntime(trace=session_manager.trace).run(
    environment,
    task=task,
    session_id=session_id,
    on_session_opened=on_session_opened,
    **options,
)

runtime = SynchronousAppRuntime()
final_state = runtime.run(environment, active_app_session)
```

The synchronous runtime repeatedly calls:

```text
before_cycle -> dispatch_events -> select_agents -> observe -> act
-> ready_to_step -> resolve_collected_actions -> step
-> after_transition -> build_events -> dispatch_events -> persist
```

`act` calls `RoomRuntime.run_turn` with authorized ROOM, Agent name, Task, session ID, Agent incremental context, the Observation state Message as events, and available tool names. Resolve the returned assistant Message into an Action.

In `step`, validate every Action. Resolve its actor to the active Agent and context. Use the exact helpers:

```python
reject_tool_action(
    agent=agent,
    observation=envelope.observation,
    tool_call=envelope.tool_call,
    reason=reason,
    message_sink=context.append_turn_messages,
)

execute_tool_action(
    agent=agent,
    observation=envelope.observation,
    tool_call=envelope.tool_call,
    message_sink=context.append_turn_messages,
)
```

The ROOM turn records the assistant Tool Call; the Environment helper appends the matching Tool Result. Verify both messages share the Tool Call ID in the same Agent context. After a valid helper call, apply domain effects and mark consumed IDs. Tool execution itself does not apply domain effects.

## Session

Use `SessionManager` for Trace and ROOM resources. Create or restore an `AppSession` containing:

```text
session_id, state, agents, contexts, rooms, state_store, state_kind
```

Register Agent profiles, create/invite declared ROOM participants, create one incremental context per Agent, save initial State, and restore State with the App State class on resume. `AppSession.persist()` is called after each transition by the synchronous runtime.

Use these exact resource calls:

```python
store = StateStore(self.session.trace.root.parent / "state" / "data")
room = self.session.create_room(room_id, session_id=session_id)
room = self.session.resume_room(room_id, session_id=session_id)
self.session.trace.update_session_metadata(session_id, public_room_id=room.room_id, app_room_id=room.room_id)
room.register(AgentProfile(name=engine_name, introduction=engine_description, role="environment"))
room.invite(engine_name)
self.room_runtime.register_agent(agent, AgentProfile(name=name, introduction=introduction, role=role))
self.room_runtime.invite_agents(room, tuple(agent_names), session_id=session_id)
context = self.room_runtime.open_incremental_context(agent_name=name, task=task, session_id=session_id)
state = store.restore(session_id, state_kind, AppState)
active = AppSession(session_id, state, agents, contexts, rooms, store, state_kind)
active.persist()
```

Open resources in this order:

```text
SessionRuntime creates/resumes Trace Session
-> resolve injected or .env.example-declared model configuration
-> construct Agents and register profiles in RoomRuntime
-> create/resume public and private ROOMs
-> register/invite Environment and authorized Agents
-> open one incremental context per Agent
-> create/restore StateStore State
-> construct AppSession
-> update Trace metadata
-> persist a newly created AppSession
-> SynchronousAppRuntime.run(environment, active_session)
```

On resume, use the same stable ROOM IDs, restore the App State class, reopen Agent contexts, and do not emit new IDs for already-projected business facts.

## Events and ROOM

Build immutable `AppEvent(event_id, event_type, source, content, metadata)` facts. `AppEvent.content` is a string; serialize structured content with deterministic JSON such as `json.dumps(value, ensure_ascii=False, sort_keys=True)`. Deliver with `EventDelivery(event_id, room_key, recipient="all" or actor tuple, private=bool)` using:

```python
dispatcher.dispatch(events, deliveries, rooms=active_session.rooms)
```

Do not assume the dispatcher deduplicates stable event IDs. Persist `emitted_event_ids` (or an equivalent App-owned delivery ledger), filter already-emitted facts before dispatch, then persist the updated ledger after successful delivery. `content` carries the complete auditable Action, artifact, or settlement result required by the blueprint.

Create initial public rules/role cards and private full scripts as stable events. Create private clue-delivery events when an actor enters a search phase. A public clue event contains only clues explicitly revealed; keep reveal/withhold decisions and unrevealed content private.

## Agent and Policy

Subclass `BasePromptBuilder.build(Task) -> Prompt`, `BasePolicy`, and `Agent`.

```python
policy = AppPolicy(prompt_builder=prompt_builder, tools=policy_tools)
agent = AppAgent(
    name=name,
    model=model,
    llm=llm,
    policy=policy,
    action=action,
    temperature=temperature,
    policy_tools=(policy_tools,),       # only if Policy executes feedback tools
    action_tools=(action_tools,),       # Action-intent tools
)
```

If the App Policy is used as the Agent prompt-builder surface, expose `build(task) -> Prompt` or make it callable. Construct `Prompt(messages=(Message(...), ...))`; do not use undeclared `system=`/`user=` constructor fields. Prompt guides decisions but never replaces validation or State transition rules.

## Discovery

`src/coworker/apps/<app_id>/environment.py` must define exactly one concrete Environment subclass from that module and it must expose `from_environment`. No central registry edit is required.
