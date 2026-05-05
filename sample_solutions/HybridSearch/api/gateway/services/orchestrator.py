"""
Service Orchestrator
Coordinates calls to all backend services
"""

import logging
import httpx
from typing import List, Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)


class ServiceOrchestrator:
    """
    Orchestrate calls to backend services.
    
    Manages communication with Retrieval, LLM, Embedding, and Ingestion services,
    handling retries, timeouts, and error propagation.
    """
    
    def __init__(
        self,
        retrieval_service_url: str,
        llm_service_url: str,
        embedding_service_url: str = None,
        ingestion_service_url: str = None
    ):
        """
        Initialize orchestrator.
        
        Args:
            retrieval_service_url (str): URL of retrieval service.
            llm_service_url (str): URL of LLM service.
            embedding_service_url (str, optional): URL of embedding service.
            ingestion_service_url (str, optional): URL of ingestion service.
        """
        self.retrieval_service_url = retrieval_service_url
        self.llm_service_url = llm_service_url
        self.embedding_service_url = embedding_service_url
        self.ingestion_service_url = ingestion_service_url
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def retrieve_context(
        self,
        query: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context for query with retry logic.
        
        Args:
            query (str): The search query.
            top_k (int): Number of results to retrieve.
            
        Returns:
            Dict[str, Any]: Dictionary with retrieval results and metadata.
            
        Raises:
            httpx.HTTPError: If retrieval service fails.
        """
        try:
            logger.info(f"Retrieving context for query: {query[:100]}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.retrieval_service_url}/api/v1/retrieve/hybrid",
                    json={
                        "query": query,
                        "top_k_candidates": 100,
                        "top_k_fusion": 50,
                        "top_k_final": top_k
                    }
                )
                response.raise_for_status()
                return response.json()
                
        except (httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(f"Retrieval service error (will retry): {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during retrieval: {e}")
            raise Exception(f"Retrieval failed: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def generate_answer(
        self,
        query: str,
        context_chunks: List[Dict],
        model_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Generate answer using LLM with retry logic.
        
        Args:
            query (str): The user query.
            context_chunks (List[Dict]): Retrieved context chunks to use as grounding.
            model_type (str): Model type strategy ('simple', 'complex', 'auto').
            
        Returns:
            Dict[str, Any]: Dictionary with generated answer, citations, and metadata.
            
        Raises:
            httpx.HTTPError: If LLM service fails.
        """
        try:
            logger.info(f"Generating answer using {model_type} model")
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.llm_service_url}/api/v1/llm/generate",
                    json={
                        "query": query,
                        "context_chunks": context_chunks,
                        "model_type": model_type,
                        "include_citations": True
                    }
                )
                response.raise_for_status()
                return response.json()
                
        except (httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(f"LLM service error (will retry): {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during answer generation: {e}")
            raise Exception(f"Answer generation failed: {str(e)}")
    
    async def check_service_health(self, service_url: str) -> Dict:
        """
        Check health of a downstream service.
        
        Args:
            service_url (str): Base URL of the service to check.
            
        Returns:
            Dict: Health status dictionary covering status and details.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{service_url}/health")
                response.raise_for_status()
                return {
                    "status": "healthy",
                    "details": response.json()
                }
        except Exception as e:
            logger.error(f"Health check failed for {service_url}: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def search_products(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search products with filters.
        
        Coordinates embedding generation (if needed) and calls retrieval service.
        
        Args:
            query (str): Search query.
            filters (Dict[str, Any]): Extracted filters to apply.
            limit (int): Max number of results.
            offset (int): Pagination offset.
            
        Returns:
            Dict[str, Any]: Product search results.
            
        Raises:
            Exception: If embedding or retrieval fails.
        """
        try:
            logger.info(f"Searching products: query='{query}', filters={filters}")
            
            # Get query embedding
            query_embedding = None
            if self.embedding_service_url:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.embedding_service_url}/api/v1/embeddings/encode",
                        json={"texts": [query], "normalize": True}
                    )
                    response.raise_for_status()
                    data = response.json()
                    # Extract first embedding from the list
                    embeddings = data.get("embeddings", [])
                    query_embedding = embeddings[0] if embeddings else None
            
            # Call retrieval service
            async with httpx.AsyncClient(timeout=60.0) as client:
                # retrieval service caps top_k at 100; guard here to avoid 422
                safe_top_k = min(limit * 5, 100)
                response = await client.post(
                    f"{self.retrieval_service_url}/api/v1/search/products",
                    json={
                        "query_embedding": query_embedding,
                        "query_text": query,
                        "filters": filters,
                        "top_k": safe_top_k
                    }
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Product search error: {e}")
            raise Exception(f"Product search failed: {str(e)}")
    
    async def get_catalog_info(self) -> Dict[str, Any]:
        """
        Get catalog information from ingestion service.
        
        Returns:
            Dict[str, Any]: Dictionary with catalog metadata (categories, sizes, etc.).
        """
        try:
            if not self.ingestion_service_url:
                return {"loaded": False, "error": "Ingestion service URL not configured"}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.ingestion_service_url}/api/v1/products/catalog/info"
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Error getting catalog info: {e}")
            return {"loaded": False, "error": str(e)}

