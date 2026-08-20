"""
当前代码的唯一任务，就是把 BM25 公式需要的所有前置变量（原材料）提前算出来存好：
TF（词频）： 对应代码里的 term_frequencies
|D|（当前文档长度）： 对应代码里的 doc_length
avgdl（语料库平均文档长度）： 对应代码里的 avg_doc_length
DF（文档频率，用于算 IDF）： 对应代码里的 document_frequency
并没有涉及计算BM25分数的代码
打分代码可能藏在系统的“检索组件（Retriever）”或底层的“向量/全文数据库”中执行

为BM25稀疏检索算法准备所需的词汇统计数据。
BM25无需大模型encoding
对于经典的 BM25 算法来说，并没有一个所谓的“预训练神经网络大模型”可以导入。它的“模型”其实就是两样东西的组合：
分词器 (Tokenizer)： 比如中文的 jieba、英文的 nltk 或 tiktoken。
词频统计逻辑： 也就是计算 TF（词频）和 IDF（逆文档频率）的数学公式。

具体做法:
怎么做？
    当你有一句话“苹果手机怎么重启”，你会：
    用 jieba 把它切成 ["苹果", "手机", "怎么", "重启"]。
    统计这个文档里每个词出现了几次（TF）。
    统计这些词在你整个知识库里出现了几次（用来算 IDF）。
    产出物是什么？
    它产出的不是一串毫无意义的浮点数，而是一个 字典 (Dictionary)：
    {"苹果": 1.2, "手机": 0.8, "重启": 2.5} （键是词，值是 BM25 算出来的权重）。
    注：这也是为什么很多老牌搜索引擎（如 Elasticsearch）天然自带 BM25，因为它们底层就是做倒排索引和词频统计的，不需要外接任何大模型。
Sparse Encoder for generating BM25 term statistics from text chunks.

This module implements the Sparse Encoder component of the Ingestion Pipeline,
responsible for extracting term statistics needed for BM25 indexing.

Design Principles:
- Stateless Processing: No internal state between encode() calls
- Observable: Accepts TraceContext for future observability integration
- Deterministic: Same inputs produce same term statistics
- Clear Contracts: Well-defined output structure for downstream BM25Indexer
"""

from typing import List, Dict, Optional, Any
from collections import Counter
import re

import jieba

from src.core.types import Chunk


