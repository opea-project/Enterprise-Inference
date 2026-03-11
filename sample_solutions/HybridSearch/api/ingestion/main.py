"""
Document Ingestion Service
Handles document upload, processing, chunking, and indexing
"""

import logging
import time
import uuid
import httpx
import asyncio
from pathlib import Path
from typing import List, Optional, Dict
from fastapi import FastAPI, File, UploadFile, HTTPException, status, Form
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from config import settings
from services.document_parser import DocumentParser
from services.chunker import TextChunker
from services.index_manager import IndexManager
from services.metadata_store import MetadataStore
from services.product_parser import ProductParser
from services.product_processor import ProductProcessor
from schemas.product_schemas import (
    UploadResponse, ProcessingStatus, FieldMapping, 
    ProductCreate, CatalogMetadata
)

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    metadata_store.close()
    logger.info("Service shutdown complete")

app = FastAPI(
    title="Document Ingestion Service",
    description="Document processing, chunking, and indexing service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
document_parser = DocumentParser()
text_chunker = TextChunker(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap
)
index_manager = IndexManager(
    index_storage_path=settings.index_storage_path,
    embedding_dim=settings.embedding_dim
)
metadata_store = MetadataStore(settings.metadata_db_path)
product_parser = ProductParser()
product_processor = ProductProcessor(
    embedding_field_template=getattr(settings, 'embedding_field_template', None)
)

# Ensure storage directories exist
Path(settings.document_storage_path).mkdir(parents=True, exist_ok=True)

# Job tracking for product processing
processing_jobs: Dict[str, Dict] = {}
system_mode: str = getattr(settings, 'system_mode', 'document')  # 'document' or 'product'


# Response Models
class DocumentResponse(BaseModel):
    """
    Response model for document upload.
    
    Attributes:
        document_id (str): Unique identifier for the uploaded document.
        filename (str): Name of the uploaded file.
        file_type (str): Extension/type of the file.
        status (str): Current processing status (e.g., 'processing').
        upload_timestamp (str): ISO timestamp of upload.
        estimated_completion_time (Optional[str]): ETA for processing completion.
    """
    document_id: str
    filename: str
    file_type: str
    status: str
    upload_timestamp: str
    estimated_completion_time: Optional[str] = None


class DocumentStatus(BaseModel):
    """
    Document processing status.
    
    Attributes:
        document_id (str): Unique identifier.
        filename (str): Name of the file.
        file_type (str): Extension/type of the file.
        processing_status (str): Current status ('processing', 'completed', 'failed').
        chunk_count (int): Number of chunks generated so far.
        upload_timestamp (str): ISO timestamp of upload.
        error_message (Optional[str]): detailed error if processing failed.
    """
    document_id: str
    filename: str
    file_type: str
    processing_status: str
    chunk_count: int
    upload_timestamp: str
    error_message: Optional[str] = None


class IndexStats(BaseModel):
    """
    Index statistics.
    
    Attributes:
        total_documents (int): Total number of documents tracked.
        total_chunks (int): Total number of chunks indexed.
        faiss_vectors (int): Number of vectors in the FAISS index.
        status_counts (dict): Breakdown of documents by status (completed, failed, etc.).
    """
    total_documents: int
    total_chunks: int
    faiss_vectors: int
    status_counts: dict


class HealthResponse(BaseModel):
    """
    Health check response.
    
    Attributes:
        status (str): Overall service status.
        service (str): Service name.
        deployment_phase (str): Deployment environment.
        storage_paths (dict): Configuration of storage directories.
    """
    status: str
    service: str
    deployment_phase: str
    storage_paths: dict


# Helper Functions
async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Call embedding service to get embeddings (with batching support).
    
    Args:
        texts (List[str]): List of texts to embed.
        
    Returns:
        List[List[float]]: List of embedding vectors.
        
    Raises:
        httpx.HTTPError: If embedding service fails.
    """
    # Batch size limit from embedding service
    BATCH_SIZE = 32
    all_embeddings = []
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Process in batches if needed
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            logger.info(f"Getting embeddings for batch {i//BATCH_SIZE + 1}/{(len(texts)-1)//BATCH_SIZE + 1} ({len(batch)} texts)")
            
            response = await client.post(
                f"{settings.embedding_service_url}/api/v1/embeddings/encode-batch",
                json={"texts": batch, "normalize": True}
            )
            response.raise_for_status()
            data = response.json()
            all_embeddings.extend(data["embeddings"])
    
    return all_embeddings


async def process_document_async(
    document_id: str,
    file_path: Path,
    file_type: str
):
    """
    Process document asynchronously.
    
    Orchestrates parsing, chunking, embedding generation, and indexing.
    Updates status in metadata store throughout the process.
    
    Args:
        document_id (str): Unique document identifier.
        file_path (Path): Path to the uploaded file on disk.
        file_type (str): File extension/type (e.g., 'pdf').
    """
    try:
        # Update status to processing
        metadata_store.update_status(document_id, "processing")
        
        # Parse document
        logger.info(f"Parsing document {document_id} ({file_type})")
        pages_or_sections = document_parser.parse_document(file_path, file_type)
        
        if not pages_or_sections:
            raise ValueError("No text content extracted from document")
        
        # Chunk text
        logger.info(f"Chunking document {document_id}")
        chunks = text_chunker.chunk_document(pages_or_sections, document_id)
        
        if not chunks:
            raise ValueError("No chunks created from document")
        
        # Get embeddings
        logger.info(f"Getting embeddings for {len(chunks)} chunks")
        texts = [chunk["text"] for chunk in chunks]
        embeddings = await get_embeddings(texts)
        
        # Add to indexes
        logger.info(f"Adding {len(chunks)} chunks to indexes")
        index_manager.add_chunks(chunks, embeddings)
        
        # Update status to completed
        metadata_store.update_status(
            document_id,
            "completed",
            chunk_count=len(chunks)
        )
        
        logger.info(f"Document {document_id} processed successfully ({len(chunks)} chunks)")
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
        metadata_store.update_status(
            document_id,
            "failed",
            error_message=str(e)
        )


async def process_products_async(
    job_id: str,
    products: List[Dict],
    field_mapping: FieldMapping,
    catalog_name: str
):
    """
    Process products asynchronously.
    
    Handles field mapping, validation, embedding generation, and indexing of product data.
    Updates job status and progress.
    
    Args:
        job_id (str): Unique job identifier.
        products (List[Dict]): List of raw product dictionaries.
        field_mapping (FieldMapping): Mapping configuration for product fields.
        catalog_name (str): Name of the catalog.
    """
    try:
        # Update job status
        processing_jobs[job_id]['status'] = 'processing'
        processing_jobs[job_id]['current_step'] = 'Processing products...'
        processing_jobs[job_id]['products_total'] = len(products)
        
        # Apply field mapping
        logger.info(f"Applying field mapping for job {job_id}")
        mapped_products = product_parser.apply_field_mapping(products, field_mapping)
        
        # Process and validate products
        logger.info(f"Processing {len(mapped_products)} products for job {job_id}")
        processed_products, invalid_products = product_processor.process_batch(
            mapped_products,
            batch_size=100,
            skip_invalid=True
        )
        
        if invalid_products:
            processing_jobs[job_id]['errors'].extend([
                f"Product {i+1}: {', '.join(err['errors'])}"
                for i, err in enumerate(invalid_products)
            ])
        
        if not processed_products:
            raise ValueError("No valid products found after processing")
        
        # Clear existing products (single catalog mode)
        logger.info(f"Clearing existing products for job {job_id}")
        metadata_store.clear_all_products()
        index_manager.clear_products_only()  # Only clear products, keep documents intact
        
        # Process in batches
        BATCH_SIZE = 100
        total_batches = (len(processed_products) + BATCH_SIZE - 1) // BATCH_SIZE
        
        categories = set()
        prices = []
        
        for batch_idx in range(0, len(processed_products), BATCH_SIZE):
            batch = processed_products[batch_idx:batch_idx + BATCH_SIZE]
            batch_num = batch_idx // BATCH_SIZE + 1
            
            # Update progress
            processing_jobs[job_id]['products_processed'] = min(batch_idx + BATCH_SIZE, len(processed_products))
            processing_jobs[job_id]['progress'] = processing_jobs[job_id]['products_processed'] / len(processed_products)
            processing_jobs[job_id]['current_step'] = f'Processing batch {batch_num}/{total_batches}...'
            
            # Collect categories and prices
            for product in batch:
                if product.get('category'):
                    categories.add(product['category'])
                if product.get('price') is not None:
                    prices.append(product['price'])
            
            # Get embeddings for batch
            logger.info(f"Getting embeddings for batch {batch_num}/{total_batches} ({len(batch)} products)")
            embedding_texts = [p['embedding_text'] for p in batch]
            embeddings = await get_embeddings(embedding_texts)
            
            # Add to database
            for product, embedding in zip(batch, embeddings):
                metadata_store.add_product(
                    product_id=product['id'],
                    name=product['name'],
                    description=product['description'],
                    category=product['category'],
                    price=product['price'],
                    rating=product['rating'],
                    review_count=product['review_count'],
                    image_url=product['image_url'],
                    brand=product['brand'],
                    embedding_text=product['embedding_text']
                )
            
            # Add to product indexes
            product_entries = [
                {
                    'id': product['id'],
                    'name': product['name'],
                    'description': product['description'],
                    'category': product['category'],
                    'price': product['price'],
                    'rating': product['rating'],
                    'review_count': product['review_count'],
                    'brand': product['brand'],
                    'image_url': product['image_url'],
                    'embedding_text': product['embedding_text']
                }
                for product in batch
            ]
            index_manager.add_products(product_entries, embeddings)
            
            logger.info(f"Processed batch {batch_num}/{total_batches}")
        
        # Update catalog metadata
        price_min = min(prices) if prices else None
        price_max = max(prices) if prices else None
        
        metadata_store.update_catalog_metadata(
            catalog_name=catalog_name,
            product_count=len(processed_products),
            categories=list(categories),
            price_range_min=price_min,
            price_range_max=price_max
        )
        
        # Update job status
        processing_jobs[job_id]['status'] = 'complete'
        processing_jobs[job_id]['progress'] = 1.0
        processing_jobs[job_id]['current_step'] = 'Complete'
        
        logger.info(f"Job {job_id} completed: {len(processed_products)} products processed")
        
    except Exception as e:
        logger.error(f"Error processing products for job {job_id}: {e}", exc_info=True)
        processing_jobs[job_id]['status'] = 'error'
        processing_jobs[job_id]['errors'].append(str(e))
        processing_jobs[job_id]['current_step'] = f'Error: {str(e)}'


# API Endpoints
@app.post(
    "/api/v1/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload document",
    description="Upload a document for processing and indexing"
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload")
):
    """
    Upload and process a document.
    
    Accepts a file upload, validates format and size, saves it locally,
    and triggers asynchronous processing.
    
    Args:
        file (UploadFile): The uploaded document file.
        
    Returns:
        DocumentResponse: Processing task details including document ID.
        
    Raises:
        HTTPException: For invalid files or I/O errors.
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        file_ext = Path(file.filename).suffix.lstrip('.').lower()
        if file_ext not in settings.supported_formats_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}. "
                       f"Supported: {', '.join(settings.supported_formats_list)}"
            )
        
        # Read file content
        try:
            content = await file.read()
            file_size = len(content)
            logger.info(f"Read file: {file.filename}, size: {file_size} bytes")
        except Exception as e:
            logger.error(f"Error reading file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read file: {str(e)}"
            )
        
        # Validate file size
        max_size = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum "
                       f"({settings.max_file_size_mb}MB)"
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        # Generate document ID
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # Save file
        try:
            storage_path = Path(settings.document_storage_path) / document_id
            storage_path.mkdir(parents=True, exist_ok=True)
            
            # Sanitize filename to avoid path issues
            safe_filename = file.filename.replace('/', '_').replace('\\', '_')
            file_path = storage_path / safe_filename
            
            with open(file_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"Saved file: {file_path} ({file_size} bytes)")
        except PermissionError as e:
            logger.error(f"Permission error saving file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Permission denied saving file to {settings.document_storage_path}"
            )
        except OSError as e:
            logger.error(f"OS error saving file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )
        
        # Add to metadata store
        try:
            metadata_store.add_document(
                document_id=document_id,
                filename=file.filename,
                file_type=file_ext,
                file_size=file_size,
                metadata={"original_filename": file.filename}
            )
        except Exception as e:
            logger.error(f"Error adding document to metadata store: {e}", exc_info=True)
            # Try to clean up saved file
            try:
                if file_path.exists():
                    file_path.unlink()
                if storage_path.exists():
                    storage_path.rmdir()
            except:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add document to metadata store: {str(e)}"
            )
        
        # Process document asynchronously
        try:
            import asyncio
            asyncio.create_task(process_document_async(document_id, file_path, file_ext))
        except Exception as e:
            logger.error(f"Error creating async task: {e}", exc_info=True)
            # Don't fail the upload if async task creation fails
            # The document is saved and can be processed later
        
        # Get document info
        try:
            doc = metadata_store.get_document(document_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Document saved but not found in metadata store"
                )
        except Exception as e:
            logger.error(f"Error retrieving document info: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve document info: {str(e)}"
            )
        
        return DocumentResponse(
            document_id=document_id,
            filename=file.filename,
            file_type=file_ext,
            status="processing",
            upload_timestamp=doc['upload_timestamp']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@app.get(
    "/api/v1/documents/{document_id}/status",
    response_model=DocumentStatus,
    status_code=status.HTTP_200_OK,
    summary="Get document status",
    description="Check the processing status of a document"
)
async def get_document_status(document_id: str):
    """
    Get document processing status.
    
    Args:
        document_id (str): Document identifier.
        
    Returns:
        DocumentStatus: Current status and progress stats.
        
    Raises:
        HTTPException: If document is not found.
    """
    doc = metadata_store.get_document(document_id)
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}"
        )
    
    return DocumentStatus(**doc)


