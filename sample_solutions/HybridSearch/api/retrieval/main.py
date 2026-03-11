"""
Retrieval Service
Hybrid search with FAISS + BM25 + RRF
"""

import logging
import time
import httpx
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from config import settings
from services.dense_retrieval import DenseRetrieval
from services.sparse_retrieval import SparseRetrieval
from services.fusion import ReciprocalRankFusion

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Retrieval Service",
    description="Hybrid search with dense + sparse + reranking",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize retrieval components
dense_retrieval = DenseRetrieval(
    index_path=settings.faiss_index_path,
    metadata_path=settings.metadata_index_path
)

sparse_retrieval = SparseRetrieval(
    index_path=settings.bm25_index_path,
    metadata_path=settings.metadata_index_path
)

# Product retrieval components
product_dense_retrieval = DenseRetrieval(
    index_path=settings.product_faiss_index_path,
    metadata_path=settings.product_metadata_index_path
)

product_sparse_retrieval = SparseRetrieval(
    index_path=settings.product_bm25_index_path,
    metadata_path=settings.product_metadata_index_path
)

rrf_fusion = ReciprocalRankFusion(k=settings.rrf_k)


# Request/Response Models
class HybridRetrievalRequest(BaseModel):
    """
    Request model for hybrid retrieval.
    
    Attributes:
        query: Search query string.
        top_k_candidates: Number of candidates to fetch from each method (dense/sparse) before fusion.
        top_k_fusion: Number of top results to keep after Reciprocal Rank Fusion.
        top_k_final: Number of final results to return after reranking (if enabled).
    """
    query: str = Field(..., description="Query string")
    top_k_candidates: int = Field(
        100,
        description="Number of candidates per method before fusion"
    )
    top_k_fusion: int = Field(
        50,
        description="Number of results after RRF fusion"
    )
    top_k_final: int = Field(
        10,
        description="Number of final results after reranking"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the key findings?",
                "top_k_candidates": 100,
                "top_k_fusion": 50,
                "top_k_final": 10
            }
        }


class RetrievalResult(BaseModel):
    """
    Single retrieval result model.
    
    Attributes:
        chunk_id: Unique chunk identifier.
        document_id: Parent document identifier.
        text: Text content of the chunk.
        page_number: Page number (optional).
        score: Relevance score (from fusion or reranking).
        rank: Final rank position (1-based).
        retrieval_method: Method that found this result (e.g., 'hybrid', 'dense', 'sparse').
        metadata: Additional metadata dictionary.
    """
    chunk_id: str
    document_id: str
    text: str
    page_number: Optional[int] = None
    score: float
    rank: int
    retrieval_method: str
    metadata: Dict[str, Any] = {}


class HybridRetrievalResponse(BaseModel):
    """
    Response model for hybrid retrieval.
    
    Attributes:
        results: List of ranked retrieval results.
        retrieval_time_ms: Total retrieval time.
        dense_time_ms: Time taken for dense search phase.
        sparse_time_ms: Time taken for sparse search phase.
        fusion_time_ms: Time taken for fusion phase.
        query: Original query.
        total_candidates: Total raw candidates found before fusion.
    """
    results: List[RetrievalResult]
    retrieval_time_ms: float
    dense_time_ms: float
    sparse_time_ms: float
    fusion_time_ms: float
    query: str
    total_candidates: int


class IndexStats(BaseModel):
    """Index statistics"""
    dense_stats: Dict
    sparse_stats: Dict
    deployment_phase: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    deployment_phase: str
    indexes_loaded: Dict[str, bool]


class ProductSearchRequest(BaseModel):
    """Request model for product search"""
    query_embedding: Optional[List[float]] = Field(None, description="Pre-computed query embedding")
    query_text: str = Field(..., description="Query text for BM25")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Product filters")
    top_k: int = Field(20, description="Number of results to return", ge=1, le=100)


class ProductSearchResponse(BaseModel):
    """
    Response model for product search.
    
    Attributes:
        results: List of product dictionaries.
        total_matches: Total number of matches found.
        retrieval_time_ms: Time taken for search in milliseconds.
    """
    results: List[Dict]
    total_matches: int
    retrieval_time_ms: float


