---
name: windows-lnk1107-corrupt-binary
description: Windows 链接/加载报 LNK1107 invalid or corrupt file: cannot read at 0x…：目标 exe/dll 文件不完整或已损坏。常见原因是复制与构建竞争（链接未完成就开始拷贝）、半写入的 DLL、或文件被映射锁定后损坏。处理：清理重建、确保复制发生在链接完成之后、比对源文件与目标文件大小/哈希。与 LNK1105/error 1224 同族，都是构建产物文件完整性问题。
---

# LNK1107 invalid or corrupt file：构建产物不完整或损坏

## 适用场景

- `fatal error LNK1107: invalid or corrupt file: cannot read at 0x...`；
- 报错对象是刚刚复制/构建出来的 exe/dll/lib；
- `file` 命令能看到 PE 头但链接器在某个偏移处读不下去。

本质：目标二进制不完整——复制发生时链接还在写文件（构建与复制脚本竞争），或文件在写入中被锁定/截断。与 LNK1105（文件被占用）、error 1224（ERROR_USER_MAPPED_FILE）同族。

## 处理步骤

1. 对比源文件与目标文件：大小是否一致、哈希是否相同（`Get-FileHash` / `fciv`）。不一致 → 复制竞争或复制不完整。
2. 清理重建：删除产物（`del build\xxx.dll`），完整重跑链接步骤，确认链接步骤的退出码为 0。
3. 修正复制时机：复制/打包必须等链接完成后进行；构建脚本里检查每一步的退出码，失败立即中止而不是继续复制。
4. 若重建后仍损坏：检查磁盘空间、杀毒软件截断行为、以及该文件是否被进程映射（参见 LNK1105/error 1224 的排查）。

## 不要做

- 不要把 LNK1107 当成源码错误去改代码；
- 不要只重跑复制步骤而不重新链接——源头产物可能已损坏；
- 不要忽略构建脚本里被吞掉的退出码。

## 证据来源

来自真实 session 审计：4222016d（DMLS）——epilog.dll 两次复制后均报 `LNK1107: invalid or corrupt file: cannot read at 0x2F8`，`file` 命令证实 PE 头存在；与 LNK1105/1224 系列（479c5e9f、a20a4070、39082932、c99032e9）同属 Windows 产物文件完整性陷阱。
