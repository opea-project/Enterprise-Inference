"""
Response Formatter
Formats product recommendations in quick or explained modes
"""

import logging
from typing import List, Dict, Any, Optional
from prompts.product_prompts import ProductPrompts

logger = logging.getLogger(__name__)

# Query intent constants (matching gateway service)
class QueryIntent:
    SEMANTIC_BROWSE = "semantic_browse"
    FILTERED_SEARCH = "filtered_search"
    HYBRID_SEARCH = "hybrid"
    SPECIFIC_PRODUCT = "specific_product"
    COMPARISON = "comparison"


class ResponseFormatter:
    """
    Format product search responses.
    
    Handles formatting of product data into either quick summaries (template-based)
    or detailed explanations (LLM-prompt-ready).
    """
    
    def __init__(self):
        """Initialize response formatter with prompt templates."""
        self.prompts = ProductPrompts()
    
    def format_response(
        self,
        query: str,
        products: List[Dict],
        intent: str,
        filters: Dict = None,
        mode: str = "explained"
    ) -> str:
        """
        Format product search response.
        
        Generates the final response text or prompt input based on the mode.
        
        Args:
            query (str): User's search query.
            products (List[Dict]): List of product dictionaries.
            intent (str): Detected query intent (e.g., 'comparison', 'filtered_search').
            filters (Dict, optional): Applied filters.
            mode (str): Response mode ("quick" or "explained").
            
        Returns:
            str: Formatted response string (or prompt).
        """
        if not products:
            return "I couldn't find any products matching your search. Try adjusting your filters or search terms."
        
        if mode == "quick":
            return self.prompts.quick_results_template(query, filters or {}, products)
        
        # Explained mode - use appropriate prompt based on intent
        if intent == QueryIntent.COMPARISON:
            return self.prompts.comparison_prompt(products)
        elif intent == QueryIntent.FILTERED_SEARCH:
            return self.prompts.filtered_search_prompt(query, filters or {}, products)
        else:
            return self.prompts.semantic_browse_prompt(query, products)
    
    def should_use_quick_mode(
        self,
        intent: str,
        product_count: int,
        has_filters: bool
    ) -> bool:
        """
        Determine if quick mode should be used.
        
        Quick mode is preferred for large result sets or explicit filtering,
        where an LLM explanation adds latency without much value.
        
        Args:
            intent (str): Query intent.
            product_count (int): Number of products found.
            has_filters (bool): Whether filters were applied.
            
        Returns:
            bool: True if quick mode should be used, False for detailed explanation.
        """
        # Use quick mode for:
        # - Filtered searches with clear intent
        # - Large result sets (>20 products)
        # - Simple queries
        
        if intent == QueryIntent.FILTERED_SEARCH and has_filters:
            return True
        
        if product_count > 20:
            return True
        
        return False

