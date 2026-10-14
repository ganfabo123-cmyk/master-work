"""
动态检索第一版设计、框架与开发者实现区

目标
====

脚本接收 Runtime 流式传入的 raw trace 事件，把事件累计成统一的轨迹对象，并按以下主线执行：

    raw trace
        -> 轨迹类
        -> 判断是否需要检索
        -> 从轨迹构造查询
        -> 调用检索策略
        -> 返回统一的检索结果结构

脚本只返回检索结果，不负责把结果写入 Prompt、消息、模型上下文或 Runtime。

文件职责：

    - dynamic_retrieval_test.py 是固定入口，只导入并创建程序，开发者不修改；
    - retrieval_program.py 是本文件，开发者只在标明的“开发者实现区”中替换可变逻辑。


框架已经实现的部分
==================

1. TraceEvent 与 Trajectory
   保存原始事件、统一事件、最近事件及轨迹元数据。

2. process_raw_trace
   每次接收一个 raw trace，通过转换函数生成统一事件并追加到轨迹。

3. RetrievalDocument
   固定保存 retrieval_content（用于检索）和 full_content（完整内容），并允许附加来源信息。

4. MaterialParserRegistry
   按 .md、.json、.txt、.yml、.yaml 扩展名注册开发者提供的解析器，并将文件解析为统一材料。

5. RetrievalQuery、RetrievalHit 与 RetrievalResult
   分别统一查询、单条命中和本次检索的整体返回结构。

6. dynamic_retrieval_check
   负责调用触发策略、查询构造函数和检索策略，并始终返回 RetrievalResult。

7. 当前开发者策略
   - user input 到达时立即触发，user input 原文直接作为 query_text；
   - rollout_summaries 的一级标题与 Skill description 通过可配置 embedding API 检索；
   - MEMORY.md 的 keywords 通过直接关键词匹配；
   - embedding API 未配置时不发送任何内容，向量语料暂不参与命中。


开发者必须实现或选择的部分
========================

1. 材料解析器
   开发者需要根据自己的文件结构实现：

       parser(path) -> Iterable[RetrievalDocument]

   例如 TXT 可以选择 description 作为 retrieval_content，Markdown 可以选择一级标题作为
   retrieval_content。JSON、YAML 的字段和拆分粒度也由开发者决定。框架不猜测文件语义。

2. 触发策略
   开发者需要提供或选择：

       should_retrieve(trajectory) -> bool

   它只决定当前是否检索，不执行检索，也不修改轨迹。

3. 查询构造函数
   开发者需要提供或选择：

       build_query(trajectory) -> RetrievalQuery

   它决定从哪些事件提取关键词、问题或上下文。

4. 检索策略
   开发者需要提供或选择：

       retrieve(query, documents) -> Iterable[RetrievalHit]

   可以实现关键词、词频、BM25、向量检索、混合检索或重排。算法需要的索引、模型和外部服务
   由策略自己管理；框架只约束输入和输出。


开发者可以修改的部分
==================

1. raw trace 转换规则
   可以替换 default_trace_converter，以适配 Runtime 的真实事件格式。

2. 轨迹、查询、材料和结果的 metadata
   可以写入项目需要的额外字段，但不应删除统一协议中的固定字段。

3. 文件拆分粒度
   一个文件可以解析成一条或多条 RetrievalDocument。

4. 检索参数
   可以通过 RetrievalQuery.top_k、filters 和 metadata 传递算法参数。

5. 策略形态
   策略可以是普通函数，也可以是持有 BM25 索引、向量索引等状态的可调用对象。

6. embedding API
   开发者可在 developer_embedding_api_config 中调整完整 API 地址、模型、密钥、批大小、超时
   和最低余弦相似度。当前实现兼容常见的 OpenAI-compatible embeddings 响应和 Ollama
   /api/embed 的 embeddings 响应。

7. 记忆材料路径和解析规则
   开发者可调整三个记忆根路径，以及 rollout 一级标题、Skill front matter description、
   MEMORY.md keywords 的提取方式。


固定协议
========

1. 所有 raw trace 先转换为 TraceEvent，再进入 Trajectory。
2. RetrievalDocument 必须包含 retrieval_content 和 full_content。
3. 触发策略必须返回 bool。
4. 查询构造函数必须返回 RetrievalQuery。
5. 检索策略必须返回 RetrievalHit 的可迭代对象。
6. dynamic_retrieval_check 始终返回 RetrievalResult。
7. 策略执行异常直接抛出，不伪装成正常的零命中。
8. NOT_TRIGGERED、EMPTY_QUERY、NO_MATERIALS 和 COMPLETED 由结果状态明确区分。


当前不实现
==========

1. 检索结果的消费和注入方式。
2. Runtime 的网络连接或流式通道管理。
3. PDF、Word、图片、音频和数据库材料。
4. 内置 BM25、向量模型或向量数据库；真实向量由可配置 embedding API 提供。
5. 文件监听、索引自动更新和索引持久化。
6. 异步接口。
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias


SUPPORTED_MATERIAL_SUFFIXES = frozenset({".md", ".json", ".txt", ".yml", ".yaml"})


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
MaterialParser: TypeAlias = Callable[[Path], Iterable[RetrievalDocument]]
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


class MaterialParserRegistry:
    """保存文件扩展名到开发者解析器的映射。"""

    def __init__(self) -> None:
        self._parsers: dict[str, MaterialParser] = {}

    def register(self, suffix: str, parser: MaterialParser) -> None:
        normalized_suffix = self._normalize_suffix(suffix)
        if normalized_suffix not in SUPPORTED_MATERIAL_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_MATERIAL_SUFFIXES))
            raise ValueError(f"当前仅支持这些材料类型：{supported}")
        if not callable(parser):
            raise TypeError("parser 必须可调用")
        self._parsers[normalized_suffix] = parser

    def parse_file(self, source: str | Path) -> list[RetrievalDocument]:
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"材料文件不存在：{path}")

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_MATERIAL_SUFFIXES:
            raise ValueError(f"不支持的材料类型：{suffix or '<无扩展名>'}")

        parser = self._parsers.get(suffix)
        if parser is None:
            raise LookupError(f"尚未为 {suffix} 注册材料解析器")

        parsed = parser(path)
        if isinstance(parsed, RetrievalDocument):
            raise TypeError("解析器必须返回 RetrievalDocument 的可迭代对象")

        documents = list(parsed)
        for document in documents:
            if not isinstance(document, RetrievalDocument):
                raise TypeError("解析器的每一项都必须是 RetrievalDocument")
        return documents

    @staticmethod
    def _normalize_suffix(suffix: str) -> str:
        if not isinstance(suffix, str):
            raise TypeError("suffix 必须是 str")
        normalized = suffix.strip().lower()
        if not normalized:
            raise ValueError("suffix 不能为空")
        if not normalized.startswith("."):
            normalized = f".{normalized}"
        return normalized


def load_materials(
    sources: Iterable[str | Path],
    registry: MaterialParserRegistry,
) -> list[RetrievalDocument]:
    """使用已注册解析器读取多个材料文件。"""

    documents: list[RetrievalDocument] = []
    for source in sources:
        documents.extend(registry.parse_file(source))
    return documents


def parse_entire_file(source: Path) -> list[RetrievalDocument]:
    """
    最小示例解析器：将整个 UTF-8 文件同时作为检索内容和完整内容。

    该函数只用于快速运行第一版流程。真实项目应按自己的 Markdown、JSON、TXT 或 YAML
    结构实现并注册解析器。
    """

    content = source.read_text(encoding="utf-8")
    return [
        RetrievalDocument(
            retrieval_content=content,
            full_content=content,
            document_id=str(source.resolve()),
            source_path=str(source),
            source_type=source.suffix.lower().lstrip("."),
            title=source.stem,
        )
    ]


def always_retrieve(trajectory: Trajectory) -> bool:
    """最小示例触发策略：轨迹中存在事件时触发检索。"""

    return trajectory.latest_event is not None


def latest_event_query_builder(trajectory: Trajectory) -> RetrievalQuery:
    """
    最小示例查询构造器：把最近事件的 content 转为 query_text。

    真实项目应根据 trace 语义提取真正需要检索的问题或关键词。
    """

    latest = trajectory.latest_event
    if latest is None:
        return RetrievalQuery(query_text="")

    content = latest.content
    if isinstance(content, str):
        query_text = content
    elif isinstance(content, (Mapping, list, tuple)):
        query_text = json.dumps(content, ensure_ascii=False, default=str)
    else:
        query_text = str(content)
    return RetrievalQuery(query_text=query_text)


def keyword_retrieval_strategy(
    query: RetrievalQuery,
    documents: Sequence[RetrievalDocument],
) -> list[RetrievalHit]:
    """
    最小示例检索策略：按查询词在 retrieval_content 中的出现次数排序。

    该实现不是 BM25，也不是面向生产环境的分词器。开发者可以直接替换为自己的策略。
    """

    query_terms = list(dict.fromkeys(re.findall(r"\w+", query.query_text.casefold())))
    if not query_terms:
        return []

    hits: list[RetrievalHit] = []
    for document in documents:
        searchable = document.retrieval_content.casefold()
        matched_terms = [term for term in query_terms if term in searchable]
        score = sum(searchable.count(term) for term in matched_terms)
        if score == 0:
            continue
        hits.append(
            RetrievalHit(
                document=document,
                score=float(score),
                matched_content=" ".join(matched_terms),
            )
        )

    hits.sort(key=lambda hit: hit.score or 0.0, reverse=True)
    return hits[: query.top_k]


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
class EmbeddingApiConfig:
    """开发者可调整的 embedding API 配置。"""

    endpoint: str
    model: str
    api_key: str | None = field(default=None, repr=False)
    batch_size: int = 32
    timeout_seconds: float = 60.0
    min_similarity: float = 0.25
    use_system_proxy: bool = False
    extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.endpoint = self.endpoint.strip()
        self.model = self.model.strip()
        if not self.endpoint:
            raise ValueError("embedding API endpoint 不能为空")
        if not self.model:
            raise ValueError("embedding model 不能为空")
        if self.batch_size <= 0:
            raise ValueError("embedding batch_size 必须大于 0")
        if self.timeout_seconds <= 0:
            raise ValueError("embedding timeout_seconds 必须大于 0")
        if not -1.0 <= self.min_similarity <= 1.0:
            raise ValueError("embedding min_similarity 必须位于 -1 到 1")


class EmbeddingApiClient:
    """
    调用可配置的 embedding API。

    请求体使用 {"model": ..., "input": [...]}。响应支持：
    - OpenAI-compatible: {"data": [{"index": 0, "embedding": [...]}]}
    - Ollama /api/embed: {"embeddings": [[...], ...]}
    """

    def __init__(self, config: EmbeddingApiConfig) -> None:
        self.config = config
        self.endpoint = _resolve_embeddings_endpoint(config.endpoint)
        self._opener = (
            urllib.request.build_opener()
            if config.use_system_proxy
            else urllib.request.build_opener(urllib.request.ProxyHandler({}))
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        normalized_texts = list(texts)
        if not normalized_texts:
            return []
        if any(not isinstance(text, str) for text in normalized_texts):
            raise TypeError("embedding 输入必须全部是 str")

        vectors: list[list[float]] = []
        for start in range(0, len(normalized_texts), self.config.batch_size):
            batch = normalized_texts[start : start + self.config.batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        payload = json.dumps(
            {"model": self.config.model, "input": list(texts)},
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers=headers,
            method="POST",
        )
        with self._opener.open(
            request,
            timeout=self.config.timeout_seconds,
        ) as response:
            response_payload = json.loads(response.read().decode("utf-8"))

        vectors = self._extract_vectors(response_payload)
        if len(vectors) != len(texts):
            raise ValueError(
                "embedding API 返回的向量数量与输入数量不一致："
                f"expected={len(texts)}, actual={len(vectors)}"
            )
        return vectors

    @staticmethod
    def _extract_vectors(payload: Any) -> list[list[float]]:
        if not isinstance(payload, Mapping):
            raise TypeError("embedding API 响应必须是 JSON object")

        if isinstance(payload.get("data"), list):
            data = payload["data"]
            ordered = sorted(
                data,
                key=lambda item: item.get("index", 0) if isinstance(item, Mapping) else 0,
            )
            raw_vectors = [
                item.get("embedding") if isinstance(item, Mapping) else None
                for item in ordered
            ]
        elif isinstance(payload.get("embeddings"), list):
            raw_vectors = payload["embeddings"]
        else:
            raise ValueError("embedding API 响应中缺少 data 或 embeddings")

        vectors: list[list[float]] = []
        dimension: int | None = None
        for raw_vector in raw_vectors:
            if not isinstance(raw_vector, list) or not raw_vector:
                raise ValueError("embedding 必须是非空数值数组")
            vector = [
                float(value)
                for value in raw_vector
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            if len(vector) != len(raw_vector):
                raise TypeError("embedding 数组中存在非数值元素")
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise ValueError("embedding API 返回了维度不一致的向量")
            vectors.append(vector)
        return vectors


class MemoryHybridRetrievalStrategy:
    """MEMORY keywords 关键词匹配与 rollout/Skill embedding 检索的混合策略。"""

    def __init__(self, embedding_config: EmbeddingApiConfig | None) -> None:
        self.embedding_client = (
            EmbeddingApiClient(embedding_config)
            if embedding_config is not None
            else None
        )
        self.min_similarity = (
            embedding_config.min_similarity
            if embedding_config is not None
            else 1.0
        )
        self._document_vectors: dict[tuple[str, str], list[float]] = {}

    def __call__(
        self,
        query: RetrievalQuery,
        documents: Sequence[RetrievalDocument],
    ) -> list[RetrievalHit]:
        keyword_documents = [
            document
            for document in documents
            if document.metadata.get("corpus") == "memory_keywords"
        ]
        vector_documents = [
            document
            for document in documents
            if document.metadata.get("corpus") in {"rollout_summary", "skill"}
        ]

        hits = self._keyword_hits(query.query_text, keyword_documents)
        if self.embedding_client is not None and vector_documents:
            hits.extend(self._embedding_hits(query.query_text, vector_documents))

        hits.sort(key=lambda hit: hit.score or 0.0, reverse=True)
        return hits[: query.top_k]

    def _keyword_hits(
        self,
        query_text: str,
        documents: Sequence[RetrievalDocument],
    ) -> list[RetrievalHit]:
        query_normalized = query_text.casefold().strip()
        query_tokens = set(_search_tokens(query_normalized))
        hits: list[RetrievalHit] = []

        for document in documents:
            keywords = document.metadata.get("keywords", [])
            if not isinstance(keywords, list):
                continue

            best_score = 0.0
            matched_keywords: list[str] = []
            for keyword in keywords:
                if not isinstance(keyword, str):
                    continue
                normalized_keyword = keyword.casefold().strip()
                if not normalized_keyword:
                    continue

                score = 0.0
                if normalized_keyword in query_normalized:
                    score = 1.0
                elif query_normalized in normalized_keyword and len(query_normalized) >= 2:
                    score = 0.95
                else:
                    keyword_tokens = set(_search_tokens(normalized_keyword))
                    if keyword_tokens:
                        overlap = len(query_tokens & keyword_tokens) / len(keyword_tokens)
                        score = overlap * 0.8

                if score > 0:
                    matched_keywords.append(keyword)
                    best_score = max(best_score, score)

            if matched_keywords:
                hits.append(
                    RetrievalHit(
                        document=document,
                        score=best_score,
                        matched_content=", ".join(matched_keywords),
                        metadata={
                            "corpus": "memory_keywords",
                            "retrieval_method": "direct_keyword",
                        },
                    )
                )
        return hits

    def _embedding_hits(
        self,
        query_text: str,
        documents: Sequence[RetrievalDocument],
    ) -> list[RetrievalHit]:
        if self.embedding_client is None:
            return []

        missing_documents: list[RetrievalDocument] = []
        missing_keys: list[tuple[str, str]] = []
        for document in documents:
            key = _document_vector_key(document)
            if key not in self._document_vectors:
                missing_documents.append(document)
                missing_keys.append(key)

        if missing_documents:
            vectors = self.embedding_client.embed(
                [document.retrieval_content for document in missing_documents]
            )
            self._document_vectors.update(zip(missing_keys, vectors, strict=True))

        query_vector = self.embedding_client.embed([query_text])[0]
        hits: list[RetrievalHit] = []
        for document in documents:
            similarity = _cosine_similarity(
                query_vector,
                self._document_vectors[_document_vector_key(document)],
            )
            if similarity < self.min_similarity:
                continue
            hits.append(
                RetrievalHit(
                    document=document,
                    score=similarity,
                    matched_content=document.retrieval_content,
                    metadata={
                        "corpus": document.metadata.get("corpus"),
                        "retrieval_method": "embedding_api_cosine",
                    },
                )
            )
        return hits


def _document_vector_key(document: RetrievalDocument) -> tuple[str, str]:
    return (document.document_id or document.source_path or "", document.retrieval_content)


def _resolve_embeddings_endpoint(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/embeddings") or normalized.endswith("/embed"):
        return normalized
    if ".maas.aliyuncs.com/" in normalized and normalized.endswith("/api/v1"):
        return (
            normalized.removesuffix("/api/v1")
            + "/compatible-mode/v1/embeddings"
        )
    return f"{normalized}/embeddings"


def _search_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_./+\-]+|[\u3400-\u9fff]+", text.casefold())


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("无法计算维度不同的 embedding 余弦相似度")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    return dot_product / (left_norm * right_norm)


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


# ============================================================================
# 开发者实现区
#
# 后续开发者只修改本区中的函数：
# - developer_material_sources
# - register_developer_parsers
# - developer_embedding_api_config
# - developer_trace_converter
# - developer_should_retrieve
# - developer_build_query
# - developer_retrieve
#
# dynamic_retrieval_test.py 固定入口不需要修改。
# ============================================================================


MEMORY_ROOT = Path(r"C:\Users\Lenovo\.codex\memories")
ROLLOUT_SUMMARIES_ROOT = MEMORY_ROOT / "rollout_summaries"
MEMORY_SKILLS_ROOT = MEMORY_ROOT / "skills"
MEMORY_INDEX_PATH = MEMORY_ROOT / "MEMORY.md"


def developer_material_sources() -> Sequence[str | Path]:
    """递归收集 rollout summaries、标准 SKILL.md 和 MEMORY.md。"""

    rollout_files = sorted(ROLLOUT_SUMMARIES_ROOT.glob("*.md"))
    skill_files = sorted(MEMORY_SKILLS_ROOT.rglob("SKILL.md"))
    return (*rollout_files, *skill_files, MEMORY_INDEX_PATH)


def register_developer_parsers(registry: MaterialParserRegistry) -> None:
    """同为 Markdown 的三种语料根据真实路径选择不同解析规则。"""

    registry.register(".md", _parse_developer_markdown)


_DOTENV_LOADED = False


def _load_dotenv() -> None:
    """
    从脚本同目录的 .env 文件加载环境变量。

    - 只填充尚未设置的环境变量，真实环境变量优先；
    - 支持 KEY=VALUE、# 注释行、成对的单/双引号包裹的值；
    - .env 不存在时静默跳过。
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True

    dotenv_path = Path(__file__).with_name(".env")
    if not dotenv_path.is_file():
        return
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def developer_embedding_api_config() -> EmbeddingApiConfig | None:
    """
    返回可调 embedding API 配置。

    所有部署相关取值都放在脚本同目录的 .env（见 _load_dotenv），脚本内不留默认值：

    - DYNAMIC_RETRIEVAL_EMBEDDING_API_URL：完整 embeddings API 地址；
    - DYNAMIC_RETRIEVAL_EMBEDDING_MODEL：模型名；
    - DYNAMIC_RETRIEVAL_EMBEDDING_API_KEY：可选密钥，未配置时请求不带 Authorization 头；
    - DYNAMIC_RETRIEVAL_EMBEDDING_BATCH_SIZE：默认 32；
    - DYNAMIC_RETRIEVAL_EMBEDDING_TIMEOUT：默认 60 秒；
    - DYNAMIC_RETRIEVAL_EMBEDDING_MIN_SIMILARITY：默认 0.25。
    - DYNAMIC_RETRIEVAL_EMBEDDING_USE_SYSTEM_PROXY：默认 false，本地 API 不经过系统代理。

    API 地址或模型未配置时返回 None。此时 MEMORY keywords 仍可检索，但 rollout 和 Skill
    不会使用假的向量结果。若使用远程 API，发送内容仅包括 user input、rollout 一级标题和
    Skill description，不发送完整文档或 MEMORY.md keywords。
    """
    _load_dotenv()

    endpoint = os.getenv("DYNAMIC_RETRIEVAL_EMBEDDING_API_URL", "").strip()
    model = os.getenv("DYNAMIC_RETRIEVAL_EMBEDDING_MODEL", "").strip()
    if not endpoint and not model:
        return None
    if not endpoint or not model:
        raise ValueError(
            "embedding API 必须同时配置 URL 和 MODEL；"
            "或同时留空以禁用向量语料"
        )

    return EmbeddingApiConfig(
        endpoint=endpoint,
        model=model,
        api_key=os.getenv("DYNAMIC_RETRIEVAL_EMBEDDING_API_KEY"),
        batch_size=int(
            os.getenv(
                "DYNAMIC_RETRIEVAL_EMBEDDING_BATCH_SIZE",
                "10" if model == "text-embedding-v4" else "32",
            )
        ),
        timeout_seconds=float(
            os.getenv("DYNAMIC_RETRIEVAL_EMBEDDING_TIMEOUT", "60")
        ),
        min_similarity=float(
            os.getenv("DYNAMIC_RETRIEVAL_EMBEDDING_MIN_SIMILARITY", "0.25")
        ),
        use_system_proxy=_environment_flag(
            "DYNAMIC_RETRIEVAL_EMBEDDING_USE_SYSTEM_PROXY",
            default=False,
        ),
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
        top_k=int(os.getenv("DYNAMIC_RETRIEVAL_TOP_K", "8")),
    )


