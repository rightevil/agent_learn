"""Agent 节点实现 - Intake / SlotFill / Plan / Verify / Reply / Visualize"""
from __future__ import annotations

from datetime import date, time, datetime, timedelta
from typing import Any

from langchain_core.messages import HumanMessage

from ..logging_setup import get_logger
from ..utils.time_calc import (
    add_minutes,
    combine_date_time,
    fmt_time,
    time_diff_minutes,
)
from .llm import get_llm, parse_llm_json
from . import llm as llm_module

# 直接通过模块属性访问，便于测试 monkeypatch
async def _llm_extract(prompt: str) -> dict[str, Any]:
    return await llm_module.llm_extract(prompt)

from .prompts import (
    ASK_HEADER,
    ASK_NEXT_ACTION_CROSS_CITY,
    ASK_NEXT_ACTION_INTRA_CITY,
    INFEASIBLE_ALTERNATIVE,
    INFEASIBLE_NO_ALTERNATIVE,
    INFEASIBLE_TEMPLATE,
    INTAKE_PROMPT,
    POI_CLASSIFY_PROMPT,
    POI_BIG_CATEGORIES_TABLE,
    POI_SEARCH_PRIORITY_CATEGORIES,
    SLOT_LABELS,
    SLOT_UPDATE_PROMPT,
    VISUALIZE_PROMPT,
)
from .state import (
    AgentState ,
    Feasibility ,
    Itinerary ,
    Place ,
    TripIntent , SegmentType ,
)
from ..tools import geocode, reverse_geocode, get_citycode, transit_route, poi_search
from ..tools.station_dict import pick_nearest_station
from ..config import settings

logger = get_logger(__name__)


# ============================================================
# Intake 节点：从用户首条消息抽取初始 TripIntent
# ============================================================
async def intake_node(state: AgentState) -> AgentState:
    logger.info("node_enter", node="intake")
    last_msg = state.last_user_message()
    if not last_msg:
        return state

    prompt = INTAKE_PROMPT.format(user_message=last_msg, today=date.today().isoformat())
    try:
        extracted = await _llm_extract(prompt)
    except Exception as e:
        logger.error("intake_llm_failed", error=str(e))
        extracted = {}

    # 增量合并到已有 intent（字段级合并，避免覆盖已填字段）
    new_intent = _apply_intent_updates(state.intent, extracted)
    state.intent = new_intent

    logger.info("intake_done", intent=new_intent.model_dump(mode="json"))
    return state


def _coerce_place(value: Any) -> Place | None:
    """把 LLM 返回的值转成 Place，容错处理多种格式。

    支持：
      - "杭州东站"                  (字符串)
      - {"raw_text": "杭州东站"}    (dict，本项目的 schema)
      - {"name": "杭州东站"}        (dict，常见变体)
      - {"address": "...", ...}     (其它字段名，会自动找)
      - {"raw_text": "...", "longitude": ..., "latitude": ..., "city": ...}
                                    (完整 Place 字段，直接 model_validate)
    """
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return Place(raw_text=s) if s else None
    if isinstance(value, dict):
        # 如果已经是完整的 Place dict，直接 validate
        if "raw_text" in value and isinstance(value["raw_text"], str):
            try:
                return Place.model_validate(value)
            except Exception:
                pass
        # 尝试常见字段名
        for key in ("raw_text", "name", "address", "location", "text"):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return Place(raw_text=v.strip())
        # dict 但找不到任何字符串字段
        return None
    return None


def _coerce_bool(value: Any) -> bool | None:
    """容错把 LLM 返回值转 bool。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "yes", "y", "是", "1"):
            return True
        if s in ("false", "no", "n", "否", "0"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _coerce_int(value: Any) -> int | None:
    """容错把 LLM 返回值转 int。支持 "4" / "4小时" / 4 等。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None  # 不要把 True/False 当成 1/0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        import re as _re
        m = _re.search(r"\d+", value)
        if m:
            return int(m.group(0))
    return None


