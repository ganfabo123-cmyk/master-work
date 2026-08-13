from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any

from ...core.base_agent import Agent
from ...core.base_environment import Environment
from ...core.events import AppEvent, EventDelivery
from ...core.models import AgentResult, Task
from ...core.base_observation import Observation
from ...core.session import SessionContext
from ...infra.events import RoomEventDispatcher
from ...infra import StateStore
from ...infra.client import OpenAICompatibleClient
from ...infra.room import AgentProfile
from ...infra.runtimes import SessionRuntime, SynchronousAppRuntime
from ...infra.runtimes.room_runtime import RoomRuntime
from ...infra.session import AppSession, SessionManager
from .agent import build_agents
from .action import HaishanActionManager, HaishanActionPayload
from ...core.action_envelope import ActionEnvelope
from .data_loader import HaishanMaterialLoader, ROLE_NAMES
from .observation import HaishanObservation, build_visible_payload, state_message
from .state import GamePhase, HaishanXianguanState, ROLE_ORDER


PHASE_AFTER_ACTION = {
    GamePhase.INTRO: GamePhase.PERSON_SEARCH,
    GamePhase.PERSON_SEARCH: GamePhase.PERSON_DISCUSS,
    GamePhase.PERSON_DISCUSS: GamePhase.SCENE_SEARCH,
    GamePhase.SCENE_SEARCH: GamePhase.SCENE_DISCUSS,
    GamePhase.SCENE_DISCUSS: GamePhase.VOTE,
    GamePhase.VOTE: GamePhase.REVEAL,
}

SCORE_RULES = {
    "pan": (("suspect_id", "maid", 6), ("image_location", "water_boat_beside_zhuyun_tower", 2)),
    "ivan": (("suspect_id", "maid", 6), ("image_location", "water_boat_beside_zhuyun_tower", 2)),
    "li": (
        ("suspect_id", "maid", 6),
        ("motive", "family_medical_cost_and_freedom", 1),
        ("image_location", "water_boat_beside_zhuyun_tower", 2),
    ),
    "maid": (("self_is_culprit", True, 8),),
    "butler": (("suspect_id", "maid", 6), ("image_location", "water_boat_beside_zhuyun_tower", 2)),
    "he": (("suspect_id", "maid", 8), ("image_location", "water_boat_beside_zhuyun_tower", 2)),
}

NOT_SCORED_TASKS = {
    "pan": ("隐瞒对道光皇帝的不满",),
    "ivan": ("隐瞒去十三行复制画",),
    "li": ("协助侍女隐瞒调包过程",),
    "maid": ("逃脱潘仕成问责", "隐瞒为李夫人换画"),
    "butler": ("隐瞒寻找道光像",),
    "he": (),
}


