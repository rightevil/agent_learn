# agent/sub_agents/base.py
from typing import Protocol
from ..state import AgentState



class SubAgent(Protocol):
    """子 Agent 统一接口。"""
    name: str



    async def run(self, state: AgentState) -> AgentState:
        """接收当前 state，返回更新后的 state。"""
        ...

async def _update_from_reply(self , state: AgentState) -> None :
    # ... 同原 _update_intent_from_reply
    pass