def _dict_to_intent_fields(d: dict[str, Any]) -> dict[str, Any]:
    """[已弃用，保留兼容] 把 LLM 抽取的 dict 转为 TripIntent update 字典。

    ⚠️ 此函数对 time_window 会返回一个全新的 TimeWindow 实例（其它字段为 None），
    直接用于 model_copy 会覆盖已有值。请改用 _apply_intent_updates。
    """
    update: dict[str, Any] = {}
    p_origin = _coerce_place(d.get("origin"))
    if p_origin:
        update["origin"] = p_origin
    p_dest = _coerce_place(d.get("destination"))
    if p_dest:
        update["destination"] = p_dest

    tw = {}
    if d.get("date"):
        try:
            tw["date"] = date.fromisoformat(str(d["date"])[:10])
        except (ValueError, TypeError):
            pass
    if d.get("earliest_time"):
        try:
            s = str(d["earliest_time"])
            s = s.strip()
            import re as _re
            m = _re.search(r"(\d{1,2}):(\d{2})", s)
            if m:
                tw["earliest_time"] = time(int(m.group(1)), int(m.group(2)))
            else:
                tw["earliest_time"] = time.fromisoformat(s[:5])
        except (ValueError, TypeError):
            pass
    if tw:
        from .state import TimeWindow
        update["time_window"] = TimeWindow(**tw)

    br = _coerce_bool(d.get("return_required"))
    if br is not None:
        update["return_required"] = br
    pi = _coerce_int(d.get("play_duration_hours"))
    if pi is not None:
        update["play_duration_hours"] = pi
    return update


def _apply_intent_updates(
    intent: TripIntent, updates: dict[str, Any]
) -> TripIntent:
    """把 LLM 抽取的 updates 增量合并到 intent，做字段级合并，避免覆盖已有值。

    关键：time_window 字段会做字段级合并 —— 只有 updates 里实际出现的字段才会被
    更新，其它字段（如已填的 date）会保留原值。
    """
    intent_updates: dict[str, Any] = {}

    # origin / destination
    if (p := _coerce_place(updates.get("origin"))):
        intent_updates["origin"] = p
    if (p := _coerce_place(updates.get("destination"))):
        intent_updates["destination"] = p

    # time_window —— 字段级合并
    tw_updates: dict[str, Any] = {}
    if updates.get("date"):
        try:
            tw_updates["date"] = date.fromisoformat(str(updates["date"])[:10])
        except (ValueError, TypeError):
            pass
    if updates.get("earliest_time"):
        try:
            s = str(updates["earliest_time"]).strip()
            import re as _re
            m = _re.search(r"(\d{1,2}):(\d{2})", s)
            if m:
                tw_updates["earliest_time"] = time(int(m.group(1)), int(m.group(2)))
            else:
                tw_updates["earliest_time"] = time.fromisoformat(s[:5])
        except (ValueError, TypeError):
            pass
    if updates.get("latest_return_time"):
        try:
            s = str(updates["latest_return_time"]).strip()
            import re as _re
            m = _re.search(r"(\d{1,2}):(\d{2})", s)
            if m:
                tw_updates["latest_return_time"] = time(int(m.group(1)), int(m.group(2)))
        except (ValueError, TypeError):
            pass
    if tw_updates:
        merged_tw = intent.time_window.model_copy(update=tw_updates)
        intent_updates["time_window"] = merged_tw

    if (br := _coerce_bool(updates.get("return_required"))) is not None:
        intent_updates["return_required"] = br
    if (pi := _coerce_int(updates.get("play_duration_hours"))) is not None:
        intent_updates["play_duration_hours"] = pi

    if not intent_updates:
        return intent
    return intent.model_copy(update=intent_updates)


# ============================================================
# SlotFill 节点：检查缺口，必要时追问
# ============================================================
async def slot_fill_node(state: AgentState) -> AgentState:
    logger.info("node_enter", node="slot_fill")

    # 若上一条是 user 消息，先用 LLM 把回答增量更新到 intent
    if state.messages and state.messages[-1]["role"] == "user":
        await _update_intent_from_reply(state)

    missing = state.intent.missing_slots()
    logger.info("slot_fill_check", missing=missing,
                intent=state.intent.model_dump(mode="json"))

    if not missing:
        return state

    # 否则准备追问消息（由 reply_node 输出）
    return state


async def _update_intent_from_reply(state: AgentState) -> None:
    """用 LLM 把用户最新回答增量更新到 intent（字段级合并）。"""
    last_msg = state.last_user_message()
    if not last_msg:
        return
    prompt = SLOT_UPDATE_PROMPT.format(
        intent_json=state.intent.model_dump_json(exclude_none=True, indent=2),
        user_message=last_msg,
        today=date.today().isoformat(),
    )
    try:
        updates = await _llm_extract(prompt)
    except Exception as e:
        logger.error("slot_update_llm_failed", error=str(e))
        return
    if not updates:
        return

    new_intent = _apply_intent_updates(state.intent, updates)
    if new_intent != state.intent:
        state.intent = new_intent
        logger.info("intent_updated", updates=updates)


# ============================================================
# Plan 节点：跨城/同城分支规划
# ============================================================

# 需要优先使用 POI 搜索而非 geocode 的大类中文名集合
# 这些类型如果用 geocode 容易返回住宅/地址坐标而非景点坐标
POI_SEARCH_PRIORITY_CATEGORIES = {"风景名胜", "科教文化服务", "购物服务", "体育休闲服务", "住宿服务"}