class HaishanXianguanEnvironment(Environment):
    session_mode = "jubensha_haishanxianguan"
    entry_agent = "pan"

    def __init__(
        self,
        *,
        traces_root: Path = Path("traces"),
        room_data_root: Path = Path("room/data"),
        max_turns: int = 5,
        material_root: Path = Path("data/jubensha"),
    ) -> None:
        bootstrap_state = HaishanXianguanState.initial("bootstrap", "bootstrap")
        super().__init__(
            agents=(),
            state=bootstrap_state,
            observation=Observation("bootstrap", "bootstrap", "bootstrap"),
            trace=None,
        )
        self.traces_root = traces_root
        self.room_data_root = room_data_root
        self.max_turns = max_turns
        self.material_loader = HaishanMaterialLoader(material_root)
        self.action_manager = HaishanActionManager()
        self.room_runtime: RoomRuntime | None = None
        self.runtime: SynchronousAppRuntime | None = None
        self.event_dispatcher: RoomEventDispatcher | None = None
        self.active_session: Any = None
        self.session: Any = SessionManager(
            traces_root=traces_root,
            room_data_root=room_data_root,
        )
        self.current_task: Task | None = None
        self.state: HaishanXianguanState | None = bootstrap_state
        self.agents: tuple[Agent, ...] = ()

    @classmethod
    def from_environment(
        cls,
        *,
        traces_root: Path = Path("traces"),
        room_data_root: Path = Path("room/data"),
        max_turns: int = 5,
    ) -> "HaishanXianguanEnvironment":
        return cls(
            traces_root=traces_root,
            room_data_root=room_data_root,
            max_turns=max_turns,
        )

    def run(
        self,
        *,
        task: Task,
        session_id: str | None = None,
        on_session_opened: object | None = None,
        **options: object,
    ) -> AgentResult:
        return SessionRuntime(trace=self.session.trace).run(
            self,
            task=task,
            session_id=session_id,
            on_session_opened=on_session_opened,
            **options,
        )

    def run_session(
        self, *, task: Task, context: SessionContext, **options: object
    ) -> AgentResult:
        self.current_task = task
        self._open_or_restore_session(task=task, context=context, options=options)
        if self.runtime is None:
            self.runtime = SynchronousAppRuntime()
        if self.active_session is None:
            raise RuntimeError("an AppSession is required for synchronous execution")
        final_state = self.runtime.run(self, self.active_session)
        return AgentResult(
            status="completed" if final_state.is_terminal else "failed",
            content=final_state.terminal_result or final_state.to_dict(),
            error=None if final_state.is_terminal else "workflow stopped before terminal state",
            session_id=final_state.session_id,
        )

    def _open_or_restore_session(
        self,
        *,
        task: Task,
        context: SessionContext,
        options: dict[str, object],
    ) -> None:
        provided_llm, model = self._resolve_model_configuration(options)
        self.agents = build_agents(llm=provided_llm, model=model)
        self.room_runtime = RoomRuntime(trace=self.session.trace, max_turns=self.max_turns)
        self.event_dispatcher = RoomEventDispatcher()
        store = StateStore(self.session.trace.root.parent / "state" / "data")
        state_kind = self.session_mode
        session_id = context.session_id
        for agent in self.agents:
            self.room_runtime.register_agent(
                agent,
                AgentProfile(
                    name=agent.name,
                    display_name=ROLE_NAMES[agent.name],
                    introduction=f"《海山仙馆之寻》角色：{ROLE_NAMES[agent.name]}",
                    role="player",
                ),
            )
        room_ids = {
            "public": f"haishan-public-{session_id}",
            **{
                f"private:{role}": f"haishan-{role}-{session_id}"
                for role in ROLE_ORDER
            },
        }
        rooms: dict[str, Any] = {}
        for key, room_id in room_ids.items():
            room = (
                self.session.resume_room(room_id, session_id=session_id)
                if context.resumed
                else self.session.create_room(room_id, session_id=session_id)
            )
            room.register(
                AgentProfile(
                    name="haishan-engine",
                    introduction="负责确定性规则校验、阶段转换、复盘和计分。",
                    role="environment",
                )
            )
            room.invite("haishan-engine")
            names = ROLE_ORDER if key == "public" else (key.split(":", 1)[1],)
            self.room_runtime.invite_agents(room, names, session_id=session_id)
            rooms[key] = room
        contexts = {
            role: self.room_runtime.open_incremental_context(
                agent_name=role,
                task=task,
                session_id=session_id,
            )
            for role in ROLE_ORDER
        }
        state = (
            store.restore(session_id, state_kind, HaishanXianguanState)
            if context.resumed
            else HaishanXianguanState.initial(
                task_id=str(getattr(task, "task_id", "haishan-task")),
                session_id=session_id,
            )
        )
        self.active_session = AppSession(
            session_id,
            state,
            {agent.name: agent for agent in self.agents},
            contexts,
            rooms,
            store,
            state_kind,
        )
        self.state = state
        self.session.trace.update_session_metadata(
            session_id,
            public_room_id=rooms["public"].room_id,
            app_room_id=rooms["public"].room_id,
            app_id=self.session_mode,
        )
        if not context.resumed:
            self.active_session.persist()

    @staticmethod
    def _resolve_model_configuration(
        options: dict[str, object],
    ) -> tuple[object, str]:
        provided_llm = options.get("llm")
        model_value = (
            options.get("model")
            or os.getenv("DEEPSEEK_MODEL")
            or os.getenv("PRO_MODEL")
        )
        if not model_value:
            raise RuntimeError(
                "run requires model=..., DEEPSEEK_MODEL, or PRO_MODEL"
            )
        if provided_llm is not None:
            return provided_llm, str(model_value)

        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("PRO_API")
        if not api_key:
            raise RuntimeError(
                "run requires llm=..., DEEPSEEK_API_KEY, or PRO_API"
            )
        base_url = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
        return (
            OpenAICompatibleClient(api_key=api_key, base_url=base_url),
            str(model_value),
        )

    def select_agents(self, state: HaishanXianguanState) -> tuple[Agent, ...]:
        actor = self.action_manager.current_actor(state)
        if actor is None:
            return ()
        return tuple(agent for agent in self.agents if agent.name == actor)

    def before_cycle(self, state: HaishanXianguanState) -> tuple[AppEvent, ...]:
        events: list[AppEvent] = []
        if state.phase is GamePhase.INTRO and not state.introductions:
            events.append(
                AppEvent(
                    event_id=f"{state.session_id}:session-opened",
                    event_type="session_opened",
                    source="haishan-engine",
                    content=json.dumps(
                        {
                            "app": "海山仙馆之寻",
                            "role_order": list(ROLE_ORDER),
                            "role_cards": self.material_loader.public_role_cards().content,
                            "phases": [phase.value for phase in GamePhase],
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    metadata={},
                )
            )
            for role in ROLE_ORDER:
                record = self.material_loader.role_script(role)
                events.append(
                    AppEvent(
                        event_id=f"{state.session_id}:private-script:{role}",
                        event_type="private_script",
                        source="haishan-engine",
                        content=json.dumps(
                            {"role": role, "source": record.source, "content": record.content},
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        metadata={"recipient": role},
                    )
                )
        if state.phase in (GamePhase.PERSON_SEARCH, GamePhase.SCENE_SEARCH):
            actor = self.action_manager.current_actor(state)
            if actor is not None:
                kind = "person" if state.phase is GamePhase.PERSON_SEARCH else "scene"
                assignments = (
                    state.person_clue_assignments
                    if kind == "person"
                    else state.scene_clue_assignments
                )
                records = self.material_loader.clues(kind)
                events.append(
                    AppEvent(
                        event_id=f"{state.session_id}:private-clues:{kind}:{actor}",
                        event_type="private_clues",
                        source="haishan-engine",
                        content=json.dumps(
                            {
                                "role": actor,
                                "clues": {
                                    clue_id: {
                                        "source": records[clue_id].source,
                                        "content": records[clue_id].content,
                                    }
                                    for clue_id in assignments[actor]
                                },
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        metadata={"recipient": actor, "kind": kind},
                    )
                )
        return tuple(events)

    def resolve_collected_actions(
        self, state: HaishanXianguanState, actions: dict[str, object]
    ) -> object:
        return self.action_manager.resolve_actions(state, actions)

    def after_transition(
        self,
        old_state: HaishanXianguanState,
        actions: object,
        new_state: HaishanXianguanState,
    ) -> HaishanXianguanState:
        self.state = new_state
        if self.active_session is not None:
            self.active_session.state = new_state
        return new_state

    def observe(self, state: HaishanXianguanState, agent: Agent) -> HaishanObservation:
        actor = str(agent.name)
        payload = build_visible_payload(state, actor, self.material_loader)
        rooms: tuple[Any, ...] = ()
        if self.active_session is not None:
            public = self.active_session.rooms.get("public")
            private = self.active_session.rooms.get(f"private:{actor}")
            rooms = tuple(room for room in (public, private) if room is not None)
        return HaishanObservation(
            observation_id=f"{state.session_id}:{state.phase.value}:{actor}",
            task_id=state.task_id,
            session_id=state.session_id,
            actor_id=actor,
            state_message=state_message(payload),
            available_tool_names=self.action_manager.available_actions(state, agent),
            rooms=rooms,
        )

    def act(self, agent: Agent, observation: HaishanObservation) -> ActionEnvelope | None:
        if self.room_runtime is None or self.active_session is None or self.current_task is None:
            raise RuntimeError("ROOM runtime and active session must be configured before act()")
        context = self.active_session.contexts[agent.name]
        turn_result = self.room_runtime.run_turn(
            room=observation.rooms[0],
            agent_name=agent.name,
            task=self.current_task,
            session_id=observation.session_id,
            additional_rooms=observation.rooms[1:],
            incremental_context=context,
            events=observation.messages,
            available_tool_names=observation.available_tool_names,
        )
        assistant = getattr(turn_result, "content", turn_result)
        return self.action_manager.resolve_action((agent.name, assistant, observation))

    def ready_to_step(self, state: HaishanXianguanState, actions: object) -> bool:
        if state.phase in (GamePhase.REVEAL, GamePhase.SCORE):
            return True
        return self.action_manager.resolve_actions(state, actions) is not None

    @staticmethod
    def _all_complete(state: HaishanXianguanState) -> bool:
        if state.phase is GamePhase.INTRO:
            return len(state.introductions) == len(state.role_order)
        if state.phase is GamePhase.PERSON_SEARCH:
            assignments = state.person_clue_assignments
            return all(set(ids).issubset(state.handled_clues[role]) for role, ids in assignments.items())
        if state.phase is GamePhase.SCENE_SEARCH:
            assignments = state.scene_clue_assignments
            return all(set(ids).issubset(state.handled_clues[role]) for role, ids in assignments.items())
        if state.phase in (GamePhase.PERSON_DISCUSS, GamePhase.SCENE_DISCUSS):
            return len(state.discussion_rounds[state.phase.value]) == len(state.role_order)
        if state.phase is GamePhase.VOTE:
            return len(state.votes) == len(state.role_order)
        return False

    @staticmethod
    def _score(state: HaishanXianguanState) -> None:
        scores: dict[str, dict[str, object]] = {}
        for role in ROLE_ORDER:
            vote = state.votes[role]
            items: list[dict[str, object]] = []
            earned = 0
            possible = 0
            for field_name, expected, points in SCORE_RULES[role]:
                correct = vote.get(field_name) == expected
                possible += points
                earned += points if correct else 0
                items.append(
                    {
                        "task": field_name,
                        "answer": vote.get(field_name),
                        "expected": expected,
                        "status": "CORRECT" if correct else "INCORRECT",
                        "points": points if correct else 0,
                        "possible": points,
                    }
                )
            for task in NOT_SCORED_TASKS[role]:
                items.append({"task": task, "status": "NOT_SCORED", "points": None})
            scores[role] = {
                "items": items,
                "earned": earned,
                "possible": possible,
                "rate": earned / possible if possible else 0.0,
            }
        best = max(float(score["rate"]) for score in scores.values())
        state.scores = scores
        state.winner_ids = tuple(role for role in ROLE_ORDER if scores[role]["rate"] == best)
        state.terminal_result = {
            "truth": {
                "culprit": "maid",
                "image_location": "water_boat_beside_zhuyun_tower",
                "motive": "family_medical_cost_and_freedom",
            },
            "collective_result": state.collective_result,
            "scores": deepcopy(scores),
            "winner_ids": list(state.winner_ids),
        }
        state.phase = GamePhase.FINISHED

    def apply_action(
        self,
        state: HaishanXianguanState,
        action: ActionEnvelope[HaishanActionPayload] | None,
    ) -> HaishanXianguanState:
        new_state = HaishanXianguanState.from_dict(state.to_dict())
        if new_state.phase is GamePhase.REVEAL:
            new_state.truth_revealed = True
            new_state.phase = GamePhase.SCORE
            return new_state
        if new_state.phase is GamePhase.SCORE:
            self._score(new_state)
            return new_state
        if action is None:
            raise ValueError(f"phase {new_state.phase.value} requires an Action")
        valid, reason = self.action_manager.validate_action(action, new_state)
        if not valid:
            raise ValueError(reason)
        actor = action.actor
        args = action.payload.arguments
        if new_state.phase is GamePhase.INTRO:
            new_state.introductions[actor] = str(args["content"]).strip()
        elif new_state.phase in (GamePhase.PERSON_SEARCH, GamePhase.SCENE_SEARCH):
            for decision in args["decisions"]:
                clue_id = str(decision["clue_id"])
                new_state.handled_clues[actor].add(clue_id)
                if decision["reveal"]:
                    new_state.revealed_clues.add(clue_id)
        elif new_state.phase in (GamePhase.PERSON_DISCUSS, GamePhase.SCENE_DISCUSS):
            new_state.discussion_rounds[new_state.phase.value][actor] = str(args["content"]).strip()
        elif new_state.phase is GamePhase.VOTE:
            new_state.votes[actor] = deepcopy(args)
        new_state.consumed_action_ids.add(action.action_id)
        if self._all_complete(new_state):
            if new_state.phase is GamePhase.VOTE:
                tally = Counter(str(vote["suspect_id"]) for vote in new_state.votes.values())
                new_state.vote_tally = dict(tally)
                highest = max(tally.values())
                leaders = tuple(role for role in ROLE_ORDER if tally.get(role) == highest)
                success = leaders == ("maid",)
                new_state.collective_result = {
                    "success": success,
                    "leaders": list(leaders),
                    "reason": "unique_correct" if success else ("tie" if len(leaders) > 1 else "wrong_suspect"),
                }
            new_state.phase = PHASE_AFTER_ACTION[new_state.phase]
        return new_state

    def step(self, state: HaishanXianguanState, action: object) -> HaishanXianguanState:
        resolved = self.action_manager.resolve_actions(state, action)
        if state.phase not in (GamePhase.REVEAL, GamePhase.SCORE):
            if resolved is None:
                raise ValueError("current phase requires a resolvable Action")
            valid, reason = self.action_manager.validate_action(resolved, state)
            agent = next((item for item in self.agents if item.name == resolved.actor), None)
            if not valid:
                if self.active_session is not None:
                    if agent is None:
                        raise RuntimeError(f"agent {resolved.actor} is not configured")
                    context = self.active_session.contexts[resolved.actor]
                    self.reject_tool_action(
                        agent=agent,
                        observation=resolved.observation,
                        tool_call=resolved.tool_call,
                        reason=reason,
                        message_sink=context.append_turn_messages,
                    )
                raise ValueError(reason)
            if self.active_session is not None:
                if agent is None:
                    raise RuntimeError(f"agent {resolved.actor} is not configured")
                context = self.active_session.contexts[resolved.actor]
                self.execute_tool_action(
                    agent=agent,
                    observation=resolved.observation,
                    tool_call=resolved.tool_call,
                    message_sink=context.append_turn_messages,
                )
        return self.apply_action(state, resolved)

    def build_events(
        self,
        old_state: HaishanXianguanState,
        actions: object,
        new_state: HaishanXianguanState,
    ) -> tuple[AppEvent, ...]:
        events: list[AppEvent] = []
        action = self.action_manager.resolve_actions(old_state, actions)
        prefix = f"{old_state.session_id}:{old_state.phase.value}"
        if action is not None and action.name != "handle_clues":
            content: dict[str, object] = {
                "actor": action.actor,
                "action": action.name,
                "payload": deepcopy(action.payload.arguments),
            }
            if action.name == "handle_clues":
                records = (
                    self.material_loader.clues("person")
                    if old_state.phase is GamePhase.PERSON_SEARCH
                    else self.material_loader.clues("scene")
                )
                content["revealed_clues"] = {
                    str(item["clue_id"]): records[str(item["clue_id"])].content
                    for item in action.payload.arguments["decisions"]
                    if item["reveal"]
                }
            events.append(
                AppEvent(
                    event_id=f"{prefix}:{action.action_id}",
                    event_type=action.name,
                    source=action.actor,
                    content=json.dumps(content, ensure_ascii=False, sort_keys=True),
                    metadata={"phase": old_state.phase.value},
                )
            )
        if action is not None and action.name == "handle_clues":
            records = (
                self.material_loader.clues("person")
                if old_state.phase is GamePhase.PERSON_SEARCH
                else self.material_loader.clues("scene")
            )
            events.append(
                AppEvent(
                    event_id=f"{prefix}:{action.action_id}:private",
                    event_type="clue_decision_private",
                    source=action.actor,
                    content=json.dumps(
                        {"actor": action.actor, "decisions": action.payload.arguments["decisions"]},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    metadata={"phase": old_state.phase.value},
                )
            )
            for item in action.payload.arguments["decisions"]:
                if item["reveal"]:
                    clue_id = str(item["clue_id"])
                    events.append(
                        AppEvent(
                            event_id=f"{prefix}:{action.action_id}:reveal:{clue_id}",
                            event_type="clue_revealed",
                            source=action.actor,
                            content=json.dumps(
                                {"actor": action.actor, "clue_id": clue_id, "content": records[clue_id].content, "source": records[clue_id].source},
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            metadata={"phase": old_state.phase.value},
                        )
                    )
        if old_state.phase is GamePhase.VOTE and new_state.phase is GamePhase.REVEAL:
            events.append(
                AppEvent(
                    event_id=f"{old_state.session_id}:votes-complete",
                    event_type="votes_revealed",
                    source="haishan-engine",
                    content=json.dumps({"votes": deepcopy(new_state.votes), "tally": dict(new_state.vote_tally), "result": new_state.collective_result}, ensure_ascii=False, sort_keys=True),
                    metadata={},
                )
            )
        if old_state.phase is GamePhase.REVEAL:
            events.append(
                AppEvent(
                    event_id=f"{old_state.session_id}:truth",
                    event_type="truth_revealed",
                    source="haishan-engine",
                    content=json.dumps({"truth": self.material_loader.truth().content}, ensure_ascii=False, sort_keys=True),
                    metadata={"culprit": "maid", "location": "water_boat_beside_zhuyun_tower"},
                )
            )
        if new_state.is_terminal:
            events.append(
                AppEvent(
                    event_id=f"{old_state.session_id}:terminal",
                    event_type="terminal_result",
                    source="haishan-engine",
                    content=json.dumps(new_state.terminal_result, ensure_ascii=False, sort_keys=True),
                    metadata={},
                )
            )
        return tuple(events)

    def event_deliveries(
        self, event: AppEvent, old_state: HaishanXianguanState
    ) -> tuple[EventDelivery, ...]:
        private_actor = None
        if event.event_type == "submit_vote":
            private_actor = event.source
        if event.event_type == "clue_decision_private":
            private_actor = event.source
        if event.event_type in ("private_script", "private_clues"):
            private_actor = str(event.metadata["recipient"])
        if private_actor:
            return (
                EventDelivery(
                    event_id=event.event_id,
                    room_key=f"private:{private_actor}",
                    recipient=(private_actor,),
                    private=True,
                ),
            )
        return (
            EventDelivery(
                event_id=event.event_id,
                room_key="public",
                recipient="all",
                private=False,
            ),
        )

    def dispatch_events(self, events: tuple[AppEvent, ...]) -> None:
        if self.event_dispatcher is None or self.state is None:
            return
        fresh_events = tuple(
            event for event in events if event.event_id not in self.state.emitted_event_ids
        )
        if not fresh_events:
            return
        deliveries = tuple(
            delivery
            for event in fresh_events
            for delivery in self.event_deliveries(event, self.state)
        )
        rooms = self.active_session.rooms if self.active_session is not None else {}
        self.event_dispatcher.dispatch(fresh_events, deliveries, rooms=rooms)
        self.state.emitted_event_ids.update(event.event_id for event in fresh_events)
        if self.active_session is not None:
            self.active_session.state = self.state
            self.active_session.persist()

    def orchestrate_agents(self) -> AgentResult:
        if self.runtime is None or self.current_task is None:
            raise RuntimeError("runtime and task must be configured")
        if self.active_session is None:
            raise RuntimeError("active session must be configured")
        final_state = self.runtime.run(self, self.active_session)
        return AgentResult(
            status="completed" if final_state.is_terminal else "failed",
            content=final_state.terminal_result or final_state.to_dict(),
            error=None if final_state.is_terminal else "workflow stopped before terminal state",
            session_id=final_state.session_id,
        )
