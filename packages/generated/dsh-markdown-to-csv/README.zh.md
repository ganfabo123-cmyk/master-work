中文 | [English](README.md)

# @deepseek-ai/dsh-markdown-to-csv

将 Markdown 表格转换为可下载的 CSV 文件。

该插件注册一个工具 `markdown_to_csv`。调用方的代理负责规范化：用户粘贴
原始 markdown（可能格式不规范——管道符对齐错乱、缺少表头分隔行、列数不
一致、夹杂正文），代理在正常回复中将其修复为干净的 markdown 表格，然后
用该表格调用此工具。工具在本地解析表格（无需额外的模型工作），序列化为
RFC 4180 CSV（CRLF 记录、字段带引号、UTF-8 BOM，以便 Excel 正确打开
非 ASCII 文本），并通过 Web 服务器上受令牌保护的路由提供下载。

工具返回下载 URL；代理将其呈现为可点击的链接。该链接仅在 dsh web GUI
中有效，因为浏览器端的 markdown 渲染器会阻止非 http(s) 目标。

## 使用

在 `dsh web` 中加载插件：

```sh
pnpm dsh web --patch ./packages/generated/dsh-markdown-to-csv/cordis.yml
```

打开 `http://127.0.0.1:3080`，粘贴 markdown 表格并请求 CSV。代理会使用
规范化后的表格调用 `markdown_to_csv`，并以下载链接作为回复。

### 配置

```yaml
plugins:
  markdown-to-csv:
    downloadTtlSeconds: 3600   # 下载链接保持有效的时间
    maxPendingDownloads: 128   # 超出后按最早优先淘汰的上限
```

所有字段均为可选；以上为默认值。

### 工具：markdown_to_csv

输入：

- `markdown`（必需）：规范化后的 markdown 表格——一行由管道符分隔单元
  格的标题行、一个可选的分隔行，然后是数据行。
- `filename`（可选，默认 `table.csv`）：提供的文件名，会被清理为带有
  `.csv` 扩展名的安全基名。

输出（`filename`、`downloadUrl`、`rowCount`、`columnCount`）。当文本中
不包含任何带管道符的表格，或数据行的单元格数多于标题行时，工具会明确报
错；行不足时以空单元格补齐。

## 模型体验

### 插件交互

#### 模型看到的内容

`markdown_to_csv` 工具的模式（必需的 `markdown`、可选的 `filename`），
以及每次调用时一个汇总行数与列数并附带纯文本下载 URL 的渲染结果。URL 以
文本形式交付；代理的回复将其转换为 markdown 链接。

插件本身不执行任何模型工作：它在本地解析 markdown，因此工具结果是模型
从转换中看到的唯一文本。

#### Token 影响

没有额外的提供商调用。工具结果仅向代理的请求上下文添加一行简短的渲染文
本（`N rows × M columns ... URL`）。

#### KV 缓存影响

无：插件从不发起提供商请求，因此请求前缀不受影响。

## 下载路由

每次转换都会将一个带 BOM 前缀的 CSV 主体以 `crypto.randomUUID()` 令牌
为键保存在内存中。路由前缀为所组合的 `ctx.webServer` 上的
`/api/md-table-csv/<token>`；响应携带 `Content-Type: text/csv; charset=utf-8`、
带 ASCII 回退和 RFC 5987 UTF-8 文件名的
`Content-Disposition: attachment`、`Content-Length` 以及
`Cache-Control: no-store`。未知或已过期的令牌返回 404。过期的条目在访问
时被移除；存储超过 `maxPendingDownloads` 时按最早优先淘汰。不会向磁盘
写入任何内容。

## 已知限制与待办工作

- 下载链接要求在同一进程中组合 Web 服务器；没有
  `@deepseek-ai/dsh-host-webserver` 的无头组合会让每次调用明确失败，而
  不会回退为写入文件。
- 工具只解析第一段连续的带管道符行；调用方代理必须传入单个表格。行长度
  超过标题会明确失败，以便代理重新对齐后重试。
- 单元格内容不能跨物理行（markdown 表格同样如此）：调用方代理在调用工
  具前必须合并或转义内嵌的换行符。
- 提供的 CSV 只存在于进程内存中：链接会随进程终止失效，并在
  `downloadTtlSeconds` 之后过期，且在重启后不会持久保留。
- 下载路由不是通用文件服务器：它只提供此插件创建的 CSV。