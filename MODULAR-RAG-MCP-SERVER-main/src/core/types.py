"""Core data types and contracts for the entire pipeline.
定义的是整条 RAG 流水线共用的数据结构（契约），
让 Loader、切分、Embedding、检索、MCP 等模块用同一套类型传数据，避免各写各的
This module defines the fundamental data structures used across all pipeline stages:
- ingestion (loaders, transforms, embedding, storage)
- retrieval (query engine, search, reranking)
- mcp_server (tools, response formatting)

Design Principles:
- Centralized contracts: All stages use these types to avoid coupling
- Serializable: All types support dict/JSON conversion
- Extensible metadata: Minimum required fields with flexible extension
- Type-safe: Full type hints for static analysis
类型	作用
Document    Loader 输出：整篇文档（Markdown 文本 + metadata）
Chunk   Splitter 输出：切出来的片段，可回溯原文位置
ChunkRecord     Embedding 后：Chunk + dense/sparse 向量，准备写入向量库
ProcessedQuery  查询预处理结果
RetrievalResult     检索返回的一条结果（chunk_id、score、text、metadata）
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

# 用于存储原始文件；提供几个方法负责校验和 dict 互转。
@dataclass
class Document:
    """Represents a raw document loaded from source.
    
    This is the output of Loaders (e.g., PDF Loader) before splitting.
    
    Attributes:
        id: Unique identifier for the document (e.g., file hash or path-based ID)
        text: Document content in standardized Markdown format.
              Images are represented as placeholders: [IMAGE: {image_id}]
        metadata: Document-level metadata including:
            - source_path (required): Original file path
            - doc_type: Document type (e.g., 'pdf', 'markdown')
            - title: Document title extracted or inferred
            - page_count: Total pages (if applicable)
            - images: List of image references (see Images Field Specification below)
            - Any other custom metadata
    
    Images Field Specification (metadata.images):
        Structure: List[{"id": str, "path": str, "page": int, "text_offset": int, 
                        "text_length": int, "position": dict}]
        Fields:
            - id: Unique image identifier (format: {doc_hash}_{page}_{seq})
            - path: Image file storage path (convention: data/images/{collection}/{image_id}.png)
            - page: Page number in original document (optional, for paginated docs like PDF)
            - text_offset: Starting character position of placeholder in Document.text (0-based)
            - text_length: Length of placeholder string (typically len("[IMAGE: {image_id}]"))
            - position: Physical position info in original doc (optional, e.g., PDF coords, pixel position)
        Note: text_offset and text_length enable precise placeholder location, 
              supporting scenarios where the same image appears multiple times
    
    原始文件存储格式
    Example:
        >>> doc = Document(
        ...     id="doc_abc123",
        ...     text="# Title\\n\\nContent...",
        ...     metadata={
        ...         "source_path": "data/documents/report.pdf",
        ...         "doc_type": "pdf",
        ...         "title": "Annual Report 2025"
        ...     }
        ... )
    """
    
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # dataclass 构造完后自动跑；检查 metadata 里有没有 source_path
    def __post_init__(self):
        """Validate required metadata fields."""
        if "source_path" not in self.metadata:
            raise ValueError("Document metadata must contain 'source_path'")
    
    # 对象 → dict（方便 JSON/落盘）
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self) # 读 self 上的 dataclass 字段，拼成字典
        # asdict 来自标准库 dataclasses
        # 它只对@dataclass类有效：这类对象的字段是声明好的（id、text、metadata），asdict 会按这些字段递归拷贝成普通 dict。
    
    # dict → Document 对象（和 Settings 的 from_dict 同类工厂方法）
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Create Document from dictionary."""
        return cls(**data) # **data 是 Python 的字典拆包（unpack），把 dict 拆成关键字参数传给函数/构造器。
        # 写法	作用	例子
        # * args / * list   按位置拆序列    f(*[1,2]) → f(1, 2)
        # ** kwargs / ** dict   按关键字拆字典  f(**{"a":1}) → f(a=1)

