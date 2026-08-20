"""
这个文件定义的是文本切分器的抽象接口，本身不切文本。真正切分在子类（如 RecursiveSplitter），由 SplitterFactory 按配置创建。
Abstract base class for text splitters.

This module defines the pluggable interface for text splitter providers,
enabling seamless switching between different splitting strategies
(Recursive, Semantic, FixedLength, etc.) through configuration-driven instantiation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class BaseSplitter(ABC):
    """
    文本分割器的抽象基类。
    
    所有拆分器实现都必须继承自此类并实现split_text() 方法。这确保了一致的接口不同的策略。
    
    应用的设计原则：
    -可插拔：可以在不更改上游代码的情况下交换子类。
    -Observable：接受可选的 TraceContext 以进行可观察性集成。
    -配置驱动：实例是根据设置通过工厂创建的。
    """
    
    # 
    @abstractmethod
    def split_text(
        self,
        text: str,
        trace: Optional[Any] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Split input text into a list of chunks.
        
        Args:
            text: Input text to split. Must be a non-empty string.
            trace: Optional TraceContext for observability (reserved for Stage F).
            **kwargs: Strategy-specific parameters (chunk_size, overlap, etc.).
        
        Returns:
            A list of text chunks. Order must preserve the original text sequence.
        
        Raises:
            ValueError: If input text is invalid.
            RuntimeError: If the splitter fails unexpectedly.
        """
        pass
    
    def validate_text(self, text: str) -> None:
        """Validate input text.
        
        Args:
            text: Input text to validate.
        
        Raises:
            ValueError: If text is not a non-empty string.
        """
        if not isinstance(text, str):
            raise ValueError(f"Input text must be a string, got {type(text).__name__}")
        if not text.strip():
            raise ValueError("Input text cannot be empty or whitespace-only")
    
    def validate_chunks(self, chunks: List[str]) -> None:
        """Validate output chunks.
        
        Args:
            chunks: List of chunk strings to validate.
        
        Raises:
            ValueError: If chunks are empty or contain invalid entries.
        """
        if not isinstance(chunks, list):
            raise ValueError("Chunks must be a list of strings")
        if not chunks:
            raise ValueError("Chunks list cannot be empty")
        for i, chunk in enumerate(chunks):
            if not isinstance(chunk, str):
                raise ValueError(
                    f"Chunk at index {i} is not a string (type: {type(chunk).__name__})"
                )
            if not chunk.strip():
                raise ValueError(
                    f"Chunk at index {i} is empty or whitespace-only"
                )