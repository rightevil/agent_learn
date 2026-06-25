"""端到端测试：mock 掉 LLM 调用，验证完整 agent 主循环。

不依赖真实 Gemini API key，用 monkeypatch 把 llm_extract 替换成预设返回。
"""
from __future__ import annotations

from typing import Any

import pytest

from trip_planner.agent import llm as llm_module
from trip_planner.agent.graph import run_agent
from trip_planner.agent.state import AgentState, SegmentType


@pytest.fixture
def mock_llm(monkeypatch):
    """把 llm_extract 替换为按顺序返回 RESPONSES 的 mock。

    每个 test 内部填充 RESPONSES 即可。
    """
    state = {"responses": [], "i": 0}

    async def fake_llm_extract(prompt: str) -> dict[str, Any]:
        i = state["i"]
        state["i"] += 1
        if i < len(state["responses"]):
            return state["responses"][i]
        return {}

    monkeypatch.setattr(llm_module, "llm_extract", fake_llm_extract)
    return state


# ============================================================
# E2E 1: 跨城 + 一次性给全信息
# ============================================================
@pytest.mark.asyncio
async def test_e2e_cross_city_hangzhou_to_ningbo(mock_llm):
    """完整跑通跨城样例：杭州 → 宁波东钱湖，用户一次说全。"""
    mock_llm["responses"] = [
        # Intake 阶段：用户首轮就给全信息
        {
            "origin": "杭州电子科技大学研究生公寓",
            "destination": "宁波东钱湖",
            "date": "2026-06-21",
            "earliest_time": "06:30",
            "return_required": False,
            "play_duration_hours": 4,
        },
    ]

    state = AgentState(session_id="test-e2e-1")
    state.messages.append({
        "role": "user",
        "content": "我想 2026-06-21 早上 6:30 之后从杭州电子科技大学研究生公寓出发，"
                   "去宁波东钱湖玩 4 小时，不回程",
    })
    state = await run_agent(state)

    # 应生成 itinerary
    assert state.itinerary is not None, "应生成 itinerary"
    assert len(state.itinerary.segments) > 0

    # 应有 rail segment
    rail_segs = [s for s in state.itinerary.segments if s.type == SegmentType.rail]
    assert len(rail_segs) >= 1, "跨城应有 rail segment"

    # 时间推理：6:30 + 30min mock 通勤 = 7:00 到站，7:30 发车，缓冲 30min，应可行
    assert state.itinerary.feasibility is not None
    assert state.itinerary.feasibility.is_feasible is True, (
        f"应判定可行: {state.itinerary.feasibility.reason}"
    )

    last = state.last_assistant_message()
    assert "行程已规划好" in last, f"应渲染行程卡片，实际: {last}"
    assert "G7561" in last  # 第一班次


