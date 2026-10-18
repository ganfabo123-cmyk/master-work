---
name: gate-cdp-devtools-endpoint-before-econnreset
description: Use when an adb-forwarded CDP client against an Android WebView devtools endpoint dies with ECONNRESET / "socket hang up" while typecheck, APK build, install and app launch all succeeded. Helps the agent localize the failure to the CDP step only, add a curl readiness gate before running the Node CDP script, and re-run the deploy+screenshot pipeline. Requires adb with a connected device, curl, and a CDP eval script that talks to http://localhost:9222/json. Do not use when the build itself fails, when there is no adb/WebView environment, or for ECONNRESET from unrelated HTTP clients.
---
# Gate the WebView DevTools endpoint before CDP eval to fix ECONNRESET

## Goal
定位并修复“构建/安装/启动全部成功但 CDP 脚本连 WebView DevTools 时报 ECONNRESET (socket hang up)”的失败，产出一条带 curl 就绪门禁的 adb forward → CDP eval → screencap 可复用命令序列，使后续部署验证命令以 Exit code 0 和 "shot saved" 结束。

## Scope
### In scope
- 链式命令中 typecheck、APK 构建（BUILD EXIT=0）、adb install、am start 均成功，仅随后的 Node CDP 客户端（连 http://localhost:9222/json 再升级 WebSocket）报 `Error: socket hang up` / `code: 'ECONNRESET'` 的场景。
- 通过 `adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>` 暴露的 Android WebView DevTools 端点。
- 失败段定位（只重跑 CDP+截图段）、curl 就绪门禁的加入，以及把门禁固化进后续同型 pipeline。
- 该类失败下“构建成功 ≠ 整体成功”的判定与分段验证。

### Out of scope
- Gradle/APK 构建失败、typecheck 失败（BUILD EXIT 非 0 或无 "BUILD EXIT=0" 的输出）。
- 应用业务逻辑或 UI 问题的修复。
- 与 adb/WebView 无关的通用 HTTP 客户端 ECONNRESET（代理、服务器崩溃等），轨迹未提供该类场景的验证。
- CDP 客户端脚本自身的 error handler 改造（轨迹未提供验证，仅作为未验证提示）。

## Inputs
- **失败的 Bash 工具输出** — 类型：字符串（含 Exit code、BUILD EXIT、Node 堆栈）；来源：失败的 tool_result（本轨迹 source_index 686）；必需：是；约束：必须同时含 `BUILD EXIT=0` 与 `ECONNRESET`/`socket hang up` 才能判定为本技能适用；默认值：无。
- **原失败命令** — 类型：shell 命令串；来源：同一次 tool_call（本轨迹 source_index 685）；必需：是；约束：需包含 `adb forward tcp:9222 localabstract:webview_devtools_remote_$pid` 与 `node cdp-eval.mjs ...`；默认值：无。
- **adb 设备序列号** — 类型：字符串；来源：命令行 `-s <ip>:<port>`；必需：是（多设备时）；约束：设备必须在线；轨迹中为 `127.0.0.1:40859`，应参数化为实际设备地址；默认值：单设备时可省略 `-s`。
- **包名与启动 Activity** — 类型：字符串；来源：项目配置/原命令；必需：是；约束：用于 `am force-stop`、`am start`、`pidof`；轨迹中为 `net.opendsp.x4x4` / `net.opendsp.x4x4/.MainActivity`，其他项目须替换；默认值：无。
- **CDP eval 脚本** — 类型：Node ESM 脚本；来源：Write 创建（本轨迹 `/tmp/cdp-eval.mjs`，source_index 470）；必需：是；约束：脚本对 `http://localhost:9222/json` 发起请求且源码中该请求未挂 error handler，端点未就绪时会以 unhandled 'error' 事件崩溃；默认值：无（须自备）。
- **curl 与 adb platform-tools** — 类型：可执行依赖；来源：环境；必需：是；约束：curl 用于就绪门禁 `curl -sf http://localhost:9222/json`，adb 位于 `$HOME/Android/Sdk/platform-tools/adb`（轨迹值，应参数化）；默认值：无。
- **门禁轮询节奏** — 类型：shell 循环参数；来源：原命令；必需：是；约束：轨迹使用 `until ...; do sleep 1; done`，未给出上限或最大等待时长；默认值：`sleep 1`（轨迹未提供超时上限）。

