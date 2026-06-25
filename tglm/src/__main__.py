"""旅行规划 Agent - CLI 入口"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .agent.graph import run_agent
from .agent.state import AgentState
from .config import settings
from .logging_setup import setup_logging, get_logger

app = typer.Typer(help="旅行规划 Agent - 学习 agentic design pattern")
console = Console()
logger = get_logger(__name__)


@app.command()
def chat():
    """启动交互式对话。"""
    setup_logging()
    state = AgentState(session_id=settings.SESSION_ID)

    console.print(Panel.fit(
        "[bold green]旅行规划 Agent[/bold green]\n"
        "告诉我你想去哪儿，我会帮你规划路线。\n"
        "按 [bold]Ctrl+C[/bold] 或 [bold]Ctrl+D[/bold] 退出。",
        border_style="green",
    ))

    while True:
        try:
            user_input = console.input("\n[bold cyan]你:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]再见！[/yellow]")
            break

        if not user_input:
            continue

        # 把用户消息塞入 messages
        state.messages.append({"role": "user", "content": user_input})

        # 调用 LangGraph
        try:
            state = asyncio.run(run_agent(state))
        except KeyboardInterrupt:
            console.print("[yellow]已中断本轮。[/yellow]")
            continue
        except Exception as e:
            console.print(f"[red]发生错误：{e}[/red]")
            logger.error("graph_invoke_failed", error=str(e))
            continue

        # 输出最后一条 assistant 消息
        last = state.last_assistant_message()
        if last:
            console.print()
            console.print(Markdown(f"**Agent:** {last}"))

        # 若已生成 itinerary，把最终 JSON 落盘
        if state.itinerary:
            _save_itinerary(state)


@app.command()
def replay(session_id: str = typer.Option("dev", help="会话 ID")):
    """回放某次会话的对话日志。"""
    log_dir = Path("logs") / session_id
    msg_file = log_dir / "messages.jsonl"
    if not msg_file.exists():
        console.print(f"[red]找不到会话日志：{msg_file}[/red]")
        raise typer.Exit(1)

    with open(msg_file, encoding="utf-8") as f:
        for line in f:
            msg = json.loads(line)
            role = msg["role"]
            content = msg["content"]
            color = "cyan" if role == "user" else "green"
            console.print(f"\n[bold {color}]{role}:[/bold {color}] {content}")


@app.command()
def show_intent():
    """打印当前的配置和默认 state（用于调试）。"""
    def _status(val: str) -> str:
        return "已配置" if val and not val.startswith("your_") else "[red]未配置[/red]"

    provider = settings.LLM_PROVIDER
    if provider == "gemini":
        llm_info = (
            f"  provider = gemini\n"
            f"  GEMINI_MODEL = {settings.GEMINI_MODEL}\n"
            f"  GEMINI_API_KEY = {_status(settings.GEMINI_API_KEY)}"
        )
    else:
        api_key, base_url, model = settings.resolve_openai_credentials()
        llm_info = (
            f"  provider = openai-compatible\n"
            f"  model = {model}\n"
            f"  base_url = {base_url or '[red]未配置[/red]'}\n"
            f"  api_key = {_status(api_key)}"
        )

    console.print(Panel.fit(
        f"[bold]LLM[/bold]\n{llm_info}\n\n"
        f"[bold]Tools[/bold]\n"
        f"  AMAP_KEY = {_status(settings.AMAP_KEY) if settings.AMAP_KEY and not settings.AMAP_KEY.startswith('your_') else '[yellow]未配置（mock 模式）[/yellow]'}\n"
        f"  MCP_12306_ENABLED = {settings.MCP_12306_ENABLED}\n\n"
        f"[bold]通用[/bold]\n"
        f"  SESSION_ID = {settings.SESSION_ID}\n"
        f"  STATION_BUFFER_MINUTES = {settings.STATION_BUFFER_MINUTES}",
        title="配置检查",
        border_style="blue",
    ))


def _save_itinerary(state: AgentState) -> None:
    """把最终 Itinerary 落盘，方便后续 review。"""
    log_dir = Path("logs") / state.session_id
    log_dir.mkdir(parents=True, exist_ok=True)
    out_file = log_dir / "itinerary.json"
    payload = {
        "saved_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "intent": state.intent.model_dump(mode="json"),
        "itinerary": state.itinerary.model_dump(mode="json") if state.itinerary else None,
        "candidate_trains": state.candidate_trains,
        "current_train_index": state.current_train_index,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("itinerary_saved", file=str(out_file))


if __name__ == "__main__":
    app()