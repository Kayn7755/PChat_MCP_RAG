"""
biz.py 是项目的业务逻辑层，真正干活的在这里。main.py 只负责收 HTTP 请求

主要职责：
启动时装配服务（init_app_services）
初始化文档存储、模型客户端注册表、RAG、Agent 工厂等全局依赖。

各资源的 CRUD
Agent、会话、消息、知识库、文档的增删改查；调 repos.py 读写数据库，再转成 api_schemas 里的 VO 返回。

驱动 Agent 运行
用户发消息时（create_chat_message），入库后通过工厂在后台跑 Agent，结果经 SSE 推给前端。

知识库文档处理
上传文件、存盘、解析 Markdown / PDF、写入向量检索。

业务校验与错误
用 BizError 表示「资源不存在」「更新失败」等，由路由层转成 HTTP 错误响应。

一句话：main.py 是门面，biz.py 是「怎么做业务」；它夹在 API 契约（api_schemas）和数据访问（repos）之间，并连接 Agent 运行时。
"""


from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable

from jchatmind_agent.chat_registry import ChatClientRegistry, ModelEndpoint
from jchatmind_agent.event_bridge import run_agent_in_background
from jchatmind_agent.factory import AgentChatOptions, AgentConfig, JChatMindFactory
from jchatmind_agent.jchat_mind import KnowledgeBaseInfo
from jchatmind_agent.tools import build_default_tool_specs

from jchatmind_app.api_schemas import (
    AgentVO,
    ChatMessageVO,
    ChatOptions,
    ChatSessionVO,
    CreateAgentRequest,
    CreateChatMessageRequest,
    CreateChatSessionRequest,
    CreateKnowledgeBaseRequest,
    DocumentVO,
    KnowledgeBaseVO,
    ToolVO,
    UpdateAgentRequest,
    UpdateChatMessageRequest,
    UpdateChatSessionRequest,
    UpdateKnowledgeBaseRequest,
)
from jchatmind_app.config import Settings, get_settings
from jchatmind_app.document_storage import DocumentStorageService
from jchatmind_app.email_util import send_email_async
from jchatmind_app.markdown_sections import parse_markdown_sections
from jchatmind_app import repos as R
from jchatmind_app.sse_bus import send_message

logger = logging.getLogger(__name__)


class BizError(Exception):
    pass


_factory: JChatMindFactory | None = None # Agent的工厂, 用于创建Agent实例
_storage: DocumentStorageService | None = None # 文档存储服务, 用于存储文档

# 构建RAG服务
def _build_rag_service(settings: Settings):
    provider = (settings.rag_provider or "langchain").strip().lower()
    backend = (settings.embed_backend or "openai").strip().lower()
    if provider in ("mcp", "modular", "modular-rag", "modular_rag"):
        from jchatmind_agent.rag_service import McpRagService

        svc = McpRagService.from_settings(settings)
        logger.info("RAG provider: mcp (Modular RAG MCP Server)")
        return svc
    if provider == "langchain":
        try:
            from jchatmind_agent.rag_service import LangChainRagService

            svc = LangChainRagService.from_settings(settings)
            logger.info("RAG provider: langchain backend=%s", backend)
            return svc
        except Exception as e:
            if backend not in ("ollama", "local"):
                raise
            logger.warning("LangChain RAG 初始化失败，回退到原生 Ollama: %s", e)

    from jchatmind_agent.rag_service import OllamaEmbeddingRagService

    logger.info("RAG provider: native ollama")
    return OllamaEmbeddingRagService(
        ollama_base=settings.ollama_base_url,
        embed_model=settings.ollama_embed_model,
        pg_dsn=settings.database_url,
    )