# # Document(原始文件) 被切分后的一个文本块
@dataclass
class Chunk:
    """Represents a text chunk after splitting a Document.
    
    This is the output of Splitters and input to Transform pipeline.
    Each chunk maintains traceability to its source document.
    
    Attributes:
        id: Unique chunk identifier (e.g., hash-based or sequential)
        text: Chunk content (subset of original document text).
              Images are represented as placeholders: [IMAGE: {image_id}]
        metadata: Chunk-level metadata inherited and extended from Document:
            - source_path (required): Original file path
            - chunk_index: Sequential position in document (0-based)
            - start_offset: Character offset in original document (optional)
            - end_offset: Character offset in original document (optional)
            - source_ref: Reference to parent document ID (optional)
            - images: Subset of Document.images that fall within this chunk (optional)
            - Any document-level metadata propagated from Document
        start_offset: Starting character position in original document (optional)
        end_offset: Ending character position in original document (optional)
        source_ref: Reference to parent Document.id (optional)
    
    Note: If chunk contains image placeholders, metadata.images should contain
          only the image references relevant to this chunk's text range.
    
    Example:
        >>> chunk = Chunk(
        ...     id="chunk_abc123_001",
        ...     text="## Section 1\\n\\nFirst paragraph...",
        ...     metadata={
        ...         "source_path": "data/documents/report.pdf",
        ...         "chunk_index": 0,
        ...         "page": 1
        ...     },
        ...     start_offset=0,
        ...     end_offset=150
        ... )
    """
    
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_offset: Optional[int] = None # 在原文中的起止字符位置（可选，便于回溯）
    end_offset: Optional[int] = None
    source_ref: Optional[str] = None # 指向父文档 Document.id（可选）
    
    def __post_init__(self):
        """Validate required metadata fields."""
        if "source_path" not in self.metadata:
            raise ValueError("Chunk metadata must contain 'source_path'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod # Chunk 的工厂方法：把字典转成一个 Chunk 对象
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        """Create Chunk from dictionary."""
        return cls(**data)

# 在 Chunk基础上加上向量(不是做文本编码, 是将前面 Embedding / BM25 步骤算好向量，这里只负责 Chunk + 向量 → ChunkRecord)后、可以写入向量库、用于检索 的完整记录
# 只是记录了Embedding / BM25编码的向量
@dataclass
class ChunkRecord:
    """Represents a fully processed chunk ready for storage and retrieval.
    
    This is the output of the embedding pipeline and the data structure
    stored in vector databases. It extends Chunk with vector representations.
    
    Attributes:
        id: Unique chunk identifier (must be stable for idempotent upsert)
        text: Chunk content (same as Chunk.text).
              Images are represented as placeholders: [IMAGE: {image_id}]
        metadata: Extended metadata including:
            - source_path (required): Original file path
            - chunk_index: Sequential position
            - All metadata from Chunk
            - images: Image references from Chunk (see Document.images specification)
            - Any enrichment from Transform pipeline (title, summary, tags)
            - image_captions: Dict[image_id, caption_text] if multimodal enrichment applied
        dense_vector: Dense embedding vector (e.g., from OpenAI, BGE)
        sparse_vector: Sparse vector for BM25/keyword matching (optional)
    
    Note: Image captions generated by ImageCaptioner are stored in metadata.image_captions
          as a dictionary mapping image_id to generated caption text.
    
    Example:
        >>> record = ChunkRecord(
        ...     id="chunk_abc123_001",
        ...     text="## Section 1\\n\\nFirst paragraph...",
        ...     metadata={
        ...         "source_path": "data/documents/report.pdf",
        ...         "chunk_index": 0,
        ...         "title": "Introduction",
        ...         "summary": "Overview of project goals"
        ...     },
        ...     dense_vector=[0.1, 0.2, ..., 0.3],
        ...     sparse_vector={"word1": 0.5, "word2": 0.3}
        ... )
    """
    
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    dense_vector: Optional[List[float]] = None # 稠密向量（语义检索，如 OpenAI Embedding）
    sparse_vector: Optional[Dict[str, float]] = None # 稀疏向量（关键词/BM25 权重）
    
    def __post_init__(self):
        """Validate required metadata fields."""
        if "source_path" not in self.metadata:
            raise ValueError("ChunkRecord metadata must contain 'source_path'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkRecord":
        """Create ChunkRecord from dictionary."""
        return cls(**data)
    
    # 用已有的 Chunk，再附上两个向量，组装成 ChunkRecord。它本身不调用模型，只是把别人算好的向量贴上去
    @classmethod 
    def from_chunk(cls, chunk: Chunk, dense_vector: Optional[List[float]] = None,
                   sparse_vector: Optional[Dict[str, float]] = None) -> "ChunkRecord":
        """Create ChunkRecord from a Chunk with vectors.
        
        Args:
            chunk: Source Chunk object
            dense_vector: Dense embedding vector
            sparse_vector: Sparse vector representation
            
        Returns:
            ChunkRecord with all fields populated from chunk
        """
        return cls(
            id=chunk.id,
            text=chunk.text,
            metadata=chunk.metadata.copy(),
            dense_vector=dense_vector,
            sparse_vector=sparse_vector
        )


# Type aliases for convenience
Metadata = Dict[str, Any]
Vector = List[float]
SparseVector = Dict[str, float]

# 用户原始问题经过 QueryProcessor 预处理后的结果，供后面的 Dense / Sparse 检索使用。
@dataclass
class ProcessedQuery:
    """Represents a processed query ready for retrieval.
    
    This is the output of QueryProcessor, containing extracted keywords
    and parsed filters for downstream Dense/Sparse retrievers.
    
    Attributes:
        original_query: The raw user query string
        keywords: List of extracted keywords after stopword removal
        filters: Dictionary of filter conditions (e.g., {"collection": "api-docs"})
        expanded_terms: Optional list of synonyms/expanded terms (for future use)
    
    Example:
        >>> pq = ProcessedQuery(
        ...     original_query="如何配置 Azure OpenAI？",
        ...     keywords=["配置", "Azure", "OpenAI"],
        ...     filters={"collection": "docs"}
        ... )
    """
    
    original_query: str # 原始提问
    # List[str]: 创建对象时如果没传这个参数，就新造一个空 list / 空 dict
    # 因为类属性上的 []/{} 会被所有实例共享，改一个会影响到别的。default_factory 保证每个实例各自一份。
    keywords: List[str] = field(default_factory=list) # 抽出的关键词（去停用词等），给稀疏检索用
    filters: Dict[str, Any] = field(default_factory=dict) # 过滤条件，如指定 collection
    expanded_terms: List[str] = field(default_factory=list) # 同义词/扩展词（预留，可为空）
    # field声明这个字段的默认值不要直接写死，而是在创建对象时调用一个函数生成
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessedQuery":
        """Create ProcessedQuery from dictionary."""
        return cls(**data)

# 表示 RAG系统中一次检索返回的结果。
# 所有检索方式最终都返回这个格式的数据，方便后续 Rerank、上下文拼接、LLM生成答案
@dataclass
class RetrievalResult:
    """Represents a single retrieval result from Dense/Sparse retrievers.
    
    This is the output of DenseRetriever, SparseRetriever, and HybridSearch,
    providing a unified contract for retrieval results across all search methods.
    
    Attributes:
        chunk_id: Unique identifier for the retrieved chunk
        score: Relevance score (higher = more relevant, normalized to [0, 1])
        text: The actual text content of the retrieved chunk
        metadata: Associated metadata (source_path, chunk_index, title, etc.)
    
    Example:
        >>> result = RetrievalResult(
        ...     chunk_id="doc1_chunk_003",
        ...     score=0.85,
        ...     text="Azure OpenAI 配置步骤如下...",
        ...     metadata={
        ...         "source_path": "docs/azure-guide.pdf",
        ...         "chunk_index": 3,
        ...         "title": "Azure Configuration"
        ...     }
        ... )
    """
    
    chunk_id: str
    score: float
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate fields after initialization."""
        if not self.chunk_id:
            raise ValueError("chunk_id cannot be empty")
        if not isinstance(self.score, (int, float)):
            raise ValueError(f"score must be numeric, got {type(self.score).__name__}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalResult":
        """Create RetrievalResult from dictionary."""
        return cls(**data)
