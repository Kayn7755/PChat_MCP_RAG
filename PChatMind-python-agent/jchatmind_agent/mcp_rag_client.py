"""
独立 Modular RAG MCP Server 的 stdio Client。

Agent 侧通过 JSON-RPC（initialize → tools/call）调用：
  - query_knowledge_hub
  - list_collections（可选）

设计：
  - 持久化子进程，避免每次检索都冷启动 Chroma / embedding
  - 同步 API，供 KnowledgeTool handler 直接调用
  - stdout 只走协议；服务端日志在 stderr（后台吞掉并 debug 记录）
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PROTOCOL_VERSION = "2025-06-18"
QUERY_TOOL = "query_knowledge_hub"
LIST_COLLECTIONS_TOOL = "list_collections"


@dataclass
class McpServerLaunchConfig:
    """如何拉起 Modular RAG MCP Server 子进程。"""

    cwd: str
    #: 解释器；默认当前 Python
    python_executable: str = field(default_factory=lambda: sys.executable)
    #: 模块入口，对应 ``python -m src.mcp_server.server``
    module: str = "src.mcp_server.server"
    #: 额外环境变量（合并进子进程 env）
    env: dict[str, str] = field(default_factory=dict)
    #: 单次 JSON-RPC 等待秒数
    timeout_seconds: float = 90.0
    client_name: str = "jchatmind-agent"
    client_version: str = "0.1.0"


class ModularRagMcpClient:
    """
    持久化 stdio MCP Client。

    用法::

        client = ModularRagMcpClient(McpServerLaunchConfig(cwd=r"...\\MODULAR-RAG-MCP-SERVER-main"))
        text = client.query_knowledge_hub("什么是 RAG", top_k=5, collection="default")
        client.close()
    """

    def __init__(self, config: McpServerLaunchConfig) -> None:
        self._config = config
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._lock = threading.RLock()
        self._initialized = False
        self._stdout_q: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._reader_stop = threading.Event()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._reader_stop.set()
            proc = self._proc
            self._proc = None
            self._initialized = False
            if proc is None:
                return
            try:
                if proc.stdin:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=3)
                except Exception:
                    logger.exception("终止 MCP Server 子进程失败")
            # 唤醒可能阻塞的 wait
            self._stdout_q.put(None)

    def __enter__(self) -> ModularRagMcpClient:
        self.ensure_ready()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def ensure_ready(self) -> None:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None and self._initialized:
                return
            self._restart()

    def _restart(self) -> None:
        self._reader_stop.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        self._initialized = False
        self._reader_stop = threading.Event()
        # 清空旧队列
        while True:
            try:
                self._stdout_q.get_nowait()
            except queue.Empty:
                break

        cwd = str(Path(self._config.cwd).resolve())
        if not Path(cwd).is_dir():
            raise FileNotFoundError(f"MCP Server 工作目录不存在: {cwd}")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env.update({k: str(v) for k, v in self._config.env.items() if v is not None})

        logger.info(
            "启动 Modular RAG MCP Server: python -m %s cwd=%s",
            self._config.module,
            cwd,
        )
        self._proc = subprocess.Popen(
            [self._config.python_executable, "-m", self._config.module],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            env=env,
            bufsize=1,
        )
        self._start_io_threads()
        self._handshake()
        self._initialized = True

    def _start_io_threads(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stdout is not None

        def _stdout_reader() -> None:
            try:
                while not self._reader_stop.is_set():
                    line = proc.stdout.readline()
                    if not line:
                        break
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        data = json.loads(stripped)
                    except json.JSONDecodeError:
                        logger.debug("忽略非 JSON stdout 行: %s", stripped[:200])
                        continue
                    if "id" in data and ("result" in data or "error" in data):
                        self._stdout_q.put(data)
            finally:
                self._stdout_q.put(None)

        def _stderr_reader() -> None:
            if proc.stderr is None:
                return
            try:
                for line in proc.stderr:
                    if self._reader_stop.is_set():
                        break
                    line = line.rstrip()
                    if line:
                        logger.debug("[mcp-server] %s", line)
            except Exception:
                pass

        threading.Thread(target=_stdout_reader, daemon=True, name="mcp-stdout").start()
        threading.Thread(target=_stderr_reader, daemon=True, name="mcp-stderr").start()

    def _handshake(self) -> None:
        init_id = self._alloc_id()
        init_resp = self._request(
            {
                "jsonrpc": "2.0",
                "id": init_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                    "clientInfo": {
                        "name": self._config.client_name,
                        "version": self._config.client_version,
                    },
                    "capabilities": {},
                },
            },
            req_id=init_id,
        )
        if "error" in init_resp:
            raise RuntimeError(f"MCP initialize 失败: {init_resp['error']}")

        self._write(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )
        logger.info("MCP Client 已与 Modular RAG Server 握手完成")

    # ------------------------------------------------------------------
    # tools
    # ------------------------------------------------------------------

    def query_knowledge_hub(
        self,
        query: str,
        *,
        top_k: int = 5,
        collection: str | None = None,
    ) -> str:
        args: dict[str, Any] = {"query": query, "top_k": int(top_k)}
        if collection:
            args["collection"] = collection
        return self.call_tool(QUERY_TOOL, args)

    def list_collections(self, *, include_stats: bool = True) -> str:
        return self.call_tool(
            LIST_COLLECTIONS_TOOL,
            {"include_stats": bool(include_stats)},
        )

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        with self._lock:
            self.ensure_ready()
            req_id = self._alloc_id()
            try:
                resp = self._request(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "method": "tools/call",
                        "params": {
                            "name": name,
                            "arguments": arguments or {},
                        },
                    },
                    req_id=req_id,
                )
            except Exception:
                self._initialized = False
                raise

            if "error" in resp:
                raise RuntimeError(f"MCP tools/call 错误: {resp['error']}")

            result = resp.get("result") or {}
            if result.get("isError"):
                text = _content_to_text(result.get("content"))
                raise RuntimeError(text or f"MCP 工具返回 isError: {name}")
            return _content_to_text(result.get("content"))

    # ------------------------------------------------------------------
    # JSON-RPC wire
    # ------------------------------------------------------------------

    def _alloc_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid

    def _write(self, message: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise RuntimeError("MCP Server 未启动")
        proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    def _request(self, message: dict[str, Any], *, req_id: int) -> dict[str, Any]:
        proc = self._proc
        if proc is None:
            raise RuntimeError("MCP Server 未启动")

        self._write(message)
        deadline = time.time() + float(self._config.timeout_seconds)
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"MCP Server 进程已退出 code={proc.returncode}")
            remaining = max(0.05, deadline - time.time())
            try:
                item = self._stdout_q.get(timeout=min(1.0, remaining))
            except queue.Empty:
                continue
            if item is None:
                raise RuntimeError("MCP Server stdout 已关闭")
            if item.get("id") == req_id:
                return item
            # 非本请求的响应：放回队列尾部（极少见；防止丢消息）
            self._stdout_q.put(item)
            time.sleep(0.01)

        raise TimeoutError(
            f"等待 MCP 响应超时 id={req_id} timeout={self._config.timeout_seconds}s"
        )


def _content_to_text(content: Any) -> str:
    if not content:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(str(block.get("text") or ""))
            elif btype == "image":
                mime = block.get("mimeType") or "image"
                parts.append(f"[image:{mime}]")
            else:
                text = block.get("text")
                if text:
                    parts.append(str(text))
    return "\n".join(p for p in parts if p).strip()
