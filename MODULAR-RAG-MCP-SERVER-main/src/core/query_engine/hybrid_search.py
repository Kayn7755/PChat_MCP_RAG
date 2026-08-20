"""混合搜索引擎，通过 RRF 融合技术协调密集检索和稀疏检索。
混合检索总编排器：把前面讲过的 QueryProcessor、Dense、Sparse、RRF 串成一条完整查询链路。MCP 的 query_knowledge_hub 最终会走到这里。

本模块实现了 HybridSearch 类，该类结合了以下组件：
1. QueryProcessor：预处理查询并提取关键词/过滤器
2. DenseRetriever：使用词嵌入进行语义搜索
3. SparseRetriever：使用 BM25 进行关键词搜索
4. RRFFusion：使用互惠排名融合技术合并搜索结果

设计原则：
- 优雅降级：如果一条检索路径失败，则回退到另一条
- 可插拔：所有组件均通过构造函数注入，便于测试
- 可观察：集成 TraceContext，便于调试和监控
- 配置驱动：Top-k 和其他参数从设置中读取

流程: 
用户问题
   │
   ▼
1. QueryProcessor → original_query + keywords + filters
   │
   ▼
2. 并行（默认）Dense + Sparse
   │     Dense ← 原句
   │     Sparse ← keywords
   │
   ▼
3. 一路失败 → 只用另一路（优雅降级）
   两路都有 → RRFFusion 融合
   │
   ▼
4. 可选：融合后再按 metadata 过滤
   │
   ▼
5. 截断到 fusion_top_k → 返回 List[RetrievalResult]
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from src.core.types import ProcessedQuery, RetrievalResult

if TYPE_CHECKING:
    from src.core.query_engine.dense_retriever import DenseRetriever
    from src.core.query_engine.fusion import RRFFusion
    from src.core.query_engine.query_processor import QueryProcessor
    from src.core.query_engine.sparse_retriever import SparseRetriever
    from src.core.settings import Settings

logger = logging.getLogger(__name__)


def _snapshot_results(
    results: Optional[List[RetrievalResult]],
) -> List[Dict[str, Any]]:
    """Create a serialisable snapshot of retrieval results for trace storage.
        创建检索结果的可序列化快照以进行跟踪存储
    Args:
        results: List of RetrievalResult objects.

    Returns:
        List of dicts with chunk_id, score, full text, source.
    """
    if not results:
        return []
    return [
        {
            "chunk_id": r.chunk_id,
            "score": round(r.score, 4),
            "text": r.text or "",
            "source": r.metadata.get("source_path", r.metadata.get("source", "")),
        }
        for r in results
    ]

# 配置参数
@dataclass
class HybridSearchConfig:
    """Configuration for HybridSearch.
    
    Attributes:
        dense_top_k: Number of results from dense retrieval
        sparse_top_k: Number of results from sparse retrieval
        fusion_top_k: Final number of results after fusion
        enable_dense: Whether to use dense retrieval
        enable_sparse: Whether to use sparse retrieval
        parallel_retrieval: Whether to run retrievals in parallel
        metadata_filter_post: Apply metadata filters after fusion (fallback)
    """
    dense_top_k: int = 20 # Dense Retriever 返回多少候选结果
    sparse_top_k: int = 20 # Sparse检索返回数量
    fusion_top_k: int = 10 # 融合之后最终返回数量
    enable_dense: bool = True
    enable_sparse: bool = True
    parallel_retrieval: bool = True
    metadata_filter_post: bool = True # 是否融合后再次过滤(先搜索数据库再过滤)

# 保存一次完整检索过程的信息
@dataclass
class HybridSearchResult:
    """Result of a hybrid search operation.
    
    Attributes:
        results: Final ranked list of RetrievalResults
        dense_results: Results from dense retrieval (for debugging)
        sparse_results: Results from sparse retrieval (for debugging)
        dense_error: Error message if dense retrieval failed
        sparse_error: Error message if sparse retrieval failed
        used_fallback: Whether fallback mode was used
        processed_query: The processed query (for debugging)
    """
    results: List[RetrievalResult] = field(default_factory=list)
    dense_results: Optional[List[RetrievalResult]] = None
    sparse_results: Optional[List[RetrievalResult]] = None
    dense_error: Optional[str] = None
    sparse_error: Optional[str] = None
    used_fallback: bool = False
    processed_query: Optional[ProcessedQuery] = None

# 混合检索核心类
class HybridSearch:
    """Hybrid Search Engine combining Dense and Sparse retrieval.
    
    此类编排完整的混合搜索流程：
        1.查询处理：从原始查询中提取关键字和过滤器
        2. 并行检索：同时运行密集和稀疏检索器
        3.融合：使用RRF算法合并结果
        4. 后过滤：应用元数据过滤器（如果指定）
    
    Design Principles Applied:
    - Graceful Degradation: If one path fails, use results from the other
    - Pluggable: All components via dependency injection
    - Observable: TraceContext support for debugging
    - Config-Driven: All parameters from settings
    
    Example:
        >>> # Initialize components
        >>> query_processor = QueryProcessor()
        >>> dense_retriever = DenseRetriever(settings, embedding_client, vector_store)
        >>> sparse_retriever = SparseRetriever(settings, bm25_indexer, vector_store)
        >>> fusion = RRFFusion(k=60)
        >>> 
        >>> # Create HybridSearch
        >>> hybrid = HybridSearch(
        ...     settings=settings,
        ...     query_processor=query_processor,
        ...     dense_retriever=dense_retriever,
        ...     sparse_retriever=sparse_retriever,
        ...     fusion=fusion
        ... )
        >>> 
        >>> # Search
        >>> results = hybrid.search("如何配置 Azure OpenAI？", top_k=10)
    """
    # 需要手动传入文件目录下的检索器, 方便替换
    def __init__(
        self,
        settings: Optional[Settings] = None,
        query_processor: Optional[QueryProcessor] = None,
        dense_retriever: Optional[DenseRetriever] = None,
        sparse_retriever: Optional[SparseRetriever] = None,
        fusion: Optional[RRFFusion] = None,
        config: Optional[HybridSearchConfig] = None,
    ) -> None:
        """Initialize HybridSearch with components.
        
        Args:
            settings: Application settings for extracting configuration.
            query_processor: QueryProcessor for preprocessing queries.
            dense_retriever: DenseRetriever for semantic search.
            sparse_retriever: SparseRetriever for keyword search.
            fusion: RRFFusion for combining results.
            config: Optional HybridSearchConfig. If not provided, extracted from settings.
        
        Note:
            At least one of dense_retriever or sparse_retriever must be provided
            for search to function. The search will gracefully degrade if one
            is unavailable or fails.
        """
        self.query_processor = query_processor
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.fusion = fusion
        
        # Extract config from settings or use provided/default
        self.config = config or self._extract_config(settings)
        
        logger.info(
            f"HybridSearch initialized: dense={self.dense_retriever is not None}, "
            f"sparse={self.sparse_retriever is not None}, "
            f"config={self.config}"
        )
    
    # 生成配置
    def _extract_config(self, settings: Optional[Settings]) -> HybridSearchConfig:
        """Extract HybridSearchConfig from Settings.
        
        Args:
            settings: Application settings object.
            
        Returns:
            HybridSearchConfig with values from settings or defaults.
        """
        if settings is None:
            return HybridSearchConfig()
        
        retrieval_config = getattr(settings, 'retrieval', None)
        if retrieval_config is None:
            return HybridSearchConfig()
        
        return HybridSearchConfig(
            dense_top_k=getattr(retrieval_config, 'dense_top_k', 20),
            sparse_top_k=getattr(retrieval_config, 'sparse_top_k', 20),
            fusion_top_k=getattr(retrieval_config, 'fusion_top_k', 10),
            enable_dense=True,
            enable_sparse=True,
            parallel_retrieval=True,
            metadata_filter_post=True,
        )
    
    # 核心检索方法
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        trace: Optional[Any] = None,
        return_details: bool = False,
    ) -> List[RetrievalResult] | HybridSearchResult:
        """Perform hybrid search combining Dense and Sparse retrieval.
        
        Args:
            查询：搜索查询字符串。
            top_k：返回的最大结果数。如果没有，则使用 config.fusion_top_k。
            过滤器：可选的元数据过滤器（例如，{“collection”：“docs”}）。
            跟踪：可选的 TraceContext 以实现可观察性。
            return_details：如果为 True，则返回带有调试信息的 
        
        Returns:
            If return_details=False: List of RetrievalResult sorted by relevance.
            If return_details=True: HybridSearchResult with full details.
        
        Raises:
            ValueError: If query is empty or invalid.
            RuntimeError: If both retrievers fail or are unavailable.
        
        Example:
            >>> results = hybrid.search("Azure configuration", top_k=5)
            >>> for r in results:
            ...     print(f"[{r.score:.4f}] {r.chunk_id}: {r.text[:50]}...")
        """
        # Validate query 防止空白问题
        if not query or not query.strip():
            raise ValueError("Query cannot be empty or whitespace-only")
        
        effective_top_k = top_k if top_k is not None else self.config.fusion_top_k
        
        logger.debug(f"HybridSearch: query='{query[:50]}...', top_k={effective_top_k}")
        
        # Step 1: Process query
        _t0 = time.monotonic()
        processed_query = self._process_query(query) # 使用QueryProcessor预处理问题
        _elapsed = (time.monotonic() - _t0) * 1000.0
        if trace is not None:
            trace.record_stage("query_processing", {
                "method": "query_processor",
                "original_query": query,
                "keywords": processed_query.keywords,
            }, elapsed_ms=_elapsed)
        
        # Merge explicit filters with query-extracted filters 合并过滤条件
        merged_filters = self._merge_filters(processed_query.filters, filters)
        
        # Step 2: Run retrievals 执行检索
        dense_results, sparse_results, dense_error, sparse_error = self._run_retrievals(
            processed_query=processed_query,
            filters=merged_filters,
            trace=trace,
        )
        
        # Step 3: Handle fallback scenarios 容错处理
        # dense出错就只用bm25
        used_fallback = False
        if dense_error and sparse_error:
            # Both failed - raise error
            raise RuntimeError(
                f"Both retrieval paths failed. "
                f"Dense error: {dense_error}. Sparse error: {sparse_error}"
            )
        elif dense_error:
            # Dense failed, use sparse only
            logger.warning(f"Dense retrieval failed, using sparse only: {dense_error}")
            used_fallback = True
            fused_results = sparse_results or []
        elif sparse_error:
            # Sparse failed, use dense only
            logger.warning(f"Sparse retrieval failed, using dense only: {sparse_error}")
            used_fallback = True
            fused_results = dense_results or []
        elif not dense_results and not sparse_results:
            # Both succeeded but returned empty
            fused_results = []
        else:
            # Step 4: Fuse results 开始融合
            fused_results = self._fuse_results(
                dense_results=dense_results or [],
                sparse_results=sparse_results or [],
                top_k=effective_top_k,
                trace=trace,
            )
        
        # Step 5: Apply post-fusion metadata filters (if any) 应用融合后元数据过滤器
        if merged_filters and self.config.metadata_filter_post:
            fused_results = self._apply_metadata_filters(fused_results, merged_filters)
        
        # Step 6: Limit to top_k
        final_results = fused_results[:effective_top_k]
        
        logger.debug(f"HybridSearch: returning {len(final_results)} results")
        
        if return_details:
            return HybridSearchResult(
                results=final_results,
                dense_results=dense_results,
                sparse_results=sparse_results,
                dense_error=dense_error,
                sparse_error=sparse_error,
                used_fallback=used_fallback,
                processed_query=processed_query,
            )
        
        return final_results
    
    # 通过QueryProcessor优化提问
    def _process_query(self, query: str) -> ProcessedQuery:
        """Process raw query using QueryProcessor.
        
        Args:
            query: Raw query string.
            
        Returns:
            ProcessedQuery with keywords and filters.
        """
        if self.query_processor is None:
            # Fallback: create basic ProcessedQuery
            logger.warning("No QueryProcessor configured, using basic tokenization")
            keywords = query.split()
            return ProcessedQuery(
                original_query=query,
                keywords=keywords,
                filters={},
            )
        
        return self.query_processor.process(query)
    
    # 把两处来源的过滤条件合成一份，供后面 Dense/Sparse/后过滤使用。
    # 来源1是QueryProcessor提取的过滤条件，来源2是调用 hybrid.search() 时多传的那个 filters= 参数(程序/工具参数里传入的 filter（参数，不是本模块里 LLM 的推断）)
    def _merge_filters(
        self,
        query_filters: Dict[str, Any],
        explicit_filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge query-extracted filters with explicit filters.
        
        Explicit filters take precedence over query-extracted filters.
        
        Args:
            query_filters: Filters extracted from query by QueryProcessor.
            explicit_filters: Filters passed explicitly to search().
            
        Returns:
            Merged filter dictionary.
        """
        merged = query_filters.copy() if query_filters else {}
        if explicit_filters:
            merged.update(explicit_filters) # 按 key 合并/覆盖,merged是字典(hash表)
        return merged
    
    # 执行检索 决定跑 Dense、Sparse 还是都跑，以及并行还是串行，最后返回四元组。
    def _run_retrievals(
        self,
        processed_query: ProcessedQuery,
        filters: Optional[Dict[str, Any]],
        trace: Optional[Any],
    ) -> Tuple[
        Optional[List[RetrievalResult]],
        Optional[List[RetrievalResult]],
        Optional[str],
        Optional[str],
    ]:
        """Run Dense and Sparse retrievals.
        
        Runs in parallel if configured, otherwise sequentially.
        
        Args:
            processed_query: The processed query with keywords.
            filters: Merged filters to apply.
            trace: Optional TraceContext.
            
        Returns:
            Tuple of (dense_results, sparse_results, dense_error, sparse_error).
        """
        dense_results: Optional[List[RetrievalResult]] = None
        sparse_results: Optional[List[RetrievalResult]] = None
        dense_error: Optional[str] = None
        sparse_error: Optional[str] = None
        
        # Determine what to run
        run_dense = (
            self.config.enable_dense 
            and self.dense_retriever is not None
        )
        run_sparse = (
            self.config.enable_sparse 
            and self.sparse_retriever is not None
            and processed_query.keywords  # Need keywords for sparse
        )
        
        if not run_dense and not run_sparse:
            # Nothing to run
            if self.dense_retriever is None and self.sparse_retriever is None:
                dense_error = "No retriever configured"
                sparse_error = "No retriever configured"
            return dense_results, sparse_results, dense_error, sparse_error
        
        if self.config.parallel_retrieval and run_dense and run_sparse:
            # Run in parallel
            dense_results, sparse_results, dense_error, sparse_error = (
                self._run_parallel_retrievals(processed_query, filters, trace)
            )
        else:
            # Run sequentially
            if run_dense:
                dense_results, dense_error = self._run_dense_retrieval(
                    processed_query.original_query, filters, trace
                )
            
            if run_sparse:
                sparse_results, sparse_error = self._run_sparse_retrieval(
                    processed_query.keywords, filters, trace
                )
        
        return dense_results, sparse_results, dense_error, sparse_error
    
    def _run_parallel_retrievals(
        self,
        processed_query: ProcessedQuery,
        filters: Optional[Dict[str, Any]],
        trace: Optional[Any],
    ) -> Tuple[
        Optional[List[RetrievalResult]],
        Optional[List[RetrievalResult]],
        Optional[str],
        Optional[str],
    ]:
        """Run Dense and Sparse retrievals in parallel using ThreadPoolExecutor.
        
        Args:
            processed_query: The processed query.
            filters: Filters to apply.
            trace: Optional TraceContext.
            
        Returns:
            Tuple of (dense_results, sparse_results, dense_error, sparse_error).
        """
        dense_results: Optional[List[RetrievalResult]] = None
        sparse_results: Optional[List[RetrievalResult]] = None
        dense_error: Optional[str] = None
        sparse_error: Optional[str] = None
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            
            # Submit dense retrieval
            futures['dense'] = executor.submit(
                self._run_dense_retrieval,
                processed_query.original_query,
                filters,
                trace,
            )
            
            # Submit sparse retrieval
            futures['sparse'] = executor.submit(
                self._run_sparse_retrieval,
                processed_query.keywords,
                filters,
                trace,
            )
            
            # Collect results
            for name, future in futures.items():
                try:
                    results, error = future.result(timeout=30)
                    if name == 'dense':
                        dense_results = results
                        dense_error = error
                    else:
                        sparse_results = results
                        sparse_error = error
                except Exception as e:
                    error_msg = f"{name} retrieval failed with exception: {e}"
                    logger.error(error_msg)
                    if name == 'dense':
                        dense_error = error_msg
                    else:
                        sparse_error = error_msg
        
        return dense_results, sparse_results, dense_error, sparse_error
    
    def _run_dense_retrieval(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        trace: Optional[Any],
    ) -> Tuple[Optional[List[RetrievalResult]], Optional[str]]:
        """Run dense retrieval with error handling.
        
        Args:
            query: Original query string.
            filters: Filters to apply.
            trace: Optional TraceContext.
            
        Returns:
            Tuple of (results, error). If successful, error is None.
        """
        if self.dense_retriever is None:
            return None, "Dense retriever not configured"
        
        try:
            _t0 = time.monotonic()
            results = self.dense_retriever.retrieve(
                query=query,
                top_k=self.config.dense_top_k,
                filters=filters,
                trace=trace,
            )
            _elapsed = (time.monotonic() - _t0) * 1000.0
            if trace is not None:
                trace.record_stage("dense_retrieval", {
                    "method": "dense",
                    "provider": getattr(self.dense_retriever, 'provider_name', 'unknown'),
                    "top_k": self.config.dense_top_k,
                    "result_count": len(results) if results else 0,
                    "chunks": _snapshot_results(results),
                }, elapsed_ms=_elapsed)
            return results, None
        except Exception as e:
            error_msg = f"Dense retrieval error: {e}"
            logger.error(error_msg)
            if trace is not None:
                trace.record_stage("dense_retrieval", {
                    "method": "dense",
                    "error": error_msg,
                    "result_count": 0,
                })
            return None, error_msg
    
    def _run_sparse_retrieval(
        self,
        keywords: List[str],
        filters: Optional[Dict[str, Any]],
        trace: Optional[Any],
    ) -> Tuple[Optional[List[RetrievalResult]], Optional[str]]:
        """Run sparse retrieval with error handling.
        
        Args:
            keywords: List of keywords from QueryProcessor.
            filters: Filters to apply.
            trace: Optional TraceContext.
            
        Returns:
            Tuple of (results, error). If successful, error is None.
        """
        if self.sparse_retriever is None:
            return None, "Sparse retriever not configured"
        
        if not keywords:
            return [], None  # No keywords, return empty (not an error)
        
        try:
            # Extract collection from filters if present
            collection = filters.get('collection') if filters else None
            
            _t0 = time.monotonic()
            results = self.sparse_retriever.retrieve(
                keywords=keywords,
                top_k=self.config.sparse_top_k,
                collection=collection,
                trace=trace,
            )
            _elapsed = (time.monotonic() - _t0) * 1000.0
            if trace is not None:
                trace.record_stage("sparse_retrieval", {
                    "method": "bm25",
                    "keyword_count": len(keywords),
                    "top_k": self.config.sparse_top_k,
                    "result_count": len(results) if results else 0,
                    "chunks": _snapshot_results(results),
                }, elapsed_ms=_elapsed)
            return results, None
        except Exception as e:
            error_msg = f"Sparse retrieval error: {e}"
            logger.error(error_msg)
            return None, error_msg
    
    # 融合结果 把 Dense、Sparse 两路结果合成一份总排名。优先用 RRF；没有 fusion 组件时用交错兜底。
    def _fuse_results(
        self,
        dense_results: List[RetrievalResult],
        sparse_results: List[RetrievalResult],
        top_k: int,
        trace: Optional[Any],
    ) -> List[RetrievalResult]:
        """Fuse Dense and Sparse results using RRF.
        
        Args:
            dense_results: Results from dense retrieval.
            sparse_results: Results from sparse retrieval.
            top_k: Number of results to return after fusion.
            trace: Optional TraceContext.
            
        Returns:
            Fused and ranked list of RetrievalResults.
        """
        if self.fusion is None:
            # Fallback: interleave results (simple round-robin)
            logger.warning("No fusion configured, using simple interleave")
            return self._interleave_results(dense_results, sparse_results, top_k)
        
        # Build ranking lists for RRF
        ranking_lists = []
        if dense_results:
            ranking_lists.append(dense_results)
        if sparse_results:
            ranking_lists.append(sparse_results)
        
        if not ranking_lists:
            return []
        
        if len(ranking_lists) == 1:
            # Only one source, no fusion needed
            return ranking_lists[0][:top_k]
        
        _t0 = time.monotonic()

        # 开始融合 , 使用query_engine.fusion import RRFFusion 里的 fuse 方法
        fused = self.fusion.fuse(
            ranking_lists=ranking_lists,
            top_k=top_k,
            trace=trace,
        )
        _elapsed = (time.monotonic() - _t0) * 1000.0
        if trace is not None:
            trace.record_stage("fusion", {
                "method": "rrf",
                "input_lists": len(ranking_lists),
                "top_k": top_k,
                "result_count": len(fused),
                "chunks": _snapshot_results(fused),
            }, elapsed_ms=_elapsed)
        return fused
    
    def _interleave_results(
        self,
        dense_results: List[RetrievalResult],
        sparse_results: List[RetrievalResult],
        top_k: int,
    ) -> List[RetrievalResult]:
        """Simple interleave fallback when no fusion is configured.
        
        Args:
            dense_results: Results from dense retrieval.
            sparse_results: Results from sparse retrieval.
            top_k: Maximum results to return.
            
        Returns:
            Interleaved results, deduped by chunk_id.
        """
        seen_ids = set()
        interleaved = []
        
        d_idx, s_idx = 0, 0
        while len(interleaved) < top_k and (d_idx < len(dense_results) or s_idx < len(sparse_results)):
            # Alternate between dense and sparse
            if d_idx < len(dense_results):
                r = dense_results[d_idx]
                d_idx += 1
                if r.chunk_id not in seen_ids:
                    seen_ids.add(r.chunk_id)
                    interleaved.append(r)
            
            if len(interleaved) >= top_k:
                break
            
            if s_idx < len(sparse_results):
                r = sparse_results[s_idx]
                s_idx += 1
                if r.chunk_id not in seen_ids:
                    seen_ids.add(r.chunk_id)
                    interleaved.append(r)
        
        return interleaved
    
    def _apply_metadata_filters(
        self,
        results: List[RetrievalResult],
        filters: Dict[str, Any],
    ) -> List[RetrievalResult]:
        """Apply metadata filters to results (post-fusion fallback).
        
        This is a backup filter mechanism for cases where the underlying
        storage doesn't fully support the filter syntax.
        
        Args:
            results: Results to filter.
            filters: Filter conditions to apply.
            
        Returns:
            Filtered results.
        """
        if not filters:
            return results
        
        filtered = []
        for result in results:
            if self._matches_filters(result.metadata, filters):
                filtered.append(result)
        
        return filtered
    
    def _matches_filters(
        self,
        metadata: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> bool:
        """Check if metadata matches all filter conditions.
        
        Args:
            metadata: Result metadata.
            filters: Filter conditions.
            
        Returns:
            True if all filters match, False otherwise.
        """
        for key, value in filters.items():
            if key == "collection":
                # Collection might be in different metadata keys
                meta_collection = (
                    metadata.get("collection") 
                    or metadata.get("source_collection")
                )
                if meta_collection != value:
                    return False
            elif key == "doc_type":
                if metadata.get("doc_type") != value:
                    return False
            elif key == "tags":
                # Tags is a list - check intersection
                meta_tags = metadata.get("tags", [])
                if not isinstance(value, list):
                    value = [value]
                if not set(meta_tags) & set(value):
                    return False
            elif key == "source_path":
                # Partial match for path
                source = metadata.get("source_path", "")
                if value not in source:
                    return False
            else:
                # Generic exact match
                if metadata.get(key) != value:
                    return False
        
        return True


# 工厂函数用于创建混合检索器
def create_hybrid_search(
    settings: Optional[Settings] = None,
    query_processor: Optional[QueryProcessor] = None,
    dense_retriever: Optional[DenseRetriever] = None,
    sparse_retriever: Optional[SparseRetriever] = None,
    fusion: Optional[RRFFusion] = None,
) -> HybridSearch:
    """Factory function to create HybridSearch with default components.
    
    This is a convenience function that creates a HybridSearch with
    default RRFFusion if not provided.
    
    Args:
        settings: Application settings.
        query_processor: QueryProcessor instance.
        dense_retriever: DenseRetriever instance.
        sparse_retriever: SparseRetriever instance.
        fusion: RRFFusion instance. If None, creates default with k=60.
        
    Returns:
        Configured HybridSearch instance.
    
    Example:
        >>> hybrid = create_hybrid_search(
        ...     settings=settings,
        ...     query_processor=QueryProcessor(),
        ...     dense_retriever=dense_retriever,
        ...     sparse_retriever=sparse_retriever,
        ... )
    """
    # Create default fusion if not provided
    if fusion is None:
        from src.core.query_engine.fusion import RRFFusion
        rrf_k = 60
        if settings is not None:
            retrieval_config = getattr(settings, 'retrieval', None)
            if retrieval_config is not None:
                rrf_k = getattr(retrieval_config, 'rrf_k', 60)
        fusion = RRFFusion(k=rrf_k)
    
    return HybridSearch(
        settings=settings,
        query_processor=query_processor,
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        fusion=fusion,
    )
