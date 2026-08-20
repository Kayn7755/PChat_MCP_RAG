"""
LLM 调用适配层：把模型返回的 tool calls 结构统一成内部好处理的格式，把 tool call 的 arguments 字符串安全解析成字典。

tool_calls ：模型不直接给最终答案时，在回复里附带的「请调用这些工具」指令列表。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx # Python 的第三方 HTTP 客户端库，可以理解为 requests 的现代升级版, 默认http1.1

from jchatmind_agent.chat_registry import ModelEndpoint

logger = logging.getLogger(__name__)
# 一个轻量 LLM 调用适配层，主要负责三件事：

# 发起一次 OpenAI 兼容的 /chat/completions 请求
# 把返回里的 tool calls 结构统一成内部好处理的格式
# 把 tool call 的 arguments 字符串安全解析成字典

# Agent 用 HTTP POST 调一次 LLM 的 /chat/completions 接口，把对话消息（和可选的 tools）发出去，再拿回模型回复。
# 流程: Agent → chat_completion（HTTP）→ LLM API → 返回 assistant message
def chat_completion(
    endpoint: ModelEndpoint, # 模型端点, 包含url、api
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    *,
    temperature: float = 0.7,
    top_p: float = 1.0,
    parallel_tool_calls: bool = False,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """
    调用 OpenAI 兼容 /chat/completions: 指的是：一个 HTTP API 接口路径: POST /chat/completions
    它的请求/响应格式遵循 OpenAI 的聊天补全规范
    返回原始 JSON 中的 choices[0].message 结构(content, tool_calls 等)。
    """
    url = endpoint.base_url.rstrip("/") + "/chat/completions" # 地址
    body: dict[str, Any] = {
        "model": endpoint.model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "parallel_tool_calls": parallel_tool_calls,
    } # 消息体
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "Content-Type": "application/json",
    } # 请求头
# temperature 和 top_p 会作为请求体字段传给大模型的 /chat/completions 接口
    with httpx.Client(timeout=timeout) as client: # 发起并处理 HTTP 请求
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            r = client.post(url, headers=headers, json=body)
            if r.status_code == 429 and attempt < 3:
                wait_s = 2 * attempt
                logger.warning( # 429 限流重试 应对调用 LLM API 时被限流
                    "LLM 限流 429, %ss 后重试 (%s/%s): %s",
                    wait_s,
                    attempt,
                    3,
                    url,
                )
                time.sleep(wait_s)
                continue
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                last_exc = e
                body_preview = (e.response.text or "")[:300]
                logger.error(
                    "LLM 请求失败 status=%s body=%s",
                    e.response.status_code,
                    body_preview,
                )
                raise
            data = r.json()
            break
        else:
            if last_exc:
                raise last_exc
            raise RuntimeError("LLM 请求失败")

    choice = data["choices"][0] # 取第一个 choice 消息。 只取模型返回的第一个候选消息作为本次回复。  
    msg = choice["message"] # 取 message 消息。
    return msg 
    # choices：模型生成结果的候选列表（数组）
    # message：某个候选里的“助手消息对象”
#     {
#   "choices": [
#     {
#       "index": 0,
#       "message": {
#         "role": "assistant",
#         "content": "你好，我可以帮你..."
#       },
#         "finish_reason": "stop"
#       }
#     ]
#   }

# 从模型返回的 message 里取出 tool_calls，并统一为 {id, name, arguments} 列表；arguments 为 JSON 字符串。
# normalize_tool_calls获取LLM需要的工具后交给agent，有其他函数执行工具调用再返回结果给大模型 完整链路是：
# 模型提出工具调用 -> Agent 执行工具 -> 工具结果回灌消息历史 -> 再次调用大模型。
# OpenAI-Compatible API 对应的是：用 OpenAI 的 /chat/completions 请求格式去调各类大模型（DeepSeek / 智谱 / 通义等），而不是官方 OpenAI SDK。
def normalize_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    raw = message.get("tool_calls") or [] # 读取模型回复中要求调用的工具列表，如果没有则返回空列表。
    out: list[dict[str, Any]] = []
    for tc in raw:
        fn = tc.get("function") or {}   # 每个 tc（tool call）通常包含:
        out.append(
            {
                "id": tc.get("id", ""), # id：这次工具调用的唯一标识
                "name": fn.get("name", ""), # function.name：要调用的工具名（比如 search_docs）
                "arguments": fn.get("arguments") or "{}", # function.arguments：调用参数（JSON 字符串）
            }
        )
    return out

# 把模型返回的工具参数 arguments（字符串）解析成 Python 字典
# 解析失败时做容错，避免程序崩掉
def parse_tool_arguments(arguments: str) -> dict[str, Any]:
    try:
        return json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        logger.warning("工具参数 JSON 解析失败: %s", arguments)
        return {}
