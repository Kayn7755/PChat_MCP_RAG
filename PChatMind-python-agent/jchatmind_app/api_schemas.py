# FastAPI 后端的接口数据契约层：用 Pydantic 定义所有 HTTP 请求/响应的结构，供 main.py（路由）和 biz.py（业务）校验、序列化数据。

# 它主要做这几件事：

# 统一响应包装 — ApiResponse[T]（code / message / data）
# 驼峰命名兼容 — CamelModel 把 Python 的 snake_case 转成前端常用的 camelCase
# 按业务域定义模型：
# Agent：创建/更新/查询
# Chat Session / Message：会话与消息
# Knowledge Base / Document：知识库与文档
# Tool：工具元数据
# 简单说：它不负责业务逻辑，只规定「前端和后端之间传什么字段、什么类型」，保证接口形状一致，并自动做校验与 OpenAPI 文档生成。
"""
HTTP 接口的数据契约层：用 Pydantic 定义请求/响应结构，供 main.py 校验入参、biz.py 组装出参，本身不做业务逻辑。
主要做三件事：
统一响应壳：ApiResponse[T] → { code, message, data }
命名对齐：CamelModel 让 Python 用 snake_case，JSON 对外用 camelCase
按业务域建模：Agent、会话/消息、知识库/文档、工具等 XxxRequest / XxxVO
和 FastAPI 的关系：路由参数写成 body: CreateAgentRequest 时，FastAPI 会自动校验类型、生成 OpenAPI 文档；返回前把 VO model_dump 进统一包装。一句话：规定前后端传什么字段、什么类型。

DB row 数据库查出来的一行 repos 返回的 dict（如 allowed_tools 还是 JSON 字符串）
VO（View Object） 给前端/API 看的视图对象 api_schemas 里的 AgentVO 等（已是 list[str]、驼峰字段）
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field
# 继承 BaseModel 后自动获得：pydantic的类型提示, 减少手动校验代码
# 校验：缺字段、类型不对会报错（FastAPI 会转成 422）
# 解析：把 JSON / dict 转成 Python 对象
# 序列化：.model_dump() / .model_dump_json() 再变回 dict / JSON
# 文档：FastAPI 据此生成 OpenAPI Schema

T = TypeVar("T")

# 修改命名方法/方便和前端对齐
def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)

# ConfigDict 是 Pydantic v2 里用来配置模型行为的字典类型，写在类属性 model_config 上。它不定义字段，只规定：这个模型怎么解析输入、怎么输出、要不要用别名等。
# 所有 API 模型的基类 作用是统一命名约定——Python 里用snake_case，和前端交互的 JSON 用 camelCase，子类不用每个字段手写别名。
class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, # 字段名自动生成驼峰别名
        populate_by_name=True, # 入参既可用 snake_case，也可用 camelCase
        ser_json_by_alias=True, # 序列化成 JSON 时用驼峰别名输出
    )

# 统一的接口返回壳子。所有成功响应都是 { code, message, data }，data 用泛型 T 填具体业务数据（Agent、消息列表等）。
# 统一的成功响应包装，结构是：{ "code": 200, "message": "success", "data": ... }
class ApiResponse(CamelModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: T | None = None
# T 是泛型，表示 data 的具体类型（比如 Agent 列表、会话详情等）。后续各种 XxxRequest / XxxVO 都继承 CamelModel，接口返回则套在 ApiResponse 里。

# --- Agent ---  智能体相关的请求/响应模型
ModelType = Literal["deepseek-chat", "glm-4.6", "qwen3-max"]

# 对话参数：温度、topP、消息长度限制
class ChatOptions(CamelModel):
    temperature: float | None = None
    top_p: float | None = Field(None, alias="topP")
    message_length: int | None = Field(None, alias="messageLength")

# 创建 Agent 时前端传的字段（名称、描述、系统提示词、模型、工具、知识库、聊天选项）
class CreateAgentRequest(CamelModel):
    name: str
    description: str | None = None
    system_prompt: str | None = None
    model: str
    allowed_tools: list[str] | None = None
    allowed_kbs: list[str] | None = None
    chat_options: ChatOptions | None = None

# 更新 Agent，字段都可选，只改传入的部分
class UpdateAgentRequest(CamelModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    allowed_tools: list[str] | None = None
    allowed_kbs: list[str] | None = None
    chat_options: ChatOptions | None = None

# 返回给前端的 Agent 视图对象（含 id）
class AgentVO(CamelModel):
    id: str
    name: str
    description: str | None = None
    system_prompt: str | None = None
    model: str
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_kbs: list[str] = Field(default_factory=list)
    chat_options: ChatOptions | None = None  # 无配置时可省略

# 列表接口的 data：{ agents: [...] }
class GetAgentsResponse(CamelModel):
    agents: list[AgentVO]

# 创建成功后返回的 { agentId: "..." }
class CreateAgentResponse(CamelModel):
    agent_id: str = Field(serialization_alias="agentId")


# --- Chat session ---
class CreateChatSessionRequest(CamelModel):
    agent_id: str
    title: str | None = None


class CreateChatSessionResponse(CamelModel):
    chat_session_id: str = Field(serialization_alias="chatSessionId")


class ChatSessionVO(CamelModel):
    id: str
    agent_id: str
    title: str | None = None


class GetChatSessionsResponse(CamelModel):
    chat_sessions: list[ChatSessionVO]


class GetChatSessionResponse(CamelModel):
    chat_session: ChatSessionVO


class UpdateChatSessionRequest(CamelModel):
    title: str | None = None


# --- Chat message ---
MessageRole = Literal["user", "assistant", "system", "tool"]


class ChatMessageMetadata(CamelModel):
    tool_calls: list[dict[str, Any]] | None = Field(None, alias="toolCalls")
    tool_response: dict[str, Any] | None = Field(None, alias="toolResponse")


class ChatMessageVO(CamelModel):
    id: str
    session_id: str
    role: MessageRole
    content: str | None = None
    metadata: dict[str, Any] | None = None


class GetChatMessagesResponse(CamelModel):
    chat_messages: list[ChatMessageVO]


class CreateChatMessageRequest(CamelModel):
    agent_id: str
    session_id: str
    role: MessageRole
    content: str
    metadata: dict[str, Any] | None = None


class CreateChatMessageResponse(CamelModel):
    chat_message_id: str = Field(serialization_alias="chatMessageId")


class UpdateChatMessageRequest(CamelModel):
    content: str | None = None
    metadata: dict[str, Any] | None = None


# --- Knowledge base ---
class KnowledgeBaseVO(CamelModel):
    id: str
    name: str
    description: str | None = None


class GetKnowledgeBasesResponse(CamelModel):
    knowledge_bases: list[KnowledgeBaseVO]


class CreateKnowledgeBaseRequest(CamelModel):
    name: str
    description: str | None = None


class CreateKnowledgeBaseResponse(CamelModel):
    knowledge_base_id: str = Field(serialization_alias="knowledgeBaseId")


class UpdateKnowledgeBaseRequest(CamelModel):
    name: str | None = None
    description: str | None = None


# --- Document ---
class DocumentVO(CamelModel):
    id: str
    kb_id: str
    filename: str
    filetype: str
    size: int


class GetDocumentsResponse(CamelModel):
    documents: list[DocumentVO]


class CreateDocumentResponse(CamelModel):
    document_id: str = Field(serialization_alias="documentId")


# --- Tool ---
ToolTypeEnum = Literal["FIXED", "OPTIONAL"]


class ToolVO(CamelModel):
    name: str
    description: str
    type: ToolTypeEnum
