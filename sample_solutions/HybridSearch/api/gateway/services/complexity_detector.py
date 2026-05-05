"""
Query Complexity Detector
Determines if a query is simple or complex
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ComplexityDetector:
    """
    Detect query complexity for routing.
    
    Classifies queries as 'simple' or 'complex' based on keywords,
    heuristics (length, question count), and structural patterns.
    """
    
    # Query patterns
    SIMPLE_INDICATORS = [
        "what is", "who is", "when did", "when was", "where is", "where did",
        "define", "list", "name", "how many", "how much",
        "show me", "tell me", "give me"
    ]
    
    COMPLEX_INDICATORS = [
        "compare", "analyze", "analyse", "explain why", "relationship between",
        "impact of", "evaluate", "synthesize", "synthesise",
        "how does", "affect", "effect",
        "differences between", "similarities", "similar to",
        "trend", "pattern", "correlation", "cause", "consequence",
        "pros and cons", "advantages", "disadvantages",
        "summarize", "summarise", "overview"
    ]
    
    def detect(self, query: str) -> Dict[str, str]:
        """
        Detect query complexity.
        
        Args:
            query (str): The user query string.
            
        Returns:
            Dict[str, str]: A dictionary containing:
                - 'complexity': 'simple' or 'complex'
                - 'reasoning': Explanation of the classification
        """
        query_lower = query.lower().strip()
        
        # Check for complex indicators first (higher priority)
        for indicator in self.COMPLEX_INDICATORS:
            if indicator in query_lower:
                logger.debug(f"Complex indicator found: '{indicator}'")
                return {
                    "complexity": "complex",
                    "reasoning": f"Contains complex indicator: '{indicator}'"
                }
        
        # Check for simple indicators
        for indicator in self.SIMPLE_INDICATORS:
            if indicator in query_lower:
                logger.debug(f"Simple indicator found: '{indicator}'")
                return {
                    "complexity": "simple",
                    "reasoning": f"Contains simple indicator: '{indicator}'"
                }
        
        # Heuristic rules
        word_count = len(query.split())
        question_count = query.count("?")
        
        # Long queries or multiple questions suggest complexity
        if word_count > 15:
            return {
                "complexity": "complex",
                "reasoning": f"Long query ({word_count} words)"
            }
        
        if question_count > 1:
            return {
                "complexity": "complex",
                "reasoning": f"Multiple questions ({question_count})"
            }
        
        # Default to simple for short, direct questions
        return {
            "complexity": "simple",
            "reasoning": "Short direct question (default)"
        }