@app.delete(
    "/api/v1/documents/clear-all",
    status_code=status.HTTP_200_OK,
    summary="Clear all indexes",
    description="Clear all vector indexes (FAISS and BM25) and metadata. WARNING: This will delete all indexed documents!"
)
async def clear_all_indexes():
    """
    Clear all vector indexes and metadata.
    
    WARNING: This operation cannot be undone. All indexed documents 
    and associated metadata will be permanently removed.
    
    Returns:
        dict: Success message.
    """
    try:
        # Clear indexes
        index_manager.clear_all()
        
        # Clear metadata store
        metadata_store.clear_all()
        
        logger.warning("All indexes and metadata cleared by user request")
        
        return {
            "message": "All indexes and metadata cleared successfully",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error clearing indexes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear indexes: {str(e)}"
        )


@app.delete(
    "/api/v1/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete document",
    description="Delete a document and its associated data"
)
async def delete_document(document_id: str):
    """
    Delete document and all associated data.
    
    Removes the document from vector indexes, metadata store, and file system.
    
    Args:
        document_id (str): Document identifier.
        
    Returns:
        dict: Success message.
        
    Raises:
        HTTPException: If document is not found or deletion fails.
    """
    doc = metadata_store.get_document(document_id)
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}"
        )
    
    try:
        # Delete from indexes
        index_manager.delete_document(document_id)
        
        # Delete file
        storage_path = Path(settings.document_storage_path) / document_id
        if storage_path.exists():
            import shutil
            shutil.rmtree(storage_path)
        
        # Delete from metadata store
        metadata_store.delete_document(document_id)
        
        logger.info(f"Deleted document: {document_id}")
        
        return {"message": f"Document {document_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@app.get(
    "/api/v1/documents/stats",
    response_model=IndexStats,
    status_code=status.HTTP_200_OK,
    summary="Get index statistics",
    description="Get statistics about indexed documents and chunks"
)
async def get_stats():
    """
    Get index statistics.
    
    Returns:
        IndexStats: overview of total documents, chunks, and vector counts.
    """
    db_stats = metadata_store.get_stats()
    index_stats = index_manager.get_stats()
    
    return IndexStats(
        total_documents=db_stats["total_documents"],
        total_chunks=index_stats["total_chunks"],
        faiss_vectors=index_stats["faiss_vectors"],
        status_counts=db_stats["status_counts"]
    )


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
        HealthResponse: Status of the service and storage path configurations.
    """
    return HealthResponse(
        status="healthy",
        service="ingestion",
        deployment_phase=settings.deployment_phase,
        storage_paths={
            "documents": settings.document_storage_path,
            "indexes": settings.index_storage_path,
            "metadata": settings.metadata_db_path
        }
    )


# Product Endpoints
@app.post(
    "/api/v1/products/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload product catalog",
    description="Upload CSV/JSON/XLSX file with products. Returns job_id for async processing."
)
async def upload_products(
    file: UploadFile = File(..., description="Product catalog file (CSV/JSON/XLSX)")
):
    """
    Upload product catalog file (CSV/JSON/XLSX).
    
    Parses the file to detect columns and generates a suggested field mapping.
    
    Args:
        file (UploadFile): The product catalog file.
        
    Returns:
        UploadResponse: Job ID and mapping suggestions.
        
    Raises:
        HTTPException: For unsupported formats or parsing errors.
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        file_ext = Path(file.filename).suffix.lstrip('.').lower()
        if file_ext not in ['csv', 'json', 'xlsx', 'xls']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}. Supported: csv, json, xlsx"
            )
        
        # Read file content
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        # Parse file
        try:
            products, detected_columns, suggested_mapping = product_parser.parse_file(content, file.filename)
        except Exception as e:
            logger.error(f"Error parsing file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse file: {str(e)}"
            )
        
        if not products:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No products found in file"
            )
        
        # Ensure detected_columns are strings (not tuples)
        detected_columns = [str(col) if not isinstance(col, str) else col for col in detected_columns]
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Store job info
        processing_jobs[job_id] = {
            'status': 'pending_confirmation',
            'filename': file.filename,
            'products': products,
            'detected_columns': detected_columns,
            'suggested_mapping': suggested_mapping,
            'products_processed': 0,
            'products_total': len(products),
            'progress': 0.0,
            'current_step': 'Waiting for field mapping confirmation',
            'errors': []
        }
        
        requires_confirmation = not suggested_mapping.name
        
        # If confirmation is not required, start processing immediately
        if not requires_confirmation:
            job = processing_jobs[job_id]
            job['status'] = 'processing'
            job['field_mapping'] = suggested_mapping
            job['catalog_name'] = Path(file.filename).stem
            
            # Apply field mapping
            mapped_products = product_parser.apply_field_mapping(
                products,
                suggested_mapping
            )
            
            # Start async processing
            asyncio.create_task(process_products_async(
                job_id,
                mapped_products,
                suggested_mapping,
                job['catalog_name']
            ))
            
            logger.info(f"Auto-started processing for job {job_id}")
        
        return UploadResponse(
            job_id=job_id,
            status='pending_confirmation' if requires_confirmation else 'processing',
            detected_columns=detected_columns,
            suggested_mapping=suggested_mapping if suggested_mapping.name else None,
            requires_confirmation=requires_confirmation
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload products: {str(e)}"
        )


