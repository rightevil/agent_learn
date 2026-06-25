# tools/mcp_adapter.py
"""把 MCP 工具包装成 LangChain @tool，让 Agent 调用方式统一"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool, Tool
from pydantic import BaseModel, create_model

from .mcp_client import mcp_manager
from ..logging_setup import get_logger

logger = get_logger(__name__)


def _schema_to_pydantic(schema: dict) -> type[BaseModel]:
    """把 MCP tool 的 JSON Schema 转成 Pydantic 模型（用于参数校验）。"""
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    fields = {}
    for name, prop in properties.items():
        py_type = str  # MVP：所有字段都当字符串处理，更复杂的可扩展
        if prop.get("type") == "integer":
            py_type = int
        elif prop.get("type") == "number":
            py_type = float
        elif prop.get("type") == "boolean":
            py_type = bool

        default = ... if name in required else None
        fields[name] = (py_type | None, default)

    return create_model("MCPToolArgs", **fields)


def mcp_tool_to_langchain(server_name: str, tool_name: str, tool_schema: Any) -> StructuredTool:
    """把一个 MCP tool 包装成 LangChain StructuredTool。"""

    # 异步调用函数
    async def _arun(**kwargs) -> dict:
        try:
            result = await mcp_manager.call_tool(server_name, tool_name, kwargs)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as e:
            logger.error("mcp_tool_call_failed",
                         server=server_name, tool=tool_name, error=str(e))
            return {"error": str(e)}

    # 同步调用函数（部分场景用）
    def _run(**kwargs) -> dict:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(_arun(**kwargs))

    # 构造 Pydantic schema
    input_schema = _schema_to_pydantic(tool_schema.inputSchema or {"properties": {}})

    return StructuredTool(
        name=f"mcp_{server_name}_{tool_name}",
        description=tool_schema.description or f"MCP tool {tool_name} from {server_name}",
        func=_run,
        coroutine=_arun,
        args_schema=input_schema,
    )


async def load_all_mcp_tools() -> list[StructuredTool]:
    """加载所有已连接 MCP Server 的所有工具，返回 LangChain Tool 列表。"""
    tools = []
    for server_name, tool_dict in mcp_manager._tools_cache.items():
        for tool_name, tool_schema in tool_dict.items():
            try:
                lc_tool = mcp_tool_to_langchain(server_name, tool_name, tool_schema)
                tools.append(lc_tool)
            except Exception as e:
                logger.warning("mcp_tool_load_failed",
                               server=server_name, tool=tool_name, error=str(e))
    logger.info("mcp_tools_loaded", count=len(tools))
    return tools