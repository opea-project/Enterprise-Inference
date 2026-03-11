"""
LLM Service - OpenAI API Wrapper for Question Answering
Handles dual-model routing for simple and complex queries
"""

import logging
import time
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
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
from services.response_formatter import ResponseFormatter
from prompts.product_prompts import ProductPrompts
from clean_monologue import clean_internal_monologue

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="LLM Service",
    description="OpenAI-powered question answering service with dual-model routing",
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

    client = api_client.get_inference_client()
    logger.info("✓ GenAI Gateway API client initialized successfully")
    logger.info(f"  Simple model: {settings.inference_model_name_simple}")
    logger.info(f"  Complex model: {settings.inference_model_name_complex}")
    logger.info(f"  Authentication: GenAI Gateway API Key")
    logger.info(f"  Base URL: {settings.genai_gateway_url}")

except Exception as e:
    logger.error(f"Failed to initialize GenAI Gateway API client: {e}")
    logger.error("Service requires GenAI Gateway authentication and endpoints")
    raise RuntimeError(f"GenAI Gateway API initialization failed: {e}") from e


# Load prompt templates
PROMPTS_DIR = Path(__file__).parent / "prompts"
SIMPLE_QA_PROMPT = (PROMPTS_DIR / "simple_qa.txt").read_text()
COMPLEX_QA_PROMPT = (PROMPTS_DIR / "complex_qa.txt").read_text()

# Initialize product response formatter
response_formatter = ResponseFormatter()
product_prompts = ProductPrompts()


# Request/Response Models
class RetrievalChunk(BaseModel):
    """
    Retrieved document chunk model.
    
    Attributes:
        chunk_id: Unique identifier for the chunk.
        document_id: ID of the parent document.
        text: Text content of the chunk.
        page_number: Page number (optional).
        score: Relevance score (similarity/ranking).
        metadata: Additional metadata dictionary.
    """
    chunk_id: str
    document_id: str
    text: str
    page_number: Optional[int] = None
    score: float
    metadata: Dict[str, Any] = {}


class Citation(BaseModel):
    """
    Citation model for generated answers.
    
    Attributes:
        document_id: ID of the cited document.
        page_number: Page number in the document (optional).
        chunk_id: ID of the specific chunk used.
        confidence_score: Relevance score of the chunk.
        relevant_text_snippet: Snippet of text justifying the citation.
    """
    document_id: str
    page_number: Optional[int] = None
    chunk_id: str
    confidence_score: float
    relevant_text_snippet: str


class LLMRequest(BaseModel):
    """Request model for LLM generation"""
    query: str = Field(..., description="User query")
    context_chunks: List[RetrievalChunk] = Field(
        ..., 
        description="Retrieved context chunks"
    )
    model_type: str = Field(
        "auto",
        description="Model type: 'simple', 'complex', or 'auto'"
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum tokens to generate (overrides defaults)"
    )
    temperature: Optional[float] = Field(
        None,
        description="Temperature for generation (overrides defaults)"
    )
    include_citations: bool = Field(
        True,
        description="Whether to extract citations from response"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the main findings?",
                "context_chunks": [
                    {
                        "chunk_id": "chunk_1",
                        "document_id": "doc_123",
                        "text": "The study found significant improvements...",
                        "page_number": 5,
                        "score": 0.92,
                        "metadata": {}
                    }
                ],
                "model_type": "auto",
                "include_citations": True
            }
        }


class LLMResponse(BaseModel):
    """
    Response model for LLM generation.
    
    Attributes:
        answer: Generated answer text.
        citations: List of citations supporting the answer.
        model_used: Name of the model used for generation.
        query_type: Detected complexity of the query ('simple' or 'complex').
        generation_time_ms: Time taken for generation in milliseconds.
        token_count: Total tokens used (if available).
    """
    answer: str
    citations: List[Citation]
    model_used: str
    query_type: str
    generation_time_ms: float
    token_count: Optional[int] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    deployment_phase: str
    models: Dict[str, str]


class ModelInfoResponse(BaseModel):
    """Model information response"""
    simple_model: str
    complex_model: str
    max_tokens_simple: int
    max_tokens_complex: int
    temperature_simple: float
    temperature_complex: float


# Helper Functions
def format_context(chunks: List[RetrievalChunk]) -> str:
    """
    Format retrieved chunks into a context string for the LLM.
    
    Args:
        chunks (List[RetrievalChunk]): List of retrieved document chunks.
        
    Returns:
        str: Formatted context string with document IDs and page numbers.
    """
    context_parts = []
    for idx, chunk in enumerate(chunks, 1):
        page_info = f" [Page {chunk.page_number}]" if chunk.page_number else ""
        context_parts.append(
            f"[{idx}] Document: {chunk.document_id}{page_info}\n{chunk.text}\n"
        )
    return "\n".join(context_parts)