_DEVELOPER_RETRIEVAL_STRATEGY: MemoryHybridRetrievalStrategy | None = None


def developer_retrieve(
    query: RetrievalQuery,
    documents: Sequence[RetrievalDocument],
) -> Iterable[RetrievalHit]:
    """执行 MEMORY keyword 与可配置 embedding API 的混合检索。"""

    global _DEVELOPER_RETRIEVAL_STRATEGY
    if _DEVELOPER_RETRIEVAL_STRATEGY is None:
        _DEVELOPER_RETRIEVAL_STRATEGY = MemoryHybridRetrievalStrategy(
            developer_embedding_api_config()
        )
    return _DEVELOPER_RETRIEVAL_STRATEGY(query, documents)


def _parse_developer_markdown(source: Path) -> list[RetrievalDocument]:
    resolved = source.resolve()
    if resolved == MEMORY_INDEX_PATH.resolve():
        return _parse_memory_keywords(source)
    if _is_under(resolved, MEMORY_SKILLS_ROOT.resolve()) and source.name.casefold() == "skill.md":
        return _parse_skill_description(source)
    if _is_under(resolved, ROLLOUT_SUMMARIES_ROOT.resolve()):
        return _parse_rollout_heading(source)
    raise ValueError(f"不属于三类开发者记忆语料：{source}")


