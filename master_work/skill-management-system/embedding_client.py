"""Independent stdlib embedding transport preserved from legacy retrieval."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
import json
import urllib.request

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

    def __init__(self, config: EmbeddingApiConfig, dimension: int = 1024) -> None:
        self.config = config
        self.model = config.model
        self.dimension = dimension
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
