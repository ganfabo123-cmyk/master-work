"""Baidu Qianfan Web Search Policy Tool owned by the AI Berkshire App."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from typing import Annotated, Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from pydantic import Field

from ...infra.tools import BaseAgentTools


SearchRecency = Literal["all", "week", "month", "semiyear", "year"]
SearchTransport = Callable[[Request, float], dict[str, Any]]
TRACKING_QUERY_KEYS = {"app", "for", "from", "path", "redirect_pc", "spm", "wfr"}


def canonicalize_source_url(url: str) -> str:
    """Remove presentation tracking while preserving source identity parameters."""
    parts = urlsplit(url.strip())
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")
    ])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


class BaiduWebSearchClient:
    """Small synchronous adapter for Baidu Qianfan Web Search."""

    endpoint = "https://qianfan.baidubce.com/v2/ai_search/web_search"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 30,
        transport: SearchTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._request_json

    @classmethod
    def from_environment(cls) -> "BaiduWebSearchClient":
        return cls(
            api_key=(
                os.getenv("QIANFAN_WEB_SEARCH_API_KEY")
                or os.getenv("APPBUILDER_TOKEN")
                or os.getenv("WEB_SEARCH_API")
            )
        )

    def search(
        self,
        *,
        query: str,
        top_k: int,
        recency: SearchRecency,
        sites: tuple[str, ...],
    ) -> dict[str, Any]:
        query = query.strip()
        if not query:
            raise ValueError("search query must not be empty")
        if not 1 <= top_k <= 5:
            raise ValueError("top_k must be between 1 and 5")
        if len(sites) > 20:
            raise ValueError("sites supports at most 20 domains")
        if not self.api_key:
            raise RuntimeError(
                "Missing QIANFAN_WEB_SEARCH_API_KEY, APPBUILDER_TOKEN, or WEB_SEARCH_API for AI Berkshire Web Search"
            )

        payload: dict[str, Any] = {
            "messages": [{"content": query, "role": "user"}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": top_k}],
        }
        normalized_sites = tuple(site.strip() for site in sites if site.strip())
        if normalized_sites:
            payload["search_filter"] = {"match": {"site": list(normalized_sites)}}
        if recency != "all":
            payload["search_recency_filter"] = recency

        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "X-Appbuilder-Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        raw = self.transport(request, self.timeout_seconds)
        if raw.get("code"):
            raise RuntimeError(f"Baidu Web Search error {raw['code']}: {raw.get('message', '')}")
        references = raw.get("references")
        if not isinstance(references, list):
            raise RuntimeError("Baidu Web Search response has no references list")

        normalized: list[dict[str, Any]] = []
        for item in references:
            if not isinstance(item, dict) or item.get("type") != "web" or not item.get("url"):
                continue
            normalized.append({
                "id": item.get("id"),
                "title": str(item.get("title") or ""),
                "url": str(item["url"]),
                "website": str(item.get("website") or item.get("web_anchor") or ""),
                "date": str(item.get("date") or ""),
                "content": str(item.get("content") or "")[:1200],
                "rerank_score": item.get("rerank_score"),
                "authority_score": item.get("authority_score"),
            })
        return {"query": query, "request_id": str(raw.get("request_id") or ""), "references": normalized}

    @staticmethod
    def _request_json(request: Request, timeout_seconds: float) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Baidu Web Search HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Baidu Web Search network error: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Baidu Web Search returned invalid JSON: {error}") from error
        if not isinstance(raw, dict):
            raise RuntimeError("Baidu Web Search returned a non-object response")
        return raw


class BaiduWebSearchTools(BaseAgentTools):
    """Per-Agent search budget and citation provenance for one research session."""

    def __init__(self, agent_name: str, client: BaiduWebSearchClient, *, max_calls: int = 6) -> None:
        super().__init__(agent_name)
        self.client = client
        self.max_calls = max_calls
        self.call_count = 0
        self.source_urls: set[str] = set()

    def tool_functions(self) -> tuple[Callable[..., str], ...]:
        return (self.search_web,)

    def search_web(
        self,
        query: Annotated[str, Field(min_length=1, description="明确、单一的网页检索问题。")],
        top_k: Annotated[int, Field(ge=1, le=5, description="最多返回的网页结果数量。")] = 5,
        recency: Annotated[SearchRecency, Field(description="可选的网页发布时间范围。")] = "all",
        sites: Annotated[list[str] | None, Field(max_length=20, description="可选的限定站点域名列表。")] = None,
    ) -> str:
        """搜索实时网页资料并返回可引用的标题、URL、日期和相关原文片段。"""
        if self.call_count >= self.max_calls:
            raise RuntimeError(f"{self.agent_name} exceeded the Web Search budget of {self.max_calls} calls")
        self.call_count += 1
        result = self.client.search(
            query=query,
            top_k=top_k,
            recency=recency,
            sites=tuple(sites or ()),
        )
        self.source_urls.update(
            canonicalize_source_url(str(item["url"]))
            for item in result["references"]
            if isinstance(item, dict) and item.get("url")
        )
        return json.dumps(result, ensure_ascii=False)
