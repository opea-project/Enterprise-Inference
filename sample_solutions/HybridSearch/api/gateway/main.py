"""
Gateway Service
Main API orchestrator for the hybrid search system
"""

import logging
import time
import os
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from config import settings
from services.complexity_detector import ComplexityDetector
from services.orchestrator import ServiceOrchestrator
from services.query_analyzer import QueryAnalyzer
from services.filter_extractor import FilterExtractor
from services.auth import get_current_user

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Gateway Service",
    description="Main API gateway for hybrid search RAG system",
    version="1.0.0"
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS (environment-based)
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
complexity_detector = ComplexityDetector()
orchestrator = ServiceOrchestrator(
    retrieval_service_url=settings.retrieval_service_url,
    llm_service_url=settings.llm_service_url,
    embedding_service_url=getattr(settings, 'embedding_service_url', None),
    ingestion_service_url=getattr(settings, 'ingestion_service_url', None)
)
query_analyzer = QueryAnalyzer()
filter_extractor = FilterExtractor(
    llm_service_url=settings.llm_service_url
)


# Request/Response Models
MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "5000"))

class QueryRequest(BaseModel):
    """
    Request model for main query endpoint.
    
    Attributes:
        query (str): The user's natural language query.
        top_k_results (int): Number of context chunks to retrieve (1-50).
        force_model (Optional[str]): Force a specific processing strategy ('simple', 'complex').
        include_debug_info (bool): Whether to include detailed execution metadata in response.
    """
    query: str = Field(..., description="User query", min_length=1, max_length=MAX_QUERY_LENGTH)
    top_k_results: int = Field(10, description="Number of results to retrieve", ge=1, le=50)
    force_model: Optional[str] = Field(
        None,
        description="Force specific model: 'simple', 'complex', or None for auto"
    )
    include_debug_info: bool = Field(False, description="Include debug information")
    
    @field_validator('query')
    @classmethod
    def validate_query_length(cls, v: str) -> str:
        """Validate query length"""
        if len(v) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters")
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the main differences between Product A and Product B?",
                "top_k_results": 10,
                "force_model": None,
                "include_debug_info": False
            }
        }


class QueryResponse(BaseModel):
    """
    Response model for query endpoint.
    
    Attributes:
        answer (str): The generated answer to the query.
        citations (list): List of sources used to generate the answer.
        confidence_score (float): Confidence score of the answer (0.0-1.0).
        query_complexity (str): Detected or forced complexity level ('simple', 'complex').
        llm_model (str): Name of the LLM model used for generation.
        retrieval_results_count (int): Number of results found in the retrieval step.
        processing_time_ms (float): Total time taken to process the query.
        debug_info (Optional[Dict]): Detailed execution metadata if requested.
    """
    answer: str
    citations: list
    confidence_score: float = 0.0
    query_complexity: str
    llm_model: str
    retrieval_results_count: int
    processing_time_ms: float
    debug_info: Optional[Dict] = None


class ProductSearchRequest(BaseModel):
    """
    Request model for product search.
    
    Attributes:
        query (str): Natural language search query.
        filters (Optional[Dict]): Explicit filters to apply (e.g., price, category).
        limit (int): Maximum number of results to return (1-100).
        offset (int): Pagination offset.
        explain (bool): Whether to generate an LLM explanation of the results.
    """
    query: str = Field(..., description="Search query", min_length=1)
    filters: Optional[Dict] = Field(None, description="Additional filters")
    limit: int = Field(20, description="Number of results", ge=1, le=100)
    offset: int = Field(0, description="Offset for pagination", ge=0)
    explain: bool = Field(True, description="Whether to generate LLM explanation")


class ProductSearchResponse(BaseModel):
    """
    Response model for product search.
    
    Attributes:
        query_interpretation (Dict): Analysis of the user's query (intent, entities).
        applied_filters (Dict): The final filters applied to the search.
        total_matches (int): Total number of matching products found.
        results (List[Dict]): List of product results.
        explanation (Optional[str]): Natural language explanation of the results.
        suggested_refinements (List[str]): Suggestions to narrow down search results.
    """
    query_interpretation: Dict
    applied_filters: Dict
    total_matches: int
    results: List[Dict]
    explanation: Optional[str] = None
    suggested_refinements: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """
    Health check response.
    
    Attributes:
        status (str): Status of the service ('healthy', etc.).
        service (str): Name of the service.
        deployment_phase (str): Current deployment environment.
    """
    status: str
    service: str
    deployment_phase: str


