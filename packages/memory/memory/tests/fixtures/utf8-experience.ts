export const UTF8_TITLE = 'DeepSeek Harness 中文文件编码回归'

export const UTF8_BODY = `## Context

DeepSeek Harness 在 Windows 下修改「测试文件.md」。
路径：C:\\Users\\测试\\项目

## Problem

中文、English、日本語和 emoji 🧠 同时出现时发生乱码。

### Root Cause

默认文件编码与目标 UTF-8 不一致。

## Attempts

PowerShell 默认写入失败；显式 UTF-8 写入成功。

## Resolution

使用明确的 UTF-8 编解码，并保留反引号 \`code\` 与 Markdown **bold**。

## Lesson

跨平台修改文本时，显式控制源文件编码。`

