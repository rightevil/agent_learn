"""LLM 客户端封装 - 支持 Gemini 与 OpenAI 兼容协议（含自定义模型服务）"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from ..config import settings
from ..logging_setup import get_logger

logger = get_logger(__name__)


def get_llm() -> BaseChatModel:
    """根据 LLM_PROVIDER 配置返回对应的 LangChain ChatModel。

    支持两种 provider:
      - gemini: 用 langchain-google-genai 的 ChatGoogleGenerativeAI
      - openai: 用 langchain-openai 的 ChatOpenAI，可对接任何 OpenAI 兼容服务
                （官方 OpenAI、自建网关、聚合服务如 Agnes/DeepSeek/Qwen-Max 等）

    OpenAI 兼容服务的凭据解析优先级：
      AGNES_API_KEY > OPENAI_API_KEY
      AGNES_BASE_URL > OPENAI_BASE_URL
      AGNES_MODEL > OPENAI_MODEL > "gpt-4o-mini"
    """
    provider = (settings.LLM_PROVIDER or "openai").lower()

    if provider == "gemini":
        return _build_gemini()
    if provider == "openai":
        return _build_openai_compatible()
    raise RuntimeError(f"未知 LLM_PROVIDER: {provider}")


def _build_gemini() -> BaseChatModel:
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("your_"):
        raise RuntimeError(
            "GEMINI_API_KEY 未配置。请在 .env 中设置 LLM_PROVIDER=gemini 并填入 GEMINI_API_KEY。"
        )
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
    )


def _build_openai_compatible() -> BaseChatModel:
    """用 ChatOpenAI 接入任意 OpenAI 兼容服务。"""
    api_key, base_url, model = settings.resolve_openai_credentials()

    if not api_key or api_key.startswith("your_"):
        raise RuntimeError(
            "未配置 LLM API Key。请在 .env 中设置 AGNES_API_KEY 或 OPENAI_API_KEY。"
        )
    if not base_url:
        raise RuntimeError(
            "未配置 base_url。请在 .env 中设置 AGNES_BASE_URL 或 OPENAI_BASE_URL。"
        )

    # 延迟 import，避免没装包时直接挂掉
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=0,
    )


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_llm_json(text: str) -> dict[str, Any]:
    """从 LLM 输出中解析 JSON，容错处理 markdown 代码块包裹。"""
    text = text.strip()

    # 1. 优先解析 ```json ... ``` 块
    m = _JSON_BLOCK_RE.search(text)
    if m:
        text = m.group(1).strip()

    # 2. 尝试找到第一个 { 和最后一个 }，截取子串
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first : last + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("llm_json_parse_failed", raw=text[:200], error=str(e))
        return {}


async def llm_extract(prompt: str) -> dict[str, Any]:
    """调用 LLM 并把输出解析成 dict。失败返回空 dict。"""
    llm = get_llm()
    resp = await llm.ainvoke([HumanMessage(content=prompt)])
    content = resp.content if isinstance(resp.content, str) else str(resp.content)
    return parse_llm_json(content)