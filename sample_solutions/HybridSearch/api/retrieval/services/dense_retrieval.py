"""
Dense Retrieval using FAISS
Semantic search using vector embeddings
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
import faiss

logger = logging.getLogger(__name__)


class DenseRetrieval:
    """
    FAISS-based dense retrieval system.
    
    Manages loading of FAISS indexes and metadata, and performing semantic search
    using vector embeddings. Supports both document and product search modes.
    """
    
    def __init__(
        self,
        index_path: str,
        metadata_path: str
    ):
        """
        Initialize dense retrieval.
        
        Args:
            index_path (str): Path to the FAISS index file (.bin).
            metadata_path (str): Path to the matching metadata pickle file (.pkl).
        """
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        
        self.index = None
        self.metadata = []
        
        self._load_index()
    
    def _load_index(self):
        """
        Load FAISS index and metadata from disk.
        
        Handles missing files gracefully by initializing empty state.
        """
        try:
            if self.index_path.exists():
                self.index = faiss.read_index(str(self.index_path))
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
            else:
                logger.warning(f"FAISS index not found at {self.index_path}")
                self.index = None
            
            if self.metadata_path.exists():
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)  # nosec B301 - indexes are written by this application
                logger.info(f"Loaded {len(self.metadata)} metadata entries")
            else:
                logger.warning(f"Metadata not found at {self.metadata_path}")
                self.metadata = []
                
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self.index = None
            self.metadata = []
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 100,
        filters: Dict = None,
        product_mode: bool = False
    ) -> List[Dict]:
        """
        Search for similar vectors with optional filters.
        
        Args:
            query_embedding (List[float]): Query vector (will be normalized).
            top_k (int): Number of results to return.
            filters (Dict, optional): Metadata filters (price, rating, category).
            product_mode (bool): If True, filters results to only 'product' type items.
            
        Returns:
            List[Dict]: List of result dictionaries containing metadata, score, rank,
                       and retrieval method.
        """
        if not self.index or self.index.ntotal == 0:
            logger.warning("Index is empty or not loaded")
            return []
        
        try:
            # Convert to numpy array and normalize
            query_vector = np.array([query_embedding], dtype=np.float32)
            faiss.normalize_L2(query_vector)
            
            # Retrieve more candidates if filters are applied (for post-retrieval filtering)
            k = min(top_k * 5 if filters else top_k, self.index.ntotal)
            distances, indices = self.index.search(query_vector, k)
            
            # Format results
            results = []
            for idx, (distance, index) in enumerate(zip(distances[0], indices[0])):
                if index < len(self.metadata):
                    result = {
                        **self.metadata[index],
                        "score": float(distance),  # Cosine similarity
                        "rank": idx + 1,
                        "retrieval_method": "dense"
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
            
            logger.info(f"Dense retrieval found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error during dense search: {e}")
            return []
    
    def _apply_filters(self, results: List[Dict], filters: Dict) -> List[Dict]:
        """
        Apply post-retrieval metadata filters.
        
        Args:
            results (List[Dict]): List of result dictionaries.
            filters (Dict): Filter dictionary (e.g., {'price_min': 10}).
            
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
        logger.info("Reloading FAISS index from disk")
        self._load_index()
    
    def get_stats(self) -> Dict:
        """
        Get index statistics.
        
        Returns:
            Dict: Dictionary containing 'total_vectors', 'total_metadata', and 'index_loaded'.
        """
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "total_metadata": len(self.metadata),
            "index_loaded": self.index is not None
        }

