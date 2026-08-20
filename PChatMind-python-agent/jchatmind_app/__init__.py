"""JChatMind 全量 Python 后端（FastAPI），API 与 Java Spring Boot 版对齐。"""

"""
FastAPI 是一个用 Python 写 Web API 的框架，适合做前后端分离的后端服务。

在这个项目里，jchatmind_app/main.py 就是用 FastAPI 搭的：定义 /api/agents、/api/chat-messages、/sse/connect/... 等路由，接收前端请求并返回 JSON 或 SSE 流。

常见特点：

基于类型注解，自动校验请求/响应（常配合 Pydantic）
自带交互式文档（Swagger：一般是 /docs）
支持异步，适合高并发 IO（调模型、查库、推 SSE）
底层常用 Uvicorn 作为 ASGI 服务器跑起来
一句话：FastAPI = 用 Python 快速写 HTTP/SSE 接口的后端框架；本项目用它把 Agent 能力暴露给前端。
"""

"""
文件	职责
main.py FastAPI 入口，定义所有 HTTP/SSE 路由
api_schemas.py 请求/响应的 Pydantic 模型（前后端契约）
biz.py 业务逻辑：CRUD + 组装 Agent 工厂 + 触发后台运行
repos.py 数据库访问（SQL CRUD）
pool.py PostgreSQL 连接池
config.py 环境变量配置（DB、API Key、RAG 等）
sse_bus.py SSE 推送通道（Agent 实时状态/内容）
document_storage.py 文档文件本地存储
email_util.py 发邮件工具的后端实现
markdown_sections.py Markdown 文档切片（上传知识库时用）
"""