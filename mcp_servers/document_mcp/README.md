# Document MCP Server

独立的 Model Context Protocol Server，为 MCP 客户端提供 PDF 解析和图片 OCR。

## 启动

从仓库根目录运行：

```powershell
python -m mcp_servers.document_mcp --transport stdio
```

也可独立安装后运行：

```powershell
python -m pip install .\mcp_servers\document_mcp
document-mcp --transport stdio
```

标准输出仅用于 MCP stdio 协议；运行日志写入标准错误。

## Tools

- `ocr_image`: 识别一张图片，返回原始文字、四点坐标和置信度。
- `parse_pdf`: 解析并缓存 PDF。原生文字层直接提取，无文字层页面使用 OCR。
- `get_pdf_content`: 按页读取已解析文档，避免一次把整本 PDF 放入模型上下文。

默认只允许读取当前工作目录、`CLAUDE_PROJECT_DIR`、`DOCUMENT_MCP_ROOTS`
中声明的目录。`DOCUMENT_MCP_ROOTS` 使用 Windows 分号或系统路径分隔符分隔。
