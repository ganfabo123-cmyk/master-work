# Agent Note: 关键词经验记忆

Status: implemented

[English](2026-08-16-keyword-experience-memory.md) | 中文

## Problem

长期记忆需要召回可复用的任务经验，同时避免加载完整 Session，也不能强迫一条经验只能属于一个主题树路径。取消分类后，临时收件箱与后续树分类只会增加第二套持久化工作，而不会改善召回。

## Decision

`@deepseek-ai/dsh-memory` 在全局 `memory.md` 中保存同级、追加式经验记录。每条 `memory-N` 记录包含标题、规范化关键词、Harness 生成的 ISO 8601 时间、明确结果和 Markdown 正文。一级 `# <title> {memory-N}` 标题是唯一 Record Boundary；正文拒绝一级标题。

`memory_record` 校验模型 Tool Call 编写的字段后直接追加到正式 Store，不经过用户确认。进程内串行队列覆盖重新加载、单调 id 分配和原子替换，避免同一进程内不同 Session 产生重复 id 或丢失更新。同一个文件不支持多个进程并发写入。

开源发布整理增加了可复现的真实 Loader 编码 Demo、三张说明图与一张经验证的终端截图，并补充面向发布的 Store 边界、UTF-8 磁盘往返、Retriever 契约、Tool 结果边界、Loader 装配、并发写入和卸载清理测试。

`memory_search` 渐进式披露 id、标题、规范化关键词、匹配关键词和结果。`KeywordRetriever` 只用匹配关键词数量选择并截断 Top-K；入选候选按 id 升序展示，Score 与 Rank 语义都不会进入面向模型的 API。`memory_get` 加载一条完整的已选经验。模型负责判断相关性，并把加载的记忆视为可能过时的历史证据。

`MemoryRetriever` 接口接收 `MemorySearchSource`。V1 的关键词精确检索扫描 Document；后续 BM25、Vector 或 Hybrid 实现可以自行维护派生索引，而不修改 Store、Service 或 Tool。`memory.md` 始终是唯一事实源。

## Alternatives considered

**保留标题树与临时收件箱。** 一个父路径无法表达技术、环境、组件和症状等多个召回维度。取消分类也就取消了临时记录的独立生命周期。

**暴露内部检索分数或保留相关性顺序。** 关键词数量、BM25 Score 和向量相似度是筛选信号，不是置信度或正确性。数字分数和相关性排序会诱导模型把最终相关性判断交给近似信号。

**进入写队列之前分配 id。** 原子替换只能避免半文件，不能阻止两个读取者分配相同 id 或互相覆盖。id 分配必须位于串行的重新加载到写回操作内。

## Consequences

插件具有三个稳定的模型操作：记录、搜索和读取。搜索保持轻量，存储与检索可以独立演进，同一进程中的并发 Session 能保留每次追加。设计放弃树导航、临时提升、旧 Markdown 格式兼容、跨进程写安全、语义检索、删除、合并和自动矛盾处理。

包测试覆盖 Markdown Boundary、规范化关键词、隐藏排名信号、Top-K 展示顺序、直接记录、旧格式拒绝与并发追加。真实 Loader 装配测试固定最终 Prompt 和 Tool 集合。