## Outputs
### Artifacts
- **修复后的部署+验证命令序列**（位置：写入 Agent 的 Bash 调用或临时脚本，如轨迹中的 `/tmp/poc.sh` 式 shell 片段；格式：单行/多行 shell），核心为：`adb forward --remove tcp:9222; adb forward tcp:9222 localabstract:webview_devtools_remote_$pid` → `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done;` → `node cdp-eval.mjs '<expression>'` → `adb exec-out screencap -p > <png>`。
- **截图产物**（位置：如 `/tmp/pads7.png`、`/tmp/pads-centered.png`；格式：PNG）；具体文件名由调用方参数化。
- **CDP 表达式返回值**（位置：stdout；格式：JSON，如 `{"connected": true}` 或表达式求值结果）。

### Success criteria
- 整条命令 Exit code 0；stdout 含 CDP 返回结果与 `shot saved`。
- 就绪门禁自检 `curl -sf http://localhost:9222/json` 返回 0 后才运行 CDP 脚本。
- 截图文件非空且可读（`> <png>` 后 `echo "shot saved"` 出现）。

### Failure criteria
- 输出仍出现 `code: 'ECONNRESET'` 或 `Error: socket hang up`，或 Node 以 `Emitted 'error' event on ClientRequest` 崩溃。
- `BUILD EXIT` 非 0、typecheck 未打印 `OK`，或 install/launch 未打印 `Success`。
- 门禁循环无限等待、CDP 脚本打印 `timeout` 或命令整体 Exit code 非 0。

## Preconditions
- 失败输出中已出现 `BUILD EXIT=0`（以及 typecheck 的 `OK`、install 的 `Success`）——否则问题在构建/安装段，先解决构建，勿套用本技能。
- adb 可见目标设备，且应用进程可被 `adb shell pidof <package>` 取到；取到的 pid 需 `tr -d '\r'` 去除回车。
- 应用的 WebView 暴露 abstract socket `webview_devtools_remote_<pid>`（轨迹中用 `adb shell cat /proc/net/unix | grep -o "webview_devtools_remote_$pid"` 验证过）。
- 环境中存在 `curl` 与 `adb`（轨迹中 adb 为 `$HOME/Android/Sdk/platform-tools/adb`，Android 构建还需 `ANDROID_HOME`、`JAVA_HOME`，仅当同条命令还包含构建时才需要）。
- 已有可运行的 CDP eval 客户端脚本（轨迹中 `/tmp/cdp-eval.mjs`，通过 `http://localhost:9222/json` 取 `webSocketDebuggerUrl` 后手写 WebSocket 升级并 `Runtime.evaluate`）。
- 上述任一项不满足：停止执行并报告缺失项，不要先改应用代码或重建 APK。

## Procedure
### Step 1: 分段定位失败
- actions：读取失败 tool_result 全文（本轨迹 `read_event` source_index 686）与原命令（source_index 685）；确认输出前缀是否为 `Exit code 1` + `OK` + `BUILD EXIT=0` + `Success`，而 Node 堆栈含 `Error: socket hang up` 与 `code: 'ECONNRESET'`。
- inputs：失败输出、原命令。
- outputs：结论“构建/安装/启动成功，仅 CDP 段失败”，记下包名、设备地址、脚本路径。
- cautions：不要因 Exit code 1 就重跑构建；构建日志已显示成功（`BUILD EXIT=0`）。
- preserve：保留原命令与日志文件（如 `/tmp/apk-build6.log`）供比对。
- next：满足“BUILD EXIT=0 且错误为 ECONNRESET”→ Step 2；否则转去解决构建/安装问题。

### Step 2: 重建端口转发并等待应用进程
- actions：`adb=...` 取设备句柄；`$adb shell am force-stop <pkg> && $adb shell am start -n <pkg>/.MainActivity`（若应用已在运行可跳过重启）；`until $adb shell pidof <pkg> >/dev/null 2>&1; do sleep 1; done;`；`pid=$($adb shell pidof <pkg> | tr -d '\r')`；`$adb forward --remove tcp:9222 2>/dev/null; $adb forward tcp:9222 localabstract:webview_devtools_remote_$pid >/dev/null`。
- inputs：设备序列号、包名、Activity。
- outputs：新鲜的 tcp:9222 转发与 pid。
- cautions：pid 变化后旧 forward 指向死 socket，必须先 `--remove` 再重建。
- preserve：不改应用代码、不改 gradle/构建配置。
- next：转发建立 → Step 3。

