"""
Reciprocal Rank Fusion (RRF)
Combines results from multiple retrieval methods
"""

import logging
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


class ReciprocalRankFusion:
    """
    RRF algorithm for combining ranked lists.
    
    Implements Reciprocal Rank Fusion to combine results from multiple retrieval
    sources (e.g., Dense and Sparse) into a single ranked list.
    """
    
    def __init__(self, k: int = 60):
        """
        Initialize RRF.
        
        Args:
            k (int): RRF constant (default factor for rank penalty).
                    Higher k reduces the impact of high rankings.
        """
        self.k = k
    
    def fuse(
        self,
        dense_results: List[Dict],
        sparse_results: List[Dict],
        top_k: int = 50,
        enrich_results: bool = False,
        product_mode: bool = False,
        filters: Dict = None
    ) -> List[Dict]:
        """
        Fuse dense and sparse retrieval results.
        
        Args:
            dense_results (List[Dict]): Results from dense retrieval.
            sparse_results (List[Dict]): Results from sparse retrieval.
            top_k (int): Number of results to return after fusion.
            enrich_results (bool): Whether to add match reasons (for products).
            product_mode (bool): Unused flag kept for interface compatibility.
            filters (Dict): Unused filters kept for interface compatibility.
            
        Returns:
            List[Dict]: List of fused results sorted by RRF score.
        """
        # Calculate RRF scores
        rrf_scores = defaultdict(float)
        chunk_data = {}  # Store chunk info
        
        # Process dense results
        for rank, result in enumerate(dense_results, 1):
            chunk_id = result.get("chunk_id") or result.get("metadata", {}).get("product_id")
            if chunk_id:
                rrf_scores[chunk_id] += 1 / (self.k + rank)
                if chunk_id not in chunk_data:
                    chunk_data[chunk_id] = result
        
        # Process sparse results
        for rank, result in enumerate(sparse_results, 1):
            chunk_id = result.get("chunk_id") or result.get("metadata", {}).get("product_id")
            if chunk_id:
                rrf_scores[chunk_id] += 1 / (self.k + rank)
                if chunk_id not in chunk_data:
                    chunk_data[chunk_id] = result
        
        # Sort by RRF score
        sorted_chunks = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        # Format results
        fused_results = []
        for rank, (chunk_id, rrf_score) in enumerate(sorted_chunks, 1):
            if chunk_id in chunk_data:
                result = {
                    **chunk_data[chunk_id],
                    "rrf_score": float(rrf_score),
                    "relevance_score": float(rrf_score),  # Alias for product search
                    "rank": rank,
                    "retrieval_method": "hybrid"
                }
                
                # Enrich with match reasons for products
                if enrich_results:
                    match_reasons = self._generate_match_reasons(result, dense_results, sparse_results)
                    result["match_reasons"] = match_reasons
                
                fused_results.append(result)
        
        logger.info(
            f"RRF fusion: {len(dense_results)} dense + {len(sparse_results)} sparse "
            f"→ {len(fused_results)} fused results"
        )
        
        return fused_results
    
    def _generate_match_reasons(
        self,
        result: Dict,
        dense_results: List[Dict],
        sparse_results: List[Dict]
    ) -> List[str]:
        """
        Generate match reasons for a product result.
        
        Analyzes why a product was matched (e.g., semantic match, price match,
        high rating, category match).
        
        Args:
            result (Dict): The result dictionary to analyze.
            dense_results (List[Dict]): Original dense retrieval results.
            sparse_results (List[Dict]): Original sparse retrieval results.
            
        Returns:
            List[str]: List of human-readable match reason strings.
        """
        reasons = []
        metadata = result.get('metadata', {})
        product_id = metadata.get('product_id')
        
        # Check if in dense results (semantic match)
        if any(r.get('chunk_id') == result.get('chunk_id') or 
               r.get('metadata', {}).get('product_id') == product_id 
               for r in dense_results[:10]):
            reasons.append("Semantic match")
        
        # Check price filter
        price = metadata.get('price')
        if price is not None:
            reasons.append(f"Price: ${price:.2f}")
        
        # Check rating
        rating = metadata.get('rating')
        if rating is not None and rating >= 4.0:
            reasons.append(f"Highly rated ({rating:.1f} stars)")
        
        # Check category
        category = metadata.get('category')
        if category:
            reasons.append(f"In {category}")
        
        return reasons if reasons else ["Matches your search"]
    
    def rerank(
        self,
        query: str,
        results: List[Dict],
        top_k: int = 10
    ) -> List[Dict]:
        """
        Rerank results using cross-encoder.
        
        Wrapper to call the Reranker service.
        
        Args:
            query (str): User query.
            results (List[Dict]): Results to rerank.
            top_k (int): Number of results to return.
            
        Returns:
            List[Dict]: Top-k reranked results.
        """
        from services.reranker import Reranker
        reranker = Reranker()
        
        if not results:
            return []
            
        # In enterprise mode, we use the cross-encoder reranker
        logger.info(f"Performing enterprise reranking for top {len(results)} results")
        return reranker.rerank(query, results, top_k)

