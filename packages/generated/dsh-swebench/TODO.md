# dsh-swebench 待解决问题（开发待办）

本文件是开发待办清单，不是用户文档。问题按优先级排序；每条包含现状、
修法方向与验证方式，供后续按文档逐条修复。涉及用户的已记录限制引用
[`README.md`](README.md) 的 Known Limitations，不在此重复。

## ✅ P0-1 django swb_eval 已改为整批运行（已完成，2026-08 复验）

- 现状：`src/scripts.ts` 的 evaluator 对每个 FAIL_TO_PASS / PASS_TO_PASS
  节点单独启动一次 `./tests/runtests.py`。Django test runner 单次启动要
  数十秒（加载 settings、准备数据库），PASS_TO_PASS 常有 10-20+ 节点，
  累计耗时 20-60 分钟。2026-08 验收中 django__django-10924 的 swb_eval
  因耗时过长被用户终止。
- 修法：django 分支改为官方 eval_script 的整批方式——一次
  `python tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1
  <labels>` 覆盖全部相关模块，再从 stdout 按测试名解析每个节点的
  ok/FAIL，得到与当前逐节点输出同构的分组判定。labels 取
  FAIL_TO_PASS / PASS_TO_PASS 节点中 `(module.Class)` 的模块部分去重。
- 已完成实现（`src/scripts.ts` buildEvaluator 的 runtests 分支）：
  - 用 `python tests/runtests.py` 调用（宿主 repo 为 CRLF，`./tests/runtests.py`
    的 shebang 带 `\r` 会 127 崩溃——这是旧版本从未在运行时跑通的隐藏根因之一）。
  - 解析输出：`FAIL:` / `ERROR:` 块标题计为失败，`<node> ... ok` 行计为通过；
    两者都未出现的节点保守计为失败（resolved 不会虚高）。
- 验证：4 个 django case（10914 / 10924 / 11001 / 11019）在真实容器中全部跑通，
  base 状态下 FAIL_TO_PASS 全部失败、PASS_TO_PASS 全部通过、resolved=false，
  ground truth 一致；单个 case 一次启动即完成，耗时降至分钟级以内
  （远低于 5 分钟目标，旧逐节点方式为 20-60 分钟）。

## ✅ P0-2 django swb_eval 全链路已复验（py3.6 兼容修复 + 整批之后）

- 现状：Python 3.6 不支持 `subprocess.run(capture_output=True, text=True)`
  （3.7+ 才有）。`src/scripts.ts` 已改为
  `stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True`
  的 3.6 兼容写法，但该修复后的 evaluator 从未在任何运行时完整跑通过。
- 本次修复与复验结论：
  1. runtests.py 接受 `module.Class.test_method` 全路径 label，也接受模块
     路径 label（容器内实证）；实现采用模块路径去重整批。
  2. test_patch 含新增文件（django__django-10924 的
     `tests/model_fields/test_filepathfield.py` 是 `new file mode 100644`）
     时，CRLF 防御 + `git apply --no-index` 可正常创建新文件（容器实证
     exit=0）。
  3. 容器内 curl 拉取官方数据可用（django 镜像 curl 7.81）。
  4. 本次额外修复：`apply_test_patch` 中残留的
     `capture_output=True, text=True`（3.7+ 专属）改为 PIPE 写法——这是
     "py3.6 兼容修复"未改彻底、evaluator 在容器内 TypeError 的另一根因。
- 验证：django__django-10924 完整执行 swb_eval，ground truth 核对通过
  （base 状态 F2P `test_callable_path` 失败、P2P `test_path` 通过、
  resolved=false）；验收运行时内子代理经 swb_eval 工具真实调用同样通过。

## ✅ P1 swb_eval 失败诊断已包含 stderr 尾部（已完成）

- 现状：`src/tools.ts` 的 `parseEvalVerdict` 报
  "no SWE_EVAL_RESULT result line in evaluator output" 时只展示 stdout
  尾部；evaluator 崩溃信息在 stderr（例如 py3.6 的 TypeError），模型拿
  不到根因，第一次 django 失败时因此无法定位。
- 修法：`parseEvalVerdict(stdout, stderr)` 在 marker 缺失时把 stderr 尾部
  一并拼进错误信息（`result.stderr` 已收集，`runDocker` 返回里有）。
- 验证：容器退出非 0 或 marker 缺失时，错误信息同时含 stderr 与 stdout
  尾部（代码路径已实现；真实复验中 evaluator 崩溃时的报错即可见
  Python traceback）。

## P2 数据集窗口固定 length=10

- 现状：`src/scripts.ts` 的 DATASET_URL 固定
  `offset=0&length=10`，只覆盖本地 10 个 case 所在窗口；窗口外的
  instance id 会报 "instance not found in dataset rows"。已在 README
  Known Limitations 记录。
- 修法（可选）：按 instance 行号构造 offset，或首次拉取后缓存行索引。
  本地 10 个 case 场景下无需修改。

## P2 本地沙箱与验收运行时的 docker 权限差异（诊断注意事项）

- 现状：在 DSH 沙箱的普通 pwsh 里直接 `docker run` 报 npipe
  permission denied（`dockerDesktopLinuxEngine`），但验收运行时经
  `ctx.subprocess.spawn` 调用 docker 正常工作（astropy swb_eval 已通过，
  说明插件运行时路径不受影响；本次 django swb_eval 验收同样经该路径
  通过）。
- 注意：后续容器内诊断优先走 `user_powershell` 桥或在验收运行时内通过
  swb_run / swb_eval 验证，不要用普通沙箱 pwsh 直接 docker run。