"""
Embedding Service - OpenAI API Wrapper
Generates vector embeddings for documents and queries
"""

import logging
import time
import math
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI, OpenAIError, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from config import settings

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Embedding Service",
    description="OpenAI-powered embedding generation service",
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

# Initialize GenAI Gateway API client
try:
    from api_client import get_api_client

    api_client = get_api_client()

    if not api_client.is_authenticated():
        raise RuntimeError("GenAI Gateway authentication failed - cannot start service without API access")

    client = api_client.get_embedding_client()
    logger.info("✓ GenAI Gateway API client initialized successfully")
    logger.info(f"  Model: {settings.embedding_model_name}")
    logger.info(f"  Authentication: GenAI Gateway API Key")
    logger.info(f"  Base URL: {settings.genai_gateway_url}")

except Exception as e:
    logger.error(f"Failed to initialize GenAI Gateway API client: {e}")
    logger.error("Service requires GenAI Gateway authentication and endpoints")
    raise RuntimeError(f"GenAI Gateway API initialization failed: {e}") from e

# Request/Response Models
class EmbeddingRequest(BaseModel):
    """
    Request model for embedding generation.
    
    Attributes:
        texts (List[str]): List of input text strings to embed.
        normalize (bool): Whether to apply L2 normalization to the embeddings.
    """
    texts: List[str] = Field(..., description="List of texts to embed", min_length=1)
    normalize: bool = Field(True, description="Whether to L2 normalize embeddings")
    
    class Config:
        json_schema_extra = {
            "example": {
                "texts": ["What is artificial intelligence?", "Machine learning basics"],
                "normalize": True
            }
        }


class EmbeddingResponse(BaseModel):
    """
    Response model for embedding generation.
    
    Attributes:
        embeddings (List[List[float]]): The generated vector embeddings.
        model (str): The name of the model used.
        dimensions (int): The dimension size of the embeddings.
        processing_time_ms (float): Time taken to generate embeddings in milliseconds.
        text_count (int): The number of texts processed.
    """
    embeddings: List[List[float]] = Field(..., description="Generated embeddings")
    model: str = Field(..., description="Model used for embedding")
    dimensions: int = Field(..., description="Embedding dimensions")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    text_count: int = Field(..., description="Number of texts processed")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    deployment_phase: str
    model: str
    dimensions: int


class ModelInfoResponse(BaseModel):
    """Model information response"""
    model: str
    dimensions: int
    max_input_length: int
    batch_size: int


# Retry Configuration for OpenAI API
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def _call_embeddings_api(
    texts: List[str],
    model: str,
):
    """
    Call embeddings API with retry logic

    Args:
        texts: List of texts to embed
        model: Model name

    Returns:
        Embeddings response

    Raises:
        OpenAIError: If all retries fail
    """
    try:
        return client.embeddings.create(
            model=model,
            input=texts,
        )
    except (RateLimitError, APIConnectionError, APITimeoutError) as e:
        logger.warning(f"API error (will retry): {type(e).__name__}: {e}")
        raise
    except OpenAIError as e:
        # Don't retry on other errors (invalid request, etc.)
        logger.error(f"API error (non-retryable): {e}")
        raise


