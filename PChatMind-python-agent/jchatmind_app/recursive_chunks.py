"""递归字符切分（LangChain RecursiveCharacterTextSplitter）。
PDF 递归字符切分（字符数，约对应通用文本 400–512 token）
"""

from __future__ import annotations


def split_recursive(
    text: str,
    *,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[str]:
    """按换行 → 句号 → 空格逐层切分，直到块小于 chunk_size。"""
    from langchain_text_splitters import RecursiveCharacterTextSplitter # 采用的是一种基于层级分隔符的递归分块

    raw = (text or "").strip()
    if not raw:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max(1, chunk_size),
        chunk_overlap=max(0, min(chunk_overlap, max(0, chunk_size - 1))),
        length_function=len,
        is_separator_regex=False,
    )
    return [c.strip() for c in splitter.split_text(raw) if c.strip()]
