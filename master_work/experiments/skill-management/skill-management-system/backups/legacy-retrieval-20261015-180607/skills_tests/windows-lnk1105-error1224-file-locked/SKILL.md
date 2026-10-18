---
name: windows-lnk1105-error1224-file-locked
description: Windows 下链接或复制可执行文件失败：LNK1105 cannot close/open file、error code 1224（ERROR_USER_MAPPED_FILE，目标 exe/dll 仍被运行中进程占用映射）、cannot open file、拒绝访问、access denied、linker command failed。典型场景：上一次测试运行的进程未退出、mspdbsrv.exe 残留、杀毒软件锁定 build 目录。这是环境问题，不要为此修改代码。
---

# Windows 链接错误 LNK1105 / error code 1224：目标文件被占用

## 适用场景

- 链接报 `LINK : fatal error LNK1105: cannot close file 'xxx.exe'; error code 1224`；
- 或 `LNK1105: cannot open file ... 拒绝访问 / access denied`；
- 代码明明编译通过（compile OK），只在 link 或复制 exe/dll 时失败；
- 同一文件反复失败，而源码没有任何改动。

error code 1224 = ERROR_USER_MAPPED_FILE：目标 exe/dll 仍被某个进程以内存映射方式占用（正在运行、被调试器或杀毒软件扫描）。

## 处理步骤

1. 先确认这是环境问题不是代码问题：编译阶段（compile）是否全部成功？只有 link/copy 阶段失败即是本 skill。
2. 查找占用进程：
   - `tasklist | findstr <exe名>`（不含扩展名也查一下）；
   - `tasklist | findstr mspdbsrv`（PDB 服务进程常残留并锁文件）。
3. 结束占用进程：
   - `taskkill /F /IM <exe名>` 或 PowerShell `Stop-Process -Name <名> -Force`；
   - 一并结束 `mspdbsrv.exe`。
4. 确认文件可删除后重新链接：`del build\xxx.exe` 成功即证明锁已释放。
5. 若反复出现且无可见进程：检查杀毒软件实时扫描是否锁定 build 目录，将 build 目录加入排除列表。

## 不要做

- 不要为 LNK1105/1224 修改任何源码或链接选项——它和代码无关；
- 不要无限重试同一条链接命令（重试不会释放被占用的文件）；
- 不要因为"换了个输出文件名能过"就改输出路径——旧锁还在，问题被推迟而非解决。

## 证据来源

来自真实 session 审计：479c5e9f（Epilog）、c99032e9（Epilog）、a20a4070（DMLS）、39082932（Yggdrasil，agent 曾用 `Stop-Process -Name yggdrasil -Force` 解决）。多项目重复出现，属于高价值环境陷阱。