### Step 3: 加入 curl 就绪门禁
- actions：在 `node cdp-eval.mjs` 之前插入 `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done;`。
- inputs：Step 2 的转发。
- outputs：确认 `http://localhost:9222/json` 可返回成功状态后才放行。
- cautions：轨迹未提供等待上限；若长时间不就绪，应回到 Step 2 检查 pid/abstract socket，而不是延长无限等待。
- preserve：门禁必须紧跟 forward、先于 CDP 脚本，顺序不可调换。
- next：门禁可通 → Step 4。

### Step 4: 运行 CDP eval 与截图验证
- actions：`cd /tmp && node cdp-eval.mjs '<expression>'`（轨迹用 `(async()=>{await globalThis.device.connect();for(let k=0;k<25&&!globalThis.device.connected;k++)await new Promise(r=>setTimeout(r,200));return globalThis.device.connected;})()'`）；成功后 `$adb exec-out screencap -p > <png> 2>/dev/null && echo "shot saved"`。
- inputs：待求值表达式、截图输出路径。
- outputs：CDP 返回值 JSON、截图文件。
- cautions：CDP 段的 stdout 被 `>/dev/null` 丢弃时，要用 `shot saved` 与 Exit code 判定，不要凭“命令没报错”臆断连接成功。
- preserve：截图路径参数化，不覆盖既有截图。
- next：输出含返回值与 `shot saved` → Step 5；否则回到 Step 2 重设转发。

### Step 5: 把门禁固化进后续同型 pipeline
- actions：将 typecheck → build → install → launch → 等 pid → forward → **curl 门禁** → CDP → screencap 组成固定模板，后续每次部署复用。
- inputs：Step 4 验证过的模板。
- outputs：可重复执行的部署验证流水线。
- cautions：任何导致 app 重启、pid 变化的改动之后，都要重新走 Step 2–4。
- preserve：模板中保留 `BUILD EXIT=$?` 这类分段状态输出。
- next：模板连续成功即停止迭代该问题。

## Decision Rules
### When 失败输出同时出现 `BUILD EXIT=0` 与 `code: 'ECONNRESET'`
只重跑 CDP 段（forward → 门禁 → node cdp-eval → screencap），不要重新构建 APK；本轨迹中仅重跑 CDP 段即得到 `"connected": true` 与 `shot saved`。

### When Node 堆栈显示 `Emitted 'error' event on ClientRequest instance`
判定为 CDP 客户端脚本对 `http://localhost:9222/json` 的请求未挂 error handler、请求被对端重置后进程崩溃；轨迹中验证的修复是在脚本前加 curl 就绪门禁，为脚本补 error handler 属未验证建议，需另行验证后才可宣称有效。

### When `adb forward` 已执行但 `curl http://localhost:9222/json` 不通
先确认 pid 仍有效（`adb shell pidof <pkg>`）与 `webview_devtools_remote_<pid>` abstract socket 存在，再 `--remove` 后重建 forward；不通过就不要启动 CDP 脚本。

### When 门禁通过后 CDP 表达式仍不返回预期值
保持门禁与转发不动，按表达式/应用状态排查（轨迹未提供该分支的进一步经验）。

### When 输出中没有 `BUILD EXIT=0` 或 typecheck 未打印 `OK`
退出本技能流程，按构建/类型检查问题单独处理。

## Invariants
- 不为修复该 ECONNRESET 而修改应用源码、构建脚本或构建/类型检查配置——失败发生在这些步骤已成功之后。
- 不跳过 curl 就绪门禁直接运行 CDP 脚本；app 重启或 pid 变化后必须重建 forward 并重新过门禁。
- 不把 `BUILD EXIT=0`/`Success` 报告为“整体验证成功”：Exit code 1 的命令里前段成功不等于后段成功，两段分别报告。
- 不在 `BUILD EXIT` 非 0、install 未打印 `Success`、或 `pidof` 取不到 pid 时继续执行 CDP 段。
- 不把“重试成功”当作对失败根因的最终证明：轨迹中“端点未就绪”是判断 + 门禁后成功的行为佐证，底层确切原因轨迹未确认，报告时按此措辞。
- 不引入未验证的替代方案（如改写 CDP 脚本加 error handler、换 websocket 库）并宣称已修复。
- 不覆盖既有截图与日志文件，截图/日志路径参数化。

