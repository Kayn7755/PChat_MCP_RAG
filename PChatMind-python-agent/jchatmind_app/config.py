"""
应用的统一配置中心：用 Pydantic Settings 集中管理运行参数，并从环境变量 / .env 读取覆盖值。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# 定义数据库、文档路径、嵌入模型、RAG、LLM（DeepSeek / 智谱 / 通义）、邮件、CORS、服务监听地址等字段及默认值
class Settings(BaseSettings):
    # 环境变量前缀为 JCHATMIND_ ，读取 .env 文件，忽略未知环境变量
    model_config = SettingsConfigDict(env_prefix="JCHATMIND_", env_file=".env", extra="ignore")
    # mysql不支持向量检索
    database_url: str = "postgresql://postgres:123456@localhost:5432/jchatmind"
    document_storage_base_path: str = "./data/documents"
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "bge-m3"
    #: langchain | ollama | mcp（mcp=独立 Modular RAG MCP Server，Agent 当 Client）
    rag_provider: str = "mcp"
    #: Modular RAG MCP Server 仓库根目录（含 src/mcp_server）
    mcp_rag_server_cwd: str = ""
    #: 启动 MCP 的 Python；空则用当前解释器
    mcp_rag_python: str = ""
    mcp_rag_module: str = "src.mcp_server.server"
    mcp_rag_timeout_seconds: float = 90.0
    mcp_default_collection: str = "default"
    #: JSON：{"kb_uuid":"collection_name"}；优先于 default_collection
    mcp_kb_collection_map: str = ""
    #: true 时用 kb_id 作为 collection 名；默认 false
    mcp_use_kb_id_as_collection: bool = False
    #: 传给 MCP 子进程的额外环境变量 JSON
    mcp_rag_server_env: str = ""
    #: true 时 MCP 检索 + 本地 LangChain embed（兼容旧入库路径）
    mcp_keep_local_embed: bool = False
    #: 嵌入后端：openai=外界 OpenAI 兼容 API；ollama=本地 Ollama
    embed_backend: str = "openai"
    #: 外界嵌入（空则回退到通义 qwen_* 配置）
    embed_api_key: str = ""
    embed_base_url: str = ""
    embed_model: str = "text-embedding-v3"
    #: 须与 chunk_bge_m3.embedding VECTOR(1024) 一致；换维需改表并重建索引
    embed_dimensions: int = 1024
    #: PDF 递归字符切分（字符数，约对应通用文本 400–512 token）
    pdf_chunk_size: int = 1500
    pdf_chunk_overlap: int = 200

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = "glm-4.6"

    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3-max"

    mail_host: str = "smtp.qq.com"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: str = ""

    cors_origins: str = "*"
    host: str = "0.0.0.0"
    port: int = 8080

    #: 为 true 时，PostgreSQL 连不上也启动进程（仅便于联调；/api 里依赖库的接口会报错）
    allow_start_without_db: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
