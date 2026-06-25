"""时间辅助函数"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta


def combine_date_time(d: date | None, t: time | None) -> datetime:
    """把 date 和 time 合并为 datetime。None 时用当天/00:00 兜底。"""
    if d is None:
        d = date.today()
    if t is None:
        t = time(0, 0)
    return datetime.combine(d, t)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)


def time_diff_minutes(later: datetime, earlier: datetime) -> int:
    """later - earlier 的分钟数（可能为负）。"""
    return int((later - earlier).total_seconds() // 60)


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")