def _parse_rollout_heading(source: Path) -> list[RetrievalDocument]:
    content = source.read_text(encoding="utf-8")
    heading_match = re.search(r"(?m)^#\s+(.+?)\s*$", content)
    if heading_match is None:
        raise ValueError(f"rollout summary 缺少一级标题：{source}")
    heading = heading_match.group(1).strip().rstrip("#").strip()
    return [
        RetrievalDocument(
            retrieval_content=heading,
            full_content=content,
            document_id=f"rollout:{source.name}",
            source_path=str(source),
            source_type="md",
            title=heading,
            metadata={"corpus": "rollout_summary"},
        )
    ]


def _parse_skill_description(source: Path) -> list[RetrievalDocument]:
    content = source.read_text(encoding="utf-8")
    description = _frontmatter_description(content)
    if not description:
        raise ValueError(f"标准 SKILL.md 缺少 description：{source}")
    return [
        RetrievalDocument(
            retrieval_content=description,
            full_content=content,
            document_id=f"skill:{source.parent.name}",
            source_path=str(source),
            source_type="md",
            title=source.parent.name,
            metadata={"corpus": "skill"},
        )
    ]


def _parse_memory_keywords(source: Path) -> list[RetrievalDocument]:
    content = source.read_text(encoding="utf-8")
    task_matches = list(re.finditer(r"(?m)^##\s+Task\s+\d+\b.*$", content))
    documents: list[RetrievalDocument] = []

    for task_match in task_matches:
        next_heading = re.search(r"(?m)^##\s+.+$", content[task_match.end() :])
        end = (
            task_match.end() + next_heading.start()
            if next_heading is not None
            else len(content)
        )
        task_block = content[task_match.start() : end].strip()
        keyword_section = re.search(
            r"(?ms)^###\s+keywords\s*$\s*(.*?)(?=^###\s|^##\s|\Z)",
            task_block,
        )
        if keyword_section is None:
            continue

        keywords: list[str] = []
        for line in keyword_section.group(1).splitlines():
            bullet_match = re.match(r"^\s*-\s+(.+?)\s*$", line)
            if bullet_match is None:
                continue
            keywords.extend(
                keyword.strip()
                for keyword in re.split(r"[,，]", bullet_match.group(1))
                if keyword.strip()
            )
        if not keywords:
            continue

        task_heading = task_match.group(0).removeprefix("##").strip()
        line_number = content.count("\n", 0, task_match.start()) + 1
        documents.append(
            RetrievalDocument(
                retrieval_content=", ".join(keywords),
                full_content=task_block,
                document_id=f"memory:{line_number}",
                source_path=str(source),
                source_type="md",
                title=task_heading,
                metadata={
                    "corpus": "memory_keywords",
                    "keywords": keywords,
                    "line_number": line_number,
                },
            )
        )
    return documents


