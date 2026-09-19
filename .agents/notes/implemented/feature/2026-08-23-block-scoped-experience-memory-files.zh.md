# Agent Note: 分块经验记忆文件

Status: implemented

[English](2026-08-23-block-scoped-experience-memory-files.md) | 中文

## Problem

单一经验文件让所有检索操作面对同一个候选语料。关键词可以表达相关性，但不能让模型选择一个有边界的技术或项目记忆集合，而且全局唯一的 `memory-N` 会把彼此无关的经验集合耦合起来。

## Decision

经验记忆在 `memoryDir` 下划分为具名文件块；该目录默认是 `$DSH_HOME/memory`。经过校验的 `block_name` 映射为 `<block_name>_memory.md`；规范化会去除首尾空格并转为小写，校验只允许 1–64 个 ASCII 字母、数字、下划线或连字符，使模型输入不能选择配置目录之外的路径。

`memory_search`、`memory_get` 和 `memory_record` 都要求 `block_name`。`MemoryService` 为每个规范化块缓存一个 `MemoryStore`，因此每个文件保留原有 Markdown 记录格式、独立的 `memory-N` 分配、原子替换、外部编辑重载行为和进程内串行写入。检索器接收已经选定的存储，不感知块。

使用默认配置时，首次访问 `global` 块会把 `$DSH_HOME/memory.md` 重命名为 `$DSH_HOME/memory/global_memory.md`，不重写其内容。如果目标冲突，该操作会拒绝执行，不合并也不覆盖。

## Alternatives considered

**在单文件中增加块元数据。** 这种方式保留全局 ID，但存储和写入所有权仍然是全局的，而当前要求的单元是一个保持原格式的完整记忆文件。

**为每个块配置一条路径。** 这种方式允许任意放置文件，但会把配置和路径权限扩大到当前“一个宿主目录中的具名文件”需求之外。

**跨块和整块读取工具。** 这些操作会削弱先选块再检索的流程，而且当前没有消费方，因此插件只保留已有的搜索、获取和记录操作，并为它们增加块名。

## Consequences

一条经验的稳定身份是 `(block_name, memory-N)`，不同块可以分别包含 `memory-1`。模型必须为每次经验操作选择块。块是命名空间而不是访问控制：拥有这些工具的模型可以指定任意合法块。仍不支持多个进程并发写入同一个块文件。
