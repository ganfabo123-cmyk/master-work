"""Generic Trace/trajectory/trigger/query/result protocol preserved from legacy retrieval.

Copied before integration; no network or management imports. The default trigger is
latest user_input, while AgentSession accepts replacement converters and policies.
"""
from __future__ import annotations
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, TypeAlias
import json
import os

@dataclass(slots=True)
class TraceEvent:
    """由 raw trace 转换得到的统一事件。"""

    event_type: str
    content: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Trajectory:
    """动态检索策略读取的统一轨迹。"""

    raw_events: list[Any] = field(default_factory=list)
    events: list[TraceEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def latest_event(self) -> TraceEvent | None:
        if not self.events:
            return None
        return self.events[-1]

    def append(self, raw_event: Any, event: TraceEvent) -> None:
        if not isinstance(event, TraceEvent):
            raise TypeError("event 必须是 TraceEvent")
        self.raw_events.append(raw_event)
        self.events.append(event)


@dataclass(slots=True)
class RetrievalDocument:
    """解析完成后交给检索策略使用的一条材料。"""

    retrieval_content: str
    full_content: str
    document_id: str | None = None
    source_path: str | None = None
    source_type: str | None = None
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.retrieval_content, str):
            raise TypeError("retrieval_content 必须是 str")
        if not isinstance(self.full_content, str):
            raise TypeError("full_content 必须是 str")


@dataclass(slots=True)
class RetrievalQuery:
    """从轨迹构造出的统一检索查询。"""

    query_text: str
    top_k: int = 5
    filters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.query_text, str):
            raise TypeError("query_text 必须是 str")
        if not isinstance(self.top_k, int) or isinstance(self.top_k, bool):
            raise TypeError("top_k 必须是 int")
        if self.top_k <= 0:
            raise ValueError("top_k 必须大于 0")


@dataclass(slots=True)
class RetrievalHit:
    """检索策略返回的一条命中。"""

    document: RetrievalDocument
    score: float | None = None
    rank: int | None = None
    matched_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.document, RetrievalDocument):
            raise TypeError("document 必须是 RetrievalDocument")
        if self.score is not None and (
            not isinstance(self.score, (int, float)) or isinstance(self.score, bool)
        ):
            raise TypeError("score 必须是数值或 None")


class RetrievalStatus(str, Enum):
    """动态检索检测的可区分状态。"""

    NOT_TRIGGERED = "not_triggered"
    EMPTY_QUERY = "empty_query"
    NO_MATERIALS = "no_materials"
    COMPLETED = "completed"


@dataclass(slots=True)
class RetrievalResult:
    """脚本对外返回的统一检索结构。"""

    status: RetrievalStatus
    query: RetrievalQuery | None = None
    items: list[RetrievalHit] = field(default_factory=list)
    strategy_name: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


TraceConverter: TypeAlias = Callable[[Any], TraceEvent]


TriggerStrategy: TypeAlias = Callable[[Trajectory], bool]


QueryBuilder: TypeAlias = Callable[[Trajectory], RetrievalQuery]


RetrievalStrategy: TypeAlias = Callable[
    [RetrievalQuery, Sequence[RetrievalDocument]],
    Iterable[RetrievalHit],
]


def default_trace_converter(raw_trace: Any) -> TraceEvent:
    """
    最小 raw trace 转换器。

    Mapping 会优先读取 type、event_type 和 content；其他输入直接作为 content。
    开发者可以替换此函数，以适配 Runtime 的真实 trace 协议。
    """

    if isinstance(raw_trace, Mapping):
        event_type = raw_trace.get("type", raw_trace.get("event_type", "mapping"))
        content = raw_trace.get("content", raw_trace)
        metadata = {
            str(key): value
            for key, value in raw_trace.items()
            if key not in {"type", "event_type", "content"}
        }
        return TraceEvent(
            event_type=str(event_type),
            content=content,
            metadata=metadata,
        )

    return TraceEvent(
        event_type=type(raw_trace).__name__,
        content=raw_trace,
    )


def process_raw_trace(
    raw_trace: Any,
    trajectory: Trajectory | None = None,
    converter: TraceConverter = default_trace_converter,
) -> Trajectory:
    """转换一个 raw trace 事件，将其追加到轨迹并返回该轨迹。"""

    target = trajectory if trajectory is not None else Trajectory()
    event = converter(raw_trace)
    if not isinstance(event, TraceEvent):
        raise TypeError("converter 必须返回 TraceEvent")
    target.append(raw_trace, event)
    return target


