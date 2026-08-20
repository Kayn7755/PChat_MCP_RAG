"""
统计 RAG Markdown 标题切分后各片段的 token 分布。

用法（项目根目录）:
  .\\.venv\\Scripts\\python.exe .\\examples\\chunk_token_stats.py
  .\\.venv\\Scripts\\python.exe .\\examples\\chunk_token_stats.py path\\to\\doc.md
  .\\.venv\\Scripts\\python.exe .\\examples\\chunk_token_stats.py --dir path\\to\\md_folder

可选安装更准的计数器:
  pip install tiktoken
  然后加参数 --tokenizer tiktoken
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from jchatmind_app.markdown_sections import MarkdownSection, parse_markdown_sections

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+|.")


@dataclass
class ChunkTokenRow:
    index: int
    title: str
    chars: int
    tokens: int
    # 入库字段是 content；title 仅用于 embedding
    stored_chars: int
    stored_tokens: int


def count_tokens_heuristic(text: str) -> int:
    """中英混合近似 token 数（不依赖第三方库）。

    经验规则（贴近常见 LLM / bge 类分词粗粒度）:
    - 每个汉字约 1 token
    - 英文单词约 1 token
    - 标点/空白按字符粗算（空白忽略）
    """
    if not text:
        return 0
    tokens = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if _CJK_RE.match(ch):
            tokens += 1
            i += 1
            continue
        if ch.isalnum() or ch == "_":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            # 较长英文词按 ~4 字符 ≈ 1 subword 粗估
            word = text[i:j]
            tokens += max(1, math.ceil(len(word) / 4))
            i = j
            continue
        tokens += 1
        i += 1
    return tokens


def count_tokens_tiktoken(text: str, encoding_name: str = "cl100k_base") -> int:
    import tiktoken

    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text or ""))


def make_counter(mode: str):
    if mode == "tiktoken":
        try:
            import tiktoken  # noqa: F401
        except ImportError as e:
            raise SystemExit(
                "未安装 tiktoken。请执行: pip install tiktoken\n"
                "或改用默认启发式: 去掉 --tokenizer tiktoken"
            ) from e
        return count_tokens_tiktoken
    return count_tokens_heuristic


def section_text(sec: MarkdownSection) -> str:
    """与「语义章节」一致：标题 + 正文。"""
    body = (sec.content or "").strip()
    title = (sec.title or "").strip()
    if not body:
        return title
    return f"{title}\n\n{body}"


def analyze_sections(
    sections: list[MarkdownSection],
    count_tokens,
) -> list[ChunkTokenRow]:
    rows: list[ChunkTokenRow] = []
    for i, sec in enumerate(sections):
        if not (sec.title or "").strip():
            continue
        full = section_text(sec)
        stored = sec.content or ""
        rows.append(
            ChunkTokenRow(
                index=i,
                title=sec.title.strip(),
                chars=len(full),
                tokens=count_tokens(full),
                stored_chars=len(stored),
                stored_tokens=count_tokens(stored),
            )
        )
    return rows


def _pct(sorted_vals: list[int], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def summarize(name: str, values: list[int]) -> None:
    if not values:
        print(f"  {name}: (无数据)")
        return
    s = sorted(values)
    avg = statistics.mean(values)
    print(
        f"  {name}: n={len(values)}  "
        f"avg={avg:.1f}  min={min(values)}  max={max(values)}  "
        f"p50={_pct(s, 0.5):.1f}  p90={_pct(s, 0.9):.1f}"
    )


def collect_md_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    pattern = "**/*.md" if recursive else "*.md"
    return sorted(p for p in path.glob(pattern) if p.is_file())


def default_sample_md() -> Path | None:
    docs = _ROOT / "data" / "documents"
    if not docs.exists():
        return None
    files = sorted(docs.rglob("*.md"))
    return files[0] if files else None


def run_on_file(md_path: Path, count_tokens, show_details: bool) -> list[ChunkTokenRow]:
    text = md_path.read_text(encoding="utf-8")
    sections = parse_markdown_sections(text)
    rows = analyze_sections(sections, count_tokens)

    print(f"\n=== 文件: {md_path} ===")
    print(f"章节数: {len(rows)}")
    if show_details:
        print(f"{'#':>3}  {'tokens':>7}  {'chars':>7}  {'stored_tok':>10}  title")
        for r in rows:
            title = r.title if len(r.title) <= 40 else r.title[:37] + "..."
            print(
                f"{r.index:3d}  {r.tokens:7d}  {r.chars:7d}  {r.stored_tokens:10d}  {title}"
            )

    summarize("章节(标题+正文) tokens", [r.tokens for r in rows])
    summarize("入库 content tokens", [r.stored_tokens for r in rows])
    summarize("章节 chars", [r.chars for r in rows])
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="统计 RAG 标题切分片段的平均 token")
    parser.add_argument(
        "path",
        nargs="?",
        help="Markdown 文件或目录；省略则使用 data/documents 下首个 .md",
    )
    parser.add_argument("--dir", dest="dir_path", help="扫描目录下全部 .md（可与 path 二选一）")
    parser.add_argument("-r", "--recursive", action="store_true", help="目录递归扫描")
    parser.add_argument(
        "--tokenizer",
        choices=("heuristic", "tiktoken"),
        default="heuristic",
        help="token 计数方式（默认 heuristic，无需额外依赖）",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="打印每个片段明细")
    args = parser.parse_args(argv)

    count_tokens = make_counter(args.tokenizer)
    print(f"Tokenizer: {args.tokenizer}")

    targets: list[Path] = []
    if args.dir_path:
        targets = collect_md_files(Path(args.dir_path), args.recursive)
    elif args.path:
        targets = collect_md_files(Path(args.path), args.recursive)
    else:
        sample = default_sample_md()
        if sample is None:
            print("未找到默认样例 Markdown，请传入文件路径。")
            return 1
        targets = [sample]

    if not targets:
        print("未找到任何 .md 文件。")
        return 1

    all_rows: list[ChunkTokenRow] = []
    for p in targets:
        all_rows.extend(run_on_file(p, count_tokens, args.verbose or len(targets) == 1))

    if len(targets) > 1:
        print(f"\n=== 汇总 ({len(targets)} 个文件, {len(all_rows)} 个片段) ===")
        summarize("全部章节 tokens", [r.tokens for r in all_rows])
        summarize("全部入库 content tokens", [r.stored_tokens for r in all_rows])

    if all_rows:
        avg = statistics.mean(r.tokens for r in all_rows)
        print(f"\n结论: 语义切分片段平均 token ≈ {avg:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