class ServiceHealthResponse(BaseModel):
    """
    Combined health check for all services.
    
    Attributes:
        gateway (str): Status of the gateway service.
        embedding (Dict): Status of the embedding service.
        retrieval (Dict): Status of the retrieval service.
        llm (Dict): Status of the LLM service.
        ingestion (Dict): Status of the ingestion service.
    """
    gateway: str
    embedding: Dict
    retrieval: Dict
    llm: Dict
    ingestion: Dict


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handle all unhandled exceptions globally.
    
    Args:
        request (Request): The incoming request that caused the error.
        exc (Exception): The unhandled exception.
        
    Returns:
        JSONResponse: A 500 Internal Server Error response with error details.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again later.",
            "type": type(exc).__name__
        }
    )


# API Endpoints
@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Main query endpoint",
    description="Process query through full RAG pipeline"
)
@limiter.limit("100/minute")
async def process_query(request: Request, query_data: QueryRequest, user: dict = Depends(get_current_user)):
    """
    Process query through the complete RAG pipeline:
    1. Detect query complexity
    2. Retrieve relevant context
    3. Generate answer with appropriate LLM
    4. Return answer with citations
    
    Args:
        request: FastAPI Request object (for rate limiting)
        query_data: QueryRequest with query and parameters
        
    Returns:
        QueryResponse with answer and metadata
    """
    try:
        start_time = time.time()
        debug_info = {}
        
        logger.info(f"Processing query: {query_data.query[:100]}")
        
        # 1. Detect query complexity
        complexity_result = complexity_detector.detect(query_data.query)
        query_complexity = query_data.force_model or complexity_result["complexity"]
        
        if query_data.include_debug_info:
            debug_info["complexity_detection"] = complexity_result
        
        logger.info(f"Query complexity: {query_complexity} ({complexity_result['reasoning']})")
        
        # 2. Retrieve relevant context
        retrieval_start = time.time()
        retrieval_response = await orchestrator.retrieve_context(
            query_data.query,
            top_k=query_data.top_k_results
        )
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        results = retrieval_response.get("results", [])
        
        if not results:
            logger.warning("No results found in retrieval")
            return QueryResponse(
                answer="I don't have enough information to answer this question.",
                citations=[],
                query_complexity=query_complexity,
                llm_model="none",
                retrieval_results_count=0,
                processing_time_ms=round((time.time() - start_time) * 1000, 2),
                debug_info=debug_info if query_data.include_debug_info else None
            )
        
        if query_data.include_debug_info:
            debug_info["retrieval"] = {
                "results_count": len(results),
                "retrieval_time_ms": round(retrieval_time, 2),
                "top_scores": [r.get("score", 0) for r in results[:3]]
            }
        
        # 3. Generate answer
        llm_start = time.time()
        llm_response = await orchestrator.generate_answer(
            query_data.query,
            results,
            model_type=query_complexity
        )
        llm_time = (time.time() - llm_start) * 1000
        
        if query_data.include_debug_info:
            debug_info["llm"] = {
                "model_used": llm_response.get("model_used"),
                "generation_time_ms": llm_response.get("generation_time_ms"),
                "token_count": llm_response.get("token_count")
            }
        
        # Calculate total processing time
        total_time = (time.time() - start_time) * 1000
        
        logger.info(
            f"Query completed in {total_time:.2f}ms "
            f"(retrieval: {retrieval_time:.2f}ms, llm: {llm_time:.2f}ms)"
        )
        
        return QueryResponse(
            answer=llm_response.get("answer", ""),
            citations=llm_response.get("citations", []),
            query_complexity=llm_response.get("query_type", query_complexity),
            llm_model=llm_response.get("model_used", ""),
            retrieval_results_count=len(results),
            processing_time_ms=round(total_time, 2),
            debug_info=debug_info if query_data.include_debug_info else None
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@app.post(
    "/api/v1/query/explain",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query with explanation",
    description="Process query and include debug information"
)
@limiter.limit("50/minute")
async def process_query_with_explanation(request: Request, query_data: QueryRequest, user: dict = Depends(get_current_user)):
    """
    Process query with debug information enabled (Explanation mode).
    
    This endpoint behaves like /query but forces debug_info to be included,
    which provides insights into the retrieval and ranking process.

    Args:
        request (Request): FastAPI Request object.
        query_data (QueryRequest): Query parameters.
        user (dict): Authenticated user context.

    Returns:
        QueryResponse: Response with detailed debug information/explanation.
    """
    query_data.include_debug_info = True
    return await process_query(request, query_data)


@app.post(
    "/api/v1/search",
    response_model=ProductSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Product search",
    description="Search products with natural language queries and filters"
)
@limiter.limit("100/minute")
async def search_products(request: Request, search_data: ProductSearchRequest, user: dict = Depends(get_current_user)):
    """
    Search products with natural language queries and dynamic filtering.
    
    1. Extracts filters from the natural language query.
    2. Analyzes query intent.
    3. Performs hybrid search on the product catalog.
    4. Optionally generates an LLM explanation of why results match.
    
    Args:
        request (Request): FastAPI Request object (rate limiting).
        search_data (ProductSearchRequest): Search query and manual filters.
        user (dict): Authenticated user context.
        
    Returns:
        ProductSearchResponse: Search results, extracted filters, and metadata.
        
    Raises:
        HTTPException: If search fails or downstream services are unavailable.
    """
    try:
        start_time = time.time()
        
        logger.info(f"Processing product search: {search_data.query[:100]}")
        
        # Get catalog info to extract known categories
        catalog_info = await orchestrator.get_catalog_info()
        known_categories = catalog_info.get('categories', []) if catalog_info.get('loaded') else []
        
        # Extract filters from query
        extracted_filters = await filter_extractor.extract_async(
            search_data.query,
            known_categories=known_categories,
            use_llm_fallback=True
        )
        
        # Merge with provided filters (provided filters take precedence)
        applied_filters = extracted_filters.copy()
        if search_data.filters:
            applied_filters.update(search_data.filters)
        
        # Analyze query intent
        query_analysis = query_analyzer.analyze(search_data.query, applied_filters)
        
        # Search products
        search_results = await orchestrator.search_products(
            query=query_analysis['semantic_query'],
            filters=applied_filters,
            limit=search_data.limit,
            offset=search_data.offset
        )
        
        # Generate explanation if requested
        explanation = None
        if search_data.explain and search_results.get('results'):
            # Call LLM for explanation
            try:
                llm_response = await orchestrator.generate_answer(
                    query=search_data.query,
                    context_chunks=search_results.get('results', [])[:5],  # Use top 5 for context
                    model_type='simple'
                )
                explanation = llm_response.get('answer', '')
            except Exception as e:
                logger.warning(f"Failed to generate explanation: {e}")
        
        # Generate suggested refinements
        suggested_refinements = []
        if search_results.get('total_matches', 0) > search_data.limit:
            if not applied_filters.get('categories') and known_categories:
                suggested_refinements.append(f"Try filtering by {known_categories[0]}")
            if not applied_filters.get('price_max'):
                suggested_refinements.append("Narrow by price range")
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(f"Product search completed in {processing_time:.2f}ms")
        
        return ProductSearchResponse(
            query_interpretation={
                "semantic_query": query_analysis['semantic_query'],
                "extracted_filters": extracted_filters,
                "intent": query_analysis['intent']
            },
            applied_filters=applied_filters,
            total_matches=search_results.get('total_matches', len(search_results.get('results', []))),
            results=search_results.get('results', []),
            explanation=explanation,
            suggested_refinements=suggested_refinements
        )
        
    except Exception as e:
        logger.error(f"Error processing product search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Product search failed: {str(e)}"
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check"
)
async def health_check():
    """
    Gateway health check endpoint.
    
    Returns:
        HealthResponse: Status of the gateway service itself.
    """
    return HealthResponse(
        status="healthy",
        service="gateway",
        deployment_phase=settings.deployment_phase
    )


@app.get(
    "/api/v1/health/services",
    response_model=ServiceHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check all services health",
    description="Check health of all backend services"
)
async def check_all_services():
    """
    Check health of all connected backend services.
    
    Queries the health endpoints of Embedding, Retrieval, LLM, and Ingestion services.
    
    Returns:
        ServiceHealthResponse: Aggregate status of all services.
    """
    embedding_health = await orchestrator.check_service_health(settings.embedding_service_url)
    retrieval_health = await orchestrator.check_service_health(settings.retrieval_service_url)
    llm_health = await orchestrator.check_service_health(settings.llm_service_url)
    ingestion_health = await orchestrator.check_service_health(settings.ingestion_service_url)
    
    return ServiceHealthResponse(
        gateway="healthy",
        embedding=embedding_health,
        retrieval=retrieval_health,
        llm=llm_health,
        ingestion=ingestion_health
    )


@app.get("/", summary="Root endpoint")
async def root():
    """
    Root endpoint with service information.
    
    Returns:
        dict: Basic service info including version and status.
    """
    return {
        "service": "Gateway Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "deployment_phase": settings.deployment_phase
    }


# Application startup
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Gateway Service on {settings.gateway_host}:{settings.gateway_port}")
    logger.info(f"Deployment phase: {settings.deployment_phase}")
    logger.info(f"Embedding service: {settings.embedding_service_url}")
    logger.info(f"Retrieval service: {settings.retrieval_service_url}")
    logger.info(f"LLM service: {settings.llm_service_url}")
    logger.info(f"Ingestion service: {settings.ingestion_service_url}")
    
    uvicorn.run(
        app,
        host=settings.gateway_host,  # nosec B104 - Binding to all interfaces is intentional for Docker container
        port=settings.gateway_port,
        log_level=settings.log_level.lower()
    )

