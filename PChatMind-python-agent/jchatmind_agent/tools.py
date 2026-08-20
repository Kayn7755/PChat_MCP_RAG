from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from jchatmind_agent.enums import ToolType
from jchatmind_agent.rag_service import RagService

logger = logging.getLogger(__name__)
# Agent 的工具层总装模块，核心功能可以概括为：

# 定义“工具规范”数据结构
# 定义每个工具给大模型看的 OpenAI function schema
# 实现工具后端（知识库检索、数据库查询、邮件发送）
# 组装默认工具列表，并按运行时配置筛选可用工具
# 建立“模型返回的函数名 -> 本地 ToolSpec”的映射，供执行阶段调用

# 定义工具规范, 相当于一个工具的说明书
@dataclass
class ToolSpec: # 把一个工具需要的关键信息放在一起，形成一个 ToolSpec 对象
    """用于 Agent 配置 allowedTools。"""

    registry_name: str # 工具的唯一标识符
    description: str # 工具的描述
    tool_type: ToolType # 工具的类型
    openai_schema: dict[str, Any] # 工具的 OpenAI function schema，给大模型看的 OpenAI function schema 是一份写给大模型看的「工具说明书」，按 OpenAI Function Calling 约定写成的 JSON。模型据此决定何时调用、传什么参数；它本身不执行任何逻辑
    # 最终保存的是JSON,  存的是 _knowledge_tool_schema()等函数的返回值

    handler: Callable[..., str] # 工具的处理函数


# 定义一个给大模型看的 KnowledgeTool 工具说明（OpenAI function schema）
# 它告诉模型三件事：
# 工具名是 KnowledgeTool
# 这个工具用于“按知识库做相似检索（RAG）”
# 调用时参数必须是：
# kbsId（知识库 ID，字符串）
# query（查询文本，字符串）
# 所以这不是在执行检索本身，而是在“声明接口契约”。
# 真正执行逻辑在后面的 handler（knowledge_query）里。
def _knowledge_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "KnowledgeTool",
            "description": (
                "从指定知识库中执行 RAG 检索（可由独立 Modular RAG MCP Server 提供 "
                "hybrid + rerank）。参数为知识库 ID（kbsId）和查询文本（query）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kbsId": {
                        "type": "string",
                        "description": "知识库 ID（MCP 模式下会映射为 collection）",
                    },
                    "query": {"type": "string", "description": "查询文本"},
                    "topK": {
                        "type": "integer",
                        "description": "返回条数，默认 5",
                    },
                },
                "required": ["kbsId", "query"],
            },
        },
    }

# 声明一个“结束任务”的工具给大模型使用。
# 必须带上 message（最终回答）；空调用会被 Agent 忽略，避免模型一上来 terminate 导致无回复。
def _terminate_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "terminate",
            "description": (
                "仅在你已经准备好给用户的最终回答时调用。必须通过 message 提交最终回答。"
                "若尚未回答用户，禁止调用。普通问答也可不调用本工具，直接用文本回复即可结束。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "给用户的最终回答（必填，不能为空）",
                    },
                },
                "required": ["message"],
            },
        },
    }

# 向大模型声明一个数据库查询工具 databaseQuery 的调用协议。
def _database_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "databaseQuery",
            "description": "在 PostgreSQL 中执行只读查询（SELECT）。",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "SELECT 语句"}},
                "required": ["sql"],
            },
        },
    }


def _email_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "sendEmail",
            "description": "发送邮件到指定收件人（异步提交时可仅记录日志）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["to", "subject", "content"],
            },
        },
    }


def _echo_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "_echo",
            "description": "原样返回输入文本。",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "需要回显的文本"}},
                "required": ["text"],
            },
        },
    }
# 这些 `_xxx_schema` 的共同作用是：**给大模型“声明可调用工具的说明书”**（OpenAI function calling schema）。

# 可以理解为“接口合同”，告诉模型：

# - 工具叫什么（`name`）
# - 干什么（`description`）
# - 参数有哪些、类型是什么、哪些必填（`parameters`）

# 在你这个文件里它们分别对应：

