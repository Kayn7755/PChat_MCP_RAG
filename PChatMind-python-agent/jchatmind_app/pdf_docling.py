"""PDF → 文本：Docling Layout-Aware 解析。
已接上 PDF 流水线：Docling 解析 → 递归字符切分 → 对 chunk 正文做 embedding
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _converter():
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def pdf_to_markdown(path: Path | str) -> str:
    """用 Docling 将 PDF 转为 Markdown 文本（保留标题/表格等版式结构）。"""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"PDF 不存在: {p}")
    result = _converter().convert(str(p))
    text = (result.document.export_to_markdown() or "").strip()
    if not text:
        logger.warning("Docling 解析结果为空: %s", p)
    return text
""" 
用Docling 将 PDF 转为 Markdown 文本
它做的是 Layout-Aware（版式感知）解析，不是简单把 PDF 里的字符抠出来。
为什么需要它
PDF 不是纯文本：多栏、页眉页脚、表格、标题层级都常见。用 PyPDF 一类「按阅读顺序抽字」经常出现：

栏位串行错乱
表格变成一堆乱序词
标题/正文边界不清，后面切 chunk 质量差
Docling 会结合版面理解，再 export_to_markdown()，尽量保留标题、表格等结构，得到更适合 RAG 的文本。

在本项目流水线里的位置
PDF → Docling（转 Markdown）→ 递归字符切分 → embed → chunk_bge_m3
代码注释也写了目标：保留标题/表格等版式结构。

代价（顺带知道）
依赖更重、首次加载/解析更慢
对扫描件（纯图片 PDF）仍依赖 OCR 能力，不是万能
一句话：为了让 PDF 变成结构更清晰的文本，提高后续切分和检索质量，所以用 Docling，而不是最轻量的 PDF 抽字库。 
"""