# 初始化应用服务
def init_app_services(settings: Settings) -> None:
    global _factory, _storage
    _storage = DocumentStorageService(settings.document_storage_base_path)

    registry = _build_registry(settings) # 模型客户端注册表, 包含模型名,url,api

    #  import repos as R
    #  从数据库取近期聊天记录，转成 Agent 内存里的消息格式
    def load_recent(session_id: str, limit: int) -> list[dict[str, Any]]:
        rows = R.message_select_by_session_recent(session_id, limit)
        return [_message_row_for_memory(r) for r in rows]

    # 把 Agent 配置里的知识库 id 列表，解析成带名称/描述的知识库对象，供 Agent 运行时做 RAG。
    def resolve_kbs(ids: list[str]) -> list[KnowledgeBaseInfo]:
        rows = R.kb_select_by_ids(ids)
        return [
            KnowledgeBaseInfo(
                id=r["id"],
                name=r.get("name") or "",
                description=r.get("description") or "",
            )
            for r in rows
        ]

    # 把一条聊天消息写入数据库，并返回新消息的 id
    def save_msg(session_id: str, role: str, content: str, metadata: dict[str, Any] | None) -> str:
        return R.message_insert(session_id, role, content, metadata)

    # 把内部消息字典整理成前端 SSE 需要的字段形状; Agent 落库并推流时，先 to_vo 转格式，再 sse_send 推给前端。
    def to_vo(d: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": d.get("id"),
            "sessionId": d.get("sessionId"),
            "role": d.get("role"),
            "content": d.get("content"),
            "metadata": d.get("metadata") or {},
        }

    rag = _build_rag_service(settings) # 创建一个 RAG 服务实例

    # 变量名  函数[[参数], 返回值] | 该变量可以是None = 该变量默认先设为 None
    # Callable 是类型标注，表示「这是一个可调用对象」；真正起回调作用的是后面赋进去的那个函数(类似cpp的回调函数)。
    email_fn: Callable[[str, str, str], None] | None = None
    if settings.mail_username and settings.mail_password:

        def _email(to: str, subject: str, content: str) -> None:
            send_email_async(
                settings.mail_host,
                settings.mail_port,
                settings.mail_username,
                settings.mail_password,
                to,
                subject,
                content,
            )

        email_fn = _email

    # 实例化默认可用工具清单
    specs = build_default_tool_specs(rag, pg_dsn=settings.database_url, email_send=email_fn)
    _factory = JChatMindFactory(
        registry=registry,
        tool_specs=specs,
        load_recent_messages=load_recent,
        resolve_knowledge_bases=resolve_kbs,
        save_agent_message=save_msg,
        sse_send=lambda sid, pl: send_message(sid, pl),
        to_sse_message_vo=to_vo,
    ) # 用配置把模型、工具、知识库、历史消息拼成一个可运行的 JChatMind

# 文档存储服务的安全取值函数：返回全局的 _storage（DocumentStorageService 实例）
# 若 _storage 还是 None（没跑过 init_app_services）→ 抛 RuntimeError("服务未初始化") 否则返回已创建好的存储服务
def get_storage() -> DocumentStorageService:
    if _storage is None:
        raise RuntimeError("服务未初始化")
    return _storage

# 构建模型客户端注册表
def _build_registry(s: Settings) -> ChatClientRegistry:
    m: dict[str, ModelEndpoint] = {} # 模型客户端注册表
    if s.deepseek_api_key:
        m["deepseek-chat"] = ModelEndpoint(
            base_url=s.deepseek_base_url,
            api_key=s.deepseek_api_key,
            model=s.deepseek_model,
        )
    if s.zhipu_api_key:
        m["glm-4.6"] = ModelEndpoint(
            base_url=s.zhipu_base_url,
            api_key=s.zhipu_api_key,
            model=s.zhipu_model,
        )
    if s.qwen_api_key:
        m["qwen3-max"] = ModelEndpoint(
            base_url=s.qwen_base_url,
            api_key=s.qwen_api_key,
            model=s.qwen_model,
        )
    return ChatClientRegistry(m)

#  把数据库里的消息行转成 Agent 对话记忆用的字典。 库表还有 id、session_id、created_at 等；喂给模型上下文时不需要这些，所以在这里裁剪、并把 JSON 文本解析好
def _message_row_for_memory(r: dict[str, Any]) -> dict[str, Any]:
    meta = json.loads(r["metadata"]) if r.get("metadata") else None
    return {"role": r["role"], "content": r["content"], "metadata": meta}