def dynamic_retrieval_check(
    trajectory: Trajectory,
    trigger_strategy: TriggerStrategy,
    query_builder: QueryBuilder,
    retrieval_strategy: RetrievalStrategy,
    documents: Sequence[RetrievalDocument],
) -> RetrievalResult:
    """
    判断是否检索，并在触发时返回统一检索结果。

    策略或构造器抛出的异常会原样向上抛出，从而与正常的空结果保持区别。
    """

    should_retrieve = trigger_strategy(trajectory)
    if not isinstance(should_retrieve, bool):
        raise TypeError("trigger_strategy 必须返回 bool")
    if not should_retrieve:
        return RetrievalResult(
            status=RetrievalStatus.NOT_TRIGGERED,
            reason="触发策略决定本次不检索",
        )

    query = query_builder(trajectory)
    if not isinstance(query, RetrievalQuery):
        raise TypeError("query_builder 必须返回 RetrievalQuery")
    if not query.query_text.strip():
        return RetrievalResult(
            status=RetrievalStatus.EMPTY_QUERY,
            query=query,
            reason="查询文本为空",
        )

    normalized_documents = tuple(documents)
    for document in normalized_documents:
        if not isinstance(document, RetrievalDocument):
            raise TypeError("documents 的每一项都必须是 RetrievalDocument")
    if not normalized_documents:
        return RetrievalResult(
            status=RetrievalStatus.NO_MATERIALS,
            query=query,
            reason="没有可检索材料",
        )

    raw_hits = retrieval_strategy(query, normalized_documents)
    if isinstance(raw_hits, RetrievalHit):
        raise TypeError("retrieval_strategy 必须返回 RetrievalHit 的可迭代对象")

    hits = list(raw_hits)
    for hit in hits:
        if not isinstance(hit, RetrievalHit):
            raise TypeError("retrieval_strategy 的每一项都必须是 RetrievalHit")

    ranked_hits = [
        replace(hit, rank=index)
        for index, hit in enumerate(hits[: query.top_k], start=1)
    ]
    return RetrievalResult(
        status=RetrievalStatus.COMPLETED,
        query=query,
        items=ranked_hits,
        strategy_name=_callable_name(retrieval_strategy),
    )


def _callable_name(callback: Callable[..., Any]) -> str:
    return getattr(callback, "__name__", callback.__class__.__name__)


@dataclass(slots=True)
class DynamicRetrievalProgram:
    """保存一次动态检索程序所需的组件和运行状态。"""

    documents: list[RetrievalDocument]
    trace_converter: TraceConverter
    trigger_strategy: TriggerStrategy
    query_builder: QueryBuilder
    retrieval_strategy: RetrievalStrategy
    trajectory: Trajectory = field(default_factory=Trajectory)

    def handle_raw_trace(self, raw_trace: Any) -> RetrievalResult:
        """
        接收一个流式 raw trace 事件并返回本次统一检索结果。

        调用方负责决定如何消费返回值。
        """

        process_raw_trace(
            raw_trace,
            trajectory=self.trajectory,
            converter=self.trace_converter,
        )
        return dynamic_retrieval_check(
            trajectory=self.trajectory,
            trigger_strategy=self.trigger_strategy,
            query_builder=self.query_builder,
            retrieval_strategy=self.retrieval_strategy,
            documents=self.documents,
        )


def developer_trace_converter(raw_trace: Any) -> TraceEvent:
    """
    将直接字符串或常见 role/type=user 事件统一标记为 user_input。

    其他事件继续使用框架默认转换器，因此不会触发本策略。
    """

    if isinstance(raw_trace, str):
        return TraceEvent(event_type="user_input", content=raw_trace)

    if isinstance(raw_trace, Mapping):
        message = raw_trace.get("message")
        message_mapping = message if isinstance(message, Mapping) else {}
        role = raw_trace.get("role", message_mapping.get("role"))
        raw_type = raw_trace.get("type", raw_trace.get("event_type", ""))
        normalized_type = str(raw_type).casefold().replace("-", "_")
        is_user_input = str(role).casefold() == "user" or normalized_type in {
            "user",
            "user_input",
            "user_message",
            "user.message",
            "message.user",
        }
        if is_user_input:
            candidate = message_mapping.get(
                "content",
                raw_trace.get(
                    "content",
                    raw_trace.get("input", raw_trace.get("text", "")),
                ),
            )
            return TraceEvent(
                event_type="user_input",
                content=_content_to_text(candidate),
                metadata={"raw_type": str(raw_type), "role": str(role or "")},
            )

    return default_trace_converter(raw_trace)


def developer_should_retrieve(trajectory: Trajectory) -> bool:
    """只有刚进入轨迹的事件是 user input 时才触发。"""

    latest = trajectory.latest_event
    return latest is not None and latest.event_type == "user_input"


def developer_build_query(trajectory: Trajectory) -> RetrievalQuery:
    """直接使用最新 user input 原文作为查询，不拼接历史轨迹。"""

    latest = trajectory.latest_event
    if latest is None or latest.event_type != "user_input":
        return RetrievalQuery(query_text="")
    return RetrievalQuery(
        query_text=_content_to_text(latest.content),
        top_k=int(os.getenv("DYNAMIC_RETRIEVAL_TOP_K", "3")),
    )


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, Mapping):
        for key in ("text", "content", "input", "value"):
            if key in content:
                return _content_to_text(content[key])
        return json.dumps(content, ensure_ascii=False, default=str)
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes, bytearray)):
        parts = [_content_to_text(item).strip() for item in content]
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return str(content)