@app.post(
    "/api/v1/products/confirm",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Confirm field mapping and start processing",
    description="Confirm field mapping and start product processing"
)
async def confirm_product_mapping(
    job_id: str = Form(...),
    catalog_name: str = Form(None),
    field_mapping: str = Form(...)  # JSON string of FieldMapping
):
    """
    Confirm field mapping and start processing.
    
    Validates field mapping, updates job status, and triggers async processing.
    
    Args:
        job_id (str): Job identifier.
        catalog_name (str): Name of the catalog (optional).
        field_mapping (str): JSON string representation of FieldMapping object.
        
    Returns:
        dict: Success message and job status.
        
    Raises:
        HTTPException: If job not found or JSON is invalid.
    """
    try:
        if job_id not in processing_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}"
            )
        
        job = processing_jobs[job_id]
        if job['status'] != 'pending_confirmation':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_id} is not in pending_confirmation status"
            )
        
        # Parse field mapping
        import json
        mapping_dict = json.loads(field_mapping)
        field_mapping_obj = FieldMapping(**mapping_dict)
        
        if not field_mapping_obj.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field mapping must include 'name' field"
            )
        
        # Update job
        job['field_mapping'] = field_mapping_obj
        job['catalog_name'] = catalog_name or Path(job['filename']).stem
        
        # Apply field mapping
        mapped_products = product_parser.apply_field_mapping(
            job['products'],
            field_mapping_obj
        )
        
        # Start async processing
        asyncio.create_task(process_products_async(
            job_id,
            mapped_products,
            field_mapping_obj,
            job['catalog_name']
        ))
        
        return {
            "message": "Processing started",
            "job_id": job_id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON in field_mapping: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error confirming mapping: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm mapping: {str(e)}"
        )


