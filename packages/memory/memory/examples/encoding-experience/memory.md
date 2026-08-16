# Windows 中文源码写入必须显式使用 UTF-8 {memory-17}

Keywords: deepseek-harness, windows, encoding, filesystem, typescript
Recorded At: 2026-08-16T02:34:23.123Z
Outcome: success

## Context

在 Windows 环境修改 DeepSeek Harness 中同时包含中文与 TypeScript 的 Markdown 和源码文件。

## Problem

依赖 PowerShell 默认编码写回文件后，中文内容发生乱码。

## Attempts

使用默认文本写入失败；改为明确指定 UTF-8 后，源码、Markdown 与测试 Fixture 均能正确往返。

## Resolution

读写包含非 ASCII 内容的文件时显式使用 UTF-8，并通过磁盘重新加载验证内容，而不是只检查内存字符串。

## Lesson

跨平台文本修改必须控制源文件编码，并用真实多语言内容做 round-trip 回归。

# Session 日志适合审计但不适合直接作为经验 {memory-31}

Keywords: deepseek-harness, session, trace, audit
Recorded At: 2026-08-16T02:40:00.000Z
Outcome: mixed

## Context

需要复用过去任务中的解决方法。

## Problem

完整 Session 包含大量过程消息，直接检索会引入噪声并消耗上下文。

## Resolution

Session 保留完整事实，Experience Memory 只保存独立、可复用的成功或失败经验。

## Lesson

审计记录与可复用经验承担不同职责，不应由同一份数据替代。