# - `_knowledge_tool_schema`：知识库检索工具
# - `_terminate_schema`：结束任务工具
# - `_database_schema`：数据库只读查询工具
# - `_email_schema`：发邮件工具

# 为什么要有这些 schema：
# - 模型只有看到这些 schema，才会正确产出 `tool_calls`
# - Agent 才能按返回的函数名和参数去执行本地 `handler`
# - 保证“模型调用格式”和“本地执行逻辑”对齐

# 一句话：**schema 负责“让模型知道怎么调用工具”，handler 负责“真正执行工具”。**


# 提供一个安全受限(只读)的数据库查询后端，专门给 Agent 工具 databaseQuery 调用。
class DatabaseToolBackend:
    """对齐 DataBaseTools：仅允许 SELECT。"""

    def __init__(self, pg_dsn: str | None) -> None:
        self._pg_dsn = pg_dsn #  dsn 是 Data Source Name，即数据库连接信息，通常包含：数据库地址、端口、用户名、密码、数据库名等。

    def query(self, sql: str) -> str:
        if not self._pg_dsn: # 如果未配置数据库 DSN，则返回错误
            return "错误：未配置数据库 DSN"
        s = sql.strip() # 去除 SQL 语句两端的空白字符
        if not re.match(r"(?is)^select\s", s): # 如果 SQL 语句不是以 SELECT 开头，则返回错误
            return f"错误：仅支持 SELECT 查询语句。提供的 SQL: {sql}"
        import psycopg2 # 导入 psycopg2 库，用于连接 PostgreSQL 数据库

        try:
            with psycopg2.connect(self._pg_dsn) as conn: # 连接 PostgreSQL 数据库
                with conn.cursor() as cur:
                    cur.execute(s) # 执行 SQL 语句
                    colnames = [d[0] for d in cur.description] if cur.description else [] # 获取列名
                    rows = cur.fetchall() # 获取查询结果
            if not colnames: # 如果查询结果为空，则返回错误
                return "查询结果为空（无列）"
            lines = [" | ".join(colnames)] # 将列名拼接成字符串
            lines.append("-" * len(lines[0]))
            for row in rows: # 将查询结果拼接成字符串
                lines.append(" | ".join("NULL" if v is None else str(v) for v in row))
            return "查询结果:\n" + "\n".join(lines) # 返回查询结果
        except Exception as e:
            logger.exception("databaseQuery 失败") # 记录错误日志   
            return f"错误：操作失败 - {e}\nSQL: {sql}"


class EmailToolBackend: # 提供一个安全受限的发邮件后端，专门给 Agent 工具 emailTool 调用。 给 Agent 提供邮件发送工具的执行后端。
    """对齐 EmailTools：可接真实 SMTP 或仅日志。"""

    def __init__(self, send_fn: Callable[[str, str, str], None] | None = None) -> None:
        self._send_fn = send_fn
#        Callable[[str, str, str], None] 这是 Python 的类型注解，表示：一个可调用对象（函数），接收 3 个 str 参数，返回 None
#        └─ 参数类型 ─┘    └─ 返回值类型 ─┘
# self._send_fn 它是一个 可选的回调函数，签名是 (to, subject, content) -> None，负责真正发邮件

    def send(self, to: str, subject: str, content: str) -> str:
        if not to or not to.strip():
            return "错误：收件人邮箱地址不能为空"
        if not subject or not str(subject).strip():
            return "错误：邮件主题不能为空"
        if not content or not str(content).strip():
            return "错误：邮件内容不能为空"
        if "@" not in to:
            return "错误：收件人邮箱地址格式不正确"
        if self._send_fn:
            self._send_fn(to.strip(), str(subject).strip(), str(content).strip())
        else:
            logger.info("EmailTool(模拟): to=%s subject=%s", to, subject)
        return f"邮件已提交发送！\n收件人: {to}\n主题: {subject}\n邮件正在后台异步发送中..."

