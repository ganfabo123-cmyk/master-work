"""One-shot MCP stdio handshake against pywechatcc's fastmcp server.

Verifies: server spawns, MCP initialize succeeds, and tools/list returns the
WeChat tools. Temporary acceptance script; not part of the repository.
"""

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_DIR = r"D:\PycharmProjects\CodeHarness\github_rep\pywechatcc\Mcp\pyweixin_rpa"
PYTHON = r"C:\Users\Lenovo\miniconda3\envs\wechat-mcp\python.exe"


async def main() -> None:
    params = StdioServerParameters(command=PYTHON, args=["-m", "mcp_server.server"], cwd=SERVER_DIR)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"server: {init.serverInfo.name} {init.serverInfo.version}")
            listed = await session.list_tools()
            print(f"tools: {len(listed.tools)}")
            for tool in listed.tools:
                print(f"  - {tool.name}: {(tool.description or '').splitlines()[0][:80]}")


asyncio.run(main())