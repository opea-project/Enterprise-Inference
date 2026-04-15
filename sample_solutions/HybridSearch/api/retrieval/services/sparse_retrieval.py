"""
Sparse Retrieval using BM25
Lexical search using keyword matching
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class SparseRetrieval:
    """
    BM25-based sparse retrieval system.
    
    Manages loading of pre-computed BM25 indexes and metadata for lexical search.
    Supports both document and product search modes.
    """
    
    def __init__(
        self,
        index_path: str,
        metadata_path: str
    ):
        """
        Initialize sparse retrieval.
        
        Args:
            index_path (str): Path to BM25 index pickle file.
            metadata_path (str): Path to metadata pickle file.
        """
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        
        self.bm25 = None
        self.metadata = []
        
        self._load_index()
    
    def _load_index(self):
        """
        Load BM25 index and metadata from disk.
        
        Handles missing files gracefully by initializing empty state.
        """
        try:
            if self.index_path.exists():
                with open(self.index_path, 'rb') as f:
                    self.bm25 = pickle.load(f)  # nosec B301 - indexes are written by this application
                logger.info("Loaded BM25 index")
            else:
                logger.warning(f"BM25 index not found at {self.index_path}")
                self.bm25 = None
            
            if self.metadata_path.exists():
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)  # nosec B301 - indexes are written by this application
                logger.info(f"Loaded {len(self.metadata)} metadata entries")
            else:
                logger.warning(f"Metadata not found at {self.metadata_path}")
                self.metadata = []
                
        except Exception as e:
            logger.error(f"Error loading BM25 index: {e}")
            self.bm25 = None
            self.metadata = []
    
    def search(
        self,
        query: str,
        top_k: int = 100,
        filters: Dict = None,
        product_mode: bool = False
    ) -> List[Dict]:
        """
        Search using BM25 with optional filters.
        
        Args:
            query (str): Query string.
            top_k (int): Number of results to return.
            filters (Dict, optional): Metadata filters.
            product_mode (bool): If True, filters results to only 'product' type items.
            
        Returns:
            List[Dict]: List of result dictionaries containing metadata, score, rank,
                       and retrieval method.
        """
        if not self.bm25 or not self.metadata:
            logger.warning("BM25 index is empty or not loaded")
            return []
        
        try:
            # Tokenize query
            tokenized_query = query.lower().split()
            
            # Get BM25 scores
            scores = self.bm25.get_scores(tokenized_query)
            
            # Get more candidates if filters are applied
            k = top_k * 5 if filters else top_k
            top_indices = scores.argsort()[-k:][::-1]
            
            # Format results
            results = []
            for rank, idx in enumerate(top_indices, 1):
                if idx < len(self.metadata) and scores[idx] > 0:
                    result = {
                        **self.metadata[idx],
                        "score": float(scores[idx]),
                        "rank": rank,
                        "retrieval_method": "sparse"
                    }
                    results.append(result)
            
            # Filter by content_type if in product_mode
            if product_mode:
                results = [r for r in results if r.get('content_type') == 'product']
                logger.debug(f"Filtered to {len(results)} product results")
            
            # Apply other filters if provided
            if filters:
                results = self._apply_filters(results, filters)
                # Limit to top_k after filtering
                results = results[:top_k]
            
            logger.info(f"Sparse retrieval found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error during sparse search: {e}")
            return []
    
    def _apply_filters(self, results: List[Dict], filters: Dict) -> List[Dict]:
        """
        Apply post-retrieval metadata filters.
        
        Args:
            results (List[Dict]): List of result dictionaries.
            filters (Dict): Filter dictionary.
            
        Returns:
            List[Dict]: Filtered list of results.
        """
        filtered = []
        
        for result in results:
            metadata = result.get('metadata', {})
            
            # Price filters
            if 'price_min' in filters or 'price_max' in filters:
                price = metadata.get('price')
                if price is None:
                    continue  # Skip products without price if price filter is set
                
                if 'price_min' in filters and price < filters['price_min']:
                    continue
                if 'price_max' in filters and price > filters['price_max']:
                    continue
            
            # Rating filters
            if 'rating_min' in filters:
                rating = metadata.get('rating')
                if rating is None or rating < filters['rating_min']:
                    continue
            
            # Category filters
            if 'categories' in filters and filters['categories']:
                category = metadata.get('category')
                if category not in filters['categories']:
                    continue
            
            filtered.append(result)
        
        logger.info(f"Filtered {len(results)} results to {len(filtered)}")
        return filtered
    
    def reload(self):
        """Reload index and metadata from disk."""
        logger.info("Reloading BM25 index from disk")
        self._load_index()
    
    def get_stats(self) -> Dict:
        """
        Get index statistics.
        
        Returns:
            Dict: Dictionary containing 'total_documents' and 'bm25_loaded'.
        """
        return {
            "total_documents": len(self.metadata),
            "bm25_loaded": self.bm25 is not None
        }