# 构建一份“默认可用工具清单”（list[ToolSpec]）给 Agent 使用。
def build_default_tool_specs(
    rag: RagService, # 知识库检索服务
    *,# 可选参数
    pg_dsn: str | None = None, # 数据库连接信息
    email_send: Callable[[str, str, str], None] | None = None, # 邮件发送函数
) -> list[ToolSpec]:
    db = DatabaseToolBackend(pg_dsn) # 创建一个数据库查询后端
    mail = EmailToolBackend(email_send) # 创建一个邮件发送后端

    # 定义rag的回调函数（MCP 模式下走 Modular query_knowledge_hub）
    def knowledge_query(**kw: Any) -> str:
        kbs_id = kw.get("kbsId") or kw.get("kbs_id") or ""
        query = kw.get("query") or ""
        raw_limit = kw.get("topK") or kw.get("top_k") or kw.get("limit") or 5
        try:
            limit = max(1, int(raw_limit))
        except (TypeError, ValueError):
            limit = 5
        chunks = rag.similarity_search(str(kbs_id), str(query), limit=limit)
        return "\n".join(chunks) if chunks else ""

    def terminate(**kw: Any) -> str:
        msg = str(kw.get("message") or "").strip()
        if not msg:
            return "错误：terminate 的 message 不能为空。请先写出最终回答再调用，或直接用文本回复用户。"
        return msg

    specs: list[ToolSpec] = [ # 构建一份“默认可用工具清单”（list[ToolSpec]）给 Agent 使用。
        ToolSpec(
            registry_name="KnowledgeTool", # 工具名称
            description="用于从知识库执行语义检索（RAG）。",
            tool_type=ToolType.FIXED, # 工具类型
            openai_schema=_knowledge_tool_schema(), # 工具的 OpenAI function schema
            handler=knowledge_query, # 工具的处理函数(回调函数), 正在执行的函数
        ), # 知识库检索工具
        ToolSpec(
            registry_name="terminate",
            description="提交最终回答并结束任务（message 必填）",
            tool_type=ToolType.FIXED,
            openai_schema=_terminate_schema(),
            handler=lambda **kw: terminate(**kw),
        ), # 结束任务工具
        ToolSpec(
            registry_name="dataBaseTool",
            description="PostgreSQL 只读查询",
            tool_type=ToolType.OPTIONAL,
            openai_schema=_database_schema(),
            handler=lambda **kw: db.query(str(kw.get("sql") or kw.get("SQL") or "")),
        ),
        ToolSpec(
            registry_name="emailTool",
            description="发送邮件",
            tool_type=ToolType.OPTIONAL,
            openai_schema=_email_schema(),
            handler=lambda **kw: mail.send( # 工具的处理函数(回调函数) 
                str(kw.get("to") or ""),
                str(kw.get("subject") or ""),
                str(kw.get("content") or ""),
            ),
        ),
        ToolSpec( # kw 是一个变量名，通常表示 keyword arguments（关键字参数）字典
            registry_name="echoTool",
            description="回显输入文本",
            tool_type=ToolType.OPTIONAL,
            openai_schema=_echo_schema(),
            handler=lambda **kw: str(kw.get("text") or ""), # 把传入参数里的 text 原样取出并返回字符串给大模型
        ),
    ]
    return specs # 返回工具清单

# 根据运行时白名单，决定本轮 Agent 真正可用的工具集合。
def resolve_runtime_tools(
    all_specs: list[ToolSpec], # 所有工具清单
    *,
    allowed_optional_registry_names: set[str] | None, # 可选工具的白名单
) -> list[ToolSpec]:
    fixed = [t for t in all_specs if t.tool_type == ToolType.FIXED] # 固定工具
    if not allowed_optional_registry_names:
        return fixed # 如果可选工具白名单为空，则返回固定工具   
    optional_map = {t.registry_name: t for t in all_specs if t.tool_type == ToolType.OPTIONAL} # 可选工具字典
    extra = [optional_map[n] for n in allowed_optional_registry_names if n in optional_map] # 可选工具列表      
    return fixed + extra # 返回固定工具和可选工具的合集


def openai_function_name_to_spec(specs: list[ToolSpec]) -> dict[str, ToolSpec]: # 把工具列表转换为 OpenAI 兼容的格式
    return {s.openai_schema["function"]["name"]: s for s in specs}
    # 从 specs 提取每个工具的 openai_schema
    # 返回给模型 API 的 tools 参数
    # 作用：告诉模型“你现在可调用哪些工具、参数怎么传”