@app.get(
    "/api/v1/products/status/{job_id}",
    response_model=ProcessingStatus,
    status_code=status.HTTP_200_OK,
    summary="Get processing status",
    description="Check the processing status of a product upload job"
)
async def get_product_status(job_id: str):
    """
    Get product processing status.
    
    Args:
        job_id (str): Job identifier.
        
    Returns:
        ProcessingStatus: Current job status and progress.
        
    Raises:
        HTTPException: If job is not found.
    """
    if job_id not in processing_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )
    
    job = processing_jobs[job_id]
    
    return ProcessingStatus(
        job_id=job_id,
        status=job['status'],
        progress=job.get('progress', 0.0),
        products_processed=job.get('products_processed', 0),
        products_total=job.get('products_total', 0),
        current_step=job.get('current_step', 'Unknown'),
        errors=job.get('errors', [])
    )


@app.delete(
    "/api/v1/products/clear",
    status_code=status.HTTP_200_OK,
    summary="Clear product catalog",
    description="Clear all products from the catalog. WARNING: This will delete all indexed products!"
)
async def clear_products():
    """
    Clear all products from the catalog.
    
    WARNING: Removes all product data from metadata store and indexes.
    
    Returns:
        dict: Success message.
    """
    try:
        metadata_store.clear_all_products()
        index_manager.clear_all()
        
        logger.warning("All products cleared by user request")
        
        return {
            "message": "All products cleared successfully",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error clearing products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear products: {str(e)}"
        )


