"""测试 Verify 节点的时间推理逻辑（不依赖 LLM）"""
from datetime import date, time

import pytest

from trip_planner.agent.nodes import verify_node
from trip_planner.agent.state import (
    AgentState,
    Feasibility,
    Itinerary,
    Place,
    Segment,
    SegmentType,
    TripIntent,
    TimeWindow,
)


def _build_test_state(earliest: str, train_depart: str,
                      leg1_duration: int) -> AgentState:
    """构造一个最小可推理的 cross-city state。"""
    intent = TripIntent(
        origin=Place(raw_text="杭电", city="杭州"),
        destination=Place(raw_text="东钱湖", city="宁波"),
        time_window=TimeWindow(
            date=date(2026, 6, 21),
            earliest_time=time.fromisoformat(earliest),
        ),
        return_required=False,
        play_duration_hours=4,
    )
    s1 = Place(raw_text="杭州东")
    s2 = Place(raw_text="宁波")
    leg1 = Segment(
        type=SegmentType.transit,
        origin=intent.origin,
        destination=s1,
        duration_minutes=leg1_duration,
    )
    rail = Segment(
        type=SegmentType.rail,
        origin=s1,
        destination=s2,
        start_time=time.fromisoformat(train_depart),
        end_time=time.fromisoformat("08:25"),
        detail={"code": "G7561"},
    )
    leg2 = Segment(
        type=SegmentType.transit,
        origin=s2,
        destination=intent.destination,
        duration_minutes=30,
    )
    itinerary = Itinerary(segments=[leg1, rail, leg2])
    state = AgentState(intent=intent, itinerary=itinerary)
    state.candidate_trains = [
        {"code": "G7561", "depart": train_depart, "arrive": "08:25"},
        {"code": "G7565", "depart": "08:00", "arrive": "08:58"},
        {"code": "G7671", "depart": "08:25", "arrive": "09:20"},
    ]
    return state


@pytest.mark.asyncio
async def test_verify_infeasible_when_too_late():
    """7:00 出发，到车站 35min，赶不上 7:30 的车"""
    state = _build_test_state("07:00", "07:30", leg1_duration=35)
    result = await verify_node(state)
    assert result.itinerary.feasibility is not None
    assert result.itinerary.feasibility.is_feasible is False
    assert result.current_train_index == 1  # 重试下一班


@pytest.mark.asyncio
async def test_verify_feasible_when_enough_buffer():
    """6:00 出发，到车站 25min，7:30 发车，缓冲 65min，可行"""
    state = _build_test_state("06:00", "07:30", leg1_duration=25)
    result = await verify_node(state)
    assert result.itinerary.feasibility.is_feasible is True
    assert result.current_train_index == 0  # 不重试


@pytest.mark.asyncio
async def test_verify_feasible_exactly_30min_buffer():
    """恰好 30 分钟缓冲，应该可行（边界条件）"""
    # 7:00 出发 + 20min 通勤 = 7:20 到站，7:50 发车，缓冲正好 30min
    state = _build_test_state("07:00", "07:50", leg1_duration=20)
    result = await verify_node(state)
    assert result.itinerary.feasibility.is_feasible is True


@pytest.mark.asyncio
async def test_verify_skips_when_no_rail():
    """同城无 rail 段时，直接判可行。"""
    intent = TripIntent(
        origin=Place(raw_text="杭电", city="杭州"),
        destination=Place(raw_text="西湖", city="杭州"),
        time_window=TimeWindow(date=date(2026, 6, 21), earliest_time=time(7, 0)),
    )
    leg = Segment(
        type=SegmentType.transit,
        origin=intent.origin,
        destination=intent.destination,
        duration_minutes=40,
    )
    state = AgentState(
        intent=intent,
        itinerary=Itinerary(segments=[leg]),
    )
    result = await verify_node(state)
    assert result.itinerary.feasibility.is_feasible is True
