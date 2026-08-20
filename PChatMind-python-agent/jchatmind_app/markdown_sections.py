from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MarkdownSection:
    title: str
    content: str


_HEADING_LINE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")

"""按文档结构切。
具体做法是按 Markdown 标题（#～######）把文档切成章节：一个标题到下一个标题之间的内容算一块，没有固定长度、没有重叠，也不是递归字符切分或语义切分。
和文里说的「页面级」同类思路——用作者已经标好的结构边界（这里是标题层级），而不是按 Token 硬切。
"""
def parse_markdown_sections(text: str) -> list[MarkdownSection]:
    """按行首 Markdown 标题切分章节。"""
    lines = text.splitlines()
    sections: list[MarkdownSection] = []
    i = 0
    while i < len(lines):
        m = _HEADING_LINE.match(lines[i])
        if not m:
            i += 1
            continue
        title = m.group(2).strip()
        if not title:
            i += 1
            continue
        i += 1
        buf: list[str] = []
        while i < len(lines):
            if _HEADING_LINE.match(lines[i]):
                break
            buf.append(lines[i])
            i += 1
        sections.append(MarkdownSection(title=title, content="\n".join(buf).strip()))
    return sections
