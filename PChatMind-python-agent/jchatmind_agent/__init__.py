"""JChatMind Agent 核心逻辑（Python 移植, hink–Execute 循环）。"""
# 对外导出核心 API，告诉你这个包对使用者暴露了哪些能力（入口导航作用）。

from jchatmind_agent.chat_registry import ChatClientRegistry, ModelEndpoint, default_registry_from_env
from jchatmind_agent.factory import (
    AgentChatOptions,
    AgentConfig,
    JChatMindFactory,
    build_factory_with_defaults,
    default_messages_from_history,
)
from jchatmind_agent.jchat_mind import JChatMind, KnowledgeBaseInfo
from jchatmind_agent.rag_service import McpRagService

__all__ = [
    "AgentChatOptions",
    "AgentConfig",
    "ChatClientRegistry",
    "JChatMind",
    "JChatMindFactory",
    "KnowledgeBaseInfo",
    "McpRagService",
    "ModelEndpoint",
    "build_factory_with_defaults",
    "default_messages_from_history",
    "default_registry_from_env",
]
# 当前项目**不会解析图片**。上传非 `.md` 只会落盘并打日志「待新增处理的文件类型」；Markdown 里的 `![](...)` 也会当普通文本切分，图片本身不会进向量库。
# 常见有两种场景，做法不同：
# ### 1. 单独上传图片（png/jpg/webp）
# 在 `upload_document` 里对图片类型加分支，典型链路：
# ```
# 图片 → OCR / Vision 模型 → 抽出文字描述 → 切 chunk → bge-m3 embedding → pgvector
# ```
# 可选实现：
# - **OCR**（偏文字图、扫描件）：PaddleOCR / Tesseract，结果当纯文本入库
# - **Vision LLM**（偏理解图意）：调带视觉的模型（如 qwen-vl），让模型输出「图片描述 + 关键文字」，再入库

# ### 2. Markdown / PDF 里嵌了图
# - **Markdown**：解析 `![](path|url)`，把本地图或下载后的图走上面同一套 OCR/Vision，把生成的文字拼进该章节的 `content`，再 embedding
# - **PDF**：`Docling` Layout-Aware 解析 → `RecursiveCharacterTextSplitter` 切分 → `bge-m3` embedding → pgvector（见 `biz._process_pdf_kb`）
# - **Markdown**：仍按标题章节切分（`parse_markdown_sections`），不变
# ### 和本仓库的衔接点
# 改动入口主要在：
# ```478:481:jchatmind_app/biz.py
#     if ft in ("md", "markdown"):
#         _process_markdown_kb(kb_id, doc_id, rel)
#     else:
#         logger.warning("待新增处理的文件类型: %s", ft)
# ```
# 例如增加：

# ```python
# elif ft in ("png", "jpg", "jpeg", "webp"):
#     _process_image_kb(kb_id, doc_id, rel)
# ```

# `_process_image_kb` 负责：读图 → 转文字 → `rag.embed(text)` → `R.chunk_insert(...)`。
# 检索侧可以继续用现有文本 RAG（`bge-m3`），不必立刻上多模态 embedding；本质是**先把图变成可检索的文本**。


# 实际是按 Markdown 标题（#～######）切成章节：一个标题 + 到下一标题前的正文 = 一个 chunk。另外，向量是对章节标题 title 做 embedding，库里存的是正文 content。
# LangChain 的 RecursiveCharacterTextSplitter 采用的是一种基于层级分隔符的递归分块


""" 
可插拔的LLM Agent执行框架
模型可换 — ChatClientRegistry 按 model 名解析端点，DeepSeek / 智谱 / 通义都能走同一套 chat_completion
工具可配 — ToolSpec + allowed_tools，工厂按配置筛出运行时工具（KnowledgeTool、数据库查询等）
知识库可挂 — allowed_kbs + resolve_knowledge_bases，RAG 作为工具接入，不绑死 Agent 逻辑
历史/提示可注入 — system_prompt、近期消息由工厂拼进 JChatMind.messages
业务回调可注入 — 落库、SSE 推送通过 save_message / sse_send 传入，Agent 内核不依赖 FastAPI/DB 细节 

没有用 LangChain Memory、Mem0、Zep 这类独立 memory 框架, 基于滑动窗口控制上下文长度, 通过pgsql持久化
"""