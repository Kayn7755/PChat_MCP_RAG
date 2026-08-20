"""
RAG 的检索服务层：把用户问题变成向量，再从知识库里找出最相关的文本片段。

另提供 ``McpRagService``：Agent 作为 MCP Client，调用独立 Modular RAG MCP Server
（hybrid + rerank），不再走本地 pgvector 单路检索。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

import httpx

logger = logging.getLogger(__name__)


class RagService(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def similarity_search(self, kb_id: str, query: str, limit: int = 3) -> list[str]: ...


def _to_pg_vector(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


class OllamaEmbeddingRagService:
    """
    Ollama /api/embeddings（bge-m3）+ PostgreSQL pgvector 检索。
    需已安装 pgvector 扩展及 chunk_bge_m3 表

    自己用 httpx 调 Ollama /api/embeddings 的接口, 生成向量 只有本地 Ollama
    """

    def __init__(
        self,
        *,
        ollama_base: str = "http://localhost:11434",
        embed_model: str = "bge-m3",
        pg_dsn: str | None = None,
    ) -> None:
        self._ollama_base = ollama_base.rstrip("/")
        self._embed_model = embed_model
        self._pg_dsn = pg_dsn

    def embed(self, text: str) -> list[float]:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{self._ollama_base}/api/embeddings",
                json={"model": self._embed_model, "prompt": text},
            )
            r.raise_for_status()
            data = r.json()
        emb = data.get("embedding")
        if not emb:
            raise RuntimeError("Ollama embedding 响应缺少 embedding 字段")
        return list(emb)

    def similarity_search(self, kb_id: str, query: str, limit: int = 3) -> list[str]:
        if not self._pg_dsn:
            logger.warning("未配置 PostgreSQL DSN，similarity_search 返回空列表")
            return []
        vec_lit = _to_pg_vector(self.embed(query))
        sql = """
            SELECT content
            FROM chunk_bge_m3
            WHERE kb_id = CAST(%s AS uuid)
            ORDER BY embedding <-> %s::vector
            LIMIT %s
        """
        import psycopg2

        with psycopg2.connect(self._pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (kb_id, vec_lit, limit))
                rows = cur.fetchall()
        return [r[0] for r in rows if r and r[0]]


class InMemoryRagService:
    """测试用：不做真实向量检索。"""

    def embed(self, text: str) -> list[float]:
        return [0.0] * 8

    def similarity_search(self, kb_id: str, query: str, limit: int = 3) -> list[str]:
        return [f"[mock rag kb={kb_id}] 无检索结果，query={query!r}"]


class LangChainRagService:
    """
    使用 LangChain Embeddings 生成向量；检索仍复用当前 pgvector SQL。
    默认走外界 OpenAI 兼容嵌入（通义/智谱/OpenAI 等），也可切回本地 Ollama。

    用 LangChain 的 Embeddings 封装 Ollama 或 OpenAI 兼容 API（由 embed_backend 决定）
    """

    def __init__(
        self,
        *,
        embeddings: Any,
        pg_dsn: str | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._pg_dsn = pg_dsn

    @classmethod
    def from_settings(cls, settings: Any) -> LangChainRagService:
        backend = (getattr(settings, "embed_backend", None) or "openai").strip().lower()
        if backend in ("ollama", "local"):
            from langchain_community.embeddings import OllamaEmbeddings

            print("embed采用ollama")
            emb = OllamaEmbeddings(
                base_url=settings.ollama_base_url.rstrip("/"),
                model=settings.ollama_embed_model,
            )
            logger.info(
                "LangChain embeddings: ollama model=%s base=%s",
                settings.ollama_embed_model,
                settings.ollama_base_url,
            )
        else:
            from langchain_openai import OpenAIEmbeddings

            print("embed采用openai")
            api_key = (settings.embed_api_key or settings.qwen_api_key or "").strip()
            base_url = (settings.embed_base_url or settings.qwen_base_url or "").rstrip("/")
            if not api_key:
                raise RuntimeError(
                    "外界嵌入未配置 API Key：请设置 JCHATMIND_EMBED_API_KEY 或 JCHATMIND_QWEN_API_KEY"
                )
            if not base_url:
                raise RuntimeError(
                    "外界嵌入未配置 base_url：请设置 JCHATMIND_EMBED_BASE_URL 或 JCHATMIND_QWEN_BASE_URL"
                )
            dims = int(getattr(settings, "embed_dimensions", 0) or 0)
            kwargs: dict[str, Any] = {
                "model": settings.embed_model,
                "api_key": api_key,
                "base_url": base_url,
            }
            if dims > 0:
                kwargs["dimensions"] = dims
            emb = OpenAIEmbeddings(**kwargs)
            logger.info(
                "LangChain embeddings: openai-compatible model=%s base=%s dims=%s",
                settings.embed_model,
                base_url,
                dims or "default",
            )
        return cls(embeddings=emb, pg_dsn=settings.database_url)

    def embed(self, text: str) -> list[float]:
        emb = self._embeddings.embed_query(text)
        if not emb:
            raise RuntimeError("LangChain embedding 结果为空")
        return [float(x) for x in emb]

    def similarity_search(self, kb_id: str, query: str, limit: int = 3) -> list[str]:
        if not self._pg_dsn:
            logger.warning("未配置 PostgreSQL DSN，similarity_search 返回空列表")
            return []
        vec_lit = _to_pg_vector(self.embed(query))
        sql = """
            SELECT content
            FROM chunk_bge_m3
            WHERE kb_id = CAST(%s AS uuid)
            ORDER BY embedding <-> %s::vector
            LIMIT %s
        """
        import psycopg2

        with psycopg2.connect(self._pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (kb_id, vec_lit, limit))
                rows = cur.fetchall()
        return [r[0] for r in rows if r and r[0]]


class McpRagService:
    """
    Agent 作为 MCP Client：检索走独立 Modular RAG MCP Server。

    - ``similarity_search(kb_id, query)`` → ``query_knowledge_hub``
    - ``kb_id`` 默认映射为 MCP ``collection``（可用 map / 默认 collection 覆盖）
    - ``embed``：检索不需要；若仍被入库路径调用，可注入 embeddings 或明确报错

    典型配置（Settings / 环境变量）::

        JCHATMIND_RAG_PROVIDER=mcp
        JCHATMIND_MCP_RAG_SERVER_CWD=../MODULAR-RAG-MCP-SERVER-main
        JCHATMIND_MCP_DEFAULT_COLLECTION=default
    """

    def __init__(
        self,
        *,
        client: Any,
        default_collection: str = "default",
        kb_collection_map: Mapping[str, str] | None = None,
        use_kb_id_as_collection: bool = False,
        embeddings: Any | None = None,
        resolve_collection: Callable[[str], str] | None = None,
    ) -> None:
        self._client = client
        self._default_collection = (default_collection or "default").strip() or "default"
        self._kb_collection_map = {str(k): str(v) for k, v in (kb_collection_map or {}).items()}
        self._use_kb_id_as_collection = use_kb_id_as_collection
        self._embeddings = embeddings
        self._resolve_collection = resolve_collection

    @classmethod
    def from_settings(cls, settings: Any) -> McpRagService:
        import sys

        from jchatmind_agent.mcp_rag_client import McpServerLaunchConfig, ModularRagMcpClient

        cwd = (getattr(settings, "mcp_rag_server_cwd", None) or "").strip()
        if not cwd:
            # 默认：PChat_MCP_RAG/MODULAR-RAG-MCP-SERVER-main
            here = Path(__file__).resolve()
            # .../PChat_MCP_RAG/PChatMind-python-agent/jchatmind_agent/rag_service.py
            guessed = here.parents[2] / "MODULAR-RAG-MCP-SERVER-main"
            cwd = str(guessed)

        py = (getattr(settings, "mcp_rag_python", None) or "").strip() or None
        module = (getattr(settings, "mcp_rag_module", None) or "src.mcp_server.server").strip()
        timeout = float(getattr(settings, "mcp_rag_timeout_seconds", 90) or 90)
        default_collection = (
            getattr(settings, "mcp_default_collection", None) or "default"
        ).strip() or "default"
        # 默认 False：未配置映射时用 mcp_default_collection，避免把 UUID 当成空 collection
        use_kb_id = bool(getattr(settings, "mcp_use_kb_id_as_collection", False))

        raw_map = getattr(settings, "mcp_kb_collection_map", None) or ""
        kb_map: dict[str, str] = {}
        if isinstance(raw_map, dict):
            kb_map = {str(k): str(v) for k, v in raw_map.items()}
        elif isinstance(raw_map, str) and raw_map.strip():
            try:
                parsed = json.loads(raw_map)
                if isinstance(parsed, dict):
                    kb_map = {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    "JCHATMIND_MCP_KB_COLLECTION_MAP 必须是 JSON 对象，例如 "
                    '{"uuid":"my_collection"}'
                ) from e

        env_extra: dict[str, str] = {}
        raw_env = getattr(settings, "mcp_rag_server_env", None) or ""
        if isinstance(raw_env, dict):
            env_extra = {str(k): str(v) for k, v in raw_env.items()}
        elif isinstance(raw_env, str) and raw_env.strip():
            try:
                parsed_env = json.loads(raw_env)
                if isinstance(parsed_env, dict):
                    env_extra = {str(k): str(v) for k, v in parsed_env.items()}
            except json.JSONDecodeError as e:
                raise RuntimeError("JCHATMIND_MCP_RAG_SERVER_ENV 必须是 JSON 对象") from e

        launch = McpServerLaunchConfig(
            cwd=cwd,
            python_executable=py or sys.executable,
            module=module,
            env=env_extra,
            timeout_seconds=timeout,
        )
        client = ModularRagMcpClient(launch)
        logger.info(
            "RAG provider: mcp cwd=%s module=%s default_collection=%s",
            cwd,
            module,
            default_collection,
        )

        embeddings = None
        if bool(getattr(settings, "mcp_keep_local_embed", False)):
            try:
                embeddings = LangChainRagService.from_settings(settings)._embeddings
            except Exception as e:
                logger.warning("mcp_keep_local_embed 开启但 embeddings 初始化失败: %s", e)

        return cls(
            client=client,
            default_collection=default_collection,
            kb_collection_map=kb_map,
            use_kb_id_as_collection=use_kb_id,
            embeddings=embeddings,
        )

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def resolve_collection(self, kb_id: str) -> str:
        kid = str(kb_id or "").strip()
        if self._resolve_collection is not None:
            return self._resolve_collection(kid)
        if kid and kid in self._kb_collection_map:
            return self._kb_collection_map[kid]
        if kid and self._use_kb_id_as_collection:
            return kid
        return self._default_collection

    def embed(self, text: str) -> list[float]:
        if self._embeddings is not None:
            emb = self._embeddings.embed_query(text)
            if not emb:
                raise RuntimeError("MCP RAG 附带 embeddings 结果为空")
            return [float(x) for x in emb]
        raise RuntimeError(
            "当前为 MCP RAG：检索由 Modular MCP Server 完成，本地 embed 未启用。"
            "文档入库请走 Modular Dashboard / ingestion，"
            "或设置 JCHATMIND_MCP_KEEP_LOCAL_EMBED=true 以保留本地嵌入。"
        )

    def similarity_search(self, kb_id: str, query: str, limit: int = 3) -> list[str]:
        collection = self.resolve_collection(kb_id)
        top_k = max(1, int(limit or 3))
        try:
            text = self._client.query_knowledge_hub(
                str(query or ""),
                top_k=top_k,
                collection=collection,
            )
        except Exception:
            logger.exception(
                "MCP query_knowledge_hub 失败 collection=%s query=%r",
                collection,
                query,
            )
            raise
        if not text:
            return []
        # KnowledgeTool 用 "\n".join(chunks)；整段带引用的 MCP 文本作为单元素即可
        return [text]
