---
name: fix-ts1484-type-only-imports
description: Use when tsc reports TS1484 ('X is a type and must be imported using a type-only import when verbatimModuleSyntax is enabled') on named imports. Helps the agent rewrite the offending import statements with inline `type` modifiers and confirm with a clean re-run of tsc --noEmit. Requires ability to run `npx tsc --noEmit` and edit the reported source files. Do not use when the errors are other codes (TS6133, TS2554, runtime errors) or when no TypeScript checker run is available.
---
# Fix TS1484 by converting named type imports to inline type-only imports

## Goal
消除 TypeScript 在 `verbatimModuleSyntax` 启用时报出的 TS1484 错误：把被报告的命名导入改写为带内联 `type` 修饰符的仅类型导入，并以 `npx tsc --noEmit` 复跑不再出现 TS1484 作为最终产物。

## Scope
### In scope
- tsc 输出中带 `error TS1484` 的行所指向的文件与列号。
- 同一命名导入列表中混合值与类型的情况（只给类型名加 `type`）。
- 同一次 `tsc --noEmit` 运行中跨多个文件出现的全部 TS1484。

### Out of scope
- 修改 tsconfig（如关闭 `verbatimModuleSyntax`）来掩盖错误。
- 其他错误码（TS6133 未使用声明、TS2554 实参数量等）的修复。
- 运行时行为、构建产物、应用启动验证。

## Inputs
- **tsc 检查输出**：类型 string；来源：Bash 运行 `npx tsc --noEmit` 的工具结果；必需；每条形如 `path(line,col): error TS1484: 'Name' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.`，行内文件路径与列号是唯一定位依据；默认值：无。
- **被报告的源文件**：类型 file；来源：tsc 输出中的路径；必需；必须可编辑；轨迹中为 React + TanStack Router 项目的 `.tsx` 文件；默认值：无。
- **项目 TypeScript 环境**：类型环境事实；来源：tsconfig（轨迹未直接展示，但错误消息证实 `verbatimModuleSyntax` 已启用；轨迹中 typescript 版本为 `^6.0.2`）；必需；不可自行关闭该选项；默认值：无。

## Outputs
### Artifacts
- 修改后的 import 语句：位于被报告的源文件首部，Markdown/文本形式的代码改动（如 `import { type A, type B } from 'react'`）。

### Success criteria
- 复跑同一 `npx tsc --noEmit` 命令，输出中不再出现任何 `error TS1484` 行（轨迹中最终复跑完全无输出）。

### Failure criteria
- 复跑后仍有 TS1484 行；或修复引入新的编译错误（如把作为值使用的名称误标为 `type`）。

## Preconditions
- 项目能执行 TypeScript 编译器检查（轨迹中通过 `npx tsc --noEmit` 在 frontend 目录运行）；若无法运行检查器则停止并报告，因为无法定位也无法验证。
- tsconfig 中 `verbatimModuleSyntax` 处于启用状态（由 TS1484 错误消息本身证实）；不得通过关闭该选项来“修复”。
- 已有本次 tsc 完整输出，且输出中确实包含 TS1484 行；若只有其他错误码，不适用本 Skill。

## Procedure
### Step 1: 运行类型检查并收集全部 TS1484 行
- actions：在 TypeScript 项目目录执行 `npx tsc --noEmit`（可加 `| head -N` 截断，但须保证 TS1484 行完整可见）；逐条摘出含 `error TS1484` 的行，记录文件路径与列号。
- inputs：项目目录；tsc 可执行。
- outputs：TS1484 错误清单（文件 + 被报告的类型名）。
- cautions：同一次输出还可能包含其他错误码（轨迹中同时有 TS6133、TS2554）；本步骤只处理 TS1484，其余错误码单独记录。
- preserve：原始 tsc 输出，供修复后对比。
- next：清单非空则进入 Step 2；为空则说明无此问题，停止。

### Step 2: 给被报告的类型名加内联 `type` 修饰符
- actions：打开每个被报告文件的 import 行；对每个被点名的类型名加 `type ` 前缀（如 `import { type CSSProperties, type ReactNode } from 'react'`）；同一行中作为值使用的名字保持不变（如 `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`）。
- inputs：Step 1 清单；源文件 import 行。
- outputs：改写后的 import 语句。
- cautions：`type` 内联修饰符写在 specifier 名字前、逗号之后；不要改动模块说明符（`from 'react'`）。
- preserve：导入的名字集合与顺序、值导入的行为。
- next：所有清单项改完后进入 Step 3。

### Step 3: 复跑类型检查验证
- actions：重新执行与 Step 1 相同的 `npx tsc --noEmit`；检查输出中不再有 TS1484。
- inputs：修改后的代码。
- outputs：新的 tsc 输出。
- cautions：若输出出现新的错误码，说明某名字被误标为 `type`（该名字在代码中被当作值使用），需回退该名字的 `type` 修饰符。
- preserve：不删除其他无关改动。
- next：TS1484 全部消失即完成；否则回到 Step 2 补齐遗漏行。