def extract_citations(
    answer: str,
    context_chunks: List[RetrievalChunk]
) -> List[Citation]:
    """
    Extract citations from the answer text.
    
    Parses citations in formats like [Page X], [Page X-Y], [Doc ID, Page X]
    and maps them back to the original context chunks.
    
    Args:
        answer (str): Generated answer text.
        context_chunks (List[RetrievalChunk]): Original context chunks used for generation.
        
    Returns:
        List[Citation]: List of extracted citation objects.
    """
    citations = []
    
    # Pattern to match citations: [Page X], [Page X-Y], [Doc ID, Page X]
    citation_patterns = [
        r'\[Page (\d+)\]',
        r'\[Page (\d+)-(\d+)\]',
        r'\[([^,]+), Page (\d+)\]'
    ]
    
    # Track which chunks were cited
    cited_chunks = set()
    
    for i, pattern in enumerate(citation_patterns):
        matches = re.finditer(pattern, answer)
        for match in matches:
            try:
                # Extract page number based on pattern type
                if i == 0:  # [Page X]
                    page_num = int(match.group(1))
                elif i == 1:  # [Page X-Y]
                    page_num = int(match.group(1))  # Use start page
                elif i == 2:  # [Doc ID, Page X]
                    page_num = int(match.group(2))
                else:
                    continue
                
                # Find matching chunks
                for chunk in context_chunks:
                    if chunk.page_number == page_num and chunk.chunk_id not in cited_chunks:
                        # Extract snippet around the citation
                        snippet = chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text
                        
                        citations.append(Citation(
                            document_id=chunk.document_id,
                            page_number=chunk.page_number,
                            chunk_id=chunk.chunk_id,
                            confidence_score=chunk.score,
                            relevant_text_snippet=snippet
                        ))
                        cited_chunks.add(chunk.chunk_id)
                        break
            except (ValueError, IndexError, AttributeError):
                continue
    
    # If no explicit citations found, use top-3 chunks as implicit citations
    if not citations and context_chunks:
        for chunk in context_chunks[:3]:
            snippet = chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text
            citations.append(Citation(
                document_id=chunk.document_id,
                page_number=chunk.page_number,
                chunk_id=chunk.chunk_id,
                confidence_score=chunk.score,
                relevant_text_snippet=snippet
            ))
    
    return citations


def detect_query_complexity(query: str) -> str:
    """
    Detect if query is simple or complex based on keywords and heuristics.
    
    Simple queries (fact retrieval) use smaller models.
    Complex queries (analysis, comparison) use reasoning models.
    
    Args:
        query (str): User query string.
        
    Returns:
        str: 'simple' or 'complex'.
    """
    query_lower = query.lower()
    
    # Complex indicators
    complex_indicators = [
        "compare", "analyze", "explain why", "relationship between",
        "impact of", "evaluate", "synthesize", "how does", "affect",
        "differences between", "similarities", "trend", "pattern",
        "correlation", "cause", "effect"
    ]
    
    # Simple indicators
    simple_indicators = [
        "what is", "who is", "when did", "where is",
        "define", "list", "name", "how many"
    ]
    
    # Check for complex indicators
    if any(indicator in query_lower for indicator in complex_indicators):
        return "complex"
    
    # Check for simple indicators
    if any(indicator in query_lower for indicator in simple_indicators):
        return "simple"
    
    # Default heuristics
    word_count = len(query.split())
    question_count = query.count("?")
    
    if word_count > 15 or question_count > 1:
        return "complex"
    
    return "simple"


