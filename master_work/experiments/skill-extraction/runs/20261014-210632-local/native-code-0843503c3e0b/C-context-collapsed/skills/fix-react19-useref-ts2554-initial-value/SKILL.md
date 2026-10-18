---
name: fix-react19-useref-ts2554-initial-value
description: Use when tsc reports TS2554 'Expected 1 arguments, but got 0' on a `useRef<T>()` call in a React 19 project whose types no longer provide the no-argument overload. Helps the agent widen the type parameter with `| undefined`, pass `undefined` explicitly, and confirm via a clean tsc --noEmit re-run. Requires tsc output naming the file/line and permission to edit that file. Do not use for TS2554 errors on other calls, or when the project's @types/react still accepts `useRef<T>()`.
---
# Fix TS2554 on zero-argument useRef by passing an explicit undefined initial value

## Goal
消除 React 19 类型环境下 `useRef<T>()` 缺少初始值导致的 TS2554 'Expected 1 arguments, but got 0'：把引用改为 `useRef<T | undefined>(undefined)`，并以 `npx tsc --noEmit` 复跑该错误消失且无新错误作为最终产物。

## Scope
### In scope
- tsc 输出中指向 `useRef<...>()` 调用（无实参）的 TS2554 行。
- 需要保存可能未初始化的句柄（如 debounce 的 `setTimeout` 返回值）的场景。
- 修复后用同一 tsc 命令复跑验证。

### Out of scope
- 其他原因的 TS2554（普通函数/组件调用实参数量不匹配）。
- useRef 语义的其他用法（引用对象、`useRef` 初始值为非 undefined 值）。
- 应用运行时行为（如定时器是否真正 debounce）——轨迹未运行应用验证。

## Inputs
- **tsc 检查输出**：类型 string；来源：Bash 运行 `npx tsc --noEmit` 的工具结果；必需；需包含形如 `path(line,col): error TS2554: Expected 1 arguments, but got 0.` 的行；默认值：无。
- **出错源码行**：类型 string；来源：用 Read 打开 tsc 报告的文件与行号读到的代码；必需；应确认该调用形如 `const x = useRef<SomeType>()`（无第二参数）；默认值：无。
- **React 类型版本**：类型环境事实；来源：前端 package.json（轨迹中 `react` 与 `@types/react` 均为 `^19.2.0`）；必需——React 19 类型不再接受无参 `useRef<T>()`；默认值：无。

## Outputs
### Artifacts
- 修改后的 useRef 声明：如 `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`，位于被报告文件的原行位置。

### Success criteria
- 复跑同一 `npx tsc --noEmit` 命令，该 TS2554 消失且没有新增错误（轨迹中最终复跑完全无输出）。

### Failure criteria
- TS2554 仍在；或改后出现新的类型错误（如使用处未按 `| undefined` 处理）。

## Preconditions
- 项目能执行 `npx tsc --noEmit` 并产出错误定位；否则无法定位或验证。
- 使用 React 19 类型（`@types/react` 19.x，无参 `useRef<T>()` 重载已不存在）；若项目类型仍接受无参调用，TS2554 不会出现，本 Skill 不适用。
- 已通过 Read 确认出错行确实是无初始值的 `useRef` 调用；若该行是其他函数调用，停止并按其他 TS2554 处理。

## Procedure
### Step 1: 定位 TS2554 并确认是 useRef 调用
- actions：运行 `npx tsc --noEmit`，找到 `error TS2554: Expected 1 arguments, but got 0.` 行；用 Read 打开该文件对应行，确认代码形如 `const name = useRef<SomeType>()`（无第二实参）。
- inputs：tsc 输出；源文件。
- outputs：确认后的出错行（文件 + 行号 + 代码）。
- cautions：TS2554 也可由其他函数调用的实参数量不匹配引起；只有确认是无参 `useRef` 才继续。
- preserve：该行原有类型参数语义（要保存的是“可能为空的句柄”）。
- next：确认为 useRef 无参调用则进入 Step 2；否则停止并按其他 TS2554 处理。

### Step 2: 显式传入 undefined 并放宽类型参数
- actions：把 `useRef<T>()` 改写为 `useRef<T | undefined>(undefined)`。轨迹中的实际改写：`const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`。
- inputs：Step 1 确认的出错行。
- outputs：改写后的 useRef 声明。
- cautions：不要用非空断言或 `@ts-ignore` 绕过；不要改动该变量的读写处——`clearTimeout(debounceRef.current)` 这类用法在 `| undefined` 下仍可编译。
- preserve：变量名与后续赋值逻辑（`debounceRef.current = setTimeout(...)` 保持不变）。
- next：改完进入 Step 3。

