---
name: powershell-command-not-found-windows
description: Windows PowerShell 假故障：The term 'xxx' is not recognized as a name of a cmdlet, function, script file, or executable program、无法将xxx项识别为 cmdlet、tail/grep/head/cat/sed 不存在、NativeCommandError、CategoryInfo、FullyQualifiedErrorId。三类原因：Unix 命令在 PowerShell 不存在；刚构建失败的 exe 不存在就去运行；wsl PATH 翻译失败。用 PowerShell 等价命令或 cmd 替代，不要误判为代码错误。
---

# PowerShell "not recognized as a name of a cmdlet"：三类真实原因

## 适用场景

- `The term 'tail' / 'grep' / 'head' is not recognized as a name of a cmdlet...`；
- `无法将...项识别为 cmdlet, function, 脚本文件或可运行程序`；
- 输出里出现 `CategoryInfo : ObjectNotFound / NativeCommandError`、`FullyQualifiedErrorId`；
- `wsl: Failed to translate '<Windows路径>'`。

## 判断原因（先分类再动手）

1. **Unix 命令在 PowerShell 中不存在**：tail/grep/cat/sed/awk 不是 PowerShell 命令。替代：
   - `tail -f x.log` → `Get-Content x.log -Tail 50 -Wait`；
   - `grep xxx file` → `Select-String -Pattern xxx file`；
   - 或改用 cmd / bash（`bash -c "grep ... "`，若装有 Git Bash/WSL）。
2. **运行的 exe 根本没生成**：`The term '.\build\tests\test_x.exe' is not recognized` 常发生在上一条链接命令失败（如 LNK1105）之后。先确认 exe 存在（`Test-Path .\build\tests\test_x.exe`），不存在则回溯上一个失败的构建步骤，而不是纠结命令写法。
3. **PATH/环境问题**：绝对路径工具报 not recognized → 路径不存在或被卸载；`wsl: Failed to translate` 说明 Windows PATH 泄入 WSL，命令应在 bash 内部写全 Linux 路径。

## 处理步骤

1. 读报错第一行，定位不被识别的词是"Unix 命令"还是"你自己的产物 exe"。
2. Unix 命令 → 换 PowerShell 等价命令或 bash -c 包裹；
3. 自己的 exe → 检查文件是否存在，回溯构建失败原因；
4. PowerShell 对 stderr 非空会包装出 NativeCommandError，**不要把这类包装当程序崩溃**，看真实退出码和 stderr 内容。

## 不要做

- 不要在 PowerShell 里反复用同一条 Unix 命令重试；
- 不要把 `NativeCommandError` 包装层误读为编译器/程序自身错误。

## 证据来源

来自真实 session 审计：09d9abe9（Pseudo-OS，tail）、07b57159（CFML，tail）、47d9fc04（grep + wsl Failed to translate）、479c5e9f（运行未生成的 exe）、a20a4070（gflags 路径不存在）。多 session 重复，Windows 环境最高频假故障之一。
