"""
Streamlit UI for InsightMapper Lite - Hybrid Search RAG Application
Simplified Chat Interface with Document Upload
"""
import streamlit as st
import os
import httpx
import logging
import re
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from config import settings
from streamlit_keycloak import login

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="RAG Chatbot",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for simplified chat interface
st.markdown("""
<style>
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {visibility: hidden; height: 0;}
    
    .block-container {
        padding-top: 0rem !important; 
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }
    
    /* Remove default column padding */
    div[data-testid="column"] {
        padding: 0 !important;
    }
    
    /* Main header - tighten spacing */
    .main-header {
        font-size: 1.75rem;
        font-weight: 600;
        color: #1f2937;
        margin-top: 0.5rem;
        margin-bottom: 0.25rem;
    }
    .sub-header {
        font-size: 0.875rem;
        color: #6b7280;
        margin-bottom: 0.5rem;
    }
    
    /* Panel styling */
    .upload-panel {
        background: transparent;
        border: none;
        padding: 0;
        border-radius: 0;
    }
    .chat-panel {
        background: transparent;
        padding: 0;
        border-radius: 0;
    }
    
    /* E-commerce Product Grid Styling */
    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
        gap: 1.25rem;
        padding: 1rem 0;
    }
    .product-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        overflow: hidden;
        transition: transform 0.2s, box-shadow 0.2s;
        cursor: pointer;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    .product-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border-color: #3b82f6;
    }
    .product-image {
        width: 100%;
        height: 200px;
        object-fit: cover;
        background: #f9fafb;
    }
    .product-info {
        padding: 1rem;
        flex: 1;
        display: flex;
        flex-direction: column;
    }
    .product-name {
        font-size: 0.95rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 0.5rem;
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .product-price {
        font-size: 1.25rem;
        font-weight: 700;
        color: #059669;
        margin-bottom: 0.5rem;
    }
    .product-rating {
        display: flex;
        align-items: center;
        gap: 0.25rem;
        margin-bottom: 0.5rem;
        font-size: 0.875rem;
    }
    .product-category {
        font-size: 0.75rem;
        color: #6b7280;
        background: #f3f4f6;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        display: inline-block;
        margin-top: auto;
    }
    
    /* Search and Filter Bar */
    .search-bar-container {
        background: transparent;
        padding: 0;
        border-radius: 0;
        box-shadow: none;
        margin-bottom: 1.5rem;
    }
    .filter-chips {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-top: 0.75rem;
    }
    .filter-chip {
        background: #eff6ff;
        color: #1e40af;
        padding: 0.375rem 0.75rem;
        border-radius: 16px;
        font-size: 0.875rem;
        border: 1px solid #bfdbfe;
    }
    .results-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding: 0 0.5rem;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 0.35rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .section-subtitle {
        font-size: 0.875rem;
        color: #6b7280;
        margin-bottom: 1rem;
    }
    
    /* Status indicator */
    .status-indicator {
        background: #fef3c7;
        border: 1px solid #fbbf24;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin: 0.75rem 0;
        color: #78350f;
        font-size: 0.875rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .status-success {
        background: #d1fae5;
        border-color: #10b981;
        color: #065f46;
    }
    
    /* Upload section styling */
    .upload-box {
        background: #f9fafb;
        border: 2px dashed #d1d5db;
        border-radius: 12px;
        padding: 2rem 1.5rem;
        text-align: center;
        margin: 1rem 0;
        transition: all 0.2s;
    }
    .upload-box:hover {
        border-color: #9ca3af;
        background: #f3f4f6;
    }
    .upload-icon {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    .upload-text {
        font-size: 0.9rem;
        color: #4b5563;
        margin-bottom: 0.35rem;
    }
    
    /* Instructions */
    .instructions {
        background: #f3f4f6;
        border-radius: 8px;
        padding: 0.875rem 1rem;
        margin-top: 1rem;
        border: 1px solid #e5e7eb;
    }
    .instructions-title {
        font-weight: 600;
        color: #374151;
        font-size: 0.875rem;
        margin-bottom: 0.5rem;
    }
    .instructions ul {
        margin: 0.5rem 0 0 0;
        padding-left: 1.25rem;
        color: #4b5563;
        font-size: 0.85rem;
        line-height: 1.5;
    }
    .instructions li {
        margin: 0.35rem 0;
    }
    
    /* Chat empty state */
    .chat-empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem 2rem;
        text-align: center;
        color: #9ca3af;
    }
    .chat-empty-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        opacity: 0.4;
    }
    .chat-empty-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #6b7280;
        margin-bottom: 0.5rem;
    }
    .chat-empty-subtitle {
        font-size: 0.9rem;
        color: #9ca3af;
        max-width: 450px;
        line-height: 1.6;
    }
    
    /* Chat message styling */
    .user-message {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        padding: 0.875rem 1.125rem;
        border-radius: 18px 18px 4px 18px;
        margin: 0.75rem 0;
        max-width: 75%;
        margin-left: auto;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
        line-height: 1.5;
    }
    .assistant-message {
        background: #ffffff;
        color: #1f2937;
        padding: 1rem 1.125rem;
        border-radius: 18px 18px 18px 4px;
        margin: 0.75rem 0;
        max-width: 85%;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
        line-height: 1.6;
    }
    
    /* Source citations */
    .citation-badge {
        background: #3b82f6;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 0 2px;
        display: inline-block;
    }
    
    /* Divider */
    .vertical-divider {
        width: 2px;
        background: linear-gradient(180deg, #e5e7eb 0%, #f3f4f6 50%, #e5e7eb 100%);
        height: 100%;
    }
    
    /* Streamlit specific overrides */
    [data-testid="column"] {
        padding: 0 !important;
        vertical-align: top !important;
    }
    
    /* Ensure columns start at the same height */
    [data-testid="column"] > div {
        height: 100%;
    }
    
    /* File uploader styling */
    [data-testid="stFileUploader"] {
        border: none !important;
        background: transparent !important;
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 0.35rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .section-subtitle {
        font-size: 0.875rem;
        color: #6b7280;
        margin-bottom: 1rem;
    }
    
    /* Hide white boxes above section headers */
    .upload-panel > div:first-child,
    .chat-panel > div:first-child {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)


class UIService:
    """
    Handle UI operations and API calls.
    
    Manages communication with the backend services (Gateway, Ingestion, Retrieval)
    via HTTP requests. Handles authentication, file uploads, query submission,
    and status polling.
    """
    
    def __init__(self):
        """
        Initialize UI Service.
        
        Sets up API endpoints from environment variables and initializes the HTTP client.
        """
        import os
        gateway_host = os.getenv("GATEWAY_SERVICE_URL", settings.gateway_service_url)
        ingestion_host = os.getenv("INGESTION_SERVICE_URL", "http://localhost:8004")
        retrieval_host = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8002")
        
        self.gateway_url = gateway_host if gateway_host.startswith("http") else f"http://{gateway_host}"
        self.ingestion_url = ingestion_host if ingestion_host.startswith("http") else f"http://{ingestion_host}"
        self.retrieval_url = retrieval_host if retrieval_host.startswith("http") else f"http://{retrieval_host}"
        self.llm_url = "http://localhost:8003"
        self.client = httpx.Client(timeout=60.0)
        self.token = None
    
    def set_token(self, token: str):
        """
        Set authentication token for client headers.
        
        Args:
            token (str): JWT access token.
        """
        self.token = token
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        
    def check_health(self) -> Dict[str, Any]:
        """
        Check health of all services.
        
        Returns:
            Dict[str, Any]: Health status of backend services.
        """
        try:
            response = self.client.get(f"{self.gateway_url}/api/v1/health/services")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def submit_query(self, query: str, include_debug: bool = False) -> Dict[str, Any]:
        """
        Submit a query to the RAG system.
        
        Args:
            query (str): The user's question.
            include_debug (bool): Whether to request debug info in the response.
            
        Returns:
            Dict[str, Any]: Normalized response with answer, citations, and metadata.
        """
        try:
            payload = {
                "query": query,
                "include_debug_info": include_debug
            }
            response = self.client.post(
                f"{self.gateway_url}/api/v1/query",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            # Normalize response fields to match UI expectations
            normalized = {
                "answer": data.get("answer", ""),
                "citations": data.get("citations", []),
                "query_type": data.get("query_complexity", data.get("query_type", "unknown")),
                "model_used": data.get("llm_model", data.get("model_used", "unknown")),
                "response_time_ms": data.get("processing_time_ms", data.get("response_time_ms", 0)),
                "debug_info": data.get("debug_info"),
                "retrieval_results_count": data.get("retrieval_results_count", 0)
            }
            
            return normalized
        except httpx.HTTPStatusError as e:
            logger.error(f"Query failed with status {e.response.status_code}: {e}")
            return {
                "error": True,
                "message": f"Server error: {e.response.status_code}",
                "detail": e.response.text
            }
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {"error": True, "message": str(e)}
    
    def upload_document(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Upload a document for indexing.
        
        Args:
            file_data (bytes): Raw file content.
            filename (str): Name of the file.
            
        Returns:
            Dict[str, Any]: Upload result containing document_id or error info.
        """
        try:
            # Verify ingestion service is accessible
            logger.info(f"Uploading {filename} ({len(file_data)} bytes) to {self.ingestion_url}")
            
            files = {"file": (filename, file_data, "application/octet-stream")}
            
            # Use longer timeout for large files
            timeout = 120.0 if len(file_data) > 10 * 1024 * 1024 else 60.0
            
            with httpx.Client(timeout=timeout) as client:
                headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
                response = client.post(
                    f"{self.ingestion_url}/api/v1/documents/upload",
                    files=files,
                    headers=headers
                )
                logger.info(f"Upload response status: {response.status_code}")
                
                if response.status_code != 200 and response.status_code != 202:
                    error_text = response.text[:500] if response.text else "No error details"
                    logger.error(f"Upload failed: {response.status_code} - {error_text}")
                    return {
                        "error": True,
                        "message": f"Server error '{response.status_code} {response.reason_phrase}' for url '{self.ingestion_url}/api/v1/documents/upload'",
                        "detail": error_text
                    }
                
                response.raise_for_status()
                return response.json()
                
        except httpx.ConnectError as e:
            logger.error(f"Connection error to {self.ingestion_url}: {e}")
            return {
                "error": True,
                "message": f"Cannot connect to ingestion service at {self.ingestion_url}. Is the service running?",
                "detail": str(e)
            }
        except httpx.TimeoutException as e:
            logger.error(f"Timeout uploading to {self.ingestion_url}: {e}")
            return {
                "error": True,
                "message": f"Upload timeout. The file may be too large or the service is slow.",
                "detail": str(e)
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e}")
            error_text = e.response.text[:500] if e.response.text else str(e)
            return {
                "error": True,
                "message": f"Server error '{e.response.status_code} {e.response.reason_phrase}' for url '{self.ingestion_url}/api/v1/documents/upload'",
                "detail": error_text
            }
        except Exception as e:
            logger.error(f"Document upload failed: {e}", exc_info=True)
            return {
                "error": True,
                "message": f"Upload failed: {str(e)}",
                "detail": str(e)
            }
    
    def get_document_status(self, doc_id: str) -> Dict[str, Any]:
        """
        Get status of an uploaded document.
        
        Args:
            doc_id (str): Document ID.
            
        Returns:
            Dict[str, Any]: Status info (processing_status, chunk_count, etc.).
        """
        try:
            response = self.client.get(
                f"{self.ingestion_url}/api/v1/documents/{doc_id}/status"
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Connection error to {self.ingestion_url}: {e}")
            return {"error": True, "message": f"Cannot connect to ingestion service: {str(e)}"}
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {"error": True, "message": str(e)}
    
    def poll_document_status(self, doc_id: str, max_wait_seconds: int = 120) -> Dict[str, Any]:
        """
        Poll document status until completion or timeout.
        
        Args:
            doc_id (str): Document ID.
            max_wait_seconds (int): Maximum seconds to wait.
            
        Returns:
            Dict[str, Any]: Final status or timeout error.
        """
        start_time = time.time()
        while (time.time() - start_time) < max_wait_seconds:
            status = self.get_document_status(doc_id)
            if "error" in status:
                return status
            
            processing_status = status.get("processing_status", "")
            if processing_status in ["completed", "failed"]:
                return status
            
            time.sleep(2)  # Poll every 2 seconds
        
        return {"error": True, "message": "Timeout waiting for document processing"}
    
    def clear_all_indexes(self) -> Dict[str, Any]:
        """
        Clear all vector indexes and metadata.
        
        Returns:
            Dict[str, Any]: Operation result.
        """
        try:
            # Clear indexes in ingestion service
            response = self.client.delete(f"{self.ingestion_url}/api/v1/documents/clear-all")
            response.raise_for_status()
            logger.info("Successfully cleared all indexes and metadata")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to clear indexes: {e}")
            return {"error": True, "message": str(e)}
    
    def generate_document_summary(self, filename: str, preview_text: str = "") -> Dict[str, Any]:
        """
        Generate a summary of the uploaded document.
        
        Constructs a query to ask the LLM for a summary of the provided text/document.
        
        Args:
            filename (str): Name of the file.
            preview_text (str): Optional text content to aid summarization.
            
        Returns:
            Dict[str, Any]: Response containing the summary.
        """
        try:
            # Create a simple query to summarize the document
            query = f"Please provide a brief summary of the document '{filename}'"
            
            # If we have preview text, use it as context
            if preview_text:
                response = self.submit_query(
                    f"Based on this document, provide a brief summary: {preview_text[:1000]}",
                    include_debug=False
                )
            else:
                # Otherwise just make a general query
                response = self.submit_query(
                    "What is this document about? Provide a brief overview.",
                    include_debug=False
                )
            
            return response
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return {
                "answer": f"Document '{filename}' has been successfully uploaded and indexed. You can now start asking questions about it!",
                "citations": []
            }
    
    # Product Catalog Methods
    def get_system_mode(self) -> str:
        """
        Get current system mode.
        
        Returns:
            str: 'document' or 'product'.
        """
        try:
            response = self.client.get(f"{self.ingestion_url}/api/v1/products/mode")
            response.raise_for_status()
            return response.json().get("mode", "document")
        except Exception as e:
            logger.error(f"Failed to get system mode: {e}")
            return "document"
    
    def set_system_mode(self, mode: str) -> Dict[str, Any]:
        """
        Switch system mode between document and product.
        
        Args:
            mode (str): Target mode ('document' or 'product').
            
        Returns:
            Dict[str, Any]: Operation result.
        """
        try:
            response = self.client.post(
                f"{self.ingestion_url}/api/v1/products/mode",
                data={"mode": mode}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to set system mode: {e}")
            return {"error": True, "message": str(e)}
    
    def upload_product_catalog(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Upload product catalog CSV/JSON file.
        
        Args:
            file_data (bytes): Raw file content.
            filename (str): Name of the file.
            
        Returns:
            Dict[str, Any]: Job info including job_id.
        """
        try:
            files = {"file": (filename, file_data)}
            response = self.client.post(
                f"{self.ingestion_url}/api/v1/products/upload",
                files=files
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to upload product catalog: {e}")
            return {"error": True, "message": str(e)}
    
    def confirm_product_mapping(self, job_id: str, catalog_name: str, field_mapping: Dict) -> Dict[str, Any]:
        """
        Confirm product field mapping and start processing.
        
        Args:
            job_id (str): Ingestion job ID.
            catalog_name (str): Name for the catalog.
            field_mapping (Dict): Mapping of file columns to standard product fields.
            
        Returns:
            Dict[str, Any]: Confirmation result.
        """
        try:
            response = self.client.post(
                f"{self.ingestion_url}/api/v1/products/confirm",
                data={
                    "job_id": job_id,
                    "catalog_name": catalog_name,
                    "field_mapping": json.dumps(field_mapping)
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to confirm product mapping: {e}")
            return {"error": True, "message": str(e)}
    
    def get_product_ingestion_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get product ingestion job status.
        
        Args:
            job_id (str): Job ID.
            
        Returns:
            Dict[str, Any]: Job status.
        """
        try:
            response = self.client.get(
                f"{self.ingestion_url}/api/v1/products/status/{job_id}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get ingestion status: {e}")
            return {"error": True, "message": str(e)}
    
    def get_catalog_info(self) -> Dict[str, Any]:
        """
        Get current catalog information.
        
        Returns:
            Dict[str, Any]: Catalog statistics (product count, categories).
        """
        try:
            response = self.client.get(f"{self.ingestion_url}/api/v1/products/catalog/info")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get catalog info: {e}")
            return {"loaded": False, "message": str(e)}
    
    def get_all_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all products from catalog.
        
        Args:
            limit (int): Maximum number of products to return.
            
        Returns:
            List[Dict[str, Any]]: List of product dictionaries.
        """
        try:
            # Use a generic query to get all products
            response = self.client.post(
                f"{self.gateway_url}/api/v1/search",
                json={"query": "product", "limit": limit}
            )
            response.raise_for_status()
            result = response.json()
            return result.get("results", [])
        except Exception as e:
            logger.error(f"Failed to get products: {e}")
            return []
    
    def search_products(self, query: str, filters: Optional[Dict] = None, limit: int = 100) -> Dict[str, Any]:
        """
        Search products using natural language query.
        
        Args:
            query (str): Search query.
            filters (Optional[Dict]): Filters to apply.
            limit (int): Max results.
            
        Returns:
            Dict[str, Any]: Search results and interpreted filters.
        """
        try:
            payload = {
                "query": query,
                "limit": limit
            }
            if filters:
                payload["filters"] = filters
            
            response = self.client.post(
                f"{self.gateway_url}/api/v1/search",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Product search failed: {e}")
            return {"error": True, "message": str(e), "results": []}
    
    def clear_product_catalog(self) -> Dict[str, Any]:
        """
        Clear all products from catalog.
        
        Returns:
            Dict[str, Any]: Operation result.
        """
        try:
            response = self.client.delete(f"{self.ingestion_url}/api/v1/products/clear")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to clear product catalog: {e}")
            return {"error": True, "message": str(e)}

    def reload_retrieval_indexes(self) -> Dict[str, Any]:
        """
        Reload retrieval indexes.
        
        Forces the retrieval service to reload indexes from disk.
        
        Returns:
            Dict[str, Any]: Operation result.
        """
        try:
            logger.info(f"Reloading indexes at {self.retrieval_url}")
            response = self.client.post(f"{self.retrieval_url}/api/v1/reload")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to reload indexes: {e}")
            return {"error": True, "message": str(e)}


def initialize_session_state():
    """
    Initialize session state variables.
    
    Sets up default values for chat history, UI service, document status,
    and product catalog state if they don't exist.
    """
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "ui_service" not in st.session_state:
        st.session_state.ui_service = UIService()
    if "current_document" not in st.session_state:
        st.session_state.current_document = None
    if "document_ready" not in st.session_state:
        st.session_state.document_ready = False
    if "active_citations" not in st.session_state:
        st.session_state.active_citations = {}
    if "upload_status" not in st.session_state:
        st.session_state.upload_status = None
    # Product catalog state
    if "system_mode" not in st.session_state:
        st.session_state.system_mode = "document"
    if "catalog_loaded" not in st.session_state:
        st.session_state.catalog_loaded = False
    if "catalog_info" not in st.session_state:
        st.session_state.catalog_info = None
    if "product_upload_job" not in st.session_state:
        st.session_state.product_upload_job = None
    if "all_products" not in st.session_state:
        st.session_state.all_products = []
    if "filtered_products" not in st.session_state:
        st.session_state.filtered_products = []
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    if "applied_filters" not in st.session_state:
        st.session_state.applied_filters = {}


def process_citations_in_text(answer: str, citations: List[Dict]) -> str:
    """
    Process citation markers in answer text.
    
    Replaces citation markers (e.g., [Page X]) with styled HTML badges.
    
    Args:
        answer (str): Text response from LLM.
        citations (List[Dict]): List of citation objects.
        
    Returns:
        str: HTML-formatted answer with styled citations.
    """
    # Find all citation patterns: [Page X], [Page X-Y], [Doc, Page X], or [X]
    citation_pattern = r'\[(Page \d+(?:-\d+)?|[^\]]+, Page \d+|\d+)\]'
    
    def replace_citation(match):
        citation_text = match.group(1)
        return f'<span class="citation-badge">[{citation_text}]</span>'
    
    # Replace all citations
    processed_answer = re.sub(citation_pattern, replace_citation, answer)
    return processed_answer


def render_header():
    """
    Render page header with mode switcher.
    
    Displays title and buttons to switch between 'RAG Chatbot' (Document)
    and 'Product Catalog Search' modes.
    """
    col1, col2 = st.columns([4, 1])
    with col1:
        if st.session_state.system_mode == "product":
            st.markdown('<div class="main-header">🛍️ Product Catalog Search</div>', unsafe_allow_html=True)
            st.markdown('<div class="sub-header">Search products with natural language queries</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="main-header">💬 RAG Chatbot</div>', unsafe_allow_html=True)
            st.markdown('<div class="sub-header">Ask questions about your documents</div>', unsafe_allow_html=True)
    with col2:
        # Mode switcher
        current_mode = st.session_state.system_mode
        if current_mode == "document":
            if st.button("🛍️ Switch to Products", use_container_width=True):
                result = st.session_state.ui_service.set_system_mode("product")
                if not result.get("error"):
                    st.session_state.system_mode = "product"
                    # Re-check catalog status instead of setting to False
                    st.session_state.catalog_info = None
                    st.session_state.all_products = []
                    st.session_state.filtered_products = []
                    st.rerun()
        else:
            if st.button("📄 Switch to Documents", use_container_width=True):
                result = st.session_state.ui_service.set_system_mode("document")
                if not result.get("error"):
                    st.session_state.system_mode = "document"
                    st.session_state.all_products = []
                    st.session_state.filtered_products = []
                    st.rerun()


def render_upload_panel():
    """
    Render left panel with document upload.
    
    Handles file upload widget, status display, and processing feedback loop.
    """
    st.markdown('<div class="upload-panel">', unsafe_allow_html=True)
    
    # Section header
    st.markdown('<div class="section-header">📄 Upload Document</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Upload a PDF to start asking questions</div>', unsafe_allow_html=True)
    
    # Show upload status
    if not st.session_state.current_document:
        st.markdown(
            '<div class="status-indicator">⚠️ No document uploaded</div>',
            unsafe_allow_html=True
        )
    else:
        doc_name = st.session_state.current_document.get("filename", "Unknown")
        chunk_count = st.session_state.current_document.get("chunk_count", 0)
        st.markdown(
            f'<div class="status-indicator status-success">✅ <strong>{doc_name}</strong><br/>'
            f'<span style="font-size: 0.8rem; margin-left: 1.5rem;">{chunk_count} chunks indexed</span></div>',
            unsafe_allow_html=True
        )
    
    # Upload interface
    st.markdown('''
    <div class="upload-box">
        <div class="upload-icon">📤</div>
        <div class="upload-text">Drop your PDF here</div>
        <div style="color: #9ca3af; font-size: 0.875rem; margin-bottom: 1rem;">or</div>
    </div>
    ''', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["pdf", "docx", "txt"],
        help="Supported formats: PDF, DOCX, TXT (max 100MB per file)",
        label_visibility="collapsed",
        key="file_uploader"
    )
    
    if uploaded_file:
        st.info(f"📄 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
    
    upload_button = st.button(
        "🚀 Upload",
        type="primary",
        use_container_width=True,
        disabled=(uploaded_file is None)
    )
    
    if upload_button and uploaded_file is not None:
        # Create placeholder for status updates
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        # Clear existing indexes silently (single document mode)
        # This ensures we always start fresh with just one document
        status_placeholder.info("🗑️ Clearing previous data...")
        progress_bar.progress(10)
        st.session_state.ui_service.clear_all_indexes()
        
        # Upload document
        status_placeholder.info("⬆️ Uploading document...")
        progress_bar.progress(20)
        
        result = st.session_state.ui_service.upload_document(
            uploaded_file.read(),
            uploaded_file.name
        )
        
        if "error" in result:
            status_placeholder.error(f"❌ Upload failed: {result['message']}")
            progress_bar.empty()
        else:
            doc_id = result.get("document_id", result.get("doc_id"))
            
            # Poll for processing status
            status_placeholder.info("🔄 Processing document...")
            progress_bar.progress(40)
            
            max_attempts = 60
            attempt = 0
            while attempt < max_attempts:
                status_info = st.session_state.ui_service.get_document_status(doc_id)
                
                if "error" in status_info:
                    status_placeholder.error(f"❌ Status check failed: {status_info['message']}")
                    break
                
                processing_status = status_info.get("processing_status", "unknown")
                chunk_count = status_info.get("chunk_count", 0)
                
                if processing_status == "completed":
                    progress_bar.progress(100)
                    status_placeholder.success(f"✅ Document processed! ({chunk_count} chunks indexed)")
                    
                    # Reload retrieval service to pick up new indexes
                    try:
                        logger.info("Reloading retrieval service with new document data")
                        retrieval_url = "http://localhost:8002"
                        reload_response = st.session_state.ui_service.client.post(f"{retrieval_url}/api/v1/reload")
                        reload_response.raise_for_status()
                        logger.info("Successfully reloaded retrieval service after document upload")
                    except Exception as reload_error:
                        logger.warning(f"Failed to reload retrieval service: {reload_error}")
                    
                    # Store document info
                    st.session_state.current_document = {
                        "doc_id": doc_id,
                        "filename": uploaded_file.name,
                        "timestamp": datetime.now().isoformat(),
                        "chunk_count": chunk_count
                    }
                    st.session_state.document_ready = True
                    
                    # Reload retrieval indexes so the new document can be found
                    with st.spinner("Reloading search indexes..."):
                        st.session_state.ui_service.reload_retrieval_indexes()
                    
                    # Generate summary and add as first message
                    with st.spinner("Generating document summary..."):
                        summary_response = st.session_state.ui_service.generate_document_summary(
                            uploaded_file.name
                        )
                        
                        # Clear chat and add welcome message
                        st.session_state.chat_history = []
                        
                        welcome_message = {
                            "type": "assistant",
                            "response": summary_response,
                            "timestamp": datetime.now().strftime("%I:%M %p"),
                            "id": "welcome_message",
                            "is_welcome": True
                        }
                        st.session_state.chat_history.append(welcome_message)
                    
                    time.sleep(1)
                    status_placeholder.empty()
                    progress_bar.empty()
                    st.rerun()
                    break
                
                elif processing_status == "failed":
                    error_msg = status_info.get("error_message", "Unknown error")
                    status_placeholder.error(f"❌ Processing failed: {error_msg}")
                    progress_bar.empty()
                    break
                
                elif processing_status == "processing":
                    progress = min(40 + (attempt * 50 // max_attempts), 90)
                    progress_bar.progress(progress)
                    status_placeholder.info(f"🔄 Processing document... ({attempt * 2}s)")
                
                time.sleep(2)
                attempt += 1
            
            if attempt >= max_attempts:
                status_placeholder.warning("⏱️ Processing is taking longer than expected.")
                progress_bar.empty()
    
    # Instructions
    st.markdown('''
    <div class="instructions">
        <div class="instructions-title">Instructions:</div>
        <ul>
            <li>Upload a PDF document (max 100MB)</li>
            <li>Wait for processing to complete</li>
            <li>Start asking questions in the chat</li>
            <li>Get intelligent answers based on your document</li>
        </ul>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close upload-panel


def render_chat_panel():
    """
    Render right panel with chat interface.
    
    Displays chat history, empty state (if no doc), and chat input.
    Handles message submission and response rendering.
    """
    st.markdown('<div class="chat-panel">', unsafe_allow_html=True)
    
    # Section header
    st.markdown('<div class="section-header">💬 Chat Assistant</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Upload a document to start chatting</div>', unsafe_allow_html=True)
    
    if not st.session_state.document_ready:
        # Empty state
        st.markdown('''
        <div class="chat-empty-state">
            <div class="chat-empty-icon">🤖</div>
            <div class="chat-empty-title">No Document Loaded</div>
            <div class="chat-empty-subtitle">Upload a PDF document on the left to start asking questions and get intelligent answers powered by AI</div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        
        # Chat messages container
        chat_container = st.container()
        
        with chat_container:
            if st.session_state.chat_history:
                for message in st.session_state.chat_history:
                    render_chat_message(message)
            
        # Chat input at bottom
        st.markdown("---")
        
        col1, col2 = st.columns([5, 1])
        
        with col1:
            query = st.text_input(
                "Type your question...",
                placeholder="Upload a document first...",
                key="chat_input",
                label_visibility="collapsed"
            )
        
        with col2:
            submit_button = st.button("📤 Send", type="primary", use_container_width=True)
        
        # Help text
        st.caption("Press Enter to send • The AI will answer based on your uploaded document")
        
        # Process query
        if submit_button and query.strip():
            # Add user message
            user_message = {
                "type": "user",
                "content": query,
                "timestamp": datetime.now().strftime("%I:%M %p"),
                "id": f"user_{len(st.session_state.chat_history)}"
            }
            st.session_state.chat_history.append(user_message)
            
            # Get response
            with st.spinner("🤔 Thinking..."):
                response = st.session_state.ui_service.submit_query(query, include_debug=False)
            
            # Add assistant message
            assistant_message = {
                "type": "assistant",
                "response": response,
                "timestamp": datetime.now().strftime("%I:%M %p"),
                "id": f"assistant_{len(st.session_state.chat_history)}"
            }
            st.session_state.chat_history.append(assistant_message)
            
            st.rerun()
        
        elif submit_button:
            st.warning("⚠️ Please enter a question")
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close chat-panel


def render_chat_message(message: Dict[str, Any]):
    """
    Render a single chat message (user or assistant).
    
    Args:
        message (Dict[str, Any]): Message object containing type, content/response, etc.
    """
    message_type = message.get("type", "assistant")
    
    if message_type == "user":
        # User message bubble
        st.markdown(
            f'<div class="user-message">{message["content"]}</div>',
            unsafe_allow_html=True
        )
    else:
        # Assistant message
        response = message.get("response", {})
        
        if "error" in response:
            st.error(f"❌ {response.get('message', 'An error occurred')}")
            return
        
        # Get answer and process citations
        answer = response.get("answer", "No answer generated")
        citations = response.get("citations", [])
        
        # Check if this is the welcome message
        is_welcome = message.get("is_welcome", False)
        
        if is_welcome:
            # Format welcome message differently
            welcome_text = f"""
            <div class="assistant-message" style="max-width: 100%; background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border: 1px solid #0ea5e9;">
                <div style="margin-bottom: 0.75rem; color: #0369a1; font-weight: 600; font-size: 1rem;">📄 Document Summary</div>
                <div style="color: #1f2937; line-height: 1.7;">{answer}</div>
                <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid #bae6fd; font-size: 0.9rem; color: #0369a1; font-weight: 500;">
                    💡 Let me know how I can help you with this document!
                </div>
            </div>
            """
            st.markdown(welcome_text, unsafe_allow_html=True)
        else:
            # Regular message with citations
            if citations:
                processed_answer = process_citations_in_text(answer, citations)
            else:
                processed_answer = answer
            
            st.markdown(f'<div class="assistant-message">{processed_answer}</div>', unsafe_allow_html=True)
            
            # Show sources if available
            if citations:
                with st.expander(f"📚 View {len(citations)} Source(s)", expanded=False):
                    for i, citation in enumerate(citations[:5], 1):
                        doc_id = citation.get('document_id', 'N/A')
                        page_num = citation.get('page_number', 'N/A')
                        snippet = citation.get('relevant_text_snippet', '')
                        
                        st.markdown(f"**[{i}]** Page {page_num}")
                        if snippet:
                            st.text(snippet[:200] + "..." if len(snippet) > 200 else snippet)
                        st.markdown("---")




def render_catalog_sidebar():
    """
    Render compact sidebar for catalog management.
    
    Displays catalog status, clear button, and file uploader for new catalogs.
    """
    with st.sidebar:
        st.markdown("### 📦 Catalog Management")
        
        # Check catalog status
        if st.session_state.catalog_info is None:
            catalog_info = st.session_state.ui_service.get_catalog_info()
            st.session_state.catalog_info = catalog_info
            st.session_state.catalog_loaded = catalog_info.get("loaded", False)
        
        if st.session_state.catalog_loaded:
            info = st.session_state.catalog_info
            st.success(f"✅ {info.get('product_count', 0)} Products Loaded")
            st.caption(f"Categories: {len(info.get('categories', []))}")
            
            if st.button("🗑️ Clear Catalog", use_container_width=True):
                result = st.session_state.ui_service.clear_product_catalog()
                if not result.get("error"):
                    st.session_state.catalog_loaded = False
                    st.session_state.catalog_info = None
                    st.session_state.all_products = []
                    st.session_state.filtered_products = []
                    st.rerun()
        else:
            st.warning("⚠️ No catalog loaded")
        
        # File upload
        st.markdown("---")
        st.markdown("**Upload New Catalog**")
        uploaded_file = st.file_uploader(
            "Select File",
            type=["csv", "json", "xlsx"],
            help="Upload CSV/JSON with products"
        )
        
        if uploaded_file is not None:
            if st.button("📤 Upload", type="primary", use_container_width=True):
                with st.spinner("Processing..."):
                    file_data = uploaded_file.read()
                    result = st.session_state.ui_service.upload_product_catalog(
                        file_data, uploaded_file.name
                    )
                    
                    if result.get("error"):
                        st.error(f"Upload failed")
                    else:
                        job_id = result.get("job_id")
                        
                        # Auto-confirm mapping
                        if result.get("requires_confirmation"):
                            suggested = result.get("suggested_mapping", {})
                            st.session_state.ui_service.confirm_product_mapping(
                                job_id, "Products", suggested
                            )
                        
                        # Monitor processing
                        progress_bar = st.progress(0)
                        max_attempts = 30
                        
                        for attempt in range(max_attempts):
                            status = st.session_state.ui_service.get_product_ingestion_status(job_id)
                            if status.get("status") == "complete":
                                progress_bar.progress(100)
                                st.session_state.catalog_loaded = True
                                st.session_state.catalog_info = None
                                st.session_state.all_products = []
                                
                                # Reload retrieval indexes
                                with st.spinner("Reloading search indexes..."):
                                    st.session_state.ui_service.reload_retrieval_indexes()
                                
                                time.sleep(1)
                                st.rerun()
                                break
                            elif status.get("status") == "failed":
                                st.error("Processing failed")
                                break
                            else:
                                progress = min(10 + (attempt * 80 // max_attempts), 90)
                                progress_bar.progress(progress)
                                time.sleep(2)


def render_ecommerce_store():
    """
    Render main e-commerce product display.
    
    Shows product grid, search bar, and empty states.
    """
    
    if not st.session_state.catalog_loaded:
        st.markdown('''
        <div class="chat-empty-state" style="padding: 3rem; text-align: center;">
            <div class="chat-empty-icon" style="font-size: 4rem;">🛍️</div>
            <div class="chat-empty-title" style="font-size: 1.5rem; margin: 1rem 0;">No Products Available</div>
            <div class="chat-empty-subtitle">Upload a product catalog from the sidebar to get started</div>
        </div>
        ''', unsafe_allow_html=True)
        return
    
    # Load all products if not already loaded
    if not st.session_state.all_products:
        with st.spinner("Loading products..."):
            products = st.session_state.ui_service.get_all_products(limit=100)
            st.session_state.all_products = products
            st.session_state.filtered_products = products
    
    # Search and filter bar
    render_search_bar()
    
    # Display products
    products_to_show = st.session_state.filtered_products if st.session_state.filtered_products else st.session_state.all_products
    
    if not products_to_show:
        st.info("🔍 No products found matching your search. Try different keywords or filters.")
        return
    
    # Results header
    st.markdown(f'<div class="results-header"><h3 style="margin:0;">{len(products_to_show)} Products</h3></div>', unsafe_allow_html=True)
    
    # Product grid
    render_product_grid(products_to_show)


def render_search_bar():
    """
    Render search bar with filters.
    
    Handles text input, search button, clear button, and active filter display.
    """
    st.markdown('<div class="search-bar-container">', unsafe_allow_html=True)
    
    # Search input
    col1, col2, col3 = st.columns([6, 1, 1])
    
    with col1:
        query = st.text_input(
            "Search",
            placeholder="Search for products...",
            key="search_input",
            label_visibility="collapsed"
        )
    
    with col2:
        search_clicked = st.button("🔍 Search", type="primary", use_container_width=True)
    
    with col3:
        clear_clicked = st.button("Clear", use_container_width=True)
    
    # Process search
    if search_clicked and query.strip():
        st.session_state.search_query = query
        with st.spinner("Searching..."):
            results = st.session_state.ui_service.search_products(query, limit=100)
            if not results.get("error"):
                st.session_state.filtered_products = results.get("results", [])
                st.session_state.applied_filters = results.get("query_interpretation", {}).get("extracted_filters", {})
                st.rerun()
    
    # Clear search
    if clear_clicked:
        st.session_state.search_query = ""
        st.session_state.filtered_products = st.session_state.all_products
        st.session_state.applied_filters = {}
        st.rerun()
    
    # Show active filters
    if st.session_state.search_query or st.session_state.applied_filters:
        st.markdown('<div class="filter-chips">', unsafe_allow_html=True)
        
        if st.session_state.search_query:
            st.markdown(f'<span class="filter-chip">🔍 "{st.session_state.search_query}"</span>', unsafe_allow_html=True)
        
        filters = st.session_state.applied_filters
        if filters.get("price_max"):
            st.markdown(f'<span class="filter-chip">💰 Under ${filters["price_max"]}</span>', unsafe_allow_html=True)
        if filters.get("price_min"):
            st.markdown(f'<span class="filter-chip">💰 Over ${filters["price_min"]}</span>', unsafe_allow_html=True)
        if filters.get("rating_min"):
            st.markdown(f'<span class="filter-chip">⭐ {filters["rating_min"]}+ stars</span>', unsafe_allow_html=True)
        if filters.get("categories"):
            for cat in filters["categories"]:
                st.markdown(f'<span class="filter-chip">📂 {cat}</span>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)


def render_product_grid(products: List[Dict[str, Any]]):
    """
    Render products in a responsive grid.
    
    Args:
        products (List[Dict[str, Any]]): List of product dictionaries to display.
    """
    # Display 4 products per row
    cols_per_row = 4
    
    for i in range(0, len(products), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(products):
                with col:
                    render_product_card(products[i + j])


def render_product_card(product: Dict[str, Any]):
    """
    Render a single product card with image.
    
    Starts HTML block for product card styling.
    
    Args:
        product (Dict[str, Any]): Product data.
    """
    # Extract product data
    name = product.get("name", "Unknown Product")
    price = product.get("price")
    rating = product.get("rating")
    review_count = product.get("review_count", 0)
    category = product.get("category", "")
    image_url = product.get("image_url") or product.get("metadata", {}).get("image_url", "")
    brand = product.get("brand") or product.get("metadata", {}).get("brand", "")
    
    # Fallback image if none provided
    if not image_url:
        image_url = "https://via.placeholder.com/400x400/e5e7eb/6b7280?text=No+Image"
    
    # Rating stars
    stars_filled = int(rating) if rating else 0
    stars_empty = 5 - stars_filled
    stars_html = "★" * stars_filled + "☆" * stars_empty
    
    # Product card HTML
    card_html = f"""
    <div class="product-card">
        <img src="{image_url}" class="product-image" alt="{name}" />
        <div class="product-info">
            <div class="product-name">{name}</div>
            <div class="product-rating">
                <span style="color: #f59e0b;">{stars_html}</span>
                <span style="color: #6b7280;">({review_count:,})</span>
            </div>
            <div class="product-price">${price:.2f}</div>
            <div class="product-category">{category}</div>
        </div>
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)


def main():
    """
    Main application entry point.
    
    Initializes session state, routing, and proper page layout based on system mode.
    """
    # Keycloak Login
    keycloak_config = {
        "url": os.getenv("KEYCLOAK_URL", os.getenv("BASE_URL", "http://localhost:8080")),
        "realm": os.getenv("KEYCLOAK_REALM", "master"),
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID", "api")
    }
    
    # keycloak = login(
    #     url=keycloak_config["url"],
    #     realm=keycloak_config["realm"],
    #     client_id=keycloak_config["client_id"],
    #     init_options={'checkLoginIframe': False}
    # )

    # if not keycloak.authenticated:
    #     st.warning("Please login to access the system.")
    #     st.stop()

    initialize_session_state()
    
    # Note: Keycloak authentication is handled at the service level (embedding, llm, etc.)
    # The UI communicates with services through the gateway without needing to pass tokens
    
    # Get current system mode
    if "system_mode_initialized" not in st.session_state:
        current_mode = st.session_state.ui_service.get_system_mode()
        st.session_state.system_mode = current_mode
        st.session_state.system_mode_initialized = True
    
    render_header()
    
    st.markdown('<div style="height: 0.5rem;"></div>', unsafe_allow_html=True)
    
    if st.session_state.system_mode == "product":
        # E-commerce mode: sidebar + full-width store
        render_catalog_sidebar()
        render_ecommerce_store()
    else:
        # Document mode: two-column layout
        col1, col2 = st.columns([1, 2], gap="medium")
        with col1:
            render_upload_panel()
        with col2:
            render_chat_panel()


if __name__ == "__main__":
    main()