## Common Failures
### Failure: CDP 段在部署后立刻报 ECONNRESET / socket hang up
- symptoms：tool_result 为 `Exit code 1`，其后是 `OK`、`BUILD EXIT=0`、`Success`，再出现 `Error: socket hang up` 与 `code: 'ECONNRESET'`，Node 版本行显示进程崩溃退出。
- causes：Assistant 判断为“CDP hit the devtools endpoint before it was ready (build/install/launch all succeeded)”；加入 curl 就绪门禁后同型命令连续成功，构成行为佐证；底层确切原因轨迹未确认（可能与 forward 刚建立、WebView devtools HTTP 端点尚未接受连接有关，此推测未在轨迹中验证）。
- recovery：保留已成功的构建产物，仅重建 forward 并在 `node cdp-eval.mjs` 前加 `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done;`，然后重跑 CDP + screencap 段。

### Failure: Node 客户端以 unhandled 'error' 事件崩溃
- symptoms：堆栈含 `node:events:497 throw er; // Unhandled 'error' event` 与 `Emitted 'error' event on ClientRequest instance at:`，脚本没有任何业务输出即退出。
- causes：脚本对 `http://localhost:9222/json` 的 `http.get` 未注册 error handler，请求失败即转为未捕获异常（脚本源码可见该请求只有 data/end 处理）。
- recovery：先用就绪门禁让请求不再失败（本轨迹验证）；给脚本补 error handler 的效果轨迹未提供验证，需要先自行验证再采用。

### Failure: 门禁一直不通过
- symptoms：`curl -sf http://localhost:9222/json` 持续失败，命令卡在 until 循环。
- causes：pid 已失效或 abstract socket `webview_devtools_remote_<pid>` 不存在，forward 指向了旧进程；确切原因需现场检查，轨迹未记录该情况的处理结果。
- recovery：回 Step 2 —— 重新 `pidof`、确认 `/proc/net/unix` 中的 socket 名、`adb forward --remove` 后重建转发；仍不通则停止并报告环境问题。

## Verification
- 分段状态输出：命令打印 `OK`、`BUILD EXIT=0`、`Success`，说明 typecheck、APK 构建、安装均成功（仅证明这三段，不证明 CDP 段）。
- 门禁自检：`curl -sf http://localhost:9222/json` 在 `node cdp-eval.mjs` 之前返回 0；可先单独运行一次观察其通过。
- CDP 段输出：`node cdp-eval.mjs` 打印出表达式返回值（本轨迹为 `{"connected": true}`），且无 `Error: socket hang up`、`code: 'ECONNRESET'`、`timeout`。
- 截图段输出：出现 `shot saved`，且对应 PNG 文件非空。
- 整体：Bash 工具未返回 `Exit code 1` / `is_error`。
- 回归：同型 pipeline（含门禁）在后续部署中重复成功——本轨迹中 source_index 707、750、795、817、850 的命令均带该门禁，其结果（如 708、755）均为 `OK`、`BUILD EXIT=0`、`Success`、`shot saved`。
- 负向检查：移除门禁前不宣称已修复——门禁是本轨迹中与成功结果直接对应的唯一改动变量（app 重启/代码改动另在别处验证，不应混入此结论）。

## Examples
### Example 1: 失败的部署+CDP pipeline（本轨迹 source_index 685 → 686）
- input：一条命令依次执行 `npm run -s typecheck && echo OK && ... ./build-apk.sh ...; echo "BUILD EXIT=$?"` → `adb install -r app/build/outputs/apk/debug/app-debug.apk` → `am force-stop`/`am start` → `until $adb shell pidof <pkg>` → `adb forward tcp:9222 localabstract:webview_devtools_remote_$pid` → **直接** `node cdp-eval.mjs '(async()=>{await globalThis.device.connect();...})()'` → `adb exec-out screencap -p > /tmp/pads7.png`。
- procedure：按 Step 1 分段读输出。
- expected result：输出前缀 `Exit code 1` / `OK` / `BUILD EXIT=0` / `Success`，随后 `Error: socket hang up`、`code: 'ECONNRESET'`，`shot saved` 未出现 —— 判定构建成功、CDP 段失败。
- parameterized values：包名 `net.opendsp.x4x4`、设备 `[REDACTED_IP]:40859`、脚本 `/tmp/cdp-eval.mjs`、截图 `/tmp/pads7.png`。

