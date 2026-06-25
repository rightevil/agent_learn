"""LangGraph 状态机定义"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes import (
    intake_node,
    plan_node,
    reply_node,
    slot_fill_node,
    verify_node,
    visualize_node,
)
from .state import AgentState


def should_ask_or_plan(state: AgentState) -> str:
    """SlotFill 之后的路由：还有缺口 → reply；否则 → plan。"""
    if state.intent.missing_slots():
        return "reply"
    return "plan"


def should_retry_or_reply(state: AgentState) -> str:
    """Verify 之后的路由：可行 → visualize；不可行/无候选 → reply。"""
    if state.itinerary and state.itinerary.feasibility:
        if state.itinerary.feasibility.is_feasible:
            return "visualize"
        # 不可行，尝试重试
        if (state.current_train_index < len(state.candidate_trains)
                and state.retry_count < 3):
            return "plan"
    return "reply"


def build_graph():
    g: StateGraph = StateGraph(AgentState)
    g.add_node("intake", intake_node)
    g.add_node("slot_fill", slot_fill_node)
    g.add_node("plan", plan_node)
    g.add_node("visualize", visualize_node)
    g.add_node("reply", reply_node)

    g.set_entry_point("intake")
    g.add_edge("intake", "slot_fill")
    g.add_conditional_edges(
        "slot_fill",
        should_ask_or_plan,
        {"reply": "reply", "plan": "plan"},
    )
    g.add_edge("plan", "visualize")
    g.add_edge("visualize", END)
    g.add_edge("reply", END)
    return g.compile()


async def run_agent(state: AgentState) -> AgentState:
    """运行一轮 agent，把 LangGraph 返回的 dict 重新包装为 AgentState。

    LangGraph 1.x 默认返回 dict；这里做一层封装方便调用方拿到的依然是 AgentState。
    """
    graph = build_graph()
    result = await graph.ainvoke(state)
    if isinstance(result, dict):
        return AgentState(**result)
    return result
