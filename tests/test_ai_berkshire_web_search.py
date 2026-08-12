from __future__ import annotations

import json
from urllib.request import Request

from coworker.apps.ai_berkshire.web_search import (
    BaiduWebSearchClient,
    BaiduWebSearchTools,
    canonicalize_source_url,
)


def test_baidu_search_builds_request_and_normalizes_web_references() -> None:
    captured: dict[str, object] = {}

    def transport(request: Request, timeout: float) -> dict[str, object]:
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("X-appbuilder-authorization")
        captured["timeout"] = timeout
        captured["payload"] = json.loads(bytes(request.data or b"").decode("utf-8"))
        return {
            "request_id": "request-1",
            "references": [
                {
                    "id": 1, "type": "web", "title": "Alibaba filing",
                    "url": "https://www.alibabagroup.com/filing", "website": "Alibaba",
                    "date": "2026-05-20", "content": "x" * 1300,
                    "rerank_score": 0.91, "authority_score": 0.88,
                },
                {"id": 2, "type": "image", "url": "https://example.com/image.jpg"},
            ],
        }

    client = BaiduWebSearchClient(api_key="secret", timeout_seconds=12, transport=transport)
    result = client.search(
        query="阿里巴巴 最新年报",
        top_k=3,
        recency="year",
        sites=("alibabagroup.com", "hkexnews.hk"),
    )

    assert captured["url"] == BaiduWebSearchClient.endpoint
    assert captured["authorization"] == "Bearer secret"
    assert captured["timeout"] == 12
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["search_source"] == "baidu_search_v2"
    assert payload["search_recency_filter"] == "year"
    assert payload["search_filter"] == {"match": {"site": ["alibabagroup.com", "hkexnews.hk"]}}
    assert len(result["references"]) == 1
    assert result["references"][0]["url"] == "https://www.alibabagroup.com/filing"
    assert len(result["references"][0]["content"]) == 1200


def test_search_tool_records_citation_provenance_and_enforces_budget() -> None:
    def transport(_: Request, __: float) -> dict[str, object]:
        return {
            "references": [{
                "id": 1, "type": "web", "title": "Source",
                "url": "https://example.com/source", "content": "evidence",
            }],
        }

    tools = BaiduWebSearchTools(
        "business-analyst",
        BaiduWebSearchClient(api_key="secret", transport=transport),
        max_calls=1,
    )
    result = json.loads(tools.search_web("Alibaba business model", top_k=1))

    assert result["references"][0]["url"] in tools.source_urls
    try:
        tools.search_web("second query", top_k=1)
    except RuntimeError as error:
        assert "budget" in str(error)
    else:
        raise AssertionError("Web Search budget was not enforced")


def test_baidu_search_requires_api_key() -> None:
    client = BaiduWebSearchClient(api_key=None)
    try:
        client.search(query="Alibaba", top_k=1, recency="all", sites=())
    except RuntimeError as error:
        assert "QIANFAN_WEB_SEARCH_API_KEY" in str(error)
    else:
        raise AssertionError("missing API key was accepted")


def test_source_url_canonicalization_removes_tracking_but_keeps_identity() -> None:
    raw = "https://BAIJIAHAO.baidu.com/s?id=123&wfr=spider&for=pc&utm_source=test#section"

    assert canonicalize_source_url(raw) == "https://baijiahao.baidu.com/s?id=123"
    assert canonicalize_source_url(
        "https://news.qq.com/rain/a/article-id?path=a&app=news&redirect_pc=1"
    ) == "https://news.qq.com/rain/a/article-id"
