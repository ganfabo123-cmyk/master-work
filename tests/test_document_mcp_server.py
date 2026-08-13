from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_servers.document_mcp.engines import OcrEngine, PdfEngine


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "jubensha" / "08_12个人物线索.pdf"


def test_pdf_engine_uses_ocr_for_scanned_page() -> None:
    document = PdfEngine(OcrEngine()).parse(PDF, pages=[6])
    assert document.page_count == 6
    assert document.pages[0].kind == "scanned"
    text = document.pages[0].text
    assert "侍女" in text
    assert "相機" in text or "相机" in text


async def _stdio_roundtrip() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_servers.document_mcp", "--transport", "stdio"],
        cwd=str(ROOT),
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert {"ocr_image", "parse_pdf", "get_pdf_content"} <= names

            parsed = await session.call_tool(
                "parse_pdf",
                {"pdf_path": str(PDF), "pages": [6], "ocr_mode": "auto"},
            )
            assert not parsed.isError
            document_id = parsed.structuredContent["document_id"]
            content = await session.call_tool(
                "get_pdf_content",
                {"document_id": document_id, "pages": [6], "max_chars": 20000},
            )
            assert not content.isError
            raw = str(content.structuredContent)
            assert "侍女" in raw
            assert "相機" in raw or "相机" in raw


def test_real_mcp_stdio_roundtrip() -> None:
    asyncio.run(_stdio_roundtrip())
