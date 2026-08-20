"""
在检索侧、真正搜库之前：把用户原句加工成 ProcessedQuery（关键词 + 过滤条件），给 Dense / BM25 用。
不切文档、不 embedding。

功能: 
分词（jieba）
去掉不必要的词（停用词、过短、重复）
解析过滤语法（如 collection:docs），从问句里剥出来
空白规范化
Query Processor for preprocessing user queries.

This module provides query preprocessing functionality including:
- Keyword extraction using rule-based tokenization
- Stopword filtering for Chinese and English
- Filter parsing from query syntax (e.g., "collection:docs")
- Query normalization and cleaning

Design Principles:
- Rule-based first: Use simple, deterministic rules for reliability
- Language-aware: Support both Chinese and English queries
- Extensible: Easy to add synonym expansion or LLM-based processing later
- Configuration-driven: Stopwords and patterns configurable via settings
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern, Set

import jieba

from src.core.types import ProcessedQuery


# Default stopwords for Chinese
CHINESE_STOPWORDS: Set[str] = {
    # 疑问词
    "如何", "怎么", "怎样", "什么", "哪个", "哪些", "为什么", "为何",
    "谁", "多少", "几", "是否", "能否", "可否",
    # 助词
    "的", "地", "得", "了", "着", "过", "吗", "呢", "吧", "啊", "呀",
    # 介词/连词
    "在", "于", "和", "与", "或", "及", "并", "而", "但", "但是",
    "因为", "所以", "如果", "那么", "虽然", "然而",
    # 代词
    "我", "你", "他", "她", "它", "我们", "你们", "他们", "这", "那",
    "这个", "那个", "这些", "那些", "这里", "那里",
    # 副词
    "很", "非常", "特别", "更", "最", "都", "也", "还", "又", "再",
    "已", "已经", "正在", "将", "会", "能", "可以", "应该", "必须",
    # 动词(通用)
    "是", "有", "做", "进行", "使用", "通过",
    # 量词
    "个", "种", "类",
    # 标点等
    "？", "。", "！", "，", "、",
}

# Default stopwords for English
ENGLISH_STOPWORDS: Set[str] = {
    # Articles
    "a", "an", "the",
    # Prepositions
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "about", "through", "between", "after", "before",
    # Conjunctions
    "and", "or", "but", "if", "then", "because", "while", "although",
    # Pronouns
    "i", "you", "he", "she", "it", "we", "they", "this", "that",
    "these", "those", "what", "which", "who", "whom", "whose",
    # Auxiliary verbs
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "can",
    # Common verbs
    "get", "use", "make",
    # Question words
    "how", "why", "when", "where",
    # Others
    "not", "no", "yes", "so", "very", "just", "also", "too",
}

# Combined default stopwords
DEFAULT_STOPWORDS: Set[str] = CHINESE_STOPWORDS | ENGLISH_STOPWORDS

# Pattern for filter syntax: key:value
FILTER_PATTERN: Pattern = re.compile(r'(\w+):([^\s]+)')

# 配置：停用词集合、最短词长、最多关键词数（默认 20）、是否解析 filter
@dataclass
class QueryProcessorConfig:
    """Configuration for QueryProcessor.
    
    Attributes:
        stopwords: Set of words to filter out
        min_keyword_length: Minimum length for a keyword to be included
        max_keywords: Maximum number of keywords to extract
        enable_filter_parsing: Whether to parse filter syntax from query
    """
    stopwords: Set[str] = field(default_factory=lambda: DEFAULT_STOPWORDS.copy())
    min_keyword_length: int = 1
    max_keywords: int = 20
    enable_filter_parsing: bool = True

# 查询处理器
class QueryProcessor:
    """预处理用户查询以进行检索
    抽关键词（去「如何」「的」「the」）
    解析 collection:docs 缩小范围   
    分词对齐 BM25 词表
    从用户原句里抽出适合检索的词和过滤条件，让 BM25（以及后续过滤）更准；原句仍会留给向量检索用语义。
    Extracts keywords, filters stopwords, and parses filter syntax
    to prepare queries for Dense and Sparse retrievers.
    
    Example:
        >>> processor = QueryProcessor()
        >>> result = processor.process("如何配置 Azure OpenAI？")
        >>> print(result.keywords)
        ['配置', 'Azure', 'OpenAI']
    """
    
    def __init__(self, config: Optional[QueryProcessorConfig] = None):
        """Initialize QueryProcessor.
        
        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or QueryProcessorConfig()
    
    def process(self, query: str) -> ProcessedQuery:
        """Process a user query into structured format.
        
        Args:
            query: Raw user query string
            
        Returns:
            ProcessedQuery with extracted keywords and filters
        """
        if not query or not query.strip():
            return ProcessedQuery(
                original_query=query or "",
                keywords=[],
                filters={}
            )
        
        # Normalize query
        normalized = self._normalize(query)
        
        # Extract filters from query (e.g., "collection:docs")
        filters, query_without_filters = self._extract_filters(normalized)
        
        # Tokenize and extract keywords
        tokens = self._tokenize(query_without_filters)
        
        # Filter stopwords and apply constraints
        keywords = self._filter_keywords(tokens)
        
        return ProcessedQuery(
            original_query=query,
            keywords=keywords,
            filters=filters
        )
    
    def _normalize(self, query: str) -> str:
        """Normalize query string.
        
        - Strip whitespace
        - Normalize unicode
        - Convert to consistent format
        
        Args:
            query: Raw query string
            
        Returns:
            Normalized query string
        """
        # Strip and normalize whitespace
        normalized = " ".join(query.split())
        return normalized
    
    def _extract_filters(self, query: str) -> tuple[Dict[str, Any], str]:
        """Extract filter syntax from query.
        
        Supports syntax like: "collection:api-docs keyword1 keyword2"
        
        Args:
            query: Normalized query string
            
        Returns:
            Tuple of (filters dict, query without filter syntax)
        """
        if not self.config.enable_filter_parsing:
            return {}, query
        
        filters: Dict[str, Any] = {}
        
        # Find all filter patterns
        matches = FILTER_PATTERN.findall(query)
        for key, value in matches:
            # Support common filter keys
            key_lower = key.lower()
            if key_lower in ("collection", "col", "c"):
                filters["collection"] = value
            elif key_lower in ("type", "doc_type", "t"):
                filters["doc_type"] = value
            elif key_lower in ("source", "src", "s"):
                filters["source_path"] = value
            elif key_lower in ("tag", "tags"):
                # Tags can be comma-separated
                if "tags" not in filters:
                    filters["tags"] = []
                filters["tags"].extend(value.split(","))
            else:
                # Generic filter
                filters[key] = value
        
        # Remove filter patterns from query
        query_without_filters = FILTER_PATTERN.sub("", query).strip()
        query_without_filters = " ".join(query_without_filters.split())
        
        return filters, query_without_filters
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words/terms.
        
        Uses jieba for Chinese text segmentation, consistent with the
        index-side tokenizer (SparseEncoder) so BM25 matching works.
        English text is handled natively by jieba (preserved as-is).
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        tokens: List[str] = []

        # Use jieba to segment (handles Chinese + keeps English intact)
        raw_tokens = jieba.lcut(text)

        for token in raw_tokens:
            token = token.strip()
            if not token:
                continue
            # Skip pure punctuation / whitespace
            if re.fullmatch(r'[\s\W]+', token, re.UNICODE):
                continue
            tokens.append(token)
        
        return tokens
    
    def _filter_keywords(self, tokens: List[str]) -> List[str]:
        """Filter tokens to get meaningful keywords.
        
        - Remove stopwords
        - Apply minimum length constraint
        - Deduplicate while preserving order
        - Apply maximum count limit
        
        Args:
            tokens: List of tokens
            
        Returns:
            List of filtered keywords
        """
        seen: Set[str] = set()
        keywords: List[str] = []
        
        for token in tokens:
            # Normalize for comparison
            token_lower = token.lower()
            
            # Skip if already seen (case-insensitive dedup)
            if token_lower in seen:
                continue
            
            # Skip stopwords (check both original and lowercase)
            if token in self.config.stopwords or token_lower in self.config.stopwords:
                continue
            
            # Skip if too short
            if len(token) < self.config.min_keyword_length:
                continue
            
            # Add keyword (preserve original case)
            seen.add(token_lower)
            keywords.append(token)
            
            # Stop if we have enough
            if len(keywords) >= self.config.max_keywords:
                break
        
        return keywords
    
    def add_stopwords(self, words: Set[str]) -> None:
        """Add words to stopword set.
        
        Args:
            words: Set of words to add
        """
        self.config.stopwords.update(words)
    
    def remove_stopwords(self, words: Set[str]) -> None:
        """Remove words from stopword set.
        
        Args:
            words: Set of words to remove
        """
        self.config.stopwords -= words


