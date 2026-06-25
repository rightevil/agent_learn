"""12306 工具 - MCP + mock 降级"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from ..config import settings
from ..logging_setup import get_logger

logger = get_logger(__name__)


@tool
async def query_trains(from_station: str, to_station: str, date: str) -> dict:
    """查询某日某两站之间的火车/高铁车次。

    Args:
        from_station: 出发站中文名（如 "杭州东"）
        to_station: 到达站中文名（如 "宁波"）
        date: 日期 YYYY-MM-DD

    Returns:
        {trains: [{code, depart, arrive, duration, price}]}
    """
    logger.info("tool_call", tool="query_trains",
                from_station=from_station,
                to_station=to_station, date=date)

    if settings.MCP_12306_ENABLED:
        try:
            return await _query_via_mcp(from_station, to_station, date)
        except Exception as e:
            logger.error("mcp_12306_failed_fallback_to_mock", error=str(e))

    return await _query_via_mock(from_station, to_station, date)


async def _query_via_mcp(from_station: str, to_station: str, date: str) -> dict:
    """通过社区 12306 MCP server 查询。

    MVP 阶段尚未验证具体 MCP 实现的 API 形状，因此此处保留调用骨架，
    实际接入时按所选 MCP 的 tool schema 调整 method name 与 args。
    """
    # 延迟 import：仅在启用 MCP 时才需要
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        raise RuntimeError(f"mcp package not installed: {e}")

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@mcp/12306-server"],
        env=None,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "query_train",
                {
                    "from": from_station,
                    "to": to_station,
                    "date": date,
                },
            )
            return _parse_mcp_result(result)


def _parse_mcp_result(result: Any) -> dict:
    """把 MCP 返回的结果归一化为 {trains: [...]}。"""
    # MCP tool result 通常是 CallToolResult，content 是 list[TextContent | ...]
    if hasattr(result, "content"):
        for c in result.content:
            if hasattr(c, "text"):
                import json
                try:
                    parsed = json.loads(c.text)
                    if isinstance(parsed, dict) and "trains" in parsed:
                        return parsed
                    if isinstance(parsed, list):
                        return {"trains": parsed}
                except json.JSONDecodeError:
                    continue
    # fallback：返回空
    return {"trains": []}


async def _query_via_mock(from_station: str, to_station: str, date: str) -> dict:
    """降级用：返回 mock 车次数据，保证主循环可跑通。

    针对 杭州-宁波、宁波-杭州 两条线路给出真实风格的车次；其它线路兜底。
    """
    key = f"{from_station}-{to_station}"

    mock_db: dict[str, list[dict[str, Any]]] = {
        "杭州东-宁波": [
            {"code": "G7561", "depart": "07:30", "arrive": "08:25",
             "duration": "00:55", "price": 73},
            {"code": "G7565", "depart": "08:00", "arrive": "08:58",
             "duration": "00:58", "price": 73},
            {"code": "G7671", "depart": "08:25", "arrive": "09:20",
             "duration": "00:55", "price": 73},
            {"code": "G7581", "depart": "09:10", "arrive": "10:08",
             "duration": "00:58", "price": 73},
            {"code": "G7583", "depart": "10:15", "arrive": "11:12",
             "duration": "00:57", "price": 73},
        ],
        "杭州东-宁波东": [
            {"code": "G7561", "depart": "07:30", "arrive": "08:25",
             "duration": "00:55", "price": 73},
            {"code": "G7565", "depart": "08:00", "arrive": "08:58",
             "duration": "00:58", "price": 73},
            {"code": "G7671", "depart": "08:25", "arrive": "09:20",
             "duration": "00:55", "price": 73},
        ],
        "宁波-杭州东": [
            {"code": "G7534", "depart": "18:42", "arrive": "19:38",
             "duration": "00:56", "price": 73},
            {"code": "G7536", "depart": "19:25", "arrive": "20:21",
             "duration": "00:56", "price": 73},
            {"code": "G7540", "depart": "20:35", "arrive": "21:31",
             "duration": "00:56", "price": 73},
        ],
        "宁波东-杭州东": [
            {"code": "G7534", "depart": "18:42", "arrive": "19:38",
             "duration": "00:56", "price": 73},
            {"code": "G7536", "depart": "19:25", "arrive": "20:21",
             "duration": "00:56", "price": 73},
        ],
        "杭州-宁波": [
            {"code": "G7561", "depart": "07:30", "arrive": "08:25",
             "duration": "00:55", "price": 73},
            {"code": "G7565", "depart": "08:00", "arrive": "08:58",
             "duration": "00:58", "price": 73},
        ],
        "宁波-杭州": [
            {"code": "G7534", "depart": "18:42", "arrive": "19:38",
             "duration": "00:56", "price": 73},
        ],
    }

    trains = mock_db.get(key)
    if trains is None:
        # 兜底
        trains = [
            {"code": "G9001", "depart": "08:00", "arrive": "09:00",
             "duration": "01:00", "price": 50},
            {"code": "G9002", "depart": "10:00", "arrive": "11:00",
             "duration": "01:00", "price": 50},
            {"code": "G9003", "depart": "14:00", "arrive": "15:00",
             "duration": "01:00", "price": 50},
        ]

    logger.info("tool_done", tool="query_trains",
                source="mock", count=len(trains))
    return {"trains": trains}
