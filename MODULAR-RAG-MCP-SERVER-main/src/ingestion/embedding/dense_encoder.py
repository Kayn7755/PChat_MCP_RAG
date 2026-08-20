"""
将文本块（Text Chunks）批量发送给底层的大模型嵌入服务（Embedding Provider），并将返回的密集向量（Dense Vectors）与原文本对齐
Dense Encoder for generating embeddings from text chunks.

This module implements the Dense Encoder component of the Ingestion Pipeline,
responsible for converting text chunks into dense vector representations using
configurable embedding providers.

Design Principles:
- Config-Driven: Uses factory pattern to obtain embedding provider from settings
- Batch Processing: Optimizes API calls through batching
- Observable: Accepts TraceContext for future observability integration
- Error Handling: Individual failures shouldn't crash entire batch
- Deterministic: Same inputs produce same outputs
"""

from typing import List, Optional, Any
from src.core.types import Chunk
from src.libs.embedding.base_embedding import BaseEmbedding


class DenseEncoder:
    """Encodes text chunks into dense vectors using BaseEmbedding provider.
    
    This encoder acts as a bridge between the ingestion pipeline and the
    pluggable embedding layer. It handles batching, error recovery, and
    maintains alignment between input chunks and output vectors.
    
    Design:
    - Dependency Injection: Receives BaseEmbedding instance (no direct factory call)
    - Batch-First: Processes all chunks in configurable batch sizes
    - Stateless: No internal state between encode() calls
    
    Example:
        >>> from src.libs.embedding.embedding_factory import EmbeddingFactory
        >>> from src.core.settings import load_settings
        >>> 
        >>> settings = load_settings("config/settings.yaml")
        >>> embedding = EmbeddingFactory.create(settings)
        >>> encoder = DenseEncoder(embedding, batch_size=32)
        >>> 
        >>> chunks = [Chunk(id="1", text="Hello world", metadata={})]
        >>> vectors = encoder.encode(chunks)
        >>> print(len(vectors))  # 1
        >>> print(len(vectors[0]))  # dimension (e.g., 1536)
    """
    
    def __init__(
        self,
        embedding: BaseEmbedding,
        batch_size: int = 100,
    ):
        """Initialize DenseEncoder.
        
        Args:
            embedding: Embedding provider instance (from EmbeddingFactory)
            batch_size: Number of chunks to process per API call (default: 100)
        
        Raises:
            ValueError: If batch_size <= 0
        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")
        
        self.embedding = embedding
        self.batch_size = batch_size
    
    # 核心编码方法
    def encode(
        self,
        chunks: List[Chunk],
        trace: Optional[Any] = None,
    ) -> List[List[float]]:
        """Encode chunks into dense vectors.
        
        This method:
        1. Extracts text from each chunk
        2. Batches texts according to batch_size
        3. Calls embedding.embed() for each batch
        4. Concatenates results maintaining chunk order
        
        Args:
            chunks: List of Chunk objects to encode
            trace: Optional TraceContext for observability (reserved for Stage F)
        
        Returns:
            List of dense vectors (one per chunk, in same order).
            Each vector is a list of floats with dimension matching the embedding model.
        
        Raises:
            ValueError: If chunks list is empty
            RuntimeError: If embedding provider fails for all batches
        
        Example:
            >>> chunks = [
            ...     Chunk(id="1", text="First chunk", metadata={}),
            ...     Chunk(id="2", text="Second chunk", metadata={})
            ... ]
            >>> vectors = encoder.encode(chunks)
            >>> len(vectors) == len(chunks)  # True
        """
        if not chunks:
            raise ValueError("Cannot encode empty chunks list")
        
        # Extract text from chunks 
        texts = [chunk.text for chunk in chunks]
        
        # 使用一个 for 循环和步长（self.batch_size）将庞大的文本列表切割成多个小批次（例如 100 条一批）。
        # Validate that all texts are non-empty
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(
                    f"Chunk at index {i} (id={chunks[i].id}) has empty or whitespace-only text"
                )
        
        # Process in batches
        all_vectors: List[List[float]] = []
        
        for batch_start in range(0, len(texts), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(texts))
            batch_texts = texts[batch_start:batch_end]
            
            try:
                # Call embedding provider
                batch_vectors = self.embedding.embed(
                    texts=batch_texts,
                    trace=trace,
                )
                
                # Validate output shape
                if len(batch_vectors) != len(batch_texts):
                    raise RuntimeError(
                        f"Embedding provider returned {len(batch_vectors)} vectors "
                        f"for {len(batch_texts)} texts in batch {batch_start}-{batch_end}"
                    )
                
                all_vectors.extend(batch_vectors)
                
            except Exception as e:
                # Re-raise with context about which batch failed
                raise RuntimeError(
                    f"Failed to encode batch {batch_start}-{batch_end}: {str(e)}"
                ) from e
        
        # Final validation
        if len(all_vectors) != len(chunks):
            raise RuntimeError(
                f"Vector count mismatch: got {len(all_vectors)} vectors "
                f"for {len(chunks)} chunks"
            )
        
        # Validate vector dimensions are consistent
        if all_vectors:
            expected_dim = len(all_vectors[0])
            for i, vec in enumerate(all_vectors):
                if len(vec) != expected_dim:
                    raise RuntimeError(
                        f"Inconsistent vector dimensions: vector {i} has "
                        f"{len(vec)} dimensions, expected {expected_dim}"
                    )
        
        return all_vectors
    
    # 计算给定的文本总数需要分多少个批次处理
    def get_batch_count(self, num_chunks: int) -> int:
        """Calculate number of batches needed for given chunk count.
        
        Utility method for logging/progress tracking.
        
        Args:
            num_chunks: Number of chunks to encode
        
        Returns:
            Number of batches required
        """
        if num_chunks <= 0:
            return 0
        return (num_chunks + self.batch_size - 1) // self.batch_size
