"""
SSE（Server-Sent Events）消息总线：把 Agent 运行时产生的事件，推到前端已建立的长连接上。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_queues: dict[str, asyncio.Queue[str]] = {}
_main_loop: asyncio.AbstractEventLoop | None = None

# 记下 FastAPI 的主事件循环（启动时设置）
def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop

# 某会话连接 SSE 时，登记一个 asyncio.Queue
def register_session(session_id: str) -> asyncio.Queue[str]:
    q: asyncio.Queue[str] = asyncio.Queue()
    _queues[session_id] = q
    return q


def unregister_session(session_id: str) -> None:
    _queues.pop(session_id, None)


def unregister_if_current(session_id: str, q: asyncio.Queue[str]) -> None:
    """避免旧连接 finally 误删新连接的 Queue。"""
    if _queues.get(session_id) is q:
        _queues.pop(session_id, None)

# Agent 侧往该会话队列里塞 JSON（线程安全投递到主 loop）
def send_message(session_id: str, payload: dict[str, Any]) -> None:
    q = _queues.get(session_id)
    if not q:
        logger.warning("SSE 无连接: session=%s", session_id)
        return
    line = json.dumps(payload, ensure_ascii=False)
    if _main_loop is None:
        logger.error("主事件循环未设置，无法推送 SSE")
        return
    fut = asyncio.run_coroutine_threadsafe(q.put(line), _main_loop)
    try:
        fut.result(timeout=30)
    except Exception as e:
        logger.warning("SSE 推送失败: %s", e)
