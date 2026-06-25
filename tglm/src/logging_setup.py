"""structlog 初始化 - 控制台 + JSONL 文件双输出"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import structlog
from .config import settings

# 全局文件句柄，避免每条日志重复 open
_file_handle = None


def _get_file_handle():
    global _file_handle
    if _file_handle is None:
        log_dir = Path("logs") / settings.SESSION_ID
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "events.jsonl"
        _file_handle = open(log_file, "a", encoding="utf-8")
    return _file_handle


def _file_writer(logger, name, event_dict):
    """自定义 processor：把事件字典以 JSONL 写入文件，再返回 event_dict 让链继续。"""
    try:
        line = json.dumps(event_dict, ensure_ascii=False, default=str)
        fh = _get_file_handle()
        fh.write(line + "\n")
        fh.flush()
    except Exception:
        # 日志写入失败不能影响主流程
        pass
    return event_dict


def _add_tz(logger, name, event_dict):
    """加一个上海时区的可读时间字段。"""
    event_dict["local_time"] = datetime.now(
        timezone(timedelta(hours=8))
    ).isoformat(timespec="seconds")
    return event_dict


def setup_logging() -> None:
    """配置 structlog：每条日志同时输出到 stderr（人类可读）和文件（JSONL）。"""
    level = getattr(structlog, settings.LOG_LEVEL, 20)
    tz = timezone(timedelta(hours=8))

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(
                fmt="iso", utc=False, key="timestamp"
            ),
            _add_tz,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # 先写文件（JSON）
            _file_writer,
            # 再渲染控制台输出（也是 JSON，但走 stderr）
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "trip_planner"):
    return structlog.get_logger(name)