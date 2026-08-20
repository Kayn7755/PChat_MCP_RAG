"""
Storage Module.

This package contains storage components:
- Vector upserter
- BM25 indexer
- Image storage
"""

from src.ingestion.storage.bm25_indexer import BM25Indexer
from src.ingestion.storage.vector_upserter import VectorUpserter

__all__ = ["BM25Indexer", "VectorUpserter"]
""" 
完整的pdf存储流程
1. 完整性检查（SHA256，避免重复摄取）
2. PdfLoader：PDF → 文本(MD风格) + 抽图落盘 + 占位符
3. Chunker：切块（不是整篇一起 embed）
4. Transform：
   - Chunk Refiner（润色切片）
   - Metadata Enricher（标题/标签等）
   - Image Captioner（Vision 给图写文字描述，便于检索）
5. Encoding：Dense embedding + Sparse 词频（给 BM25）
6. Storage：
   - 向量 → Chroma
   - BM25 → JSON
   - 图片索引 → SQLite（文件多半 Loader 已存好） 
   """