#  把数据库里的 agent 行转成 Agent 运行时配置 AgentConfig（给 jchatmind_agent 用，不是给前端 API 的 AgentVO）。
def _row_to_agent_config(row: dict[str, Any]) -> AgentConfig:
    at = json.loads(row["allowed_tools"]) if row.get("allowed_tools") else []
    ak = json.loads(row["allowed_kbs"]) if row.get("allowed_kbs") else []
    co = json.loads(row["chat_options"]) if row.get("chat_options") else {}
    opts = AgentChatOptions(
        temperature=float(co.get("temperature", 0.7)),
        top_p=float(co.get("topP", 1.0)),
        message_length=int(co.get("messageLength", 10)),
    )
    return AgentConfig(
        id=row["id"],
        name=row.get("name") or "",
        description=row.get("description") or "",
        system_prompt=row.get("system_prompt") or "",
        model=row["model"],
        allowed_tools=list(at) if isinstance(at, list) else [],
        allowed_kbs=list(ak) if isinstance(ak, list) else [],
        chat_options=opts,
    )

# _row_to_agent_vo 把数据库 agent 行转成 API 用的 AgentVO，给前端列表/详情用。
def _row_to_agent_vo(row: dict[str, Any]) -> AgentVO:
    co = json.loads(row["chat_options"]) if row.get("chat_options") else {}
    chat_options = None
    if co:
        chat_options = ChatOptions(
            temperature=co.get("temperature"),
            top_p=co.get("topP"),
            message_length=co.get("messageLength"),
        )
    return AgentVO(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        system_prompt=row.get("system_prompt"),
        model=row["model"],
        allowed_tools=json.loads(row["allowed_tools"]) if row.get("allowed_tools") else [],
        allowed_kbs=json.loads(row["allowed_kbs"]) if row.get("allowed_kbs") else [],
        chat_options=chat_options,
    )


def _row_to_chat_message_vo(row: dict[str, Any]) -> ChatMessageVO:
    meta = json.loads(row["metadata"]) if row.get("metadata") else None
    return ChatMessageVO(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row.get("content"),
        metadata=meta,
    )


def _row_to_session_vo(row: dict[str, Any]) -> ChatSessionVO:
    return ChatSessionVO(
        id=row["id"],
        agent_id=row["agent_id"],
        title=row.get("title"),
    )


def _row_to_kb_vo(row: dict[str, Any]) -> KnowledgeBaseVO:
    return KnowledgeBaseVO(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
    )


def _row_to_doc_vo(row: dict[str, Any]) -> DocumentVO:
    return DocumentVO(
        id=row["id"],
        kb_id=row["kb_id"],
        filename=row["filename"],
        filetype=row["filetype"],
        size=int(row["size"]),
    )


# --- Agents ---
#  查出所有 Agent，转成 AgentVO 列表返回。
def list_agents() -> list[AgentVO]:
    return [_row_to_agent_vo(r) for r in R.agent_select_all()]

# 根据前端创建请求，组装一行数据并插入数据库
def create_agent(req: CreateAgentRequest) -> str:
    now = datetime.now()
    allowed_tools = req.allowed_tools if req.allowed_tools is not None else []
    allowed_kbs = req.allowed_kbs if req.allowed_kbs is not None else []
    if req.chat_options is not None:
        co = req.chat_options.model_dump(exclude_none=True, by_alias=True)
    else:
        co = {}
    co.setdefault("temperature", 0.7)
    co.setdefault("topP", 1.0)
    co.setdefault("messageLength", 10)
    row = {
        "name": req.name,
        "description": req.description,
        "system_prompt": req.system_prompt,
        "model": req.model,
        "allowed_tools": json.dumps(allowed_tools),
        "allowed_kbs": json.dumps(allowed_kbs),
        "chat_options": json.dumps(co),
        "created_at": now,
        "updated_at": now,
    }
    return R.agent_insert(row)

# 
def update_agent(aid: str, req: UpdateAgentRequest) -> None:
    if not R.agent_select_by_id(aid):
        raise BizError(f"Agent 不存在: {aid}")
    fields: dict[str, Any] = {}
    if req.name is not None:
        fields["name"] = req.name
    if req.description is not None:
        fields["description"] = req.description
    if req.system_prompt is not None:
        fields["system_prompt"] = req.system_prompt
    if req.model is not None:
        fields["model"] = req.model
    if req.allowed_tools is not None:
        fields["allowed_tools"] = json.dumps(req.allowed_tools)
    if req.allowed_kbs is not None:
        fields["allowed_kbs"] = json.dumps(req.allowed_kbs)
    if req.chat_options is not None:
        fields["chat_options"] = json.dumps(req.chat_options.model_dump(exclude_none=True, by_alias=True))
    if not fields:
        return
    if not R.agent_update(aid, fields):
        raise BizError("更新 agent 失败")


