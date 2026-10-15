---
name: project-build-entry-and-env-probe
description: 新项目或新会话动手前，先找该项目的规范构建入口（build.bat、Makefile、package.json scripts、README/CONTRIBUTING），并复用本会话内已成功过的调用（含 cwd 与环境）。Windows 批处理脚本用 cmd 执行。首次进入项目先做环境探针：构建系统、工具版本、已知损坏的工具，再开始修改。
---

# 构建入口优先：先找规范入口与环境探针，再动手构建

## 适用场景

- 首次在某项目构建/测试，不确定命令；
- 之前用某条命令构建成功过，后来换了一条变体命令结果异常；
- 构建脚本为 bat/cmd（应用 cmd 而非 PowerShell 执行）；
- 新会话承接旧项目任务。

核心原则：**项目都有规范构建入口；本会话内存在"确实成功过"的调用时，它是最高优先级基准。**

## 处理步骤

1. 会话开始（或首次构建前）做环境探针，一次性记录：
   - 构建系统（Makefile / build.bat / gradle / npm scripts / cmake）与入口文件；
   - 工具链版本（编译器、解释器、包管理器）；
   - 已知不可用的工具（坏掉的 shell、缺失的 PATH 项）。
2. 找规范入口：仓库根的 build.bat / Makefile / package.json / README / CONTRIBUTING / CI 配置；以它们声明的命令为准，不自行拼装。
3. 复用已知成功调用：本会话早前某条命令产出过预期结果（产物、测试输出），后续就重复那条调用本身（连同其 cwd 与环境），不更换变体。
4. bat/cmd 脚本用 cmd 执行（`cmd /c build.bat`）；确认 cwd 在仓库根。
5. 构建失败时，先回到"成功基准调用"验证环境没变，再分析新错误。

## 不要做

- 不要在存在成功基准的情况下换用其他命令变体反复尝试；
- 不要在没看入口文件的情况下凭记忆拼构建命令；
- 不要用 PowerShell 直接执行依赖 cmd 语法的 bat 脚本。

## 证据来源

来自真实 session 审计：a20a4070（DMLS）——session 早段存在成功的构建调用，后段换用变体命令空转 4 次；09d9abe9、47d9fc04 也出现"未先探明环境就动手"的模式。该 skill 对应"项目首次会话注入"策略。