# API Endpoints
@app.post(
    "/api/v1/embeddings/encode",
    response_model=EmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate embeddings for texts",
    description="Generate vector embeddings for one or more texts using OpenAI API"
)
async def encode_embeddings(request: EmbeddingRequest):
    """
    Generate embeddings for the provided texts.
    
    Args:
        request (EmbeddingRequest): The request containing texts to embed.
        
    Returns:
        EmbeddingResponse: Object containing generated embeddings and metadata.
        
    Raises:
        HTTPException: If input validation fails or external API errors occur.
    """
    try:
        start_time = time.time()
        
        # Validate batch size
        if len(request.texts) > settings.embedding_batch_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch size exceeds maximum of {settings.embedding_batch_size}"
            )
        
        # Validate text lengths
        for idx, text in enumerate(request.texts):
            if not text.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Text at index {idx} is empty"
                )
        
        logger.info(f"Generating embeddings for {len(request.texts)} texts")

        # Use GenAI Gateway via OpenAI client
        model_name = settings.embedding_model_name

        # Call API with retry logic
        response = _call_embeddings_api(
            texts=request.texts,
            model=model_name,
        )

        # Extract embeddings
        raw_embeddings = [item.embedding for item in response.data]
        dimensions = len(raw_embeddings[0]) if raw_embeddings else 768

        # Sanitize embeddings
        embeddings = []
        for embedding in raw_embeddings:
            sanitized_embedding = []
            for val in embedding:
                if math.isnan(val) or math.isinf(val):
                    sanitized_embedding.append(0.0)
                else:
                    sanitized_embedding.append(val)
            embeddings.append(sanitized_embedding)

        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000

        logger.info(
            f"Successfully generated {len(embeddings)} embeddings "
            f"in {processing_time:.2f}ms (dimensions={dimensions})"
        )
        
        return EmbeddingResponse(
            embeddings=embeddings,
            model=model_name,
            dimensions=dimensions,
            processing_time_ms=round(processing_time, 2),
            text_count=len(request.texts)
        )
        
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OpenAI API error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.post(
    "/api/v1/embeddings/encode-batch",
    response_model=EmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate embeddings in batch",
    description="Alias for /encode endpoint for batch processing"
)
async def encode_batch(request: EmbeddingRequest):
    """
    Generate embeddings for multiple texts (alias for encode endpoint).
    
    This is functionally identical to /encode but provides a clearer
    endpoint name for explicit batch operations.

    Args:
        request (EmbeddingRequest): The request containing texts to embed.

    Returns:
        EmbeddingResponse: Object containing generated embeddings and metadata.
    """
    return await encode_embeddings(request)


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check if the embedding service is healthy"
)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        HealthResponse: Status of the service and configuration details.
    """
    if settings.is_enterprise_configured():
        model_name = settings.embedding_model_name
        dimensions = 768  # BGE default
    else:
        model_name = "N/A"
        dimensions = 0
    
    return HealthResponse(
        status="healthy",
        service="embedding",
        deployment_phase=settings.deployment_phase,
        model=model_name,
        dimensions=dimensions
    )


@app.get(
    "/api/v1/embeddings/model-info",
    response_model=ModelInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get model information",
    description="Get information about the embedding model being used"
)
async def get_model_info():
    """
    Get embedding model information.
    
    Returns:
        ModelInfoResponse: Details about the model, dimensions, and limits.
    """
    if settings.is_enterprise_configured():
        model_name = settings.embedding_model_name
        dimensions = 768  # BGE default
    else:
        model_name = "N/A"
        dimensions = 0
    
    return ModelInfoResponse(
        model=model_name,
        dimensions=dimensions,
        max_input_length=settings.embedding_max_length,
        batch_size=settings.embedding_batch_size
    )


@app.get(
    "/",
    summary="Root endpoint",
    description="Service information"
)
async def root():
    """
    Root endpoint with service information.
    
    Returns:
        dict: Basic service info including version and status.
    """
    return {
        "service": "Embedding Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


# Application startup
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Embedding Service on {settings.embedding_host}:{settings.embedding_port}")
    logger.info(f"Deployment phase: {settings.deployment_phase}")
    
    if settings.is_enterprise_configured():
        logger.info("Provider: GenAI Gateway")
        logger.info(f"Model: {settings.embedding_model_name}")
        logger.info("Dimensions: 768 (BGE default)")
    else:
        logger.warning("Provider: Not configured (GenAI Gateway required)")
    
    uvicorn.run(
        app,
        host=settings.embedding_host,  # nosec B104 - Binding to all interfaces is intentional for Docker container
        port=settings.embedding_port,
        log_level=settings.log_level.lower()
    )

