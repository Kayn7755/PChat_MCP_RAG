"""
JChatMind 的 FastAPI 入口：创建应用、管理生命周期，并对外暴露 HTTP/SSE API
FastAPI 是 Web 服务框架：负责对外提供 HTTP/SSE，把请求交给 biz，本身几乎不做业务和 SQL。
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from jchatmind_app.api_schemas import (
    CreateAgentRequest,
    CreateAgentResponse,
    CreateChatMessageRequest,
    CreateChatMessageResponse,
    CreateChatSessionRequest,
    CreateChatSessionResponse,
    CreateDocumentResponse,
    CreateKnowledgeBaseRequest,
    CreateKnowledgeBaseResponse,
    GetAgentsResponse,
    GetChatMessagesResponse,
    GetChatSessionResponse,
    GetChatSessionsResponse,
    GetDocumentsResponse,
    GetKnowledgeBasesResponse,
    UpdateAgentRequest,
    UpdateChatMessageRequest,
    UpdateChatSessionRequest,
    UpdateKnowledgeBaseRequest,
)
from jchatmind_app import biz
from jchatmind_app.biz import BizError
from jchatmind_app.config import get_settings
from jchatmind_app.pool import DatabaseUnavailable, close_pool, try_init_pool
from jchatmind_app import sse_bus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
_UI_DIST = _ROOT / "ui" / "dist"

# 把 Pydantic 模型转成可 JSON 序列化的 dict
def _dump(model: Any) -> Any:
    if model is None:
        return None
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", by_alias=True)
    return model

# 返回成功响应
def _ok(data: Any = None) -> dict[str, Any]:
    return {"code": 200, "message": "success", "data": _dump(data)}

# 返回原始数据响应
def _ok_raw(data: Any) -> dict[str, Any]:
    return {"code": 200, "message": "success", "data": data}

# lifespan 是 FastAPI/Starlette 的应用生命周期钩子：在服务真正开始接请求之前、以及进程关闭时，各跑一段初始化/清理逻辑
@asynccontextmanager # @asynccontextmanager 写成异步上下文管理器，用于在应用生命周期中执行初始化/清理逻辑
async def lifespan(app: FastAPI):
    # # --- 启动：只执行一次 ---
    s = get_settings() # 获取配置
    db_ok = try_init_pool(s.database_url) # 尝试初始化数据库连接池
    if not db_ok:
        target = s.database_url.split("@")[-1] if "@" in s.database_url else s.database_url
        logger.error(
            "无法连接 PostgreSQL，目标 %s。请启动服务并创建库 jchatmind，"
            "或通过 JCHATMIND_DATABASE_URL 指定连接串。"
            "若仅做前端联调可设 JCHATMIND_ALLOW_START_WITHOUT_DB=1。",
            target,
        )
        if not s.allow_start_without_db:
            raise RuntimeError(
                "PostgreSQL 连接失败。详见上方日志；或设置 JCHATMIND_ALLOW_START_WITHOUT_DB=1 跳过（数据库接口将不可用）。"
            )
    biz.init_app_services(s) # 初始化应用服务
    sse_bus.set_main_loop(asyncio.get_running_loop()) # 设置主线程循环
    logger.info(
        "JChatMind Python 已启动%s",
        "，数据库已连接" if db_ok else "（无数据库：仅联调用，勿依赖 /api 持久化）",
    )
    yield # 生成器，用于在应用生命周期中执行初始化/清理逻辑
    # yield 之前：启动阶段（建库连接池、初始化业务服务、绑定 SSE 事件循环）
    # yield：应用正常运行、处理请求
    # yield 之后：关闭阶段（关掉连接池）
    # --- 关闭：进程退出时 ---
    close_pool()
    logger.info("连接池已关闭")

# 默认的app = FastAPI() 和 app = FastAPI(lifespan=lifespan) 都能正常跑；
# 差别只在于：要不要在「服务启动 / 关闭」时自动做一些事。 没有它只是少了「启动初始化 + 关闭清理」
# lifespan告诉FastAPI：用这个异步上下文管理器管生命周期; 在项目中作用: 在接受请求前初始化连接池、业务服务和SSE事件循环, 在进程退出时关闭连接池。
app = FastAPI(title="JChatMind", lifespan=lifespan)

_s = get_settings()
_origins = ["*"] if _s.cors_origins.strip() == "*" else [x.strip() for x in _s.cors_origins.split(",") if x.strip()]

# 给 FastAPI 加 CORS 中间件，让浏览器里的前端（比如 localhost:5173）能跨域调后端 8080 的接口
app.add_middleware(
    CORSMiddleware, # 处理跨域：给响应加 Access-Control-* 头，并应答浏览器的 OPTIONS 预检
    allow_origins=_origins, # 允许的源域名列表，* 表示允许所有域名
    allow_credentials=True, # 是否允许携带 cookie
    allow_methods=["*"],
    allow_headers=["*"], # 允许的请求头列表 
)

# FastAPI 的全局异常处理器：路由或业务里抛出对应异常时，不走默认 500 堆栈页，而是统一打成你们约定的 JSON 返回给前端
# 业务主动抛的错（如「知识库不存在」） 把错误信息放进 message 返回
@app.exception_handler(BizError)
async def biz_err_handler(_, exc: BizError):
    return JSONResponse(status_code=200, content={"code": 500, "message": str(exc), "data": None})

# 数据库不可用 专门提示库连不上这类问题
@app.exception_handler(DatabaseUnavailable)
async def db_unavailable_handler(_, exc: DatabaseUnavailable):
    return JSONResponse(status_code=200, content={"code": 500, "message": str(exc), "data": None})

# 其它所有未处理异常 打日志，对外只说「服务器内部错误」（避免泄露内部细节）
@app.exception_handler(Exception)
async def any_err_handler(_, exc: Exception):
    logger.exception("服务器内部错误")
    return JSONResponse(status_code=200, content={"code": 500, "message": "服务器内部错误", "data": None})

# --- /api/agents Agent的 CRUD 接口：HTTP 入口很薄，校验/序列化在这里，真正逻辑在 biz 里---
# http://主机:端口/路径
#       └─host─┘ └port┘ └── /api/agents
@app.get("/api/agents")
def api_get_agents():
    agents = biz.list_agents()
    return _ok(GetAgentsResponse(agents=agents))


@app.post("/api/agents")
def api_create_agent(body: CreateAgentRequest):
    aid = biz.create_agent(body)
    return _ok(CreateAgentResponse(agent_id=aid))


@app.delete("/api/agents/{agent_id}")
def api_delete_agent(agent_id: str):
    biz.delete_agent(agent_id)
    return _ok(None)

# PATCH 是 HTTP 方法，表示部分更新：只改你传过来的字段，没传的保持原样。
@app.patch("/api/agents/{agent_id}")
def api_update_agent(agent_id: str, body: UpdateAgentRequest):
    biz.update_agent(agent_id, body)
    return _ok(None)


# --- /api/chat-sessions ---
@app.get("/api/chat-sessions")
def api_list_sessions():
    return _ok(GetChatSessionsResponse(chat_sessions=biz.list_sessions()))

# 前端点击侧边栏的某个Agent时, 会打开http://192.168.119.1:5173/chat/643d52b7-bea0-464c-9093-cdbc9097bd7f, 
# 前端会请求后端触发 1. @app.get("/api/chat-sessions/{sid}")拿取会话信息
# 2. @app.get("/api/chat-messages/session/{session_id}")→ 拉这个会话的历史消息
# 3. @app.post("/api/chat-messages")→ 发新消息
@app.get("/api/chat-sessions/{sid}")
def api_get_session(sid: str):
    return _ok(GetChatSessionResponse(chat_session=biz.get_session(sid)))


@app.get("/api/chat-sessions/agent/{agent_id}")
def api_sessions_by_agent(agent_id: str):
    return _ok(GetChatSessionsResponse(chat_sessions=biz.list_sessions_by_agent(agent_id)))


@app.post("/api/chat-sessions")
def api_create_session(body: CreateChatSessionRequest):
    sid = biz.create_session(body)
    return _ok(CreateChatSessionResponse(chat_session_id=sid))


@app.delete("/api/chat-sessions/{sid}")
def api_delete_session(sid: str):
    biz.delete_session(sid)
    return _ok(None)


@app.patch("/api/chat-sessions/{sid}")
def api_update_session(sid: str, body: UpdateChatSessionRequest):
    biz.update_session(sid, body)
    return _ok(None)


# --- /api/chat-messages ---
@app.get("/api/chat-messages/session/{session_id}")
def api_messages(session_id: str):
    return _ok(GetChatMessagesResponse(chat_messages=biz.list_messages_by_session(session_id)))


@app.post("/api/chat-messages")
def api_create_message(body: CreateChatMessageRequest):
    mid = biz.create_chat_message(body)
    return _ok(CreateChatMessageResponse(chat_message_id=mid))


@app.delete("/api/chat-messages/{mid}")
def api_delete_message(mid: str):
    biz.delete_message(mid)
    return _ok(None)


@app.patch("/api/chat-messages/{mid}")
def api_update_message(mid: str, body: UpdateChatMessageRequest):
    biz.update_message(mid, body)
    return _ok(None)


# --- /api/knowledge-bases ---
@app.get("/api/knowledge-bases")
def api_kbs():
    return _ok(GetKnowledgeBasesResponse(knowledge_bases=biz.list_kbs()))


@app.post("/api/knowledge-bases")
def api_create_kb(body: CreateKnowledgeBaseRequest):
    kid = biz.create_kb(body)
    return _ok(CreateKnowledgeBaseResponse(knowledge_base_id=kid))


@app.delete("/api/knowledge-bases/{kid}")
def api_delete_kb(kid: str):
    biz.delete_kb(kid)
    return _ok(None)


@app.patch("/api/knowledge-bases/{kid}")
def api_update_kb(kid: str, body: UpdateKnowledgeBaseRequest):
    biz.update_kb(kid, body)
    return _ok(None)


# --- /api/documents ---
@app.get("/api/documents")
def api_docs_all():
    return _ok(GetDocumentsResponse(documents=biz.list_documents()))


@app.get("/api/documents/kb/{kb_id}")
def api_docs_kb(kb_id: str):
    return _ok(GetDocumentsResponse(documents=biz.list_documents_by_kb(kb_id)))


@app.post("/api/documents/upload")
async def api_upload(kb_id: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    did = biz.upload_document(kb_id, file.filename, data)
    return _ok(CreateDocumentResponse(document_id=did))


@app.delete("/api/documents/{did}")
def api_delete_doc(did: str):
    biz.delete_document(did)
    return _ok(None)


# --- /api/tools ---
@app.get("/api/tools")
def api_tools():
    tools = biz.list_optional_tools()
    return _ok_raw([t.model_dump(mode="json", by_alias=True) for t in tools])


# --- SSE（与前端 EventSource 路径一致）---
@app.get("/sse/connect/{session_id}")
async def sse_connect(session_id: str):
    q = sse_bus.register_session(session_id)

    async def gen():
        try:
            yield b"event: init\ndata: connected\n\n"
            while True:
                payload = await q.get()
                line = f"event: message\ndata: {payload}\n\n".encode("utf-8")
                yield line
        finally:
            sse_bus.unregister_if_current(session_id, q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _mount_built_ui(app: FastAPI) -> None:
    """若已执行 `ui` 目录下 `npm run build`，则同端口提供前端 SPA。"""
    if not _UI_DIST.is_dir():
        logger.info("未找到 %s，仅提供 API（前端请用: cd ui && npm run dev）", _UI_DIST)
        return
    assets_dir = _UI_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="ui_assets")

    @app.get("/", include_in_schema=False)
    async def _ui_index():
        return FileResponse(_UI_DIST / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def _ui_spa(path: str):
        if path.startswith("api") or path.startswith("sse"):
            raise HTTPException(status_code=404)
        raw = (_UI_DIST / path).resolve()
        try:
            raw.relative_to(_UI_DIST.resolve())
        except ValueError:
            raise HTTPException(status_code=404) from None
        if raw.is_file():
            return FileResponse(raw)
        return FileResponse(_UI_DIST / "index.html")


_mount_built_ui(app)


def run() -> None:
    s = get_settings()
    uvicorn.run(
        "jchatmind_app.main:app",
        host=s.host,
        port=s.port,
        reload=False,
    )


if __name__ == "__main__":
    run()

"""
1. 为什么用 lifespan？
连接池、业务服务、SSE 事件循环都是进程级共享资源，应在「开始接请求前」建好，在「进程退出时」关掉。
lifespan 把 startup / shutdown 写在同一个上下文里（yield 前后），比旧的 on_event("startup") / on_event("shutdown") 更清晰，也是 FastAPI 现在推荐的写法。若放到每个请求里初始化，会重复建池、竞态多、关不干净。

