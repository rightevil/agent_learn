# tools/mcp_client.py
"""MCP Client - 动态加载外部 MCP Server 的工具"""
from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from ..config import settings
from ..logging_setup import get_logger

logger = get_logger(__name__)


class MCPClientManager:
    """管理多个 MCP Server 连接，把它们的工具暴露为 LangChain Tool。"""

    def __init__(self):
        self._sessions: dict[str, ClientSession] = {}
        self._exit_stack = AsyncExitStack()
        self._tools_cache: dict[str, dict] = {}  # server_name → {tool_name: schema}

    async def connect_stdio(self, name: str, command: str, args: list[str], env: dict | None = None):
        """连接一个 stdio 类型的 MCP Server。"""
        logger.info("mcp_connect_stdio", name=name, command=command)
        server_params = StdioServerParameters(command=command, args=args, env=env)
        read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        # 列出工具
        tools_result = await session.list_tools()
        self._tools_cache[name] = {t.name: t for t in tools_result.tools}
        self._sessions[name] = session
        logger.info("mcp_connected", name=name, tools=list(self._tools_cache[name].keys()))

    async def connect_sse(self, name: str, url: str):
        """连接一个 SSE 类型的 MCP Server。"""
        logger.info("mcp_connect_sse", name=name, url=url)
        read, write = await self._exit_stack.enter_async_context(sse_client(url))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        tools_result = await session.list_tools()
        self._tools_cache[name] = {t.name: t for t in tools_result.tools}
        self._sessions[name] = session
        logger.info("mcp_connected", name=name, tools=list(self._tools_cache[name].keys()))

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """调用某个 MCP Server 上的工具。"""
        session = self._sessions.get(server_name)
        if not session:
            raise RuntimeError(f"MCP Server {server_name} not connected")

        logger.info("mcp_call_tool", server=server_name, tool=tool_name, args=arguments)
        result = await session.call_tool(tool_name, arguments)
        return self._parse_result(result)

    def list_all_tools(self) -> dict[str, list[str]]:
        """列出所有已连接 Server 的所有工具。"""
        return {srv: list(tools.keys()) for srv, tools in self._tools_cache.items()}

    async def close(self):
        await self._exit_stack.aclose()

    @staticmethod
    def _parse_result(result: Any) -> Any:
        """把 MCP CallToolResult 解析成 Python 对象。"""
        if hasattr(result, "content"):
            for c in result.content:
                if hasattr(c, "text"):
                    import json
                    try:
                        return json.loads(c.text)
                    except json.JSONDecodeError:
                        return c.text
        return result


# 全局单例
mcp_manager = MCPClientManager()

async def init_all_mcp_servers() :
    """根据配置批量连接 MCP Server。"""
    if not settings.MCP_SERVERS :
        return
    servers = json.loads( settings.MCP_SERVERS )
    for srv in servers :
        try :
            if srv[ "type" ] == "stdio" :
                await mcp_manager.connect_stdio(
                    name=srv[ "name" ] ,
                    command=srv[ "command" ] ,
                    args=srv.get( "args" , [ ] ) ,
                    env=srv.get( "env" ) ,
                )
            elif srv[ "type" ] == "sse" :
                await mcp_manager.connect_sse(
                    name=srv[ "name" ] ,
                    url=srv[ "url" ] ,
                )
        except Exception as e :
            logger.error( "mcp_connect_failed" , server=srv[ "name" ] , error=str( e ) )

    # 后续可加更多 server
    # await mcp_manager.connect_sse("weather", "https://mcp.weather.com/sse")