def _frontmatter_description(content: str) -> str:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    try:
        closing_index = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration:
        return ""

    frontmatter = lines[1:closing_index]
    for index, line in enumerate(frontmatter):
        match = re.match(r"^description:\s*(.*)$", line)
        if match is None:
            continue
        value = match.group(1).strip()
        if value in {"|", "|-", "|+", ">", ">-", ">+"}:
            continuation: list[str] = []
            for next_line in frontmatter[index + 1 :]:
                if next_line and not next_line[0].isspace():
                    break
                continuation.append(next_line.strip())
            separator = "\n" if value.startswith("|") else " "
            return separator.join(part for part in continuation if part).strip()
        return value.strip("'\"")
    return ""


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


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _environment_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} 必须是 true/false、1/0、yes/no 或 on/off")


# ============================================================================
# 固定组装区
#
# 该函数把开发者实现区的组件组装为统一程序。通常不需要修改。
# ============================================================================


def create_developer_program() -> DynamicRetrievalProgram:
    """读取开发者配置并创建可接收 raw trace 的动态检索程序。"""

    registry = MaterialParserRegistry()
    register_developer_parsers(registry)

    sources = tuple(developer_material_sources())
    documents = load_materials(sources, registry) if sources else []

    return DynamicRetrievalProgram(
        documents=documents,
        trace_converter=developer_trace_converter,
        trigger_strategy=developer_should_retrieve,
        query_builder=developer_build_query,
        retrieval_strategy=developer_retrieve,
    )