### Example 2: 重设转发 + curl 门禁后仅重跑 CDP 段（source_index 689 → 690）
- input：不重建 APK，只执行 `adb ... && pid=$($adb shell pidof <pkg> | tr -d '\r') && $adb forward --remove tcp:9222 2>/dev/null; $adb forward tcp:9222 localabstract:webview_devtools_remote_$pid >/dev/null && until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done; cd /tmp && node cdp-eval.mjs '<connect expression>' && $adb exec-out screencap -p > /tmp/pads7.png 2>/dev/null && echo "shot saved"`。
- procedure：Step 2 → Step 3 → Step 4。
- expected result：工具结果为 `{"connected": true}` 加 `shot saved`，`is_error` 为 false —— ECONNRESET 消失。
- parameterized values：门禁 `sleep 1`、截图输出 `/tmp/pads7.png`。

### Example 3: 门禁固化进完整 pipeline（source_index 707 → 708）
- input：`cd <web 模块> && npm run -s typecheck && echo OK && cd <android 模块> && export ANDROID_HOME=... JAVA_HOME=... && ./build-apk.sh > <log> 2>&1; echo "BUILD EXIT=$?"; ... 等 pid → adb forward ... && until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done; cd /tmp && node cdp-eval.mjs '<expr>' >/dev/null && adb exec-out screencap -p > /tmp/pads-centered.png 2>/dev/null && echo "shot saved"`。
- procedure：Step 5 模板化后执行。
- expected result：`OK`、`BUILD EXIT=0`、`Success`、`shot saved`，Exit code 0；同型命令在 750、795、817、850 反复复用成功。
- parameterized values：模块路径 `/home/USER/Code/tracks-dsp/web`、`/home/USER/Code/tracks-dsp/android`（应参数化）、构建日志 `/tmp/apk-build7.log`、截图 `/tmp/pads-centered.png`。

## Evidence
- **problem** — file_id: `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__original`，source_index: 686，source_part_index: 0，quote: `Exit code 1
OK
BUILD EXIT=0
Success
node:events:497`，supports: 失败命令的 typecheck、APK 构建、安装均成功，进程在随后的 Node CDP 段崩溃，故属 CDP 段专属失败。
- **problem** — 同上文件，source_index: 686，source_part_index: 0，quote: `Emitted 'error' event on ClientRequest instance at:`，supports: 崩溃来自 CDP 客户端 `http.get("http://localhost:9222/json", ...)` 的未处理 error 事件。
- **problem** — 同上文件，source_index: 686，source_part_index: 0，quote: `code: 'ECONNRESET'`，supports: 错误键与 error_key `symbolic-code:ECONNRESET` 对应。
- **diagnosis (assistant 判断)** — 同上文件，source_index: 688，source_part_index: 0，quote: `CDP hit the devtools endpoint before it was ready (build/install/launch all succeeded). Let me retry the connect + screenshot now that the app's up.`，supports: 把失败定位到 devtools 端点未就绪、且不重跑构建的处置策略；这是 Assistant 判断，不是工具结果。
- **action** — 同上文件，source_index: 689，source_part_index: 0，quote: `$adb forward tcp:9222 localabstract:webview_devtools_remote_$pid >/dev/null && until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done;`，supports: 关键改动 = 重建 forward 后、CDP 脚本前插入 curl 就绪门禁。
- **verification** — 同上文件，source_index: 690，source_part_index: 0，quote: `{
  "connected": true
}
shot saved`，supports: 加门禁后仅重跑 CDP+截图段即成功（is_error: false），ECONNRESET 消除。
- **action（固化进 pipeline）** — 同上文件，source_index: 707，source_part_index: 0，quote: `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done; cd /tmp && node cdp-eval.mjs`，supports: 门禁被写入完整 build→install→launch→CDP→screencap 流水线。
- **verification（固化后）** — 同上文件，source_index: 708，source_part_index: 0，quote: `OK
BUILD EXIT=0
Success
shot saved`，supports: 含门禁的完整流水线整体 Exit code 0 且完成截图。
- **verification（重复复用）** — 同上文件，source_index: 755，source_part_index: 0，quote: `OK
BUILD EXIT=0
Success
shot saved`，supports: 同型含门禁命令（750）再次成功，说明该修复可复用而非一次侥幸。
- **context** — 同上文件，source_index: 462，source_part_index: 0，quote: `sock=webview_devtools_remote_32373`，supports: 转发目标 abstract socket 名按 pid 组成，pid 失效时转发会指向死 socket。
- **context（脚本缺陷）** — 同上文件，source_index: 470，source_part_index: 0，quote: `http.get("http://localhost:9222/json", (r) => {`，supports: CDP 脚本的 http.get 只有 data/end 处理、无 error handler，端点失败即崩溃为 unhandled 'error' 事件。
