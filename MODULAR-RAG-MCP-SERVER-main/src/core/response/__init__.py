"""
Response Module.

This package contains response building components:
- Response builder
- Citation generator
- Multimodal assembler
"""

from src.core.response.citation_generator import Citation, CitationGenerator
from src.core.response.multimodal_assembler import (
    ImageContent,
    ImageReference,
    MultimodalAssembler,
)
from src.core.response.response_builder import MCPToolResponse, ResponseBuilder

__all__ = [
    "Citation",
    "CitationGenerator",
    "ImageContent",
    "ImageReference",
    "MCPToolResponse",
    "MultimodalAssembler",
    "ResponseBuilder",
]
"""
Query 链路的最后一环：把检索结果（RetrievalResult）整理成 MCP Tool 可返回的结构化回答，而不是做检索本身。
HybridSearch 检索结果
    → ResponseBuilder
        → CitationGenerator（引用）
        → MultimodalAssembler（图片，可选）
    → query_knowledge_hub 返回给 Agent

检索只给出“相关片段”；Agent/用户还需要：
    可读答案（带引用标记的 Markdown）
    可溯源（结构化 citations，方便核对出处）
    多模态（相关图能一并返回）
    空结果/异常 的统一包装
所以它是 “检索结果 → MCP 响应”的格式化层。你正在看的 response_builder.py 就是这个文件夹的入口。
"""

"""
详细流程（概念级，不用抠代码）
一次查询到 Response 大致是：

1. 拿到检索结果
RetrievalResult 列表：chunk 文本、分数、来源路径、页码、metadata（可能含图片引用）。

2. 空结果单独处理
没有命中 → 返回友好提示（换关键词、检查是否已入库等），避免 Agent 瞎编。

3. 生成引用（Citation）
每个结果变成一条结构化引用：序号 [1]、来源文件、页码、相关度、短摘要。
目的：可溯源、可对账，不只是「一段话」。

4. 拼 Markdown 正文
例如：标题 + 查询复述 + 若干条结果摘要，正文里带 [1]、[2]。
通常只展示 top-N（如 5 条），避免把整坨检索结果塞进上下文。

5. 可选：挂图片
若 chunk 元数据里有图片引用 → 读本地图 → base64 → MCP ImageContent。
图丢了不拖垮文本（降级）。

6. 封装成 MCP 响应

给人读的：Markdown 文本
给机器用的：citations / metadata（JSON）
可选：图片块
Agent 拿到后：用证据回答，并标明出处。

面试可能怎么问（按重要性）
A. 定位类（常考，答清即可）
Q1：RAG 里「检索」和「生成」分别谁负责？你们项目呢？

经典 RAG：Retriever 找文档 → Generator（LLM）基于上下文答题。
本项目对外是 MCP Tool：侧重检索 + 结构化引用；生成常由 Host Agent 完成。Response 层是「把检索结果变成可消费上下文」，不是 Hybrid Search 本身。
Q2：为什么一定要 Citation，直接返回 chunk 文本不行吗？

幻觉可控：强迫「有出处才敢说」。
产品可信：用户能点回 PDF/页码。
评测友好：Faithfulness / 人工抽查都靠对齐来源。
Agent 友好：结构化引用比纯长文本更好用。
Q3：Response 层算不算 RAG 核心？你会怎么写简历？

不算算法核心；算工程完整性。
简历一笔带过即可：「检索结果带引用与多模态组装，对接 MCP」。
篇幅留给 Hybrid Search、RRF、可插拔、评估

B. 设计权衡类（中级）
Q4：返回「原始 chunk」还是「已经写好的答案」？

策略	优点	缺点
只返回证据（本项目偏这种）  透明、Host 可再推理、少一次 LLM     体验依赖上游 Agent
Server 内直接 LLM 生成答案  开箱即用    成本高、黑盒、难复用
可答：MCP 知识库更适合当 context provider，生成留给 Host，职责清晰。

Q5：top_k、展示条数、snippet 长度怎么定？

太少：召回不够，答不全。
太多：挤占上下文、噪声大、费用高。
常见：检索粗排 10–20，精排/展示 3–5，snippet 截断。
面试加分：提 context window 与「lost in the middle」。
Q6：空结果怎么处理？
明确「未找到」+ 建议，而不是硬生成。这和「拒绝回答 / abstain」同一类产品设计。
"""