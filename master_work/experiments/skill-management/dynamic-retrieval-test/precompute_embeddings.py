# -*- coding: utf-8 -*-
"""
预计算全部 skill 检索部分（description）的 embedding，落盘持久缓存。

背景：SkillDescriptionSimilarityStrategy 的语料向量是冷启动最大耗时项
（每个 description 一次 API embedding）。本脚本把两个语料库的全部 skill
一次性嵌入并写入 embedding_cache.json，之后检索程序与 mock 运行直接命中
缓存，只补算新增或 description 变更的条目。

- 语料：skills_tests（手工 10 个）+ skills_b（B 组抽取 35 个），按目录自动计数；
- API 配置完全来自脚本同目录 .env（developer_embedding_api_config），脚本内
  不留任何端点/密钥/模型默认值；
- 嵌入与检索都走 SkillDescriptionSimilarityStrategy 的真实路径（缓存命中判断、
  批量请求、余弦排序、min_similarity 过滤全部与运行时一致）；
- 末尾用一条真实 LNK1105 工具输出做冒烟检索（1 次查询 RTT），打印 top-5；
- 幂等：缓存已命中时重复运行除冒烟查询外零 API 请求。

用法：
    python precompute_embeddings.py
"""

from __future__ import annotations

import time

import retrieval_program as rp

SMOKE_QUERY = (
    "LINK : fatal error LNK1105: cannot close file 'bin\\yggdrasil.exe'; "
    "error code 1224"
)


def collect_documents() -> list[tuple[str, rp.RetrievalDocument]]:
    """收集两个语料库的全部 SKILL.md，返回 (语料名, RetrievalDocument)。"""

    corpus_roots = {
        "skills_tests": rp.SKILLS_TESTS_ROOT,
        "skills_b": rp.SKILLS_TESTS_ROOT.parent / "skills_b",
    }
    documents: list[tuple[str, rp.RetrievalDocument]] = []
    for corpus_name, root in corpus_roots.items():
        if not root.is_dir():
            raise SystemExit(f"语料目录不存在：{root}")
        for source in sorted(root.rglob("SKILL.md")):
            parsed = rp._parse_skill_description(source)
            if len(parsed) != 1:
                raise SystemExit(f"预期单文档解析，实际 {len(parsed)}：{source}")
            documents.append((corpus_name, parsed[0]))
    return documents


def main() -> None:
    config = rp.developer_embedding_api_config()
    if config is None:
        raise SystemExit(".env 未配置 embedding API（URL/MODEL），无法预计算")

    documents = collect_documents()
    cache = rp._load_embedding_cache(config.model)

    per_corpus: dict[str, int] = {}
    for corpus_name, _ in documents:
        per_corpus[corpus_name] = per_corpus.get(corpus_name, 0) + 1
    warm = sum(
        1
        for _, document in documents
        if document.document_id in cache
        and cache[document.document_id].get("sha256")
        == rp._sha256_text(document.retrieval_content)
    )
    print(f"语料：{'，'.join(f'{k} {v} 个' for k, v in per_corpus.items())}")
    print(f"缓存预热：{warm}/{len(documents)} 条可直接命中，其余需调用 API")
    print(f"模型 {config.model}；端点 {rp.EmbeddingApiClient(config).endpoint}")

    strategy = rp.SkillDescriptionSimilarityStrategy(config)
    docs = [document for _, document in documents]
    pre_count = len(strategy._cache_entries)

    started = time.perf_counter()
    hits = strategy(
        rp.RetrievalQuery(query_text=SMOKE_QUERY, top_k=5), docs
    )
    elapsed = time.perf_counter() - started

    missing_vectors = [
        document.document_id
        for document in docs
        if rp._document_vector_key(document) not in strategy._description_vectors
    ]
    if missing_vectors:
        raise SystemExit(f"仍有文档缺少向量：{missing_vectors}")

    post_entries = rp._load_embedding_cache(config.model)
    dims = {len(entry["vector"]) for entry in post_entries.values()}
    print(
        f"\n缓存落盘：{rp.EMBEDDING_CACHE_PATH.name}，{len(post_entries)} 条"
        f"（本次新增 {len(post_entries) - pre_count}），维度 {sorted(dims)}"
    )
    print(f"预计算 + 冒烟查询总耗时 {elapsed:.1f}s")

    print("\n冒烟检索（真实 LNK1105 工具输出 -> description 余弦 top-5）：")
    for rank, hit in enumerate(hits, start=1):
        print(f"  {rank}. [{hit.score:.4f}] {hit.document.document_id}")
    if not hits:
        print("  （无命中：全部低于 min_similarity）")


if __name__ == "__main__":
    main()
