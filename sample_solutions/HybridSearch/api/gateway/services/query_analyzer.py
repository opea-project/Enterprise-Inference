"""
Query Analyzer
Classifies query intent types for product search
"""

import logging
import re
from typing import Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    """Query intent types"""
    SEMANTIC_BROWSE = "semantic_browse"  # Pure semantic search
    FILTERED_SEARCH = "filtered_search"  # Explicit constraints
    HYBRID_SEARCH = "hybrid"  # Semantic + filters
    SPECIFIC_PRODUCT = "specific_product"  # Exact product lookup
    COMPARISON = "comparison"  # Product comparison


class QueryAnalyzer:
    """
    Analyze queries to determine intent and extract information.
    
    Uses regex patterns and heuristic rules to classify user intent
    (e.g., specific product search, comparison, browsing) and cleaning
    the query for semantic search.
    """
    
    def __init__(self):
        """
        Initialize query analyzer.
        
        Sets up regex patterns for specific product matching and comparison detection.
        """
        # Patterns for specific product queries
        self.specific_product_patterns = [
            r'show me (the )?([A-Z][a-zA-Z0-9\s-]+)',
            r'find (the )?([A-Z][a-zA-Z0-9\s-]+)',
            r'where is (the )?([A-Z][a-zA-Z0-9\s-]+)',
            r'([A-Z][a-zA-Z0-9\s-]+) (model|version|product)'
        ]
        
        # Patterns for comparison queries
        self.comparison_patterns = [
            r'compare',
            r'difference between',
            r'vs\.?',
            r'versus',
            r'which (is|are) better',
            r'which (one|product) should',
            r'help me choose',
            r'help me decide'
        ]
    
    def classify_intent(self, query: str, has_filters: bool = False) -> QueryIntent:
        """
        Classify query intent based on patterns and context.
        
        Args:
            query (str): User query string.
            has_filters (bool): Whether filters have already been extracted.
            
        Returns:
            QueryIntent: The classified intent enum value.
        """
        query_lower = query.lower()
        
        # Check for specific product queries
        for pattern in self.specific_product_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return QueryIntent.SPECIFIC_PRODUCT
        
        # Check for comparison queries
        for pattern in self.comparison_patterns:
            if re.search(pattern, query_lower):
                return QueryIntent.COMPARISON
        
        # Determine based on filters
        if has_filters:
            # Check if query has semantic content beyond filters
            # Simple heuristic: if query is mostly filter keywords, it's filtered_search
            filter_keywords = ['under', 'over', 'above', 'below', 'between', 'stars', 'rated', 'category']
            query_words = set(query_lower.split())
            filter_word_count = sum(1 for word in filter_keywords if word in query_words)
            
            if filter_word_count > 2 or len(query_words) < 5:
                return QueryIntent.FILTERED_SEARCH
            else:
                return QueryIntent.HYBRID_SEARCH
        else:
            return QueryIntent.SEMANTIC_BROWSE
    
    def extract_semantic_query(self, query: str, filters: Dict) -> str:
        """
        Extract cleaned semantic query (with filters significant phrases removed).
        
        Removes parts of the query that correspond to extracted filters
        (like "under $50" or "red category") to improve semantic search quality.
        
        Args:
            query (str): Original query.
            filters (Dict): Extracted filters dictionary.
            
        Returns:
            str: Cleaned semantic query string.
        """
        # Remove filter-related phrases
        semantic_query = query
        
        # Remove price-related phrases
        price_patterns = [
            r'under \$?\d+',
            r'less than \$?\d+',
            r'below \$?\d+',
            r'over \$?\d+',
            r'more than \$?\d+',
            r'above \$?\d+',
            r'\$?\d+\s*to\s*\$?\d+',
            r'between \$?\d+\s+and\s+\$?\d+',
            r'around \$?\d+',
            r'about \$?\d+'
        ]
        
        for pattern in price_patterns:
            semantic_query = re.sub(pattern, '', semantic_query, flags=re.IGNORECASE)
        
        # Remove rating-related phrases
        rating_patterns = [
            r'\d+\+?\s*stars?',
            r'\d+\s*star\s+and\s+above',
            r'rated\s+\d+',
            r'highly\s+rated',
            r'top\s+rated',
            r'best\s+reviewed',
            r'well\s+reviewed'
        ]
        
        for pattern in rating_patterns:
            semantic_query = re.sub(pattern, '', semantic_query, flags=re.IGNORECASE)
        
        # Remove category mentions if they're in filters
        if filters.get('categories'):
            for category in filters['categories']:
                semantic_query = re.sub(category, '', semantic_query, flags=re.IGNORECASE)
        
        # Clean up whitespace
        semantic_query = ' '.join(semantic_query.split())
        
        return semantic_query.strip() if semantic_query.strip() else query
    
    def analyze(self, query: str, filters: Dict) -> Dict:
        """
        Analyze query and return intent classification and cleaned query.
        
        Args:
            query (str): User query.
            filters (Dict): Extracted filters.
            
        Returns:
            Dict: Dictionary containing:
                - 'intent': Classified intent string
                - 'semantic_query': Query processing for semantic search
                - 'original_query': The raw input
        """
        intent = self.classify_intent(query, has_filters=bool(filters))
        semantic_query = self.extract_semantic_query(query, filters)
        
        result = {
            "intent": intent.value,
            "semantic_query": semantic_query,
            "original_query": query
        }
        
        logger.info(f"Query analyzed: intent={intent.value}, semantic_query='{semantic_query}'")
        
        return result

