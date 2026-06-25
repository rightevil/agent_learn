"""测试 TripIntent 与 Place 状态模型"""
from datetime import date, time

from trip_planner.agent.state import (
    AgentState,
    Place,
    TimeWindow,
    TripIntent,
)


def test_place_is_geocoded():
    p = Place(raw_text="杭电")
    assert not p.is_geocoded()
    p2 = Place(raw_text="杭电", longitude=120.0, latitude=30.0)
    assert p2.is_geocoded()
    assert p2.coord() == "120.0,30.0"


def test_intent_missing_slots_empty_intent():
    intent = TripIntent()
    missing = intent.missing_slots()
    assert "origin" in missing
    assert "destination" in missing
    assert "date" in missing
    assert "earliest_time" in missing


def test_intent_is_cross_city_true():
    intent = TripIntent(
        origin=Place(raw_text="杭电", city="杭州"),
        destination=Place(raw_text="东钱湖", city="宁波"),
    )
    assert intent.is_cross_city() is True


def test_intent_is_cross_city_false():
    intent = TripIntent(
        origin=Place(raw_text="杭电", city="杭州"),
        destination=Place(raw_text="西湖", city="杭州"),
    )
    assert intent.is_cross_city() is False


def test_intent_is_cross_city_none_when_city_missing():
    intent = TripIntent(
        origin=Place(raw_text="杭电"),  # 没有 city
        destination=Place(raw_text="西湖", city="杭州"),
    )
    assert intent.is_cross_city() is None


def test_missing_slots_cross_city_requires_return_required():
    intent = TripIntent(
        origin=Place(raw_text="杭电", city="杭州"),
        destination=Place(raw_text="东钱湖", city="宁波"),
        time_window=TimeWindow(date=date(2026, 6, 21), earliest_time=time(7, 0)),
    )
    missing = intent.missing_slots()
    assert "return_required" in missing
    assert "play_duration_hours" not in missing  # 还没确定 return_required


def test_missing_slots_cross_city_requires_play_duration_when_return_required():
    intent = TripIntent(
        origin=Place(raw_text="杭电", city="杭州"),
        destination=Place(raw_text="东钱湖", city="宁波"),
        time_window=TimeWindow(date=date(2026, 6, 21), earliest_time=time(7, 0)),
        return_required=True,
    )
    missing = intent.missing_slots()
    assert "play_duration_hours" in missing


def test_missing_slots_intra_city_skips_return_required():
    intent = TripIntent(
        origin=Place(raw_text="杭电", city="杭州"),
        destination=Place(raw_text="西湖", city="杭州"),
        time_window=TimeWindow(date=date(2026, 6, 21), earliest_time=time(7, 0)),
    )
    assert intent.missing_slots() == []


def test_collected_summary_includes_destination():
    intent = TripIntent(destination=Place(raw_text="东钱湖"))
    summary = intent.collected_summary()
    assert any("东钱湖" in s for s in summary)


def test_agent_state_last_messages():
    state = AgentState(messages=[
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ])
    assert state.last_user_message() == "hi"
    assert state.last_assistant_message() == "hello"
