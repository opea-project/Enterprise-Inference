"""
Product Parser
Handles CSV/JSON parsing with field detection and mapping
"""

import logging
import csv
import json
import io
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
from schemas.product_schemas import FieldMapping

logger = logging.getLogger(__name__)


class ProductParser:
    """
    Parse product data from CSV/JSON/XLSX files.
    
    Handlers format detection, parsing, and column mapping normalization
    to standardized product fields.
    """
    
    # Common field name variations
    FIELD_MAPPINGS = {
        'name': ['name', 'title', 'product_name', 'product_title', 'item_name', 'item'],
        'description': ['description', 'desc', 'details', 'product_description', 'summary'],
        'category': ['category', 'categories', 'cat', 'product_category', 'type'],
        'price': ['price', 'cost', 'amount', 'product_price', 'cost_price', 'list_price'],
        'rating': ['rating', 'stars', 'star_rating', 'avg_rating', 'average_rating', 'score'],
        'review_count': ['review_count', 'reviews', 'num_reviews', 'review_number', 'total_reviews'],
        'image_url': ['image_url', 'image', 'img', 'image_link', 'picture', 'photo'],
        'brand': ['brand', 'manufacturer', 'maker', 'company', 'vendor'],
        'id': ['id', 'product_id', 'item_id', 'sku', 'asin', 'identifier']
    }
    
    def __init__(self):
        """Initialize product parser"""
        pass
    
    def detect_file_type(self, filename: str) -> str:
        """
        Detect file type from filename extension.
        
        Args:
            filename (str): Name of the file.
            
        Returns:
            str: Detected type ('csv', 'json', 'xlsx', or 'unknown').
        """
        ext = Path(filename).suffix.lower()
        if ext == '.csv':
            return 'csv'
        elif ext == '.json':
            return 'json'
        elif ext in ['.xlsx', '.xls']:
            return 'xlsx'
        else:
            return 'unknown'
    
    def parse_csv(self, content: bytes, filename: str) -> tuple[List[Dict], List[str]]:
        """
        Parse CSV file content.
        
        Args:
            content (bytes): File content bytes.
            filename (str): Original filename (used for logging).
            
        Returns:
            tuple[List[Dict], List[str]]: Tuple containing:
                - List of product dictionaries (rows)
                - List of column names found
        """
        try:
            # Try to detect encoding
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = content.decode('latin-1')
            except UnicodeDecodeError:
                text = content.decode('utf-8', errors='ignore')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(text))
        columns = csv_reader.fieldnames or []
        
        # Ensure columns is a list of strings
        if columns:
            columns = [str(col) if not isinstance(col, str) else col for col in columns]
        else:
            columns = []
        
        products = []
        for row in csv_reader:
            # Convert empty strings to None
            clean_row = {k: (v if v and v.strip() else None) for k, v in row.items()}
            products.append(clean_row)
        
        logger.info(f"Parsed CSV: {len(products)} products, {len(columns)} columns")
        return products, columns
    
    def parse_json(self, content: bytes) -> tuple[List[Dict], List[str]]:
        """
        Parse JSON file content.
        
        Handles simple lists, or wrapped objects (e.g. {'products': [...]}).
        
        Args:
            content (bytes): File content bytes.
            
        Returns:
            tuple[List[Dict], List[str]]: Tuple containing:
                - List of product dictionaries
                - List of unique field names found across all products
                
        Raises:
            ValueError: If JSON structure is invalid/unsupported.
        """
        try:
            text = content.decode('utf-8')
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            raise ValueError(f"Invalid JSON format: {e}")
        
        # Handle different JSON structures
        if isinstance(data, list):
            products = data
        elif isinstance(data, dict):
            # Check if it's a wrapper object
            if 'products' in data:
                products = data['products']
            elif 'items' in data:
                products = data['items']
            else:
                # Single product
                products = [data]
        else:
            raise ValueError("JSON must be an object or array")
        
        # Get all unique field names
        all_fields = set()
        for product in products:
            if isinstance(product, dict):
                all_fields.update(product.keys())
        
        logger.info(f"Parsed JSON: {len(products)} products, {len(all_fields)} fields")
        return products, list(all_fields)
    
    def parse_xlsx(self, content: bytes) -> tuple[List[Dict], List[str]]:
        """
        Parse Excel (XLSX) file content.
        
        Args:
            content (bytes): File content bytes.
            
        Returns:
            tuple[List[Dict], List[str]]: Tuple containing:
                - List of product dictionaries (rows)
                - List of column names
                
        Raises:
            ValueError: If parsing fails.
        """
        try:
            # Read Excel file
            df = pd.read_excel(io.BytesIO(content))
            columns = df.columns.tolist()
            
            # Convert to list of dictionaries
            products = df.replace({pd.NA: None, '': None}).to_dict('records')
            
            logger.info(f"Parsed XLSX: {len(products)} products, {len(columns)} columns")
            return products, columns
        except Exception as e:
            logger.error(f"XLSX parse error: {e}")
            raise ValueError(f"Failed to parse XLSX file: {e}")
    
    def detect_field_mapping(self, columns: List[str]) -> FieldMapping:
        """
        Auto-detect field mapping from column names.
        
        Uses common variations (e.g., 'cost' -> 'price') to suggest mappings.
        
        Args:
            columns (List[str]): List of column names from the file.
            
        Returns:
            FieldMapping: Object containing suggested field-to-column mappings.
        """
        mapping = FieldMapping()
        
        # Normalize column names for matching (handle tuples/strings)
        normalized_columns = {}
        for col in columns:
            # Convert to string if it's a tuple or other type
            col_str = str(col) if not isinstance(col, str) else col
            normalized_key = col_str.lower().strip().replace(' ', '_').replace('-', '_')
            normalized_columns[normalized_key] = col_str
        
        # Try to match each field
        for field_name, variations in self.FIELD_MAPPINGS.items():
            for variation in variations:
                normalized_var = variation.lower().strip().replace(' ', '_').replace('-', '_')
                if normalized_var in normalized_columns:
                    # Found a match
                    setattr(mapping, field_name, normalized_columns[normalized_var])
                    break
        
        logger.info(f"Detected field mapping: {mapping.model_dump(exclude_none=True)}")
        return mapping
    
    def parse_file(
        self,
        content: bytes,
        filename: str,
        field_mapping: Optional[FieldMapping] = None
    ) -> tuple[List[Dict], List[str], FieldMapping]:
        """
        Parse product file and return products with field mapping.
        
        Main entry point that delegates to specific parsers based on file type.
        
        Args:
            content (bytes): File content.
            filename (str): Name of file.
            field_mapping (Optional[FieldMapping]): Existing mapping to use, or None to auto-detect.
            
        Returns:
            tuple: (products, columns, field_mapping)
            
        Raises:
            ValueError: If file type unsupported or required fields missing.
        """
        file_type = self.detect_file_type(filename)
        
        if file_type == 'csv':
            products, columns = self.parse_csv(content, filename)
        elif file_type == 'json':
            products, columns = self.parse_json(content)
        elif file_type == 'xlsx':
            products, columns = self.parse_xlsx(content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Ensure columns are strings
        columns = [str(col) if not isinstance(col, str) else col for col in columns]
        
        # Auto-detect mapping if not provided
        if field_mapping is None:
            field_mapping = self.detect_field_mapping(columns)
        
        # Validate required fields
        if not field_mapping.name:
            raise ValueError("Required field 'name' not found. Please provide field mapping.")
        
        logger.info(f"Parsed {len(products)} products from {filename}")
        return products, columns, field_mapping
    
    def apply_field_mapping(
        self,
        products: List[Dict],
        field_mapping: FieldMapping
    ) -> List[Dict]:
        """
        Apply field mapping to normalize product dictionaries.
        
        Renames keys in product dictionaries according to the mapping.
        
        Args:
            products (List[Dict]): List of raw product dictionaries.
            field_mapping (FieldMapping): Mapping configuration.
            
        Returns:
            List[Dict]: List of normalized product dictionaries.
        """
        normalized_products = []
        
        for product in products:
            normalized = {}
            mapping_dict = field_mapping.model_dump(exclude_none=True)
            
            for target_field, source_field in mapping_dict.items():
                if source_field in product:
                    normalized[target_field] = product[source_field]
                else:
                    normalized[target_field] = None
            
            normalized_products.append(normalized)
        
        return normalized_products

