# dsh-memory 插件开发现状

## 已完成

- 新增模型工具 `memory_list_blocks`：无参数，按字典序返回当前拥有持久块文件的所有块名（扫描磁盘 `<block>_memory.md` 文件，含未在本进程加载的块；memoryDir 不存在时返回空清单）。
- 新增 `MemoryService.listBlocks()` 服务方法（`src/service.ts`）。
- 新增 `formatBlockIndex()` 输出格式化（`src/model.ts`），并导出（`src/index.ts`）。
- 更新 `SYSTEM_PROMPT`：在选块前先用 `memory_list_blocks` 发现当前块集合。
- 测试：`tests/memory.spec.ts`、`tests/loader-composition.spec.ts`、`tests/lifecycle.spec.ts` 已更新；memory 包相关 5 个测试文件共 30 个测试全部通过；typecheck 与 `tsc -b` 构建通过。
- 文档：`README.md`、`README.zh.md`、`docs/tool-catalog.md`（重新生成）、`docs/tool-catalog.zh.md`、`scripts/gen-tool-catalog.ts` 已同步。

## 未完成

- `verify-translation-pairing` 的 `.i18n.yaml` 配对记录未重新记录（tool-catalog 与 memory README 均报 out of sync，需 `--write`）。
- 尚未进行 acceptance（fresh DSH 验收）。

## 与本次改动无关的预存状态

- `tests/fact.spec.ts` 有 3 个失败（`persists facts to the per-cwd markdown file`、`injects the current cwd facts as a system-prompt section`、`injects cwd facts into the real system prompt sent to the model`）：该文件及其相关实现为工作区预存的半成品改动（`memoryFile`→`memoryDir` 迁移、`formatFactSection` 编号格式与旧断言不一致），未在本轮处理。
- 工作区存在大量与 memory 无关的预存未提交改动（`cordis_sub_agent`、`generated` 插件等）。