@app.get(
    "/api/v1/products/mode",
    status_code=status.HTTP_200_OK,
    summary="Get system mode",
    description="Get current system mode (document or product)"
)
async def get_mode():
    """
    Get current system mode.
    
    Returns:
        dict: Current mode ('document' or 'product') and available modes.
    """
    return {
        "mode": system_mode,
        "available_modes": ["document", "product"]
    }


@app.post(
    "/api/v1/products/mode",
    status_code=status.HTTP_200_OK,
    summary="Set system mode",
    description="Switch between document and product mode"
)
async def set_mode(mode: str = Form(...)):
    """
    Set system mode.
    
    Switches the system between 'document' and 'product' modes, affecting
    default search behavior.
    
    Args:
        mode (str): System mode ('document' or 'product').
        
    Returns:
        dict: Confirmation message.
    """
    global system_mode
    
    if mode not in ['document', 'product']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode: {mode}. Must be 'document' or 'product'"
        )
    
    system_mode = mode
    logger.info(f"System mode changed to: {mode}")
    
    return {
        "message": f"System mode set to {mode}",
        "mode": system_mode
    }


@app.get(
    "/api/v1/products/catalog/info",
    status_code=status.HTTP_200_OK,
    summary="Get catalog info",
    description="Get information about the current product catalog"
)
async def get_catalog_info():
    """
    Get catalog information.
    
    Returns:
        dict: Catalog metadata, product counts, price ranges, etc.
    """
    catalog_metadata = metadata_store.get_catalog_metadata()
    product_stats = metadata_store.get_product_stats()
    
    if not catalog_metadata:
        return {
            "loaded": False,
            "message": "No catalog loaded"
        }
    
    return {
        "loaded": True,
        "name": catalog_metadata['catalog_name'],
        "product_count": catalog_metadata['product_count'],
        "categories": catalog_metadata.get('categories', []),
        "price_range": {
            "min": catalog_metadata.get('price_range_min'),
            "max": catalog_metadata.get('price_range_max')
        },
        "upload_date": catalog_metadata['upload_date'],
        "stats": product_stats
    }


@app.get("/", summary="Root endpoint")
async def root():
    """
    Root endpoint with service information.
    
    Returns:
        dict: Basic service info including version, status, and mode.
    """
    return {
        "service": "Document Ingestion Service",
        "version": "1.0.0",
        "status": "running",
        "mode": system_mode,
        "docs": "/docs",
        "health": "/health"
    }


# Application startup/shutdown
# Application startup
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Ingestion Service on {settings.ingestion_host}:{settings.ingestion_port}")
    logger.info(f"Deployment phase: {settings.deployment_phase}")
    logger.info(f"Document storage: {settings.document_storage_path}")
    logger.info(f"Index storage: {settings.index_storage_path}")
    
    uvicorn.run(
        app,
        host=settings.ingestion_host,  # nosec B104 - Binding to all interfaces is intentional for Docker container
        port=settings.ingestion_port,
        log_level=settings.log_level.lower()
    )

