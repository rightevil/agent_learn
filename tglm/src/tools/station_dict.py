"""城市 → 主要火车站 映射表 + 选站策略"""
from __future__ import annotations

from typing import Any

from ..agent.state import Place
from ..logging_setup import get_logger
from ..utils.geo import haversine_km

logger = get_logger(__name__)

# 主要火车站（粗略经纬度，MVP 够用）
STATION_DICT: dict[str, list[dict[str, Any]]] = {
    "杭州": [
        {"name": "杭州东", "longitude": 120.213333, "latitude": 30.290556},
        {"name": "杭州", "longitude": 120.174444, "latitude": 30.243056},
        {"name": "杭州南", "longitude": 120.301944, "latitude": 30.168056},
    ],
    "宁波": [
        {"name": "宁波", "longitude": 121.550556, "latitude": 29.833611},
        {"name": "宁波东", "longitude": 121.583333, "latitude": 29.833611},
    ],
    "上海": [
        {"name": "上海虹桥", "longitude": 121.319722, "latitude": 31.194167},
        {"name": "上海", "longitude": 121.457222, "latitude": 31.251944},
        {"name": "上海南", "longitude": 121.433611, "latitude": 31.152778},
    ],
    "南京": [
        {"name": "南京南", "longitude": 118.797778, "latitude": 31.975833},
        {"name": "南京", "longitude": 118.788611, "latitude": 32.093611},
    ],
    "苏州": [
        {"name": "苏州", "longitude": 120.602778, "latitude": 31.317222},
        {"name": "苏州北", "longitude": 120.729167, "latitude": 31.421667},
    ],
    "绍兴": [
        {"name": "绍兴北", "longitude": 120.581944, "latitude": 30.049444},
        {"name": "绍兴", "longitude": 120.596667, "latitude": 30.001389},
    ],
    "嘉兴": [
        {"name": "嘉兴南", "longitude": 120.763889, "latitude": 30.747222},
        {"name": "嘉兴", "longitude": 120.761944, "latitude": 30.773611},
    ],
}


def pick_nearest_station(city: str | None, place: Place) -> dict[str, Any]:
    """在指定城市中选择距离 place 最近的火车站。

    Args:
        city: 城市名
        place: 出发地或目的地（需已 geocode）

    Returns:
        火车站 dict: {name, longitude, latitude}
    """
    stations = STATION_DICT.get(city or "", [])
    if not stations:
        logger.warning("station_dict_empty", city=city)
        # 兜底返回城市名本身作为车站
        return {"name": (city or "未知") + "站", "longitude": 0, "latitude": 0}

    if not place.is_geocoded():
        # 未 geocode 时默认返回第一个
        return stations[0]

    nearest = min(
        stations,
        key=lambda s: haversine_km(
            place.longitude, place.latitude, s["longitude"], s["latitude"]
        ),
    )
    logger.info("station_picked", city=city, station=nearest["name"])
    return nearest
