"""
Reranker Service
Handles precise ranking of candidates using cross-encoders
"""

import logging
import time
from typing import List, Dict, Any
from api_client import get_api_client
from config import settings

logger = logging.getLogger(__name__)

class Reranker:
    """
    Enterprise Reranker implementation using Keycloak and BGE-Reranker.
    
    Delegates reranking to the enterprise API client.
    """
    
    def __init__(self):
        self.api_client = get_api_client()
        self.enabled = settings.use_reranking
        
    def rerank(self, query: str, candidates: List[Dict], top_k: int = 10) -> List[Dict]:
        """
        Rerank a list of candidates based on the query.
        
        Sends pairs of (query, document_text) to the enterprise cross-encoder
        API to get precise relevance scores.
        
        Args:
            query (str): The user query.
            candidates (List[Dict]): List of retrieved chunks to rerank.
            top_k (int): Number of results to return.
            
        Returns:
            List[Dict]: Top-k reranked results with updated scores.
        """
        if not self.enabled or not candidates:
            return candidates[:top_k]
            
        try:
            start_time = time.time()
            
            # Prepare documents for reranking
            # Enterprise cross-encoders typically expect query and doc text pairs
            docs = [c.get("text", "") for c in candidates]
            
            logger.info(f"Reranking {len(docs)} candidates for query: '{query[:50]}...'")
            
            # Call enterprise rerank endpoint
            scores = self.api_client.rerank_pairs(query, docs)
            
            # Update scores and sort
            for i, score in enumerate(scores):
                candidates[i]["rerank_score"] = float(score)
                # Blend or replace original score
                candidates[i]["original_score"] = candidates[i].get("score", 0.0)
                candidates[i]["score"] = float(score)
            
            # Sort by new score
            reranked = sorted(
                candidates,
                key=lambda x: x.get("score", 0.0),
                reverse=True
            )
            
            duration = (time.time() - start_time) * 1000
            logger.info(f"Reranking completed in {duration:.2f}ms")
            
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            # Fallback to original order
            return candidates[:top_k]
