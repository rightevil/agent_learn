"""测试 12306 mock 数据"""
import pytest

from trip_planner.tools.train import query_trains


@pytest.mark.asyncio
async def test_query_trains_mock_hangzhou_to_ningbo():
    result = await query_trains.ainvoke({
        "from_station": "杭州东",
        "to_station": "宁波",
        "date": "2026-06-21",
    })
    assert "trains" in result
    assert len(result["trains"]) > 0
    first = result["trains"][0]
    assert "code" in first
    assert "depart" in first
    assert "arrive" in first
    assert first["depart"] == "07:30"


@pytest.mark.asyncio
async def test_query_trains_mock_return_journey():
    result = await query_trains.ainvoke({
        "from_station": "宁波",
        "to_station": "杭州东",
        "date": "2026-06-21",
    })
    assert len(result["trains"]) >= 1
    # 返程默认取最晚一班
    last = result["trains"][-1]
    assert last["code"] == "G7540"


@pytest.mark.asyncio
async def test_query_trains_mock_unknown_route():
    result = await query_trains.ainvoke({
        "from_station": "北京",
        "to_station": "上海",
        "date": "2026-06-21",
    })
    # 兜底数据
    assert len(result["trains"]) == 3
