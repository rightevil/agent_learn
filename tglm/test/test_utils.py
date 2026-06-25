"""测试时间与地理辅助函数"""
from datetime import date, datetime, time

from trip_planner.utils.geo import haversine_km
from trip_planner.utils.time_calc import (
    add_minutes,
    combine_date_time,
    fmt_time,
    time_diff_minutes,
)


def test_haversine_same_point():
    assert haversine_km(120.0, 30.0, 120.0, 30.0) == 0.0


def test_haversine_known_distance():
    # 杭州东 → 宁波，约 140 公里
    d = haversine_km(120.213333, 30.290556, 121.550556, 29.833611)
    assert 130 < d < 150


def test_combine_date_time():
    dt = combine_date_time(date(2026, 6, 21), time(7, 30))
    assert dt == datetime(2026, 6, 21, 7, 30)


def test_combine_date_time_none():
    dt = combine_date_time(None, None)
    assert dt.time() == time(0, 0)


def test_add_minutes():
    dt = datetime(2026, 6, 21, 7, 0)
    assert add_minutes(dt, 30) == datetime(2026, 6, 21, 7, 30)
    assert add_minutes(dt, -10) == datetime(2026, 6, 21, 6, 50)


def test_time_diff_minutes():
    a = datetime(2026, 6, 21, 7, 30)
    b = datetime(2026, 6, 21, 7, 0)
    assert time_diff_minutes(a, b) == 30
    assert time_diff_minutes(b, a) == -30


def test_fmt_time():
    assert fmt_time(datetime(2026, 6, 21, 7, 30)) == "07:30"
