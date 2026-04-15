"""
Product Processor
Handles data validation, text preparation, and batch processing
"""

import logging
import re
import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from schemas.product_schemas import ProductCreate

logger = logging.getLogger(__name__)


class ProductProcessor:
    """
    Process and validate product data.
    
    Handles data cleaning, normalization (price, rating), validation, and 
    generation of embedding text fields.
    """
    
    def __init__(self, embedding_field_template: str = None):
        """
        Initialize product processor.
        
        Args:
            embedding_field_template (str, optional): Template for creating embedding text.
                Default: "{name}. {description}. Category: {category}. Brand: {brand}"
        """
        self.embedding_field_template = embedding_field_template or \
            "{name}. {description}. Category: {category}. Brand: {brand}"
    
    def normalize_price(self, price: any) -> Optional[float]:
        """
        Normalize price from various formats.
        
        Handles strings with currency symbols ($, €, etc.), commas, and ISO codes.
        
        Args:
            price (any): Price value (string, float, int, or None).
            
        Returns:
            Optional[float]: Normalized price as float, or None if invalid.
        """
        if price is None:
            return None
        
        if isinstance(price, (int, float)):
            return float(price) if price >= 0 else None
        
        if isinstance(price, str):
            # Remove currency symbols and whitespace
            price_str = price.strip()
            if not price_str:
                return None
            
            # Remove common currency symbols
            price_str = re.sub(r'[$€£¥₹]', '', price_str)
            
            # Remove "USD", "EUR", etc.
            price_str = re.sub(r'\b(USD|EUR|GBP|JPY|INR)\b', '', price_str, flags=re.IGNORECASE)
            
            # Remove commas and other formatting
            price_str = price_str.replace(',', '').strip()
            
            # Extract number
            match = re.search(r'[\d.]+', price_str)
            if match:
                try:
                    value = float(match.group())
                    return value if value >= 0 else None
                except ValueError:
                    return None
        
        return None
    
    def normalize_rating(self, rating: any) -> Optional[float]:
        """
        Normalize rating to 0-5 scale.
        
        Handles string parsing and rescaling 0-10 ratings to 0-5.
        
        Args:
            rating (any): Rating value (string, float, int, or None).
            
        Returns:
            Optional[float]: Normalized rating (0-5) or None.
        """
        if rating is None:
            return None
        
        if isinstance(rating, (int, float)):
            value = float(rating)
            # If rating is > 5, assume it's out of 10 and scale down
            if value > 5:
                value = value / 2.0
            return value if 0 <= value <= 5 else None
        
        if isinstance(rating, str):
            rating_str = rating.strip()
            if not rating_str:
                return None
            
            # Extract number
            match = re.search(r'[\d.]+', rating_str)
            if match:
                try:
                    value = float(match.group())
                    # If rating is > 5, assume it's out of 10 and scale down
                    if value > 5:
                        value = value / 2.0
                    return value if 0 <= value <= 5 else None
                except ValueError:
                    return None
        
        return None
    
    def normalize_review_count(self, count: any) -> Optional[int]:
        """
        Normalize review count.
        
        Removes commas and parses integers.
        
        Args:
            count (any): Review count value (string, int, or None).
            
        Returns:
            Optional[int]: Normalized review count as int or None.
        """
        if count is None:
            return None
        
        if isinstance(count, int):
            return count if count >= 0 else None
        
        if isinstance(count, str):
            count_str = count.strip()
            if not count_str:
                return None
            
            # Remove commas and extract number
            count_str = count_str.replace(',', '').strip()
            match = re.search(r'\d+', count_str)
            if match:
                try:
                    value = int(match.group())
                    return value if value >= 0 else None
                except ValueError:
                    return None
        
        return None
    
    def clean_text(self, text: Optional[str], max_length: int = None) -> Optional[str]:
        """
        Clean and normalize text.
        
        Removes HTML tags, normalizes whitespace, and truncates if necessary.
        
        Args:
            text (Optional[str]): Text to clean.
            max_length (int, optional): Maximum length (truncate if longer).
            
        Returns:
            Optional[str]: Cleaned text or None if empty.
        """
        if not text:
            return None
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Handle special characters
        text = text.strip()
        
        # Truncate if needed
        if max_length and len(text) > max_length:
            text = text[:max_length-3] + '...'
        
        return text if text else None
    
    def create_embedding_text(
        self,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None
    ) -> str:
        """
        Create embedding text from product fields
        
        Args:
            name: Product name
            description: Product description
            category: Product category
            brand: Product brand
            
        Returns:
            Concatenated text for embedding
        """
        # Clean and prepare fields
        name = self.clean_text(name) or ""
        description = self.clean_text(description) or ""
        category = self.clean_text(category) or ""
        brand = self.clean_text(brand) or ""
        
        # Build embedding text using template
        embedding_text = self.embedding_field_template.format(
            name=name,
            description=description,
            category=category,
            brand=brand
        )
        
        # Clean up the result
        embedding_text = ' '.join(embedding_text.split())
        
        # Ensure we have at least the name
        if not embedding_text:
            embedding_text = name
        
        return embedding_text
    
    def validate_product(self, product: Dict) -> Tuple[bool, List[str]]:
        """
        Validate product data.
        
        Checks required fields and ensures numeric fields are within valid ranges.
        
        Args:
            product (Dict): Product dictionary.
            
        Returns:
            Tuple[bool, List[str]]: processing status (True/False) and list of error messages.
        """
        errors = []
        
        # Check required fields
        if not product.get('name'):
            errors.append("Product name is required")
        
        # Validate price
        price = product.get('price')
        if price is not None:
            normalized = self.normalize_price(price)
            if normalized is None:
                errors.append(f"Invalid price format: {price}")
            elif normalized < 0:
                errors.append(f"Price cannot be negative: {normalized}")
        
        # Validate rating
        rating = product.get('rating')
        if rating is not None:
            normalized = self.normalize_rating(rating)
            if normalized is None:
                errors.append(f"Invalid rating format: {rating}")
            elif not (0 <= normalized <= 5):
                errors.append(f"Rating must be between 0 and 5: {normalized}")
        
        # Validate review count
        review_count = product.get('review_count')
        if review_count is not None:
            normalized = self.normalize_review_count(review_count)
            if normalized is None:
                errors.append(f"Invalid review count format: {review_count}")
            elif normalized < 0:
                errors.append(f"Review count cannot be negative: {normalized}")
        
        return len(errors) == 0, errors
    
    def process_product(self, product: Dict, generate_id: bool = True) -> Dict:
        """
        Process and normalize a single product.
        
        Applies cleaning, normalization, and generates embedding text.
        
        Args:
            product (Dict): Raw product dictionary.
            generate_id (bool): Whether to generate UUID if ID is missing.
            
        Returns:
            Dict: Normalized product dictionary ready for ingestion.
        """
        # Generate ID if missing
        if not product.get('id') and generate_id:
            product['id'] = f"prod_{uuid.uuid4().hex[:12]}"
        
        # Normalize fields
        processed = {
            'id': product.get('id'),
            'name': self.clean_text(product.get('name')),
            'description': self.clean_text(product.get('description')),
            'category': self.clean_text(product.get('category')),
            'price': self.normalize_price(product.get('price')),
            'rating': self.normalize_rating(product.get('rating')),
            'review_count': self.normalize_review_count(product.get('review_count')),
            'image_url': self.clean_text(product.get('image_url')),
            'brand': self.clean_text(product.get('brand'))
        }
        
        # Create embedding text
        processed['embedding_text'] = self.create_embedding_text(
            name=processed['name'] or "",
            description=processed['description'],
            category=processed['category'],
            brand=processed['brand']
        )
        
        return processed
    
    def process_batch(
        self,
        products: List[Dict],
        batch_size: int = 100,
        skip_invalid: bool = True
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Process products in batches.
        
        Args:
            products (List[Dict]): List of raw product dictionaries.
            batch_size (int): Number of products per batch (unused in logic but kept for interface compatibility).
            skip_invalid (bool): Whether to skip invalid products or raise error.
            
        Returns:
            Tuple[List[Dict], List[Dict]]: (processed_products, invalid_products_with_errors).
        """
        processed = []
        invalid = []
        
        for i, product in enumerate(products):
            try:
                # Process product
                processed_product = self.process_product(product)
                
                # Validate
                is_valid, errors = self.validate_product(processed_product)
                
                if is_valid:
                    processed.append(processed_product)
                else:
                    if skip_invalid:
                        logger.warning(f"Product {i+1} invalid: {', '.join(errors)}")
                        invalid.append({
                            'product': product,
                            'errors': errors
                        })
                    else:
                        raise ValueError(f"Product {i+1} invalid: {', '.join(errors)}")
            
            except Exception as e:
                logger.error(f"Error processing product {i+1}: {e}")
                if skip_invalid:
                    invalid.append({
                        'product': product,
                        'errors': [str(e)]
                    })
                else:
                    raise
        
        logger.info(f"Processed {len(processed)} products, {len(invalid)} invalid")
        return processed, invalid
    
    def detect_duplicates(
        self,
        products: List[Dict],
        similarity_threshold: float = 0.9
    ) -> List[Tuple[int, int]]:
        """
        Detect duplicate products by name similarity
        
        Args:
            products: List of processed products
            similarity_threshold: Similarity threshold (0-1)
            
        Returns:
            List of (index1, index2) tuples for duplicate pairs
        """
        # Simple duplicate detection based on exact name match
        # In production, could use more sophisticated similarity
        name_to_indices = {}
        duplicates = []
        
        for idx, product in enumerate(products):
            name = product.get('name', '').lower().strip()
            if name:
                if name in name_to_indices:
                    # Found duplicate
                    for prev_idx in name_to_indices[name]:
                        duplicates.append((prev_idx, idx))
                    name_to_indices[name].append(idx)
                else:
                    name_to_indices[name] = [idx]
        
        return duplicates

