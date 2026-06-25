"""Agent 状态定义 - Pydantic 模型"""
from datetime import date as Date, time as Time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Place(BaseModel):
    """一个地点：原始文本 + 地理编码结果。"""

    raw_text: str
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    city: Optional[str] = None
    citycode: Optional[str] = None  # 高德城市编码（poi_search 返回）
    formatted: Optional[str] = None  # 高德格式化后的标准地址
    poi_category: Optional[str] = None  # POI 一级大类中文名（如 "风景名胜"），来自 LLM 推断

    def is_geocoded(self) -> bool:
        return self.longitude is not None and self.latitude is not None

    def coord(self) -> Optional[str]:
        """返回高德所需的 "lng,lat" 字符串。"""
        if not self.is_geocoded():
            return None
        return f"{self.longitude},{self.latitude}"

    def __str__(self) -> str:
        return self.formatted or self.raw_text


class TimeWindow(BaseModel):
    date: Optional[Date] = None
    earliest_time: Optional[Time] = None
    latest_return_time: Optional[Time] = None


class TripIntent(BaseModel):
    """用户意图的结构化表示。SlotFill 节点的填充对象。"""

    origin: Optional[Place] = None
    destination: Optional[Place] = None
    time_window: TimeWindow = Field(default_factory=TimeWindow)
    return_required: Optional[bool] = None
    play_duration_hours: Optional[int] = None

    def is_cross_city(self) -> Optional[bool]:
        """是否跨城。两端都已 geocode 且都有 city 时才能判定。"""
        if (
            self.origin
            and self.origin.city
            and self.destination
            and self.destination.city
        ):
            return self.origin.city != self.destination.city
        return None

    def missing_slots(self) -> list[str]:
        """返回缺失的必填字段名列表。"""
        missing: list[str] = []
        if not self.origin:
            missing.append("origin")
        if not self.destination:
            missing.append("destination")
        if not self.time_window.date:
            missing.append("date")
        if not self.time_window.earliest_time:
            missing.append("earliest_time")
        # 跨城时才追问回程与游玩时长
        if self.is_cross_city() is True:
            if self.return_required is None:
                missing.append("return_required")
            if self.return_required and not self.play_duration_hours:
                missing.append("play_duration_hours")
        return missing

    def collected_summary(self) -> list[str]:
        """已收集到的字段的可读列表，用于追问时复述给用户。"""
        bullets: list[str] = []
        if self.destination:
            bullets.append(f"目的地：{self.destination.raw_text}")
        if self.origin:
            bullets.append(f"出发地：{self.origin.raw_text}")
        if self.time_window.date:
            bullets.append(f"日期：{self.time_window.date.isoformat()}")
        if self.time_window.earliest_time:
            bullets.append(f"最早可出发：{self.time_window.earliest_time.strftime('%H:%M')}")
        if self.is_cross_city() is True:
            bullets.append("跨城出行（需坐火车/高铁）")
        elif self.is_cross_city() is False:
            bullets.append("同城出行")
        if self.return_required is True:
            bullets.append("需要回程")
        elif self.return_required is False:
            bullets.append("不需要回程")
        if self.play_duration_hours:
            bullets.append(f"游玩时长：{self.play_duration_hours} 小时")
        return bullets


class SegmentType(str, Enum):
    walk = "walk"
    transit = "transit"
    rail = "rail"
    play = "play"


class Segment(BaseModel):
    """行程中的最小规划单元。"""

    type: SegmentType
    origin: Place
    destination: Place
    start_time: Optional[Time] = None
    end_time: Optional[Time] = None
    duration_minutes: Optional[int] = None
    detail: dict[str, Any] = Field(default_factory=dict)


class Feasibility(BaseModel):
    is_feasible: bool
    reason: str = ""
    suggested_train_index: Optional[int] = None


class Itinerary(BaseModel):
    segments: list[Segment] = Field(default_factory=list)
    feasibility: Optional[Feasibility] = None
    warnings: list[str] = Field(default_factory=list)
    raw_plan: Optional[dict[str, Any]] = None  # 高德/12306 原始返回数据，供 visualize 节点使用


class AgentState(BaseModel):
    """LangGraph 状态对象，贯穿整个对话。"""

    messages: list[dict[str, str]] = Field(default_factory=list)
    intent: TripIntent = Field(default_factory=TripIntent)
    itinerary: Optional[Itinerary] = None
    candidate_trains: list[dict[str, Any]] = Field(default_factory=list)
    current_train_index: int = 0
    retry_count: int = 0
    session_id: str = ""

    def last_user_message(self) -> Optional[str]:
        for m in reversed(self.messages):
            if m["role"] == "user":
                return m["content"]
        return None

    def last_assistant_message(self) -> Optional[str]:
        for m in reversed(self.messages):
            if m["role"] == "assistant":
                return m["content"]
        return None