def clean_internal_monologue(text: str) -> str:
    """
    Remove internal thinking/monologue from LLM response.
    Handles:
    1. <think>...</think> tags (Qwen models)
    2. Internal monologue patterns at the start
    
    Args:
        text: Raw LLM response
        
    Returns:
        Cleaned text with internal monologue removed
    """
    if not text:
        return text
    
    # STEP 1: Remove <think>...</think> blocks (Qwen's internal thinking)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = text.strip()
    
    if not text:
        return text
    
    # STEP 2: Remove paragraph-level thinking patterns
    paragraphs = text.split('\n\n')
    
    # Patterns that indicate internal thinking (case-insensitive)
    thinking_patterns = [
        r'^okay,?\s+let\'?s',
        r'^first,?\s+i\s',
        r'^i\s+need\s+to',
        r'^i\s+should',
        r'^i\s+will',
        r'^i\'ll',
        r'^starting\s+with',
        r'^putting\s+this\s+together',
        r'^the\s+user\s+(wants|is\s+asking)',
        r'^looking\s+at',
        r'^going\s+through',
        r'^analyzing',
        r'^from\s+what\s+i\s+can\s+see',
    ]
    
    cleaned_paragraphs = []
    skip_mode = False
    
    for para in paragraphs:
        para_stripped = para.strip()
        if not para_stripped:
            continue
            
        para_lower = para_stripped.lower()
        
        # Check if this paragraph starts with thinking patterns
        is_thinking = any(re.match(pattern, para_lower) for pattern in thinking_patterns)
        
        # Check for first-person pronouns at the start
        has_first_person_start = re.match(r'^(i\s|my\s|we\s|our\s)', para_lower)
        
        # If we find thinking patterns, skip until we find actual content
        if is_thinking or (has_first_person_start and len(para_stripped.split()) < 50):
            skip_mode = True
            continue
        
        # Look for section headers or structured content (likely the actual answer)
        if re.match(r'^#+\s+', para_stripped) or re.match(r'^\d+\.', para_stripped) or re.match(r'^[A-Z][^.!?]*:', para_stripped):
            skip_mode = False
        
        # If we're past the thinking phase, keep the content
        if not skip_mode:
            cleaned_paragraphs.append(para)
    
    # If we filtered everything out, return the original (safety fallback)
    if not cleaned_paragraphs:
        # Try to find the first paragraph that looks like actual content
        for para in paragraphs:
            para_stripped = para.strip()
            if len(para_stripped) > 100 and not any(re.match(pattern, para_stripped.lower()) for pattern in thinking_patterns):
                cleaned_paragraphs.append(para)
                break
        
        # If still nothing, return original
        if not cleaned_paragraphs:
            return text
    
    return '\n\n'.join(cleaned_paragraphs).strip()


