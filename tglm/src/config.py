"""旅行规划 Agent - 配置加载"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，从 .env 文件加载。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM Provider 选择：gemini / openai（兼容任何 OpenAI 协议的自定义服务）
    LLM_PROVIDER: str = "openai"

    # Gemini 配置
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # OpenAI 兼容配置（支持任何 OpenAI 协议的模型，包括自建/聚合服务）
    AGNES_API_KEY: str = ""           # 或 OPENAI_API_KEY
    AGNES_BASE_URL: str = ""          # 如 https://your-llm-gateway.com/v1
    AGNES_MODEL: str = "agnes-2.0-flash"
    # 别名，方便用 OPENAI_API_KEY / OPENAI_BASE_URL 环境变量
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL: str = ""

    # 高德
    AMAP_KEY: str = ""

    # 12306 MCP
    MCP_12306_ENABLED: bool = False
    MCP_SERVERS: str = ""  # JSON 字符串，声明所有要连接的 MCP server

    # 通用
    LOG_LEVEL: str = "INFO"
    SESSION_ID: str = "dev"

    # 业务可调
    STATION_BUFFER_MINUTES: int = 30   # 火车发车前需提前多少分钟到站
    MAX_TRAIN_RETRY: int = 8           # Verify 不可行时最多回溯几班车（覆盖一天车次足够）

    def resolve_openai_credentials(self) -> tuple[str, str, str]:
        """解析 OpenAI 兼容服务的凭据：AGNES_* 优先，OPENAI_* 兜底。

        返回 (api_key, base_url, model)
        """
        api_key = self.AGNES_API_KEY or self.OPENAI_API_KEY
        base_url = self.AGNES_BASE_URL or self.OPENAI_BASE_URL
        model = self.AGNES_MODEL or self.OPENAI_MODEL or "gpt-4o-mini"
        return api_key, base_url, model

MCP_SERVERS='[{"name": "weather", "type": "sse", "url": "https://mcp.weather.com/sse"},}]'
settings = Settings()