### Step 3: 复跑类型检查验证
- actions：重新执行相同的 `npx tsc --noEmit`；确认目标 TS2554 消失且无新增错误。
- inputs：修改后的代码。
- outputs：新的 tsc 输出。
- cautions：若出现新错误，检查使用处是否对 undefined 情形做了错误假设。
- preserve：其他文件的改动（如同时进行的 TS1484 修复）不受影响。
- next：目标错误消失且无新增错误即完成；否则回到 Step 1 重新核对行号。

## Decision Rules
### When TS2554 指向无初始值的 useRef
采用 `useRef<T | undefined>(undefined)` 改写。证据：出错行是 `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`，改写为 `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`。

### When 该 ref 保存的是可延迟获取的句柄（如 setTimeout 返回值）
保留 `| undefined` 类型，因为首次赋值前变量确实为空；不要改成必赋值断言。

### When TS2554 指向的不是 useRef 调用
本 Skill 不适用；按对应调用的实参数量问题单独处理（轨迹未覆盖此类情形）。

## Invariants
- 不用 `@ts-ignore`、非空断言 `!` 或放宽 tsconfig 来绕过错误。
- 只改出错的 useRef 声明行，不改该变量的读写逻辑与其他文件。
- 不在未复跑 tsc 前声称修复成功。

## Common Failures
### Failure: 改完 TS2554 仍在
- symptoms：复跑仍指向同一行报 TS2554。
- causes：改动没有落到 tsc 报告的确切行；或项目里存在多个相似的无参 useRef 调用，只改了一处。
- recovery：用 Read 重新核对行号与当前代码，逐个处理所有无参 useRef 调用后复跑。

### Failure: 复跑出现新的类型错误
- symptoms：新错误出现在使用该 ref 的地方。
- causes：类型参数与初始值不一致（例如只把初始值写成 `undefined` 却未在类型参数里加 `| undefined`）。
- recovery：统一写法为 `useRef<T | undefined>(undefined)`，使类型参数与 `undefined` 初始值匹配后复跑。

### Failure: 误把其他函数的 TS2554 当成本问题处理
- symptoms：按 useRef 方式修改后错误位置不变或语义被破坏。
- causes：该行并非 useRef 调用；本 Skill 的改写方式不适用。
- recovery：撤销改动，按该调用真实的实参数量问题处理（轨迹未覆盖此类情形的验证方案）。

## Verification
- 复跑与最初相同的 `npx tsc --noEmit`，输出里不再有指向该行的 `TS2554`。
- 该行代码形如 `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`：类型参数含 `| undefined`，第二实参为 `undefined`。
- 复跑输出中没有因本次改动新增的错误码。
- 轨迹中的最终观察：该修复与 TS1484 修复一起完成后，`npx tsc --noEmit` 的工具结果为无输出。以上为应执行的检查项，不代表任何后续会话已执行。

## Examples
### Example 1: debounce 定时器句柄
- input：tsc 报 `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.`；该行为 `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`,组件随后用 `debounceRef.current = setTimeout(...)` 赋值、`clearTimeout(debounceRef.current)` 清除。
- procedure：Step 1 用 Read 确认该行是无参 useRef；Step 2 改写为 `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`；Step 3 复跑 `npx tsc --noEmit`。
- expected result：该 TS2554 消失，且复跑无新增错误；后续 `debounceRef.current` 的赋值与 clearTimeout 用法无需改动即可通过类型检查。
- parameterized values：类型参数替换为你的句柄类型（如 `HTMLInputElement`、worker/observer 句柄）；变量名替换为实际名称。

## Evidence
- problem：file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`，source_index 217，source_part_index 0，quote：`src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.`，supports：problem（TS2554 报告位置）。
- problem context：同 file_id，source_index 245，source_part_index 0，quote：`const debounceRef = useRef<ReturnType<typeof setTimeout>>()`，supports：problem（Read 该文件确认出错行是无初始值的 useRef 调用）。
- action：同 file_id，source_index 252，source_part_index 0，quote：`const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`，supports：action（把类型参数放宽为 `| undefined` 并显式传入 `undefined` 的改写方式）。
- verification：同 file_id，source_index 255，source_part_index 0，quote：`(Bash completed with no output)`，supports：verification（修复后复跑 `npx tsc --noEmit` 无输出，TS2554 与其余错误全部消失）。
