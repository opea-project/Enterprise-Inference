from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

from app.api.routes import router
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PDF_SERVICE_NAME,
    description="Extract text from PDFs with OCR support for scanned documents",
    version=settings.PDF_SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, tags=["PDF Processing"])

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info(f"{settings.PDF_SERVICE_NAME} starting up...")
    logger.info(f"Service running on port {settings.PDF_SERVICE_PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info(f"{settings.PDF_SERVICE_NAME} shutting down...")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.PDF_SERVICE_NAME,
        "version": settings.PDF_SERVICE_VERSION,
        "description": "Extract text from PDFs with OCR support",
        "endpoints": {
            "extract": "POST /extract - Extract text from PDF",
            "extract_structure": "POST /extract-structure - Extract document structure",
            "extract_with_ocr": "POST /extract-with-ocr - Force OCR extraction",
            "health": "GET /health - Health check",
            "languages": "GET /languages - Supported OCR languages",
            "docs": "GET /docs - API documentation"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PDF_SERVICE_PORT)