# Helper Functions
async def get_query_embedding(query: str) -> List[float]:
    """
    Get query embedding from embedding service.
    
    Args:
        query (str): Query string to encode.
        
    Returns:
        List[float]: Query embedding vector.
        
    Raises:
        httpx.HTTPError: If embedding service is unreachable or returns error.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.embedding_service_url}/api/v1/embeddings/encode",
            json={"texts": [query], "normalize": True}
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]


# API Endpoints
@app.post(
    "/api/v1/retrieve/hybrid",
    response_model=HybridRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid search",
    description="Search using dense + sparse + fusion + reranking"
)
async def hybrid_search(request: HybridRetrievalRequest):
    """
    Perform hybrid search using Dense + Sparse + Fusion + Reranking.
    
    Orchestrates the retrieval pipeline:
    1. Generates query embedding.
    2. Runs parallel dense (FAISS) and sparse (BM25) searches.
    3. Fuses results using Reciprocal Rank Fusion (RRF).
    4. Optionally reranks top results using a cross-encoder model.
    
    Args:
        request (HybridRetrievalRequest): Search parameters.
        
    Returns:
        HybridRetrievalResponse: Ranked search results and timing metrics.
        
    Raises:
        HTTPException: If search fails.
    """
    try:
        start_time = time.time()
        
        logger.info(f"Hybrid search query: {request.query[:100]}")
        
        # Get query embedding
        query_embedding = await get_query_embedding(request.query)
        
        # Dense retrieval
        dense_start = time.time()
        dense_results = dense_retrieval.search(
            query_embedding,
            top_k=request.top_k_candidates
        )
        dense_time = (time.time() - dense_start) * 1000
        
        # Sparse retrieval
        sparse_start = time.time()
        sparse_results = sparse_retrieval.search(
            request.query,
            top_k=request.top_k_candidates
        )
        sparse_time = (time.time() - sparse_start) * 1000
        
        # Fusion
        fusion_start = time.time()
        fused_results = rrf_fusion.fuse(
            dense_results,
            sparse_results,
            top_k=request.top_k_fusion
        )
        
        # Reranking (enterprise cross-encoder)
        if settings.use_reranking:
            final_results = rrf_fusion.rerank(
                request.query,
                fused_results,
                top_k=request.top_k_final
            )
        else:
            final_results = fused_results[:request.top_k_final]
        
        fusion_time = (time.time() - fusion_start) * 1000
        
        # Calculate total time
        total_time = (time.time() - start_time) * 1000
        
        # Format results
        formatted_results = [
            RetrievalResult(**result) for result in final_results
        ]
        
        logger.info(
            f"Hybrid search completed: {len(formatted_results)} results in {total_time:.2f}ms "
            f"(dense: {dense_time:.2f}ms, sparse: {sparse_time:.2f}ms, fusion: {fusion_time:.2f}ms)"
        )
        
        return HybridRetrievalResponse(
            results=formatted_results,
            retrieval_time_ms=round(total_time, 2),
            dense_time_ms=round(dense_time, 2),
            sparse_time_ms=round(sparse_time, 2),
            fusion_time_ms=round(fusion_time, 2),
            query=request.query,
            total_candidates=len(dense_results) + len(sparse_results)
        )
        
    except Exception as e:
        logger.error(f"Error during hybrid search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid search failed: {str(e)}"
        )


@app.post(
    "/api/v1/retrieve/dense-only",
    response_model=HybridRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Dense search only",
    description="Search using only FAISS dense retrieval"
)
async def dense_only_search(request: HybridRetrievalRequest):
    """
    Perform dense-only search (FAISS).
    
    Used for testing or when keyword matching is not needed.
    
    Args:
        request (HybridRetrievalRequest): Search parameters.
        
    Returns:
        HybridRetrievalResponse: Dense search results.
    """
    try:
        start_time = time.time()
        
        query_embedding = await get_query_embedding(request.query)
        
        dense_start = time.time()
        dense_results = dense_retrieval.search(
            query_embedding,
            top_k=request.top_k_final
        )
        dense_time = (time.time() - dense_start) * 1000
        
        total_time = (time.time() - start_time) * 1000
        
        formatted_results = [
            RetrievalResult(**result) for result in dense_results
        ]
        
        return HybridRetrievalResponse(
            results=formatted_results,
            retrieval_time_ms=round(total_time, 2),
            dense_time_ms=round(dense_time, 2),
            sparse_time_ms=0,
            fusion_time_ms=0,
            query=request.query,
            total_candidates=len(dense_results)
        )
        
    except Exception as e:
        logger.error(f"Error during dense search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dense search failed: {str(e)}"
        )


@app.post(
    "/api/v1/retrieve/sparse-only",
    response_model=HybridRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Sparse search only",
    description="Search using only BM25 sparse retrieval"
)
async def sparse_only_search(request: HybridRetrievalRequest):
    """
    Perform sparse-only search (BM25).
    
    Used for testing or exact keyword matching.
    
    Args:
        request (HybridRetrievalRequest): Search parameters.
        
    Returns:
        HybridRetrievalResponse: Sparse search results.
    """
    try:
        start_time = time.time()
        
        sparse_start = time.time()
        sparse_results = sparse_retrieval.search(
            request.query,
            top_k=request.top_k_final
        )
        sparse_time = (time.time() - sparse_start) * 1000
        
        total_time = (time.time() - start_time) * 1000
        
        formatted_results = [
            RetrievalResult(**result) for result in sparse_results
        ]
        
        return HybridRetrievalResponse(
            results=formatted_results,
            retrieval_time_ms=round(total_time, 2),
            dense_time_ms=0,
            sparse_time_ms=round(sparse_time, 2),
            fusion_time_ms=0,
            query=request.query,
            total_candidates=len(sparse_results)
        )
        
    except Exception as e:
        logger.error(f"Error during sparse search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sparse search failed: {str(e)}"
        )


@app.get(
    "/api/v1/retrieve/stats",
    response_model=IndexStats,
    status_code=status.HTTP_200_OK,
    summary="Get index statistics"
)
async def get_stats():
    """
    Get retrieval index statistics.
    
    Returns:
        IndexStats: Statistics for both dense and sparse indexes.
    """
    return IndexStats(
        dense_stats=dense_retrieval.get_stats(),
        sparse_stats=sparse_retrieval.get_stats(),
        deployment_phase=settings.deployment_phase
    )


@app.post(
    "/api/v1/reload",
    status_code=status.HTTP_200_OK,
    summary="Reload indexes",
    description="Reload indexes from disk (useful after clearing or updating indexes)"
)
async def reload_indexes():
    """
    Reload all indexes from disk.
    
    Useful after clearing or re-ingesting data without restarting the service.
    
    Returns:
        dict: Status message and loaded index flags.
    """
    try:
        dense_retrieval.reload()
        sparse_retrieval.reload()
        product_dense_retrieval.reload()
        product_sparse_retrieval.reload()
        
        logger.info("Successfully reloaded all indexes")
        
        return {
            "message": "Indexes reloaded successfully",
            "status": "success",
            "indexes_loaded": {
                "dense": dense_retrieval.index is not None,
                "sparse": sparse_retrieval.bm25 is not None,
                "dense_vectors": dense_retrieval.index.ntotal if dense_retrieval.index else 0,
                "sparse_documents": len(sparse_retrieval.metadata),
                "product_dense": product_dense_retrieval.index is not None,
                "product_sparse": product_sparse_retrieval.bm25 is not None,
                "product_vectors": product_dense_retrieval.index.ntotal if product_dense_retrieval.index else 0
            }
        }
    except Exception as e:
        logger.error(f"Error reloading indexes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload indexes: {str(e)}"
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check"
)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="retrieval",
        deployment_phase=settings.deployment_phase,
        indexes_loaded={
            "dense": dense_retrieval.index is not None,
            "sparse": sparse_retrieval.bm25 is not None,
            "product_dense": product_dense_retrieval.index is not None,
            "product_sparse": product_sparse_retrieval.bm25 is not None
        }
    )


@app.post(
    "/api/v1/search/products",
    response_model=ProductSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Product search",
    description="Search products with filters using hybrid retrieval"
)
async def search_products(request: ProductSearchRequest):
    """
    Search products with filters using hybrid retrieval.
    
    Extends hybrid search to support product-specific metadata filtering
    and result formatting.
    
    Args:
        request (ProductSearchRequest): Query and filter parameters.
        
    Returns:
        ProductSearchResponse: Formatted product results.
    """
    try:
        start_time = time.time()
        
        logger.info(f"Product search: query='{request.query_text[:100]}', filters={request.filters}")
        
        # Get query embedding if not provided
        query_embedding = request.query_embedding
        if not query_embedding:
            query_embedding = await get_query_embedding(request.query_text)
        
        # Dense retrieval with filters (uses UNIFIED index, filter by content_type=product)
        dense_start = time.time()
        dense_results = dense_retrieval.search(
            query_embedding,
            top_k=request.top_k * 5,  # Get more candidates for filtering
            filters=request.filters,
            product_mode=True
        )
        dense_time = (time.time() - dense_start) * 1000
        
        # Sparse retrieval with filters (uses UNIFIED index, filter by content_type=product)
        sparse_start = time.time()
        sparse_results = sparse_retrieval.search(
            request.query_text,
            top_k=request.top_k * 5,  # Get more candidates for filtering
            filters=request.filters,
            product_mode=True
        )
        sparse_time = (time.time() - sparse_start) * 1000
        
        # Fusion with enrichment (product mode)
        fusion_start = time.time()
        fused_results = rrf_fusion.fuse(
            dense_results,
            sparse_results,
            top_k=request.top_k,
            product_mode=True,
            filters=request.filters
        )
        fusion_time = (time.time() - fusion_start) * 1000
        
        # Format results for products
        product_results = []
        for result in fused_results:
            metadata = result.get('metadata', {})
            product_id = metadata.get('product_id') or result.get('document_id')
            
            # Format as ProductSearchResult
            product_result = {
                "product_id": product_id,
                "name": metadata.get('name', ''),
                "description": (result.get('text', '') or metadata.get('description', ''))[:200],
                "category": metadata.get('category'),
                "price": metadata.get('price'),
                "rating": metadata.get('rating'),
                "review_count": metadata.get('review_count'),
                "image_url": metadata.get('image_url'),
                "relevance_score": result.get('relevance_score', result.get('rrf_score', 0.0)),
                "match_reasons": result.get('match_reasons', []),
                "attributes": {}  # Would be populated from product_attributes table
            }
            product_results.append(product_result)
        
        total_time = (time.time() - start_time) * 1000
        
        logger.info(
            f"Product search completed: {len(product_results)} results in {total_time:.2f}ms "
            f"(dense: {dense_time:.2f}ms, sparse: {sparse_time:.2f}ms, fusion: {fusion_time:.2f}ms)"
        )
        
        return ProductSearchResponse(
            results=product_results,
            total_matches=len(product_results),  # This would be calculated before filtering
            retrieval_time_ms=round(total_time, 2)
        )
        
    except Exception as e:
        logger.error(f"Error during product search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Product search failed: {str(e)}"
        )


@app.get("/", summary="Root endpoint")
async def root():
    """
    Root endpoint with service information.
    
    Returns:
        dict: Basic service info (version, status).
    """
    return {
        "service": "Retrieval Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


# Application startup
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Retrieval Service on {settings.retrieval_host}:{settings.retrieval_port}")
    logger.info(f"Deployment phase: {settings.deployment_phase}")
    logger.info(f"FAISS index: {settings.faiss_index_path}")
    logger.info(f"BM25 index: {settings.bm25_index_path}")
    
    uvicorn.run(
        app,
        host=settings.retrieval_host,  # nosec B104 - Binding to all interfaces is intentional for Docker container
        port=settings.retrieval_port,
        log_level=settings.log_level.lower()
    )