# ============================================================
# E2E 2: 多轮追问 + 自动重试
# ============================================================
@pytest.mark.asyncio
async def test_e2e_multiturn_then_infeasible_retry(mock_llm):
    """分多轮说全信息，且出发太晚赶不上车，自动重试到下一班次。

    每个 turn 中 Intake 与 SlotFill 都会调用 LLM 一次。
    3 个 turn 共需要 6 次 LLM 响应（其中第 1 次 Intake 后 SlotFill 也会调）。
    """
    # 第 1 轮：用户只说要去宁波 → Intake 抽出 destination，SlotFill 没有新信息
    # 第 2 轮：用户补 origin → Intake 把 origin 抽出，SlotFill 没有新信息
    # 第 3 轮：用户补全时间信息 → Intake 抽出，SlotFill 增量
    full_intent = {
        "origin": "杭州电子科技大学研究生公寓",
        "destination": "宁波东钱湖",
        "date": "2026-06-21",
        "earliest_time": "07:00",  # 7:00 出发，赶不上 7:30
        "return_required": False,
        "play_duration_hours": 4,
    }
    mock_llm["responses"] = [
        # turn 1: Intake (用户说"去宁波东钱湖玩")
        {"destination": "宁波东钱湖"},
        # turn 1: SlotFill 增量（用户消息里没有更多新信息，返回空）
        {},
        # turn 2: Intake (用户说"从杭州电子科技大学研究生公寓出发")
        {"origin": "杭州电子科技大学研究生公寓"},
        # turn 2: SlotFill 增量（无）
        {},
        # turn 3: Intake (用户说"2026-06-21 7:00 出发玩 4 小时不回程")
        {"date": "2026-06-21", "earliest_time": "07:00",
         "return_required": False, "play_duration_hours": 4},
        # turn 3: SlotFill 增量（无）
        {},
    ]

    state = AgentState(session_id="test-e2e-2")

    # 第 1 轮
    state.messages.append({"role": "user", "content": "我想去宁波东钱湖玩"})
    state = await run_agent(state)
    last = state.last_assistant_message()
    assert "还需要确认" in last, f"第 1 轮应追问，实际: {last}"

    # 第 2 轮
    state.messages.append({
        "role": "user",
        "content": "从杭州电子科技大学研究生公寓出发",
    })
    state = await run_agent(state)
    last = state.last_assistant_message()
    assert "还需要确认" in last, f"第 2 轮应继续追问时间，实际: {last}"

    # 第 3 轮：信息全了，开始规划
    state.messages.append({
        "role": "user",
        "content": "2026-06-21 早上 7:00 出发，玩 4 小时，不回程",
    })
    state = await run_agent(state)

    # 7:00 + 30min mock = 7:30 到站，7:30 发车，缓冲 0min → 不可行 → 重试
    # 8:00 G7565 发车，7:00 + 30min = 7:30 到站，缓冲 30min → 可行
    assert state.itinerary is not None
    last = state.last_assistant_message()
    assert "行程已规划好" in last, (
        f"重试后应给出可行方案，实际: {last}"
    )
    assert "G7565" in last  # 第二班次


# ============================================================
# E2E 3: 同城（不出火车）
# ============================================================
@pytest.mark.asyncio
async def test_e2e_intra_city(mock_llm):
    """同城样例：杭电 → 杭州西湖。"""
    mock_llm["responses"] = [
        {
            "origin": "杭州电子科技大学研究生公寓",
            "destination": "杭州西湖",
            "date": "2026-06-21",
            "earliest_time": "08:00",
            "return_required": False,
            "play_duration_hours": 3,
        },
    ]

    state = AgentState(session_id="test-e2e-3")
    state.messages.append({
        "role": "user",
        "content": "2026-06-21 早上 8 点从杭州电子科技大学研究生公寓出发去杭州西湖，玩 3 小时，不回程",
    })
    state = await run_agent(state)

    assert state.itinerary is not None
    assert state.intent.is_cross_city() is False
    last = state.last_assistant_message()
    assert "行程已规划好" in last
    # 同城不应有火车段
    assert "G7561" not in last and "G7565" not in last


# ============================================================
# E2E 4: 需要回程
# ============================================================
@pytest.mark.asyncio
async def test_e2e_with_return_trip(mock_llm):
    """需要回程的场景：应额外规划返程车次与两端市内通勤。"""
    mock_llm["responses"] = [
        {
            "origin": "杭州电子科技大学研究生公寓",
            "destination": "宁波东钱湖",
            "date": "2026-06-21",
            "earliest_time": "06:30",
            "return_required": True,
            "play_duration_hours": 4,
        },
    ]

    state = AgentState(session_id="test-e2e-4")
    state.messages.append({
        "role": "user",
        "content": "2026-06-21 6:30 出发从杭电研究生公寓去宁波东钱湖玩 4 小时，要回程",
    })
    state = await run_agent(state)

    assert state.itinerary is not None
    rail_segs = [s for s in state.itinerary.segments if s.type == SegmentType.rail]
    assert len(rail_segs) >= 2, "需要回程时应有去程+返程两段 rail"
    last = state.last_assistant_message()
    assert "行程已规划好" in last
    assert "返程" in last or "返" in last