async def _classify_destination_type(destination_name: str) -> dict[str, Any]:
    """用 LLM 推断目的地名称属于哪个 POI 一级大类（返回大类中文名）。"""
    prompt = POI_CLASSIFY_PROMPT.format(
        poi_categories_table=POI_BIG_CATEGORIES_TABLE,
        destination_name=destination_name,
    )
    try:
        result = await _llm_extract(prompt)
        return result
    except Exception as e:
        logger.error("poi_classify_failed", error=str(e), dest=destination_name)
        return {}


async def _resolve_place_coordinates(place: Place, region: str = "") -> Place:
    """解析地点坐标：优先使用 POI 搜索，失败则降级到 geocode。

    LLM 输出的是大类中文名（如"风景名胜"），直接作为 poi_search 的 types 参数传入。
    """
    if place.is_geocoded():
        return place

    category = place.poi_category
    if category in POI_SEARCH_PRIORITY_CATEGORIES:
        try:
            poi_result = await poi_search.ainvoke({
                "keywords": place.raw_text,
                "types": category,
                "region": region,
                "city_limit": True,
            })
            if "error" not in poi_result:
                updated = {k: v for k, v in poi_result.items()
                           if k in ("longitude", "latitude", "city", "citycode", "formatted")}
                return place.model_copy(update=updated)
        except Exception as e:
            logger.warning("poi_search_fallback_to_geocode", error=str(e))

    # 降级：使用普通 geocode
    try:
        geo = await geocode.ainvoke({"address": place.raw_text})
        if "error" not in geo:
            updated = {k: v for k, v in geo.items()
                       if k in ("longitude", "latitude", "city", "formatted")}
            return place.model_copy(update=updated)
    except Exception as e:
        logger.error("geocode_fallback_failed", error=str(e))

    return place


async def plan_node(state: AgentState) -> AgentState:
    logger.info("node_enter", node="plan",
                train_index=state.current_train_index)

    intent = state.intent

    # Step 1: 推断目的地 POI 大类（如果尚未推断）
    if intent.destination and not intent.destination.poi_category:
        classify_result = await _classify_destination_type(intent.destination.raw_text)
        category = classify_result.get("category")
        confidence = classify_result.get("confidence", "low")
        if category and confidence in ("high", "medium"):
            intent.destination = intent.destination.model_copy(
                update={"poi_category": category}
            )
            logger.info("poi_category_classified",
                        dest=intent.destination.raw_text,
                        category=category,
                        confidence=confidence)

    # Step 2: 目的地坐标解析（优先 POI 搜索，降级 geocode）
    if intent.destination and not intent.destination.is_geocoded():
        dest_region = intent.destination.city or ""
        intent.destination = await _resolve_place_coordinates(
            intent.destination, region=dest_region
        )

    # Step 3: 出发地坐标解析（直接用 geocode，出发地通常是住宅/地址）
    if intent.origin and not intent.origin.is_geocoded():
        try:
            geo = await geocode.ainvoke({"address": intent.origin.raw_text})
            if "error" not in geo:
                intent.origin = intent.origin.model_copy(update=geo)
        except Exception as e:
            logger.error("geocode_origin_failed", error=str(e))

    # Step 4: 推断城市（如果尚未推断）
    if intent.destination and intent.destination.city is None and intent.destination.is_geocoded():
        try:
            city = await reverse_geocode.ainvoke({
                "longitude": intent.destination.longitude,
                "latitude": intent.destination.latitude,
            })
            if city:
                intent.destination = intent.destination.model_copy(update={"city": city})
        except Exception as e:
            logger.error("reverse_geocode_dest_failed", error=str(e))

    if intent.origin and intent.origin.city is None and intent.origin.is_geocoded():
        try:
            city = await reverse_geocode.ainvoke({
                "longitude": intent.origin.longitude,
                "latitude": intent.origin.latitude,
            })
            if city:
                intent.origin = intent.origin.model_copy(update={"city": city})
        except Exception as e:
            logger.error("reverse_geocode_origin_failed", error=str(e))

    # Step 5: 分支
    transit_data = await _safe_transit(
        intent.origin, intent.destination,
        city1=intent.origin.city,
        city2=intent.destination.city,
    )
    state.itinerary = Itinerary(raw_plan=transit_data)
    print(transit_data)
    return state