def delete_agent(aid: str) -> None:
    if not R.agent_select_by_id(aid):
        raise BizError(f"Agent 不存在: {aid}")
    if not R.agent_delete(aid):
        raise BizError("删除 agent 失败")


# --- Sessions ---
def list_sessions() -> list[ChatSessionVO]:
    return [_row_to_session_vo(r) for r in R.session_select_all()]


def get_session(sid: str) -> ChatSessionVO:
    row = R.session_select_by_id(sid)
    if not row:
        raise BizError(f"聊天会话不存在: {sid}")
    return _row_to_session_vo(row)


def list_sessions_by_agent(agent_id: str) -> list[ChatSessionVO]:
    return [_row_to_session_vo(r) for r in R.session_select_by_agent(agent_id)]


def create_session(req: CreateChatSessionRequest) -> str:
    if not R.agent_select_by_id(req.agent_id):
        raise BizError(f"Agent 不存在: {req.agent_id}")
    now = datetime.now()
    return R.session_insert(
        {"agent_id": req.agent_id, "title": req.title, "metadata": None, "created_at": now, "updated_at": now}
    )


def update_session(sid: str, req: UpdateChatSessionRequest) -> None:
    if not R.session_select_by_id(sid):
        raise BizError(f"聊天会话不存在: {sid}")
    f: dict[str, Any] = {}
    if req.title is not None:
        f["title"] = req.title
    if not f:
        return
    if not R.session_update(sid, f):
        raise BizError("更新会话失败")


def delete_session(sid: str) -> None:
    if not R.session_select_by_id(sid):
        raise BizError(f"聊天会话不存在: {sid}")
    if not R.session_delete(sid):
        raise BizError("删除会话失败")


# --- Messages ---
def list_messages_by_session(session_id: str) -> list[ChatMessageVO]:
    return [_row_to_chat_message_vo(r) for r in R.message_select_by_session(session_id)]


def create_chat_message(req: CreateChatMessageRequest) -> str:
    arow = R.agent_select_by_id(req.agent_id)
    if not arow:
        raise BizError(f"Agent 不存在: {req.agent_id}")
    mid = R.message_insert(req.session_id, req.role, req.content, req.metadata)
    if _factory is not None:
        run_agent_in_background(_factory, _row_to_agent_config(arow), req.session_id)
    return mid


def update_message(mid: str, req: UpdateChatMessageRequest) -> None:
    if not R.message_select_by_id(mid):
        raise BizError(f"聊天消息不存在: {mid}")
    if not R.message_update(mid, req.content, req.metadata):
        raise BizError("更新消息失败")


def delete_message(mid: str) -> None:
    if not R.message_select_by_id(mid):
        raise BizError(f"聊天消息不存在: {mid}")
    if not R.message_delete(mid):
        raise BizError("删除消息失败")


# --- Knowledge bases ---
def list_kbs() -> list[KnowledgeBaseVO]:
    return [_row_to_kb_vo(r) for r in R.kb_select_all()]


def create_kb(req: CreateKnowledgeBaseRequest) -> str:
    return R.kb_insert(req.name, req.description)


def update_kb(kid: str, req: UpdateKnowledgeBaseRequest) -> None:
    if not R.kb_select_by_id(kid):
        raise BizError(f"知识库不存在: {kid}")
    if req.name is None and req.description is None:
        return
    if not R.kb_update(kid, req.name, req.description):
        raise BizError("更新知识库失败")


def delete_kb(kid: str) -> None:
    if not R.kb_select_by_id(kid):
        raise BizError(f"知识库不存在: {kid}")
    if not R.kb_delete(kid):
        raise BizError("删除知识库失败")


# --- Documents ---
def list_documents() -> list[DocumentVO]:
    return [_row_to_doc_vo(r) for r in R.doc_select_all()]


def list_documents_by_kb(kb_id: str) -> list[DocumentVO]:
    return [_row_to_doc_vo(r) for r in R.doc_select_by_kb(kb_id)]


def delete_document(did: str) -> None:
    row = R.doc_select_by_id(did)
    if not row:
        raise BizError(f"文档不存在: {did}")
    R.chunk_delete_by_doc(did)
    try:
        meta = json.loads(row["metadata"]) if row.get("metadata") else {}
        fp = meta.get("filePath")
        if fp:
            get_storage().delete_file(fp)
    except Exception:
        logger.warning("删除文档文件失败 doc=%s", did)
    if not R.doc_delete(did):
        raise BizError("删除文档失败")