def create_query_processor(
    stopwords: Optional[Set[str]] = None,
    min_keyword_length: int = 1,
    max_keywords: int = 20,
    enable_filter_parsing: bool = True
) -> QueryProcessor:
    """Factory function to create QueryProcessor.
    
    Args:
        stopwords: Custom stopwords set. Uses default if None.
        min_keyword_length: Minimum keyword length
        max_keywords: Maximum keywords to extract
        enable_filter_parsing: Whether to parse filter syntax
        
    Returns:
        Configured QueryProcessor instance
    """
    config = QueryProcessorConfig(
        stopwords=stopwords if stopwords is not None else DEFAULT_STOPWORDS.copy(),
        min_keyword_length=min_keyword_length,
        max_keywords=max_keywords,
        enable_filter_parsing=enable_filter_parsing
    )
    return QueryProcessor(config)
"""
为什么要这么做
混合检索两条路吃的东西不一样：

Dense：吃整句，需要语义（「如何配置 Azure」也能对上「Azure 部署步骤」）
BM25：吃词，停用词和疑问词几乎没区分度，「如何」「的」「the」进索引只会稀释专有名词
所以查询侧要做一次拆零件：原句给向量，关键词给 BM25，collection: 给过滤。这是为了两路各吃各的，不是为了把问题「写得更漂亮」。

面试问答
Q1：Query Processor 是干什么的？是不是 Query Rewrite？
A：是查询预处理，不是 LLM 改写。做分词、去停用词、解析 key:value 过滤。输出 original_query、keywords、filters。Rewrite/HyDE 是另一层，本项目没做。

Q2：为什么不把原句直接丢给 BM25？
A：BM25 靠词频和 IDF。疑问词、助词 df 极高、IDF 低，还会占掉有效词。抽关键词后，「Azure」「OpenAI」「配置」权重更突出，专有名词召回更好。向量那路仍用原句，语义不丢。

Q3：为什么查询分词要用 jieba？
A：入库 SparseEncoder 也是 jieba。查询和索引必须同一套切词，否则「OpenAI」一边切成一个词、一边切碎，BM25 对不上。

Q4：去停用词会不会误伤？
A：会，所以停用词要可控（add_stopwords/remove_stopwords）。专有名词、API 名不在表里会保留。Dense 仍用原句，即使关键词抽漏了，语义检索还能补。

Q5：collection:docs 这种 filter 为什么放在 Processor 里？
A：这是检索约束，不是语义的一部分。提前剥掉，避免「collection」被当成关键词去搜；同时让下游只在指定集合里查，减少噪音。

Q6：为什么不用 LLM 做预处理？
A：规则确定、便宜、稳定、可测。LLM 改写有延迟、不稳定、可能改偏。本项目原则是 rule-based first，LLM 留给 caption/refine/rerank 等收益更大的地方。

Q7：和 Hybrid Search 怎么配合？
A：Processor 输出 → Dense 用 original_query 向量化 → Sparse 用 keywords 查倒排 → RRF 融合。Processor 不打分，只准备输入。

Q8：一句话总结设计理由？
A：让稀疏检索吃「有区分度的词」，让稠密检索吃「完整语义」，让过滤条件从问句里剥离——用很小的规则成本，把混合检索两路的输入对齐好。


"""
