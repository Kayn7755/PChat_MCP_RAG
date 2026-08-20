"""
MCP Server 的启动入口：用官方 SDK、走 stdio, 只能本机调用
把 Cursor/Claude 等 Client 拉起的子进程变成可调工具的服务。
本身不算检索，检索在 query_knowledge_hub 等 tool 里。

    配置 MCP Server 基本信息；
    修复日志输出问题（避免破坏 MCP 的 JSON-RPC 通信）；
    预加载重量级依赖（避免多线程 import 死锁）；
    创建 MCP Server；
    通过 stdio（标准输入输出）协议运行服务器。
MCP stdio 模式通信:
                Client
                |
                stdin/stdout
                |
                MCP Server

stdout：专门传输 JSON-RPC 消息
stderr：输出日志


Cursor 配置 command → python -m src.mcp_server.server
                              │
                              ▼
                     server.py（本文件）
                       · 日志改 stderr
                       · 预加载重依赖
                       · create_mcp_server（注册 tools）
                       · stdio 读写 JSON-RPC
                              │
                              ▼
              tools/list、tools/call → HybridSearch 等
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from src.mcp_server.protocol_handler import create_mcp_server
from src.observability.logger import get_logger

if TYPE_CHECKING:
    pass


SERVER_NAME = "modular-rag-mcp-server"
SERVER_VERSION = "0.1.0"

# 把所有 Python 日志重定向到 stderr（标准错误流）
def _redirect_all_loggers_to_stderr() -> None:
    """Redirect all root logger handlers to stderr.

    MCP stdio transport reserves stdout for JSON-RPC messages.
    Any logging to stdout corrupts the protocol stream.
    """
    import logging as _logging

    root = _logging.getLogger()
    stderr_handler = _logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(
        _logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    # Replace any existing stream handlers that might point to stdout
    for handler in root.handlers[:]:
        if isinstance(handler, _logging.StreamHandler) and not isinstance(
            handler, _logging.FileHandler
        ):
            root.removeHandler(handler)
    root.addHandler(stderr_handler)


def _preload_heavy_imports() -> None:
    """Eagerly import heavy third-party modules in the **main thread**.

    MCP SDK uses anyio + background threads for stdin/stdout I/O.
    When a tool handler runs ``asyncio.to_thread(fn)``, *fn* executes in
    a new worker thread.  If it tries to ``import chromadb`` (which
    transitively pulls in onnxruntime, numpy, sqlite3 C extensions …),
    that import can deadlock with the stdin-reader thread because both
    compete for Python's global *import lock*.

    Pre-importing here – before anyio spins up its I/O threads – avoids
    the deadlock entirely: subsequent ``import`` statements in worker
    threads simply hit ``sys.modules`` and return immediately.
    """
    # chromadb is the heaviest culprit (onnxruntime, numpy, …)
    try:
        import chromadb  # noqa: F401
        import chromadb.config  # noqa: F401
    except ImportError:
        pass  # optional at install time

    # Internal modules that tools lazy-import inside asyncio.to_thread
    try:
        import src.core.query_engine.query_processor  # noqa: F401
        import src.core.query_engine.hybrid_search  # noqa: F401
        import src.core.query_engine.dense_retriever  # noqa: F401
        import src.core.query_engine.sparse_retriever  # noqa: F401
        import src.core.query_engine.reranker  # noqa: F401
        import src.ingestion.storage.bm25_indexer  # noqa: F401
        import src.libs.embedding.embedding_factory  # noqa: F401
        import src.libs.vector_store.vector_store_factory  # noqa: F401
    except ImportError:
        pass

# 异步运行 MCP server 通过 stdio 协议; 核心启动函数
async def run_stdio_server_async() -> int:
    """Run MCP server over stdio asynchronously.

    Returns:
        Exit code.
    """
    # Import here to avoid import errors if mcp not installed
    import mcp.server.stdio

    # Ensure ALL logging goes to stderr (stdout is reserved for JSON-RPC)
    _redirect_all_loggers_to_stderr()

    # Pre-load heavy deps in main thread to prevent import-lock deadlocks
    # when tool handlers later call asyncio.to_thread().
    _preload_heavy_imports()

    logger = get_logger(log_level="INFO")
    logger.info("Starting MCP server (stdio transport) with official SDK.")

    # Create server with protocol handler 创建 MCP Server 实例
    server = create_mcp_server(SERVER_NAME, SERVER_VERSION)

    # Run with stdio transport 通过 stdio 协议运行服务器
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        ) # 启动stdio通信

    logger.info("MCP server shutting down.")
    return 0


def run_stdio_server() -> int:
    """Run MCP server over stdio (synchronous wrapper).

    Returns:
        Exit code.
    """
    return asyncio.run(run_stdio_server_async())


def main() -> int:
    """Entry point for stdio MCP server."""
    return run_stdio_server()


if __name__ == "__main__":
    sys.exit(main())

"""
stdio 是 standard input/output（标准输入/标准输出） 的缩写。
所以stdio模式只能本地程序调用本地程序
stdio 主要用于本地客户端和工具服务之间的低延迟通信。它通过 stdin/stdout 传递 JSON-RPC 消息，因此需要严格隔离日志输出到 stderr，避免破坏协议流。


MCP 中的 stdio 是什么？
MCP Server 不监听 TCP 端口，而是通过 进程管道通信。

"""