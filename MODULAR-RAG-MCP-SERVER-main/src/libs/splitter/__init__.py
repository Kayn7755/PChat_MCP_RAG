"""
该文件夹用于实现文本分割器，目前支持递归分割器。
Splitter Module.

This package contains text splitter abstractions and implementations:
- Base splitter class # 抽象基类
- Splitter factory # 工厂类
- Implementations (Recursive, Semantic, FixedLength) # 实现类
"""

from src.libs.splitter.base_splitter import BaseSplitter
from src.libs.splitter.splitter_factory import SplitterFactory

# Import concrete implementations (they auto-register with factory)
try:
    from src.libs.splitter.recursive_splitter import RecursiveSplitter
except ImportError:
    RecursiveSplitter = None  # type: ignore[assignment, misc]

__all__ = [
    "BaseSplitter",
    "SplitterFactory",
    "RecursiveSplitter",
]