## Decision Rules
### When 一行导入同时包含值和类型
只给被报告为类型的 specifier 加 `type`，值 specifier 不动。证据例：`import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`（前四个是值，ReactNode 加 `type`）。

### When 一行中有多个被报告的类型名
逐个都加 `type`（轨迹中 ui.tsx 一行 5 个名字全部被报告：CSSProperties、ReactNode、InputHTMLAttributes、TextareaHTMLAttributes、SelectHTMLAttributes，5 处都要加）。

### When tsc 输出中还混有其他错误码
先修全部 TS1484，再单独处理其余错误码；验证时以“TS1484 全部消失”为本 Skill 的完成条件。

### When 复跑后出现新的错误
说明某个名字被误标为 `type`——它在代码里被当作值使用；去掉该名字的 `type` 修饰符后复跑。

## Invariants
- 不通过修改 tsconfig（关闭 `verbatimModuleSyntax` 等）来消除错误。
- 只改被报告的 import specifier，不改动组件/逻辑代码、不重排导入名字顺序。
- 不把推测当事实：只有 tsc 输出中列出的名字才加 `type`；未被报告的名字保持原样。
- 不在未复跑 tsc 前声称修复成功。

## Common Failures
### Failure: 只修了一个文件，复跑仍报其他文件的 TS1484
- symptoms：复跑 tsc 后仍出现别的文件的 TS1484 行。
- causes：tsc 一次输出可能包含多个文件的多条 TS1484（轨迹中 ui.tsx 5 条 + auth.tsx 1 条），逐个修完才算完成。
- recovery：重新收集完整 tsc 输出，把剩余 TS1484 行全部改完再复跑。

### Failure: 修复后出现新错误，某个值导入被标成了 type
- symptoms：复跑输出出现新错误码（如运行时报找不到或编译期报该名字不能当值用）。
- causes：误给实际作为值使用的 specifier 加了 `type`。
- recovery：去掉该名字的 `type` 修饰符，只保留给纯类型名的修饰符后复跑。

### Failure: 引入了新的 TS1484 却没注意到
- symptoms：复跑输出里出现了此前没有的 TS1484。
- causes：新增代码中的导入沿用了旧写法。
- recovery：对新增行同样加内联 `type` 并再次复跑。

## Verification
- 复跑与最初相同的 `npx tsc --noEmit`（轨迹中命令为在 frontend 目录执行 `npx tsc --noEmit`），输出里 grep 不到 `TS1484`。
- 修复后的 import 行包含被报告名字的 `type ` 前缀，且同一行的值导入没有 `type` 前缀。
- 复跑输出中没有因本次改动新增的错误码。
- 轨迹中的最终观察：修复 6 条 TS1484 并顺带处理 TS6133/TS2554 后，`npx tsc --noEmit` 的工具结果为无输出（即零错误）。以上为应执行的检查项，不代表任何后续会话已执行。

## Examples
### Example 1: React 类型导入（多名字、单文件）
- input：tsc 报 `src/components/ui.tsx(1,10)` 至 `(1,81)` 共 5 条 TS1484；原行为 `import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'`。
- procedure：Step 1 收集 5 条错误；Step 2 把 5 个名字全部加 `type`；Step 3 复跑 tsc。
- expected result：tsc 输出中该文件不再出现 TS1484。
- parameterized values：文件路径替换为你的项目路径；名字替换为实际被报告的类型名。

### Example 2: 值与类型混合的导入
- input：tsc 报 `src/context/auth.tsx(1,58)` 的 `'ReactNode'`；原行为 `import { createContext, useContext, useState, useEffect, ReactNode } from 'react'`。
- procedure：只给 ReactNode 加 `type`，其余四个值导入保持不变；复跑 tsc。
- expected result：该文件 TS1484 消失，值导入行为不变。
- parameterized values：模块名可为 `react` 或其他包；值名替换为实际使用的 hooks/工具函数。

## Evidence
- problem：file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`，source_index 217，source_part_index 0，quote：`src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.`，supports：problem（TS1484 在 verbatimModuleSyntax 下对命名类型导入的报错形态；同一结果中还有 ui.tsx 4 条与 auth.tsx 1 条同码错误）。
- action：同 file_id，source_index 218，source_part_index 0，quote：`import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`，supports：action（对单行多类型名加内联 `type` 修饰符的改写方式）。
- action：同 file_id，source_index 221，source_part_index 0，quote：`import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`，supports：action（值与类型混合导入时只给类型名加 `type`）。
- verification：同 file_id，source_index 255，source_part_index 0，quote：`(Bash completed with no output)`，supports：verification（修复后复跑 `npx tsc --noEmit` 的工具结果为空输出，即零编译错误）。
