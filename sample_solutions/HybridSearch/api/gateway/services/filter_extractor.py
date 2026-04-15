"""
Filter Extractor
Extracts structured filters from natural language queries
"""

import logging
import re
import httpx
from typing import Dict, List, Optional, Any
from config import settings

logger = logging.getLogger(__name__)


class FilterExtractor:
    """Extract filters from natural language queries"""
    
    def __init__(self, llm_service_url: str = None):
        """
        Initialize filter extractor.
        
        Args:
            llm_service_url (str, optional): URL of LLM service for complex extraction fallback.
                Defaults to configuration settings if not provided.
        """
        self.llm_service_url = llm_service_url or getattr(settings, 'llm_service_url', 'http://localhost:8003')
        
        # Price filter patterns
        self.price_patterns = [
            (r'under\s+\$?(\d+(?:\.\d+)?)', 'price_max'),
            (r'less\s+than\s+\$?(\d+(?:\.\d+)?)', 'price_max'),
            (r'below\s+\$?(\d+(?:\.\d+)?)', 'price_max'),
            (r'over\s+\$?(\d+(?:\.\d+)?)', 'price_min'),
            (r'more\s+than\s+\$?(\d+(?:\.\d+)?)', 'price_min'),
            (r'above\s+\$?(\d+(?:\.\d+)?)', 'price_min'),
            (r'\$?(\d+(?:\.\d+)?)\s+to\s+\$?(\d+(?:\.\d+)?)', 'price_range'),
            (r'between\s+\$?(\d+(?:\.\d+)?)\s+and\s+\$?(\d+(?:\.\d+)?)', 'price_range'),
            (r'\$?(\d+(?:\.\d+)?)\s*-\s*\$?(\d+(?:\.\d+)?)', 'price_range'),
            (r'around\s+\$?(\d+(?:\.\d+)?)', 'price_around'),
            (r'about\s+\$?(\d+(?:\.\d+)?)', 'price_around'),
        ]
        
        # Rating filter patterns
        self.rating_patterns = [
            (r'(\d+(?:\.\d+)?)\+?\s*stars?', 'rating_min'),
            (r'(\d+(?:\.\d+)?)\s+star\s+and\s+above', 'rating_min'),
            (r'rated\s+(\d+(?:\.\d+)?)', 'rating_min'),
            (r'highly\s+rated', 'rating_high'),
            (r'top\s+rated', 'rating_high'),
            (r'best\s+reviewed', 'rating_high'),
            (r'well\s+reviewed', 'rating_well'),
        ]
        
        # Quantity/limit patterns
        self.limit_patterns = [
            (r'top\s+(\d+)', 'limit'),
            (r'best\s+(\d+)', 'limit'),
            (r'show\s+me\s+(\d+)', 'limit'),
            (r'first\s+(\d+)', 'limit'),
        ]
    
    def extract_price_filters(self, query: str) -> Dict[str, float]:
        """
        Extract price filters from query using regex patterns.
        
        Args:
            query (str): User query string.
            
        Returns:
            Dict[str, float]: Dictionary containing:
                - 'price_min': Minimum price filter
                - 'price_max': Maximum price filter
        """
        filters = {}
        query_lower = query.lower()
        
        for pattern, filter_type in self.price_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                if filter_type == 'price_max':
                    filters['price_max'] = float(match.group(1))
                elif filter_type == 'price_min':
                    filters['price_min'] = float(match.group(1))
                elif filter_type == 'price_range':
                    filters['price_min'] = float(match.group(1))
                    filters['price_max'] = float(match.group(2))
                elif filter_type == 'price_around':
                    price = float(match.group(1))
                    filters['price_min'] = price * 0.8
                    filters['price_max'] = price * 1.2
                break  # Use first match
        
        return filters
    
    def extract_rating_filters(self, query: str) -> Dict[str, float]:
        """
        Extract rating filters from query using regex patterns.
        
        Args:
            query (str): User query string.
            
        Returns:
            Dict[str, float]: Dictionary containing 'rating_min' if found.
        """
        filters = {}
        query_lower = query.lower()
        
        for pattern, filter_type in self.rating_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                if filter_type == 'rating_min':
                    filters['rating_min'] = float(match.group(1))
                elif filter_type == 'rating_high':
                    filters['rating_min'] = 4.0
                elif filter_type == 'rating_well':
                    filters['rating_min'] = 3.5
                break  # Use first match
        
        return filters
    
    def extract_limit(self, query: str, default: int = 10) -> int:
        """
        Extract result limit from query (e.g., "top 5 items").
        
        Args:
            query (str): User query string.
            default (int): Default limit if no pattern matches.
            
        Returns:
            int: The extracted limit or the default value.
        """
        query_lower = query.lower()
        
        for pattern, _ in self.limit_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return default
    
    def extract_category_filters(
        self,
        query: str,
        known_categories: List[str] = None
    ) -> List[str]:
        """
        Extract category filters from query using fuzzy matching against known categories.
        
        Args:
            query (str): User query string.
            known_categories (List[str]): List of valid categories in the catalog.
            
        Returns:
            List[str]: List of matched category names.
        """
        if not known_categories:
            return []
        
        query_lower = query.lower()
        matched_categories = []
        
        # Simple keyword matching
        category_keywords = {
            'electronics': ['electronics', 'electronic', 'tech', 'technology'],
            'home': ['home', 'household', 'house'],
            'kitchen': ['kitchen', 'cooking', 'cookware'],
            'clothing': ['clothing', 'clothes', 'apparel', 'fashion'],
            'books': ['books', 'book', 'reading'],
            'sports': ['sports', 'sport', 'fitness', 'exercise'],
            'toys': ['toys', 'toy', 'games', 'game'],
        }
        
        for category in known_categories:
            category_lower = category.lower()
            
            # Direct match
            if category_lower in query_lower:
                matched_categories.append(category)
                continue
            
            # Keyword match
            for keyword, variations in category_keywords.items():
                if keyword in category_lower:
                    for variation in variations:
                        if variation in query_lower:
                            matched_categories.append(category)
                            break
                    if category in matched_categories:
                        break
        
        return list(set(matched_categories))  # Remove duplicates
    
    async def extract_with_llm(self, query: str) -> Dict[str, Any]:
        """
        Extract filters using LLM (fallback for complex queries).
        
        Args:
            query (str): User query string.
            
        Returns:
            Dict[str, Any]: Dictionary containing extracted filters.
        """
        try:
            prompt = f"""Extract shopping filters from this query. Return JSON with:
- semantic_query: cleaned query without filters
- filters: object with price_min, price_max, rating_min, categories (array)
- intent: "semantic_browse", "filtered_search", "hybrid", "specific_product", or "comparison"

Query: "{query}"

Return only valid JSON, no other text."""

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.llm_service_url}/api/v1/llm/extract-filters",
                    json={"query": query, "prompt": prompt}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('filters', {})
                else:
                    logger.warning(f"LLM filter extraction failed: {response.status_code}")
                    return {}
        
        except Exception as e:
            logger.warning(f"LLM filter extraction error: {e}")
            return {}
    
    def extract(
        self,
        query: str,
        known_categories: List[str] = None,
        use_llm_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        Extract all filters from query (synchronously).
        
        Combines regex-based extraction for price, rating, category, and limit.
        Note: LLM fallback is skipped in synchronous orchestration unless called via async wrapper.
        
        Args:
            query (str): User query string.
            known_categories (List[str]): List of known categories.
            use_llm_fallback (bool): Whether to attempt LLM fallback (skipped in sync method).
            
        Returns:
            Dict[str, Any]: Dictionary containing all extracted filters.
        """
        filters = {}
        
        # Extract price filters
        price_filters = self.extract_price_filters(query)
        filters.update(price_filters)
        
        # Extract rating filters
        rating_filters = self.extract_rating_filters(query)
        filters.update(rating_filters)
        
        # Extract category filters
        if known_categories:
            category_filters = self.extract_category_filters(query, known_categories)
            if category_filters:
                filters['categories'] = category_filters
        
        # Extract limit
        limit = self.extract_limit(query)
        if limit != 10:  # Only include if different from default
            filters['limit'] = limit
        
        # If no filters found and use_llm_fallback, try LLM
        if not filters and use_llm_fallback:
            # Note: This would be async, so we'd need to handle it differently
            # For now, we'll skip LLM fallback in sync context
            logger.debug("No filters found via regex, but LLM fallback requires async")
        
        logger.info(f"Extracted filters: {filters}")
        return filters
    
    async def extract_async(
        self,
        query: str,
        known_categories: List[str] = None,
        use_llm_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Extract filters asynchronously (supports LLM fallback).
        
        First attempts regex-based extraction. If no filters are found and
        fallback is enabled, queries the LLM service.
        
        Args:
            query (str): User query string.
            known_categories (List[str]): List of known categories.
            use_llm_fallback (bool): Whether to use LLM for complex queries.
            
        Returns:
            Dict[str, Any]: Dictionary with extracted filters.
        """
        # First try regex extraction
        filters = self.extract(query, known_categories, use_llm_fallback=False)
        
        # If no filters found and LLM fallback enabled, try LLM
        if not filters and use_llm_fallback:
            llm_filters = await self.extract_with_llm(query)
            if llm_filters:
                filters.update(llm_filters)
        
        return filters

