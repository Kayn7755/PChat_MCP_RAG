"""
Agent 组装工厂：按某个Agent 的配置，把模型、工具、知识库、历史消息等拼好，创建可运行的 JChatMind 实例。
前端界面的智能体助手
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from jchatmind_agent.chat_registry import ChatClientRegistry
from jchatmind_agent.jchat_mind import JChatMind, KnowledgeBaseInfo, SaveMessageFn, SseSendFn
from jchatmind_agent.tools import ToolSpec, build_default_tool_specs, resolve_runtime_tools

logger = logging.getLogger(__name__)


@dataclass
class AgentChatOptions:
    """
    Agent 的聊天选项: 温度、top_p、消息长度。
    """
    temperature: float = 0.7
    top_p: float = 1.0
    message_length: int = 20

# 一份智能体配置声明：只描述「这个 Agent 长什么样、能用什么」，不负责真正跑对话
@dataclass
class AgentConfig:
    """
    Agent 配置：id、name、description、system_prompt、model、allowed_tools、allowed_kbs、chat_options。
    """
    id: str
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    model: str = "qwen3-max"
    allowed_tools: list[str] = field(default_factory=list) # 允许的可选工具名列表
    allowed_kbs: list[str] = field(default_factory=list) # 允许的知识库 id 列表
    chat_options: AgentChatOptions = field(default_factory=AgentChatOptions) # 温度、top_p、历史消息条数等生成参数

# 回调函数的类型别名，不是具体实现。工厂只约定「要传什么样的函数」，真正逻辑由业务层注入
LoadRecentMessagesFn = Callable[[str, int], list[dict[str, Any]]] # 加载近期消息函数类型，包含 session_id、消息长度。
ResolveKnowledgeBasesFn = Callable[[list[str]], list[KnowledgeBaseInfo]] # 解析知识库函数类型，包含知识库 id 列表。


def _args_to_str(args: Any) -> str:
    if isinstance(args, str):
        return args
    try:
        return json.dumps(args if args is not None else {}, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"


def _to_openai_tool_call(tc: dict[str, Any]) -> dict[str, Any]:
    """把扁平 toolCall 或已是 OpenAI 格式的记录，统一成 API 要求的嵌套结构。"""
    if isinstance(tc.get("function"), dict):
        fn = tc["function"]
        return {
            "id": tc.get("id") or "",
            "type": tc.get("type") or "function",
            "function": {
                "name": fn.get("name") or "",
                "arguments": _args_to_str(fn.get("arguments")),
            },
        }
    return {
        "id": tc.get("id") or "",
        "type": tc.get("type") or "function",
        "function": {
            "name": tc.get("name") or "",
            "arguments": _args_to_str(tc.get("arguments")),
        },
    }


# 把「DB 里的近期聊天记录」转成「调用 LLM 时用的 messages 列表」
def default_messages_from_history(
    system_prompt: str, # Agent 的系统提示词
    recent: list[dict[str, Any]], # 近期消息列表
) -> list[dict[str, Any]]:
    """将近期消息转为 OpenAI role/content 列表（简化版，对齐 DB 中 role 字段）。"""
    out: list[dict[str, Any]] = []
    if system_prompt:
        out.append({"role": "system", "content": system_prompt}) # 在系统提示词中加历史信息
    for m in recent: # 遍历近期消息列表，转换成 OpenAI 的 role/content 格式
        if system_prompt and (m.get("role") or "").lower() == "system": # 如果系统提示词存在且消息角色为系统，则跳过
            continue
        role = (m.get("role") or "user").lower()
        if role == "system" and not (m.get("content") or "").strip(): # 如果消息角色为系统且内容为空，则跳过
            continue
        if role == "user" and not (m.get("content") or "").strip(): # 如果消息角色为用户且内容为空，则跳过
            continue
        if role == "assistant": # 如果消息角色为助手，则转换成 OpenAI 的 role/content 格式
            item: dict[str, Any] = {
                "role": "assistant",
                "content": m.get("content"),
            }
            tcs = m.get("tool_calls") or (m.get("metadata") or {}).get("toolCalls")
            if tcs:
                # DB/前端存的是扁平 {id,name,arguments}；回灌 LLM 必须转成 OpenAI 嵌套 function 格式，否则通义等会 400
                item["tool_calls"] = [
                    _to_openai_tool_call(tc) for tc in tcs if isinstance(tc, dict)
                ]
            out.append(item)
        elif role == "tool":
            meta = m.get("metadata") or {}
            tid = meta.get("toolCallId") or meta.get("tool_call_id") or ""
            tr = meta.get("toolResponse") or {}
            if not tid:
                tid = tr.get("id") or ""
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": tid,
                    "content": m.get("content") or "",
                }
            )
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    return out

# 用配置把模型、工具、知识库、历史消息拼成一个可运行的 JChatMind。
@dataclass
class JChatMindFactory:
    """
  加载 Agent 配置、拼装工具回调、构建 JChatMind。
    持久化与 SSE 通过注入的回调完成，便于接 FastAPI / SQLAlchemy 等。
    """

    registry: ChatClientRegistry # 模型注册表，根据模型名找到对应的 ChatClient
    tool_specs: list[ToolSpec] # 工具规范列表，每个工具都有 name、description、parameters 等
    load_recent_messages: LoadRecentMessagesFn # 加载近期消息函数，包含 session_id、消息长度。
    resolve_knowledge_bases: ResolveKnowledgeBasesFn # 解析知识库函数，包含知识库 id 列表。
    save_agent_message: SaveMessageFn | None = None # 保存助手消息函数，包含消息内容、角色、时间等。
    sse_send: SseSendFn | None = None # 发送 SSE 消息函数，包含消息内容、角色、时间等。
    to_sse_message_vo: Callable[[dict[str, Any]], dict[str, Any]] | None = None # 转换消息为 SSE 消息格式函数，包含消息内容、角色、时间等。

    def create(self, agent: AgentConfig, chat_session_id: str) -> JChatMind:
        endpoint = self.registry.get(agent.model)
        if endpoint is None:
            raise RuntimeError(f"未找到对应的 ChatClient: {agent.model}")

        allowed_opt = set(agent.allowed_tools) if agent.allowed_tools else set()
        runtime_tools = resolve_runtime_tools(
            self.tool_specs, allowed_optional_registry_names=allowed_opt
        )
        kbs = self.resolve_knowledge_bases(agent.allowed_kbs)
        recent = self.load_recent_messages(chat_session_id, agent.chat_options.message_length)
        messages = default_messages_from_history(agent.system_prompt, recent)
        
        # 创建 JChatMind 实例，传入配置和回调函数
        return JChatMind(
            agent_id=agent.id,
            name=agent.name,
            description=agent.description,
            system_prompt=agent.system_prompt,
            chat_session_id=chat_session_id,
            endpoint=endpoint,
            tool_specs=runtime_tools,
            knowledge_bases=kbs,
            temperature=agent.chat_options.temperature,
            top_p=agent.chat_options.top_p,
            max_messages=agent.chat_options.message_length,
            messages=messages,
            save_message=self.save_agent_message,
            sse_send=self.sse_send,
            to_sse_message_vo=self.to_sse_message_vo,
        )


def build_factory_with_defaults(
    *,
    registry: ChatClientRegistry,
    rag,
    pg_dsn: str | None = None,
    load_recent_messages: LoadRecentMessagesFn,
    resolve_knowledge_bases: ResolveKnowledgeBasesFn,
    save_agent_message: SaveMessageFn | None = None,
    sse_send: SseSendFn | None = None,
    to_sse_message_vo: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> JChatMindFactory:
    specs = build_default_tool_specs(rag, pg_dsn=pg_dsn)
    return JChatMindFactory(
        registry=registry,
        tool_specs=specs,
        load_recent_messages=load_recent_messages,
        resolve_knowledge_bases=resolve_knowledge_bases,
        save_agent_message=save_agent_message,
        sse_send=sse_send,
        to_sse_message_vo=to_sse_message_vo,
    )