2. 加中间件方式
方式一: 类中间件：挂现成组件
app.add_middleware(
    CORSMiddleware, # 处理跨域：给响应加 Access-Control-* 头，并应答浏览器的 OPTIONS 预检
    allow_origins=_origins, # 允许的源域名列表，* 表示允许所有域名
    allow_credentials=True, # 是否允许携带 cookie
    allow_methods=["*"],
    allow_headers=["*"], # 允许的请求头列表 
)
传入一个中间件类（通常继承 Starlette 的 BaseHTTPMiddleware 或纯 ASGI 中间件）
用关键字参数配置行为
适合：CORS、GZip、TrustedHost 等可复用、可配置的官方/第三方中间件

方式二: 装饰器：自己写逻辑
@app.middleware("http")
async def middleware(request, call_next):
    print("中间件1开始")
    response = await call_next(request)
    print("中间件1结束")
    return response
直接在 main 里写一个函数
request → 做事前逻辑 → await call_next(request) 交给后面（路由/其它中间件）→ 拿到 response 再处理后返回
适合：打日志、计时、改请求/响应头、简单鉴权等项目内自定义逻辑
---
一句话总结：
装饰器：我自己写「请求前后干什么」
add_middleware：把别人写好的中间件类挂上，并传配置
你们项目里 CORS 用第二种；FastAPI/main.py 里打印「中间件1开始/结束」用第一种，本质都是包在路由外面的一层。
"""