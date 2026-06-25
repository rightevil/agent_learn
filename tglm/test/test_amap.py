"""测试高德 mock 模式"""
import pytest

from trip_planner.tools.amap import geocode, reverse_geocode, transit_route


@pytest.mark.asyncio
async def test_geocode_mock_known_address():
    result = await geocode.ainvoke({"address": "杭州电子科技大学研究生公寓"})
    assert "error" not in result
    assert result["city"] == "杭州"
    assert result["longitude"] > 0


@pytest.mark.asyncio
async def test_geocode_mock_unknown_address_returns_fallback():
    result = await geocode.ainvoke({"address": "随便什么不知道的地方"})
    # mock 兜底返回杭州市中心
    assert "longitude" in result
    assert result["city"] == "杭州"


@pytest.mark.asyncio
async def test_reverse_geocode_mock_hangzhou():
    city = await reverse_geocode.ainvoke({
        "longitude": 120.194472,
        "latitude": 30.298914,
    })
    assert city == "杭州"


@pytest.mark.asyncio
async def test_reverse_geocode_mock_ningbo():
    city = await reverse_geocode.ainvoke({
        "longitude": 121.622222,
        "latitude": 29.766944,
    })
    assert city == "宁波"


@pytest.mark.asyncio
async def test_transit_route_mock():
    result = await transit_route.ainvoke({
        "origin": "120.194472,30.298914",
        "destination": "120.213333,30.290556",
        "city": "杭州",
    })
    assert "duration_minutes" in result
    assert result["duration_minutes"] > 0
    assert len(result["steps"]) > 0