# 上传知识库文档的完整业务流程——校验、登记、存盘、按类型做RAG切分入库，最后返回 doc_id
def upload_document(kb_id: str, filename: str | None, data: bytes) -> str:
    if not data:
        raise BizError("上传的文件为空")
    if not R.kb_select_by_id(kb_id):
        raise BizError(f"知识库不存在: {kb_id}")
    ft = "unknown"
    if filename and "." in filename:
        ft = filename.rsplit(".", 1)[-1].lower()
    now = datetime.now()
    row = {
        "kb_id": kb_id,
        "filename": filename or "unnamed",
        "filetype": ft,
        "size": len(data),
        "metadata": None,
        "created_at": now,
        "updated_at": now,
    }
    doc_id = R.doc_insert(row)
    rel = get_storage().save_upload(kb_id, doc_id, filename, data)
    R.doc_update(doc_id, {"metadata": {"filePath": rel}})
    if ft in ("md", "markdown"):
        _process_markdown_kb(kb_id, doc_id, rel)
    elif ft == "pdf":
        _process_pdf_kb(kb_id, doc_id, rel)
    else:
        logger.warning("待新增处理的文件类型: %s", ft)
    return doc_id


def _vec_lit(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"

# 把已上传的 Markdown 按章节切分、向量化并写入 chunk_bge_m3，供知识库检索。
def _process_markdown_kb(kb_id: str, doc_id: str, relative_path: str) -> None:
    settings = get_settings()
    rag = _build_rag_service(settings)
    path = get_storage().full_path(relative_path)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("读取 Markdown 失败: %s", e)
        return
    sections = parse_markdown_sections(text) # 调用parse_markdown_sections将md按标题拆分
    if not sections:
        logger.warning("Markdown 无章节 doc=%s", doc_id)
        return
    for sec in sections:
        if not sec.title.strip():
            continue
        try:
            emb = rag.embed(sec.title) # 将拆分的内容编码
            R.chunk_insert(kb_id, doc_id, sec.content or "", _vec_lit(emb)) # 存入数据库
        except Exception:
            logger.exception("写入 chunk 失败 title=%s", sec.title)


def _process_pdf_kb(kb_id: str, doc_id: str, relative_path: str) -> None:
    """Docling 解析 PDF → 递归字符切分 → 对 chunk 正文 embedding 入库。"""
    from jchatmind_app.pdf_docling import pdf_to_markdown
    from jchatmind_app.recursive_chunks import split_recursive

    settings = get_settings()
    rag = _build_rag_service(settings)
    path = get_storage().full_path(relative_path)
    try:
        text = pdf_to_markdown(path) # 由pdf_to_markdown函数解析pdf
    except Exception as e:
        logger.error("Docling 解析 PDF 失败 doc=%s: %s", doc_id, e)
        return
    chunks = split_recursive(
        text,
        chunk_size=settings.pdf_chunk_size,
        chunk_overlap=settings.pdf_chunk_overlap,
    ) # 将解析的pdf按照递归字符切分
    # Markdown 自带可靠的结构边界，PDF 转出来的文本通常没有（或不稳定）, 所以要递归切分
    if not chunks:
        logger.warning("PDF 无可用 chunk doc=%s", doc_id)
        return
    for i, chunk in enumerate(chunks):
        try:
            emb = rag.embed(chunk)
            R.chunk_insert(kb_id, doc_id, chunk, _vec_lit(emb))
        except Exception:
            logger.exception("写入 PDF chunk 失败 doc=%s idx=%s", doc_id, i)

# 列出系统里所有「可选工具」的元数据，给前端配置 Agent 时勾选
def list_optional_tools() -> list[ToolVO]:
    from jchatmind_agent.enums import ToolType as TT
    from jchatmind_agent.rag_service import InMemoryRagService

    specs = build_default_tool_specs(InMemoryRagService(), pg_dsn=None)
    out: list[ToolVO] = []
    for s in specs:
        if s.tool_type == TT.OPTIONAL:
            out.append(
                ToolVO(
                    name=s.registry_name,
                    description=s.description,
                    type=s.tool_type.value,
                )
            )
    return out
