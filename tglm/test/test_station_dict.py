"""测试车站字典选站逻辑"""
from trip_planner.agent.state import Place
from trip_planner.tools.station_dict import pick_nearest_station


def test_pick_station_known_city():
    place = Place(raw_text="杭电", longitude=120.194472, latitude=30.298914)
    s = pick_nearest_station("杭州", place)
    assert s["name"] in ("杭州东", "杭州", "杭州南")
    # 杭电在下沙，离杭州东最近
    assert s["name"] == "杭州东"


def test_pick_station_unknown_city_returns_default():
    place = Place(raw_text="某地", longitude=100.0, latitude=30.0)
    s = pick_nearest_station("未知城市", place)
    assert "name" in s


def test_pick_station_ungocoded_returns_first():
    place = Place(raw_text="某地")  # 未 geocode
    s = pick_nearest_station("杭州", place)
    # 默认返回列表第一个
    assert s["name"] == "杭州东"
