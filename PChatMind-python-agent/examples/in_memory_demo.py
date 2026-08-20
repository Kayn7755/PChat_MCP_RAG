"""
内存演示：不连数据库，展示 JChatMindFactory + JChatMind.run() 的调用方式。
需设置环境变量 JCHATMIND_DEEPSEEK_API_KEY 或 JCHATMIND_ZHIPU_API_KEY。
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from jchatmind_agent.chat_registry import default_registry_from_env
from jchatmind_agent.factory import AgentConfig, AgentChatOptions, build_factory_with_defaults
from jchatmind_agent.jchat_mind import KnowledgeBaseInfo
from jchatmind_agent.rag_service import InMemoryRagService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 会话内存：session_id -> 消息列表（简化结构）
_STORE: dict[str, list[dict[str, Any]]] = {}


def load_recent(session_id: str, limit: int) -> list[dict[str, Any]]:
    rows = _STORE.get(session_id, [])
    return rows[-limit:] if limit else rows


def resolve_kbs(ids: list[str]) -> list[KnowledgeBaseInfo]:
    return [KnowledgeBaseInfo(id=i, name=i, description="demo kb") for i in ids]


def save_message(session_id: str, role: str, content: str, metadata: dict[str, Any] | None) -> str:
    mid = str(uuid.uuid4())
    _STORE.setdefault(session_id, []).append(
        {"id": mid, "role": role, "content": content, "metadata": metadata or {}}
    )
    logger.info("saved %s %s id=%s", role, (content or "")[:80], mid)
    return mid


def to_vo(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "sessionId": row.get("sessionId"),
        "role": row.get("role"),
        "content": row.get("content"),
        "metadata": row.get("metadata") or {},
    }


def sse_send(session_id: str, payload: dict[str, Any]) -> None:
    logger.info("SSE [%s] %s", session_id, json.dumps(payload, ensure_ascii=False)[:500])


def main() -> None:
    registry = default_registry_from_env()
    if not registry.get("deepseek-chat") and not registry.get("glm-4.6"):
        logger.error("请设置 JCHATMIND_DEEPSEEK_API_KEY 或 JCHATMIND_ZHIPU_API_KEY")
        sys.exit(1)

    rag = InMemoryRagService()
    factory = build_factory_with_defaults(
        registry=registry,
        rag=rag,
        pg_dsn=None,
        load_recent_messages=load_recent,
        resolve_knowledge_bases=resolve_kbs,
        save_agent_message=save_message,
        sse_send=sse_send,
        to_sse_message_vo=to_vo,
    )

    session_id = "sess-demo-1"
    user_text = "你好，用一句话介绍你自己，然后调用 terminate 结束。"
    _STORE[session_id] = [{"id": "u1", "role": "user", "content": user_text, "metadata": {}}]

    model = "deepseek-chat" if registry.get("deepseek-chat") else "glm-4.6"
    agent = AgentConfig(
        id="agent-1",
        name="Demo",
        description="demo",
        system_prompt="你是一个简洁的助手。完成用户诉求后请调用 terminate。",
        model=model,
        allowed_tools=[],
        allowed_kbs=[],
        chat_options=AgentChatOptions(message_length=20),
    )

    jm = factory.create(agent, session_id)
    jm.run()
    logger.info("最终状态: %s", jm.agent_state)


if __name__ == "__main__":
    main()
