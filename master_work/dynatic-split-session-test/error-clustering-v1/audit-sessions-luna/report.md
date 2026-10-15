# Luna 错误聚类审查（42组最终复核）

本次最终范围只包含 native-code 14 组与 exception-type 28 组；message-template 已停止，不进入统计。结论来自逐组阅读 groups.json evidence 并按 source_index 回到原始 JSONL；没有用“附近出现 fix/pass”自动配对。

## 总体判断

### native-code

共 14 组；归组状态：consistent 13、mixed 1；经验状态：usable 0、candidate 2、unsupported 12；usable 0/14，candidate 2/14。

### exception-type

共 28 组；归组状态：consistent 23、mixed 3、false_positive 2；经验状态：usable 1、candidate 1、unsupported 26；usable 1/28，candidate 1/28。

## 完整 usable 例子

exception-type-b5e7d3b42ad0：测试规格中 User/GameMap 未解析；1142 给出缺少类型导入的诊断，1143 实际修改限定名与 createTablesFor，1167 对同一 campaign/models/maps 目标报告 31 tests、0 failures、0 errors。audit.json 的 source_evidence 用 role=error/diagnosis/action/verification 分开列出。

## candidate 例子

native-code-c6460e120c75：LNK1107 的诊断明确指出 DLL 构建目标错误，229 行实际用 Windows MSVC target 重建 DLL；重建后 232 行仍报 LNK1107，缺少成功验证。

exception-type-c9afbe50532d：TypeError 的诊断明确指出 dataclass 默认字段顺序问题，129 行修改 ast_nodes.py；后续只看到 lexer 输出，未验证原始 TypeError 的完整目标。

## 降级与边界

其余组没有形成同一错误→针对性处理→同目标真实验证的完整链。错误名、助手计划、同一 Session 中其他项目的修复、README 或不同测试目标的通过结果均不作为本组经验证据。源码中的 CodeGenError/LexError/ParseError 类型声明保留为 false_positive。

## 全量核对

已人工复核 42/42 组，策略合计 14+28=42；group_id 唯一。source_index 保留原始零基行号，json_pointer 的 jsonl:N 保留一基行号。未执行轨迹命令，未修改算法和 sessions-30 原始产物。
