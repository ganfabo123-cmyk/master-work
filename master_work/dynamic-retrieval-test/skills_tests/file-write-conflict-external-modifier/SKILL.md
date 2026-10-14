---
name: file-write-conflict-external-modifier
description: 写文件反复失败：File has been modified since read, either by the user or by a linter、File has not been read yet. Read it first before writing to it、写入后读回内容与写入不一致、文件被 linter/formatter 自动改写。存在外部修改者（format on save、文件监视器、另一进程）与 agent 互相覆盖。连续两次写冲突后必须先找出外部修改者，禁止盲目重试。
---

# 文件写冲突：存在外部修改者（formatter/linter/watcher）

## 适用场景

- `File has been modified since read, either by the user or by a linter. Read it again before attempting to write it.`；
- `File has not been read yet. Read it first before writing to it.`（非首次编辑该文件时出现）；
- write → read back 内容与刚写入的不一致（缩进/引号/换行被改）；
- 同一文件编辑-保存循环中反复出现上述错误。

本质：有外部进程（编辑器 format on save、ESLint/Prettier watcher、代码格式化钩子、另一个 agent/终端）在 agent 写入后立即改写文件。

## 处理步骤

1. 出现一次冲突：立即重新 Read 该文件再写，这是正常恢复。
2. 连续第二次冲突：停止盲目重试。查 git diff / 时间戳确认文件确实被改，比对被改的模式（缩进？引号？import 排序？）判断修改者类型。
3. 定位修改者：项目是否有 .prettierrc/.eslintrc + 编辑器 format on save、文件监视任务、构建钩子；询问用户是否有编辑器开着该文件。
4. 化解冲突（二选一）：
   - 尊重格式化器：先写，再主动跑一次 formatter，然后把 formatter 的输出作为最终版本读回，在其基础上继续编辑；
   - 请用户临时关闭 format on save / watcher，完成编辑后再恢复。
5. 之后每次写该文件前都先 Read，缩小读写窗口。

## 不要做

- 不要循环 write → 冲突 → write 超过两次而不分析修改者；
- 不要在每次冲突后重写"整个文件"来对抗格式化器——会无限互搏；
- 不要把冲突误判为自己的写入内容有错。

## 证据来源

来自真实 session 审计：7563bddf（prettify-reddit，与外部 formatter 互搏多轮，`File has been modified since read` 原文出现于 L575，`File has not been read yet` 于 L338/L342）；同类错误也散见于 39082932、4222016d、3be5ba0c。
