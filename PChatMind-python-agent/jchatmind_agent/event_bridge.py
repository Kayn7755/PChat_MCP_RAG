"""
用户消息入库后，在后台异步跑 Agent，避免卡住 HTTP 请求。

具体做了这些事：

维护一个 8 线程的线程池 _executor
run_agent_in_background(...) 把任务丢进线程池后立刻返回
后台线程里：factory.create() → jm.run()；出错只打日志，不影响接口响应
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor # py封装的线程池

from jchatmind_agent.factory import AgentConfig, JChatMindFactory

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="jchatmind-agent")
# 维护一个 8 线程的线程池 _executor，用于异步执行 Agent 任务。

# 把一次 Agent 运行丢进后台线程，立刻返回。
def run_agent_in_background(factory: JChatMindFactory, agent: AgentConfig, chat_session_id: str) -> None:
    """对齐 Java @Async ChatEventListener.handle(ChatEvent)：用户消息入库后触发 Agent.run()。"""

    def _job() -> None:
        try:
            jm = factory.create(agent, chat_session_id)
            jm.run()
        except Exception:
            logger.exception("后台 Agent 运行失败 session=%s", chat_session_id)

    _executor.submit(_job)
