"""
Product Data Models
Pydantic models for product data structures
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ProductBase(BaseModel):
    """Base product model"""
    name: str = Field(..., description="Product name/title")
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Product category")
    price: Optional[float] = Field(None, description="Product price", ge=0)
    rating: Optional[float] = Field(None, description="Product rating (0-5)", ge=0, le=5)
    review_count: Optional[int] = Field(None, description="Number of reviews", ge=0)
    image_url: Optional[str] = Field(None, description="Product image URL")
    brand: Optional[str] = Field(None, description="Product brand")


class ProductCreate(ProductBase):
    """Product creation model"""
    id: Optional[str] = Field(None, description="Product ID (auto-generated if not provided)")
    embedding_text: Optional[str] = Field(None, description="Text used for embedding")


class ProductInDB(ProductBase):
    """Product model as stored in database"""
    id: str
    embedding_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    attributes: Dict[str, str] = Field(default_factory=dict, description="Product attributes")
    
    class Config:
        from_attributes = True


class ProductAttribute(BaseModel):
    """Product attribute model"""
    attribute_name: str = Field(..., description="Attribute name (e.g., 'color', 'size')")
    attribute_value: str = Field(..., description="Attribute value")


class CatalogMetadata(BaseModel):
    """Catalog metadata model"""
    catalog_name: str = Field(..., description="Catalog name")
    upload_date: datetime
    product_count: int = Field(..., description="Number of products", ge=0)
    categories: List[str] = Field(default_factory=list, description="List of unique categories")
    price_range_min: Optional[float] = Field(None, description="Minimum price in catalog")
    price_range_max: Optional[float] = Field(None, description="Maximum price in catalog")


class ProductSearchResult(BaseModel):
    """Product search result model"""
    product_id: str
    name: str
    description: str = Field(..., description="Truncated description (~200 chars)")
    category: Optional[str] = None
    price: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    image_url: Optional[str] = None
    relevance_score: float = Field(..., description="RRF relevance score", ge=0, le=1)
    match_reasons: List[str] = Field(default_factory=list, description="Why this product matched")
    attributes: Dict[str, str] = Field(default_factory=dict, description="Product attributes")


class SearchResponse(BaseModel):
    """Search response model"""
    query: str
    interpreted_as: str = Field(..., description="Cleaned semantic query")
    applied_filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")
    total_matches: int = Field(..., description="Total matches before limit", ge=0)
    results: List[ProductSearchResult]
    suggested_filters: List[str] = Field(default_factory=list, description="Suggested filter refinements")


class FieldMapping(BaseModel):
    """Field mapping model for CSV/JSON parsing"""
    name: Optional[str] = Field(None, description="Maps to product name")
    description: Optional[str] = Field(None, description="Maps to product description")
    category: Optional[str] = Field(None, description="Maps to product category")
    price: Optional[str] = Field(None, description="Maps to product price")
    rating: Optional[str] = Field(None, description="Maps to product rating")
    review_count: Optional[str] = Field(None, description="Maps to review count")
    image_url: Optional[str] = Field(None, description="Maps to image URL")
    brand: Optional[str] = Field(None, description="Maps to product brand")
    id: Optional[str] = Field(None, description="Maps to product ID")


class UploadResponse(BaseModel):
    """Product upload response"""
    job_id: str
    status: str = Field(..., description="processing, pending_confirmation, or error")
    detected_columns: List[str] = Field(default_factory=list, description="Detected CSV/JSON columns")
    suggested_mapping: Optional[FieldMapping] = Field(None, description="Suggested field mapping")
    requires_confirmation: bool = Field(False, description="Whether user confirmation is needed")
    error_message: Optional[str] = Field(None, description="Error message if status is error")


class ProcessingStatus(BaseModel):
    """Processing status response"""
    job_id: str
    status: str = Field(..., description="processing, complete, or error")
    progress: float = Field(..., description="Progress percentage (0-1)", ge=0, le=1)
    products_processed: int = Field(..., description="Number of products processed", ge=0)
    products_total: int = Field(..., description="Total number of products", ge=0)
    current_step: str = Field(..., description="Current processing step")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")