class SparseEncoder:
    """Encodes text chunks into BM25 term statistics.
    
    This encoder prepares term-level statistics needed for BM25 indexing.
    The actual index construction is handled by BM25Indexer (C12).
    
    Output Structure:
        For each chunk, produces:
        {
            "chunk_id": str,
            "term_frequencies": Dict[str, int],  # term -> count in this chunk
            "doc_length": int,                    # number of terms in chunk
            "unique_terms": int                   # vocabulary size in chunk
        }
    
    Design:
    - Tokenization: Simple whitespace + lowercasing (can be enhanced later)
    - Stop Words: None by default (can add in future iterations)
    - Deterministic: Same chunk text always produces same statistics
    
    Example:
        >>> from src.core.types import Chunk
        >>> encoder = SparseEncoder()
        >>> 
        >>> chunks = [Chunk(id="1", text="Hello world hello", metadata={})]
        >>> stats = encoder.encode(chunks)
        >>> stats[0]["term_frequencies"]["hello"]  # 2
        >>> stats[0]["doc_length"]  # 3
    """
    
    def __init__(
        self,
        min_term_length: int = 2, # 允许的最小词长，默认是 2（这意味在默认情况下，单字如“的”、“是”、“a”、“I”等会被直接过滤掉，这起到了一种基础停用词过滤的作用）。
        lowercase: bool = True, # 是否将所有英文字母转换为小写，默认为 True，用于统一大小写以提高匹配率。
    ):
        """Initialize SparseEncoder.
        
        Args:
            min_term_length: Minimum character length for a term (default: 2)
            lowercase: Whether to convert terms to lowercase (default: True)
        
        Raises:
            ValueError: If min_term_length < 1
        """
        if min_term_length < 1:
            raise ValueError(f"min_term_length must be >= 1, got {min_term_length}")
        
        self.min_term_length = min_term_length
        self.lowercase = lowercase
    
    # 接收一批文本块（Chunks），处理并返回每个文本块的词频统计信息（Chunk 级别的统计）。
    def encode(
        self,
        chunks: List[Chunk],
        trace: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Encode chunks into BM25 term statistics.
        
        For each chunk, extracts:
        - Term frequencies (term -> count)
        - Document length (total terms)
        - Unique terms count
        
        Args:
            chunks: List of Chunk objects to encode
            trace: Optional TraceContext for observability (reserved for Stage F)
        
        Returns:
            List of statistics dictionaries (one per chunk, in same order).
            Each dict contains: chunk_id, term_frequencies, doc_length, unique_terms
        
        Raises:
            ValueError: If chunks list is empty
            ValueError: If any chunk has empty text
        
        Example:
            >>> chunks = [
            ...     Chunk(id="1", text="machine learning", metadata={}),
            ...     Chunk(id="2", text="deep learning networks", metadata={})
            ... ]
            >>> stats = encoder.encode(chunks)
            >>> len(stats) == len(chunks)  # True
            >>> stats[0]["term_frequencies"]["machine"]  # 1
            >>> stats[1]["doc_length"]  # 3
        """
        if not chunks:
            raise ValueError("Cannot encode empty chunks list")
        
        results = []
        
        for i, chunk in enumerate(chunks):
            # Validate chunk text
            if not chunk.text or not chunk.text.strip():
                raise ValueError(
                    f"Chunk at index {i} (id={chunk.id}) has empty or whitespace-only text"
                )
            
            # Tokenize and count terms 调用底层的 _tokenize 方法对每个文本块进行分词
            terms = self._tokenize(chunk.text) 
            term_frequencies = Counter(terms) # 使用 Python 内置的 Counter 计算每个词在该文本块中出现的次数
            
            # 为每个文本块生成一个结果字典，包含：
            # chunk_id：文本块的唯一标识。
            # term_frequencies：字典，记录每个词及其在该文本中的出现次数（即 TF）。
            # doc_length：该文本块的总词数。
            # unique_terms：该文本块包含的不重复词汇的数量。
            stat_dict = {
                "chunk_id": chunk.id,
                "term_frequencies": dict(term_frequencies),  # Convert Counter to dict
                "doc_length": len(terms),
                "unique_terms": len(term_frequencies),
            }
            
            results.append(stat_dict) # 返回一个列表，里面包含了所有文本块对应的统计字典
        
        return results
    
    # 将一段完整文本切割成符合要求的词汇列表
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms.
        
        Uses jieba for Chinese text segmentation and regex for English.
        This ensures consistent tokenization with the query-side
        (QueryProcessor), which is required for BM25 matching.
        
        Args:
            text: Input text to tokenize
        
        Returns:
            List of valid terms
        """
        tokens: List[str] = []

        # 使用 jieba.lcut(text) 对文本进行精确模式分词
        # Use jieba to segment the text (handles both Chinese and English)
        raw_tokens = jieba.lcut(text)

        # 遍历切出来的每一个词，使用正则表达式 r'[\s\W]+' 剔除掉纯标点符号和纯空白字符。
        # Clean tokens: keep only alphanumeric and Chinese characters
        for token in raw_tokens:
            token = token.strip()
            if not token:
                continue
            # Skip pure punctuation / whitespace
            if re.fullmatch(r'[\s\W]+', token, re.UNICODE):
                continue
            tokens.append(token)
        
        # Apply lowercase if configured
        if self.lowercase:
            tokens = [t.lower() for t in tokens]
        
        # Filter by minimum length
        terms = [t for t in tokens if len(t) >= self.min_term_length]
        
        return terms # 返回一个干净、标准化后的词汇列表。
    
    # 把 encode 方法输出的多个“单个文本统计结果”聚合起来，计算全局（Corpus 级别）的统计信息。BM25 算法在计算 IDF（逆文档频率）时极其依赖这些全局数据
    def get_corpus_stats(
        self,
        encoded_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate corpus-level statistics from encoded chunks.
        
        Utility method for BM25Indexer to compute:
        - Average document length
        - Document frequency (how many docs contain each term)
        - Total number of documents
        
        Args:
            encoded_chunks: List of statistics dicts from encode()
        
        Returns:
            Dictionary with corpus-level statistics:
            {
                "num_docs": int,
                "avg_doc_length": float,
                "document_frequency": Dict[str, int]  # term -> # docs containing it
            }
        """
        if not encoded_chunks:
            return {
                "num_docs": 0,
                "avg_doc_length": 0.0,
                "document_frequency": {}
            }
        
        num_docs = len(encoded_chunks)
        total_length = sum(chunk["doc_length"] for chunk in encoded_chunks)
        avg_doc_length = total_length / num_docs if num_docs > 0 else 0.0
        
        # Calculate document frequency (DF) for each term
        doc_freq: Dict[str, int] = {}
        for chunk_stats in encoded_chunks:
            # Each unique term in this chunk contributes 1 to DF
            for term in chunk_stats["term_frequencies"].keys():
                doc_freq[term] = doc_freq.get(term, 0) + 1
        
        return {
            "num_docs": num_docs,
            "avg_doc_length": avg_doc_length,
            "document_frequency": doc_freq,
        }
