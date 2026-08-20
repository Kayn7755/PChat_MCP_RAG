from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
# 统一定义 SSE 推送消息的数据结构和序列化格式，保证后端发给前端的事件格式一致

# 定义事件类型枚举
class SseMessageType(str, Enum):
    AI_GENERATED_CONTENT = "AI_GENERATED_CONTENT" # 生成内容消息
    AI_PLANNING = "AI_PLANNING" # 规划消息
    AI_THINKING = "AI_THINKING" # 思考消息
    AI_EXECUTING = "AI_EXECUTING" # 执行消息
    AI_DONE = "AI_DONE" # 完成消息

# 消息体：具体消息内容、状态文案、是否结束
@dataclass
class SsePayload: # 定义 SSE 消息负载(payload)，包含 message、status_text、done。
    message: dict[str, Any] | None = None # 具体聊天消息
    status_text: str | None = None # 状态文本 (如“思考中”)
    done: bool | None = None # 是否完成

# 元数据：对应数据库里的 chat_message_id
@dataclass
class SseMetadata: # 定义 SSE 消息元数据(metadata)，包含 chat_message_id。
    chat_message_id: str | None = None # 对应持久化消息 id

# 完整一条 SSE 消息 = type + payload + metadata
@dataclass
class SseMessage: # 定义 SSE 消息，包含 type、payload、metadata。
    type: SseMessageType # 消息类型
    payload: SsePayload # 消息负载
    metadata: SseMetadata = field(default_factory=SseMetadata) # 消息元数据

    def to_json_dict(self) -> dict[str, Any]: # 将 SSE 消息转换为 JSON 字典 (符合前端 EventSource 事件格式)
        return {
            "type": self.type.value,
            "payload": {
                "message": self.payload.message,
                "statusText": self.payload.status_text,
                "done": self.payload.done,
            },
            "metadata": {"chatMessageId": self.metadata.chat_message_id},
        }


# SSE（Server-Sent Events） 是一种浏览器原生的「服务器单向推送」机制：客户端连上一次，服务器就能持续往前端推消息。

# 和常见方式的对比：

# 方式	        方向	        特点
# 普通HTTP 请求   |  一次请求一次响应，要新状态就得轮询 |请求一次响应，要新状态就得轮询
# SSE | 服务器 → 浏览器  | 一条长连接，服务器主动推
# WebSocket| 双向 | 更重，适合双方频繁互发 更重，适合双方频繁互发

# 在这个项目里，Agent 跑在后台时（思考、规划、执行、生成内容），不会等整轮结束才给前端结果，而是通过 SSE 实时推：

# AI_THINKING / AI_PLANNING / AI_EXECUTING：状态文案
# AI_GENERATED_CONTENT：生成的内容
# AI_DONE：结束
# 对应代码在 schemas.py（消息格式）和 main.py 的 /sse/connect/{session_id}（推送通道）。

# 一句话：SSE = 让前端实时看到 Agent 进度的推送通道。