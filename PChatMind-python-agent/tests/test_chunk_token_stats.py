"""单元测试：Markdown 标题切分后的片段 token 统计。"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from examples.chunk_token_stats import (
    analyze_sections,
    count_tokens_heuristic,
    section_text,
)
from jchatmind_app.markdown_sections import parse_markdown_sections

SAMPLE_MD = """# 总标题

前言不会单独成章。

## 第一节

这是第一节正文，包含一些中文内容。

## 第二节

第二节较短。

### 子节

子节正文 abcdefghij 12345。
"""


def test_parse_and_avg_tokens():
    sections = parse_markdown_sections(SAMPLE_MD)
    assert len(sections) == 4  # 总标题 / 第一节 / 第二节 / 子节

    rows = analyze_sections(sections, count_tokens_heuristic)
    assert len(rows) == 4
    assert all(r.tokens > 0 for r in rows)

    avg = statistics.mean(r.tokens for r in rows)
    assert avg > 0
    # 入库 content 不含标题，通常 <= 标题+正文
    for r in rows:
        assert r.stored_tokens <= r.tokens


def test_section_text_includes_title():
    sections = parse_markdown_sections("## Hello\n\nworld\n")
    assert len(sections) == 1
    text = section_text(sections[0])
    assert text.startswith("Hello")
    assert "world" in text


def test_heuristic_counts_cjk_and_english():
    assert count_tokens_heuristic("你好") == 2
    assert count_tokens_heuristic("hi") == 1
    assert count_tokens_heuristic("") == 0


if __name__ == "__main__":
    test_parse_and_avg_tokens()
    test_section_text_includes_title()
    test_heuristic_counts_cjk_and_english()
    sections = parse_markdown_sections(SAMPLE_MD)
    rows = analyze_sections(sections, count_tokens_heuristic)
    avg = statistics.mean(r.tokens for r in rows)
    print(f"样例片段数={len(rows)}, 平均 token={avg:.1f}")
    for r in rows:
        print(f"  [{r.index}] tokens={r.tokens} title={r.title!r}")
    print("OK")