# Retry Configuration for OpenAI API
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def _call_chat_completion(
    client_instance: OpenAI,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float
):
    """
    Call chat completion API with retry logic
    
    Args:
        client_instance: OpenAI client instance (or compatible)
        model: Model name
        prompt: User prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        
    Returns:
        Chat completion response
        
    Raises:
        OpenAIError: If all retries fail
    """
    try:
        return client_instance.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful document analysis assistant. You must output ONLY the final answer. Do not include any internal monologue, thinking process, or self-correction. Start your response directly with the answer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature
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
    "/api/v1/llm/generate",
    response_model=LLMResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate answer for query",
    description="Generate answer using appropriate LLM based on query complexity"
)
async def generate_answer(request: LLMRequest):
    """
    Generate answer for the query using retrieved context.
    
    Orchestrates the generation process:
    1. Determines query complexity (if set to auto)
    2. Selects appropriate model (simple vs complex)
    3. Formats context chunks
    4. Calls LLM (OpenAI or Enterprise)
    5. Cleans response and extracts citations
    
    Args:
        request (LLMRequest): Request object containing query, context chunks, and parameters.
        
    Returns:
        LLMResponse: Generated answer with metadata and citations.
        
    Raises:
        HTTPException: If LLM API call fails.
    """
    try:
        start_time = time.time()
        
        # Determine query type
        if request.model_type == "auto":
            query_type = detect_query_complexity(request.query)
        else:
            query_type = request.model_type
        
        # Select model and parameters
        current_client = client  # Default to global client
        
        if settings.is_enterprise_configured():
            # Enterprise API with dual model support
            if query_type == "simple":
                model = settings.inference_model_name_simple
                endpoint = settings.inference_model_endpoint_simple
                max_tokens = request.max_tokens or settings.max_tokens_simple
                temperature = request.temperature or settings.temperature_simple
                prompt_template = SIMPLE_QA_PROMPT
            else:
                model = settings.inference_model_name_complex
                endpoint = settings.inference_model_endpoint_complex
                max_tokens = request.max_tokens or settings.max_tokens_complex
                temperature = request.temperature or settings.temperature_complex
                prompt_template = COMPLEX_QA_PROMPT
            
            # Get specific client for the endpoint
            from api_client import get_api_client
            api_client_inst = get_api_client()
            current_client = api_client_inst.get_inference_client(endpoint=endpoint)
            
        else:
            # Fallback (should not be reached if config validation works)
            logger.warning("Enterprise config missing, using simple model default")
            model = settings.inference_model_name_simple
            max_tokens = request.max_tokens or settings.max_tokens_simple
            temperature = request.temperature or settings.temperature_simple
            prompt_template = SIMPLE_QA_PROMPT
        
        logger.info(
            f"Generating answer using {model} "
            f"(query_type={query_type}, chunks={len(request.context_chunks)})"
        )
        
        # Format context
        context = format_context(request.context_chunks)
        
        # Build prompt
        prompt = prompt_template.format(context=context, query=request.query)
        
        # Call API with retry logic
        response = _call_chat_completion(
            client_instance=current_client,
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Extract answer
        answer = response.choices[0].message.content
        token_count = response.usage.total_tokens if response.usage else None
        
        # Log raw LLM output for debugging
        logger.info(f"Raw LLM output (first 500 chars): {answer[:500]}...")
        logger.info(f"Total LLM output length: {len(answer)} characters")
        
       
        cleaned_answer = clean_internal_monologue(answer)
        logger.info(f"Cleaned output (first 500 chars): {cleaned_answer[:500]}...")
        logger.info(f"Cleaning removed {len(answer) - len(cleaned_answer)} characters")
        answer = cleaned_answer
        
        # Extract citations
        citations = []
        if request.include_citations:
            citations = extract_citations(answer, request.context_chunks)
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(
            f"Answer generated in {processing_time:.2f}ms "
            f"(tokens={token_count}, citations={len(citations)})"
        )
        
        return LLMResponse(
            answer=answer,
            citations=citations,
            model_used=model,
            query_type=query_type,
            generation_time_ms=round(processing_time, 2),
            token_count=token_count
        )
        
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OpenAI API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.post(
    "/api/v1/llm/generate/simple",
    response_model=LLMResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate answer using simple model",
    description="Force use of simple model (gpt-4o-mini) for factual questions"
)
async def generate_simple(request: LLMRequest):
    """
    Generate answer using simple model.
    
    Forces the use of the 'simple' model configuration (optimized for speed and fact retrieval),
    bypassing complexity detection.
    
    Args:
        request (LLMRequest): Request object.
        
    Returns:
        LLMResponse: Generated answer.
    """
    request.model_type = "simple"
    return await generate_answer(request)


@app.post(
    "/api/v1/llm/generate/complex",
    response_model=LLMResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate answer using complex model",
    description="Force use of complex model (gpt-4-turbo) for analytical questions"
)
async def generate_complex(request: LLMRequest):
    """
    Generate answer using complex model.
    
    Forces the use of the 'complex' model configuration (reasoning/analysis focused),
    bypassing complexity detection.
    
    Args:
        request (LLMRequest): Request object.
        
    Returns:
        LLMResponse: Generated answer.
    """
    request.model_type = "complex"
    return await generate_answer(request)


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check"
)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        HealthResponse: Status of the service, current deployment phase,
                      and configured models.
    """
    if settings.is_enterprise_configured():
        models_info = {
            "provider": "GenAI Gateway",
            "simple_model": settings.inference_model_name_simple,
            "complex_model": settings.inference_model_name_complex
        }
    else:
        models_info = {
            "provider": "GenAI Gateway (Not Configured)",
            "simple": "N/A",
            "complex": "N/A"
        }
    
    return HealthResponse(
        status="healthy",
        service="llm",
        deployment_phase=settings.deployment_phase,
        models=models_info
    )


@app.get(
    "/api/v1/llm/models/info",
    response_model=ModelInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get model information"
)
async def get_model_info():
    """
    Get LLM model information.
    
    Returns:
        ModelInfoResponse: Configuration details of currently active models
                         (simple/complex names, token limits, temperature).
    """
    return ModelInfoResponse(
        simple_model=settings.inference_model_name_simple,
        complex_model=settings.inference_model_name_complex,
        max_tokens_simple=settings.max_tokens_simple,
        max_tokens_complex=settings.max_tokens_complex,
        temperature_simple=settings.temperature_simple,
        temperature_complex=settings.temperature_complex
    )


# Product Endpoints
class ProductRecommendationRequest(BaseModel):
    """
    Request model for product recommendation.
    
    Attributes:
        query: User's original query.
        products: List of retrieved product dictionaries to analyze.
        intent: Detected intent type.
        filters: Applied filters (optional).
        mode: Response mode ('quick' or 'explained').
    """
    query: str = Field(..., description="User query")
    products: List[Dict[str, Any]] = Field(..., description="List of products")
    intent: str = Field(..., description="Query intent type")
    filters: Optional[Dict[str, Any]] = Field(None, description="Applied filters")
    mode: str = Field("explained", description="Response mode: 'quick' or 'explained'")


class ProductRecommendationResponse(BaseModel):
    """
    Response model for product recommendation.
    
    Attributes:
        recommendation: Generated recommendation text/HTML.
        mode: Mode used for generation ('quick' or 'explained').
        products_count: Number of products analyzed.
    """
    recommendation: str
    mode: str
    products_count: int


@app.post(
    "/api/v1/llm/generate/product-recommendation",
    response_model=ProductRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate product recommendation",
    description="Generate personalized product recommendations"
)
async def generate_product_recommendation(request: ProductRecommendationRequest):
    """
    Generate product recommendation.
    
    Uses either a template-based 'quick' mode for standard listings or an
    LLM-based 'explained' mode for in-depth advice, depending on intent
    and result count.
    
    Args:
        request (ProductRecommendationRequest): Request data.
        
    Returns:
        ProductRecommendationResponse: Generated recommendation content.
        
    Raises:
        HTTPException: If generation fails.
    """
    try:
        # Use formatter to determine mode and generate response
        use_quick = response_formatter.should_use_quick_mode(
            intent=request.intent,
            product_count=len(request.products),
            has_filters=bool(request.filters)
        )
        
        mode = "quick" if use_quick or request.mode == "quick" else "explained"
        
        if mode == "quick":
            # Template-based response
            recommendation = response_formatter.format_response(
                query=request.query,
                products=request.products,
                intent=request.intent,
                filters=request.filters,
                mode="quick"
            )
        else:
            # LLM-generated response
            prompt = response_formatter.format_response(
                query=request.query,
                products=request.products,
                intent=request.intent,
                filters=request.filters,
                mode="explained"
            )
            
            # Determine model and client
            if settings.is_enterprise_configured():
                model = settings.inference_model_name_simple
                endpoint = settings.inference_model_endpoint_simple
                from api_client import get_api_client
                api_client_inst = get_api_client()
                current_client = api_client_inst.get_inference_client(endpoint=endpoint)
            else:
                model = settings.inference_model_name_simple # Default fallback
                current_client = client

            # Call LLM
            response = current_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful shopping assistant. You must output ONLY the final recommendation. Do not include any internal monologue or thinking process."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.max_tokens_simple,
                temperature=settings.temperature_simple
            )
            
            recommendation = response.choices[0].message.content
        
        return ProductRecommendationResponse(
            recommendation=recommendation,
            mode=mode,
            products_count=len(request.products)
        )
        
    except Exception as e:
        logger.error(f"Error generating product recommendation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendation: {str(e)}"
        )


@app.post(
    "/api/v1/llm/generate/filtered-results",
    response_model=ProductRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate filtered results explanation",
    description="Generate explanation for filtered search results"
)
async def generate_filtered_results(request: ProductRecommendationRequest):
    """
    Generate explanation for filtered search results.
    
    Wrapper around recommendation generation with forced 'filtered_search' intent.
    
    Args:
        request (ProductRecommendationRequest): Request data.
        
    Returns:
        ProductRecommendationResponse: Generated explanation.
    """
    request.intent = "filtered_search"
    return await generate_product_recommendation(request)


@app.post(
    "/api/v1/llm/generate/comparison",
    response_model=ProductRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate product comparison",
    description="Generate comparison between products"
)
async def generate_comparison(request: ProductRecommendationRequest):
    """
    Generate product comparison.
    
    Wrapper around recommendation generation with forced 'comparison' intent.
    
    Args:
        request (ProductRecommendationRequest): Request data.
        
    Returns:
        ProductRecommendationResponse: Generated comparison.
    """
    request.intent = "comparison"
    return await generate_product_recommendation(request)


@app.get("/", summary="Root endpoint")
async def root():
    """
    Root endpoint with service information.
    
    Returns:
        dict: Basic service info including version and status.
    """
    return {
        "service": "LLM Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


# Application startup
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting LLM Service on {settings.llm_host}:{settings.llm_port}")
    logger.info(f"Deployment phase: {settings.deployment_phase}")
    
    if settings.is_enterprise_configured():
        logger.info("Provider: GenAI Gateway")
        logger.info(f"Simple model: {settings.inference_model_name_simple}")
        logger.info(f"Complex model: {settings.inference_model_name_complex}")
    else:
        logger.warning("Provider: Not configured (GenAI Gateway required)")
    
    uvicorn.run(
        app,
        host=settings.llm_host,  # nosec B104 - Binding to all interfaces is intentional for Docker container
        port=settings.llm_port,
        log_level=settings.log_level.lower()
    )

