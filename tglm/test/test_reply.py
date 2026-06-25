"""测试 Reply 节点的渲染逻辑（不依赖 LLM）"""
from datetime import date, time

import pytest

from trip_planner.agent.nodes import reply_node
from trip_planner.agent.state import (
    AgentState,
    Feasibility,
    Itinerary,
    Place,
    Segment,
    SegmentType,
    TimeWindow,
    TripIntent,
)


@pytest.mark.asyncio
async def test_reply_renders_ask_when_missing_slots():
    """意图不完整时，应渲染追问消息。"""
    state = AgentState(
        intent=TripIntent(destination=Place(raw_text="宁波东钱湖")),
        messages=[{"role": "user", "content": "我想去宁波玩"}],
    )
    result = await reply_node(state)
    text = result.messages[-1]["content"]
    assert "目的地" in text
    assert "你从哪里出发" in text  # 应该追问 origin
    assert "Agent" not in text  # 不应带 markdown 标记


@pytest.mark.asyncio
async def test_reply_renders_infeasible_with_alternative():
    """不可行但有下一班车次时，应给出替代提示。"""
    intent = TripIntent(
        origin=Place(raw_text="杭电", city="杭州"),
        destination=Place(raw_text="东钱湖", city="宁波"),
        time_window=TimeWindow(date=date(2026, 6, 21), earliest_time=time(7, 0)),
        return_required=False,
        play_duration_hours=4,
    )
    itinerary = Itinerary(
        segments=[
            Segment(type=SegmentType.transit,
                    origin=intent.origin,
                    destination=Place(raw_text="杭州东"),
                    duration_minutes=35),
            Segment(type=SegmentType.rail,
                    origin=Place(raw_text="杭州东"),
                    destination=Place(raw_text="宁波"),
                    start_time=time(7, 30),
                    end_time=time(8, 25),
                    detail={"code": "G7561", "price": 73}),
        ],
        feasibility=Feasibility(
            is_feasible=False,
            reason="7:00 出发，到杭州东 35min，预计 7:35 到站，发车前 30min 是 7:00，来不及。",
            suggested_train_index=1,
        ),
    )
    state = AgentState(intent=intent, itinerary=itinerary)
    result = await reply_node(state)
    text = result.messages[-1]["content"]
    assert "不可行" in text
    assert "自动尝试下一班次" in text


@pytest.mark.asyncio
async def test_reply_renders_feasible_cross_city_card():
    """可行时渲染完整行程卡片。"""
    intent = TripIntent(
        origin=Place(raw_text="杭州电子科技大学研究生公寓", city="杭州",
                     longitude=120.194, latitude=30.298),
        destination=Place(raw_text="宁波东钱湖", city="宁波",
                          longitude=121.622, latitude=29.766),
        time_window=TimeWindow(date=date(2026, 6, 21), earliest_time=time(6, 0)),
        return_required=False,
        play_duration_hours=4,
    )
    itinerary = Itinerary(
        segments=[
            Segment(type=SegmentType.transit,
                    origin=intent.origin,
                    destination=Place(raw_text="杭州东"),
                    duration_minutes=25,
                    detail={"steps": [{"instruction": "地铁 1 号线"}]}),
            Segment(type=SegmentType.rail,
                    origin=Place(raw_text="杭州东"),
                    destination=Place(raw_text="宁波"),
                    start_time=time(7, 30),
                    end_time=time(8, 25),
                    detail={"code": "G7561", "duration": "00:55", "price": 73}),
            Segment(type=SegmentType.transit,
                    origin=Place(raw_text="宁波"),
                    destination=intent.destination,
                    duration_minutes=55,
                    detail={"steps": [{"instruction": "地铁 2 号线"}]}),
        ],
        feasibility=Feasibility(is_feasible=True),
    )
    state = AgentState(intent=intent, itinerary=itinerary)
    result = await reply_node(state)
    text = result.messages[-1]["content"]
    assert "行程已规划好" in text
    assert "G7561" in text
    assert "杭州东" in text
    assert "宁波东钱湖" in text
    assert "时间校验" in text