async def _safe_transit(
    origin: Place,
    destination: Place,
    city1: str | None,
    city2: str | None = None,
) -> dict:
    """安全调用地图 transit_route（V5 接口），失败返回空 dict。

    V5 规范：
      - city1 是起点城市，city2 是终点城市
      - 城市名或 citycode 都可以传，transit_route 内部会自动调 get_citycode 转换
      - city1 == city2 表示同城

    若 origin/destination 尚未 geocode，会先调一次 geocode。
    """
    # 必要时先 geocode
    if not origin.is_geocoded():
        try:
            geo = await geocode.ainvoke({"address": origin.raw_text})
            if "error" not in geo:
                origin = origin.model_copy(update=geo)
        except Exception as e:
            logger.error("transit_geocode_origin_failed", error=str(e))
            return {}
    if not destination.is_geocoded():
        try:
            geo = await geocode.ainvoke({"address": destination.raw_text})
            if "error" not in geo:
                destination = destination.model_copy(update=geo)
        except Exception as e:
            logger.error("transit_geocode_dest_failed", error=str(e))
            return {}

    # city1 / city2 兜底
    if not city1:
        city1 = (origin.city or destination.city or "")
    if not city2:
        city2 = (destination.city or city1 or "")
    if not city1:
        logger.warning("transit_skip_no_city",
                       origin=origin.raw_text, destination=destination.raw_text)
        return {}

    if not origin.is_geocoded() or not destination.is_geocoded():
        logger.warning("transit_skip_still_not_geocoded",
                       origin=origin.raw_text, destination=destination.raw_text)
        return {}

    try:
        return await transit_route.ainvoke({
            "origin": origin.coord(),
            "destination": destination.coord(),
            "city1": city1,    # 城市名或 citycode，transit_route 内部自动转
            "city2": city2,
        })
    except Exception as e:
        logger.error("transit_failed", error=str(e),
                     origin=origin.raw_text, destination=destination.raw_text)
        return {}


# ============================================================
# Verify 节点：时间推理
# ============================================================
async def verify_node(state: AgentState) -> AgentState:
    logger.info("node_enter", node="verify")
    intent = state.intent
    it = state.itinerary
    if not it or not it.segments:
        # segments 为空时，如果有 raw_plan 则视为可行（跳过 verify）
        if it.raw_plan:
            it.feasibility = Feasibility(is_feasible=True)
        return state


# ============================================================
# Visualize 节点：调用 LLM 渲染行程可视化
# ============================================================
async def visualize_node(state: AgentState) -> AgentState:
    """调用 LLM 将行程数据渲染为可视化卡片。"""
    logger.info("node_enter", node="visualize")
    it = state.itinerary
    intent = state.intent
    # 把 intent + 原始行程数据一起注入 prompt
    prompt = VISUALIZE_PROMPT.format(
        origin=str(intent.origin),
        destination=str(intent.destination),
        date=intent.time_window.date.isoformat() if intent.time_window.date else "未指定",
        earliest_time=intent.time_window.earliest_time.strftime("%H:%M")
                      if intent.time_window.earliest_time else "未指定",
        return_required=("需要" if intent.return_required
                         else "不需要" if intent.return_required is False else "未指定"),
        play_hours=str(intent.play_duration_hours or "未指定"),
        segments_detail=str(it.raw_plan),
    )

    llm = get_llm()
    resp = await llm.ainvoke([HumanMessage(content=prompt)])
    content = resp.content if isinstance(resp.content, str) else str(resp.content)

    state.messages.append({"role": "assistant", "content": content})
    logger.info("visualize_done")
    return state


# ============================================================
# Reply 节点：渲染结构化输出给用户
# ============================================================
async def reply_node(state: AgentState) -> AgentState:
    logger.info("node_enter", node="reply")

    text = _render_reply(state)
    state.messages.append({"role": "assistant", "content": text})
    return state


def _render_reply(state: AgentState) -> str:
    intent = state.intent
    missing = intent.missing_slots()

    # 情况 1：还有缺口要追问
    if missing:
        return _render_ask(intent, missing)

    # 情况 2：没有 itinerary 或没有原始数据
    it = state.itinerary
    if not it or not it.raw_plan:
        if it and it.warnings:
            return "⚠️ " + "\n".join(it.warnings)
        return "出了点问题，请重新描述你的需求。"


    # 情况 4：可行但走到了 reply（理论上不应该发生，兜底）
    return "行程规划已完成。"


def _render_ask(intent: TripIntent, missing: list[str]) -> str:
    collected = intent.collected_summary()
    bullets_collected = "\n".join(f"  - {b}" for b in collected) if collected else "  - （暂无）"
    bullets_missing = "\n".join(f"  {i+1}. {SLOT_LABELS[s]}" for i, s in enumerate(missing[:3]))
    next_action = (ASK_NEXT_ACTION_CROSS_CITY
                   if intent.is_cross_city() is True
                   else ASK_NEXT_ACTION_INTRA_CITY)
    return (
        f"{ASK_HEADER}\n{bullets_collected}\n\n"
        f"还需要确认：\n{bullets_missing}\n\n"
        f"这样我才能帮你{next_action}。"
    )