"""
Index Manager
Manages FAISS vector index and BM25 sparse index
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import faiss
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class IndexManager:
    """
    Manage FAISS and BM25 indexes.
    
    Handles creation, loading, saving, and updating of vector (FAISS) 
    and sparse (BM25) indexes for both documents and products.
    """
    
    def __init__(
        self,
        index_storage_path: str,
        embedding_dim: int = 768
    ):
        """
        Initialize index manager.
        
        Args:
            index_storage_path (str): Path to store index files.
            embedding_dim (int): Dimension of embeddings (default: 768).
        """
        self.index_storage_path = Path(index_storage_path)
        self.index_storage_path.mkdir(parents=True, exist_ok=True)
        
        self.embedding_dim = embedding_dim
        
        # Document index paths
        self.faiss_index_path = self.index_storage_path / "faiss_index.bin"
        self.bm25_index_path = self.index_storage_path / "bm25_index.pkl"
        self.metadata_path = self.index_storage_path / "metadata.pkl"
        self.filters_cache_path = self.index_storage_path / "filters_cache.pkl"
        
        # Product index paths (separate from documents)
        self.product_faiss_index_path = self.index_storage_path / "product_faiss_index.bin"
        self.product_bm25_index_path = self.index_storage_path / "product_bm25_index.pkl"
        self.product_metadata_path = self.index_storage_path / "product_metadata.pkl"
        self.product_filters_cache_path = self.index_storage_path / "product_filters_cache.pkl"
        
        # Initialize document indexes
        self.faiss_index = None
        self.bm25_index = None
        self.metadata = []
        
        # Initialize product indexes (separate)
        self.product_faiss_index = None
        self.product_bm25_index = None
        self.product_metadata = []
        
        # Product-specific: filters cache for fast filtering
        self.filters_cache = {
            "prices": [],
            "categories": [],
            "ratings": [],
            "product_ids": []
        }
        
        # Load existing indexes if available
        self._load_indexes()
        self._load_product_indexes()
    
    def _load_indexes(self):
        """
        Load existing indexes from disk.
        
        Initializes FAISS and BM25 indexes and loads metadata.
        Creates fresh indexes if files are missing or corrupt.
        """
        try:
            # Load FAISS index
            if self.faiss_index_path.exists():
                self.faiss_index = faiss.read_index(str(self.faiss_index_path))
                logger.info(f"Loaded FAISS index with {self.faiss_index.ntotal} vectors (d={self.faiss_index.d})")
            else:
                # Create new FAISS index (IndexFlatIP for cosine similarity)
                self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
                logger.info(f"Created new FAISS index (d={self.embedding_dim})")
            
            # Load BM25 index
            if self.bm25_index_path.exists():
                with open(self.bm25_index_path, 'rb') as f:
                    self.bm25_index = pickle.load(f)  # nosec B301 - indexes are written by this application
                logger.info("Loaded BM25 index")
            
            # Load metadata
            if self.metadata_path.exists():
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)  # nosec B301 - indexes are written by this application
                logger.info(f"Loaded {len(self.metadata)} metadata entries")

            # Load filters cache (for products)
            if self.filters_cache_path.exists():
                with open(self.filters_cache_path, 'rb') as f:
                    self.filters_cache = pickle.load(f)  # nosec B301 - indexes are written by this application
                logger.info(f"Loaded filters cache with {len(self.filters_cache.get('product_ids', []))} products")
            
        except Exception as e:
            logger.error(f"Error loading indexes: {e}")
            # Initialize new indexes
            self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
            self.bm25_index = None
            self.metadata = []
            self.filters_cache = {
                "prices": [],
                "categories": [],
                "ratings": [],
                "product_ids": []
            }
    
    def _load_product_indexes(self):
        """Load existing product indexes from disk"""
        try:
            if self.product_faiss_index_path.exists():
                self.product_faiss_index = faiss.read_index(str(self.product_faiss_index_path))
                logger.info(f"Loaded product FAISS index with {self.product_faiss_index.ntotal} vectors")
            else:
                self.product_faiss_index = faiss.IndexFlatIP(self.embedding_dim)
                logger.info("Created new product FAISS index")
            
            if self.product_bm25_index_path.exists():
                with open(self.product_bm25_index_path, 'rb') as f:
                    self.product_bm25_index = pickle.load(f)  # nosec B301 - indexes are written by this application
                logger.info("Loaded product BM25 index")
            
            if self.product_metadata_path.exists():
                with open(self.product_metadata_path, 'rb') as f:
                    self.product_metadata = pickle.load(f)  # nosec B301 - indexes are written by this application
                logger.info(f"Loaded {len(self.product_metadata)} product metadata entries")
            
            if self.product_filters_cache_path.exists():
                with open(self.product_filters_cache_path, 'rb') as f:
                    product_filters = pickle.load(f)  # nosec B301 - indexes are written by this application
                    self.filters_cache.update(product_filters)
                logger.debug("Loaded product filters cache")
                
        except Exception as e:
            logger.error(f"Error loading product indexes: {e}")
            self.product_faiss_index = faiss.IndexFlatIP(self.embedding_dim)
            self.product_bm25_index = None
            self.product_metadata = []
    
    def _save_indexes(self):
        """
        Save indexes to disk.
        
        Persists FAISS index, BM25 index, metadata, and cache to configured storage paths.
        
        Raises:
            IOError: If saving fails.
        """
        try:
            # Save FAISS index
            faiss.write_index(self.faiss_index, str(self.faiss_index_path))
            logger.info(f"Saved FAISS index ({self.faiss_index.ntotal} vectors)")
            
            # Save BM25 index
            if self.bm25_index:
                with open(self.bm25_index_path, 'wb') as f:
                    pickle.dump(self.bm25_index, f)
                logger.info("Saved BM25 index")
            
            # Save metadata
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)
            logger.info(f"Saved {len(self.metadata)} metadata entries")
            
            # Save filters cache (for products)
            with open(self.filters_cache_path, 'wb') as f:
                pickle.dump(self.filters_cache, f)
            logger.debug("Saved filters cache")
            
        except Exception as e:
            logger.error(f"Error saving indexes: {e}", exc_info=True)
            raise
    
    def add_chunks(
        self,
        chunks: List[Dict],
        embeddings: List[List[float]],
        content_type: str = "document"
    ):
        """
        Add chunks to indexes.
        
        Updates both FAISS (dense) and BM25 (sparse) indexes with new chunks.
        
        Args:
            chunks (List[Dict]): List of chunk dictionaries with text and metadata.
            embeddings (List[List[float]]): List of embedding vectors corresponding to chunks.
            content_type (str): Type of content ("document" or "product").
            
        Raises:
            ValueError: If chunks and embeddings counts mismatch.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
        
        if not chunks:
            logger.warning("No chunks to add")
            return
        
        # Add to FAISS index
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # Normalize vectors for cosine similarity
        faiss.normalize_L2(embeddings_array)
        
        # Add debug logging for dimensions
        logger.info(f"Adding embeddings to FAISS index: embedding_dim={embeddings_array.shape[1]}, index_dim={self.faiss_index.d}")
        
        # Add to index
        self.faiss_index.add(embeddings_array)
        
        # Add metadata with content_type
        for chunk in chunks:
            chunk['content_type'] = content_type
            self.metadata.append(chunk)
        
        # Rebuild BM25 index with all texts
        all_texts = [chunk["text"] for chunk in self.metadata]
        tokenized_corpus = [text.lower().split() for text in all_texts]
        self.bm25_index = BM25Okapi(tokenized_corpus)
        
        logger.info(f"Added {len(chunks)} chunks to indexes (content_type={content_type})")
        
        # Save indexes
        self._save_indexes()
    
    def get_stats(self) -> Dict:
        """
        Get index statistics.
        
        Returns:
            Dict: Dictionary containing detailed index stats (counts, dims, etc.).
        """
        return {
            "total_chunks": len(self.metadata),
            "faiss_vectors": self.faiss_index.ntotal if self.faiss_index else 0,
            "bm25_enabled": self.bm25_index is not None,
            "embedding_dim": self.embedding_dim
        }
    
    def delete_document(self, document_id: str):
        """
        Delete all chunks for a document.
        
        Removed chunks from metadata and rebuilds indexes (expensive operation).
        
        Args:
            document_id (str): Document ID to delete.
        """
        # Find indices to remove
        indices_to_remove = []
        new_metadata = []
        
        for idx, chunk in enumerate(self.metadata):
            if chunk.get("document_id") == document_id:
                indices_to_remove.append(idx)
            else:
                new_metadata.append(chunk)
        
        if not indices_to_remove:
            logger.warning(f"No chunks found for document {document_id}")
            return
        
        # For simplicity, rebuild indexes without deleted chunks
        # In production, consider more efficient index update strategies
        logger.info(f"Rebuilding indexes after deleting {len(indices_to_remove)} chunks")
        
        # Rebuild FAISS index
        self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        
        # Add back remaining chunks (this requires re-embedding, which we skip for now)
        # In production, store embeddings with metadata and rebuild from those
        self.metadata = new_metadata
        
        # Rebuild BM25
        if new_metadata:
            all_texts = [chunk["text"] for chunk in new_metadata]
            tokenized_corpus = [text.lower().split() for text in all_texts]
            self.bm25_index = BM25Okapi(tokenized_corpus)
        else:
            self.bm25_index = None
        
        # Save indexes
        self._save_indexes()
        
        logger.info(f"Deleted document {document_id}")
    
    def clear_all(self):
        """Clear all indexes"""
        self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.bm25_index = None
        self.metadata = []
        
        # Clear product indexes
        self.product_faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.product_bm25_index = None
        self.product_metadata = []
        
        self.filters_cache = {
            "prices": [],
            "categories": [],
            "ratings": [],
            "product_ids": []
        }
        
        self._save_indexes()
        self._save_product_indexes()
        logger.info("Cleared all indexes (documents and products)")
    
    def clear_products_only(self):
        """
        Clear only products from the unified index, keeping documents intact.
        
        Filters metadata to remove product entries and rebuilds BM25.
        Note: FAISS vectors remain but metadata filtering ensures only current content is returned.
        """
        # Count existing products before clearing
        product_count = sum(1 for chunk in self.metadata if chunk.get('content_type') == 'product')
        
        # Filter out products, keep only documents
        self.metadata = [chunk for chunk in self.metadata if chunk.get('content_type') != 'product']
        
        # Rebuild BM25 index with remaining content (documents only)
        if self.metadata:
            all_texts = [chunk["text"] for chunk in self.metadata]
            tokenized_corpus = [text.lower().split() for text in all_texts]
            self.bm25_index = BM25Okapi(tokenized_corpus)
        else:
            self.bm25_index = None
        
        # Clear filters cache (product-specific)
        self.filters_cache = {
            "prices": [],
            "categories": [],
            "ratings": [],
            "product_ids": []
        }
        
        # Save the updated metadata and BM25 index
        # Note: FAISS index keeps old vectors but metadata filtering ensures correctness
        self._save_indexes()
        
        logger.info(f"Cleared {product_count} products from unified index. {len(self.metadata)} documents remain")
    
    def add_products(
        self,
        products: List[Dict],
        embeddings: List[List[float]]
    ):
        """
        Add products to unified indexes (uses main index with content_type="product").
        
        Args:
            products (List[Dict]): List of product dictionaries with metadata.
            embeddings (List[List[float]]): List of embedding vectors (one per product).
            
        Raises:
            ValueError: If products and embeddings counts mismatch.
        """
        if len(products) != len(embeddings):
            raise ValueError("Number of products must match number of embeddings")
        
        if not products:
            logger.warning("No products to add")
            return
        
        # Create chunks with product metadata and content_type
        chunks = []
        for product in products:
            chunk = {
                'chunk_id': f"{product.get('product_id', product.get('id'))}_chunk",
                'document_id': product.get('product_id', product.get('id')),
                'text': product.get('embedding_text', ''),
                'content_type': 'product',  # Mark as product
                'metadata': {
                    'product_id': product.get('product_id', product.get('id')),
                    'name': product.get('name'),
                    'category': product.get('category'),
                    'price': product.get('price'),
                    'rating': product.get('rating'),
                    'brand': product.get('brand'),
                    'description': product.get('description'),
                    'review_count': product.get('review_count'),
                    'image_url': product.get('image_url')
                }
            }
            chunks.append(chunk)
            
            # Update filters cache for fast filtering
            product_id = product.get('product_id', product.get('id'))
            self.filters_cache['product_ids'].append(product_id)
            self.filters_cache['prices'].append(product.get('price'))
            self.filters_cache['categories'].append(product.get('category'))
            self.filters_cache['ratings'].append(product.get('rating'))
        
        # Add to UNIFIED FAISS index (same as documents)
        embeddings_array = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings_array)
        self.faiss_index.add(embeddings_array)
        
        # Add metadata to unified metadata list
        for chunk in chunks:
            self.metadata.append(chunk)
            
        # Rebuild unified BM25 index with all content (documents + products)
        all_texts = [chunk["text"] for chunk in self.metadata]
        tokenized_corpus = [text.lower().split() for text in all_texts]
        self.bm25_index = BM25Okapi(tokenized_corpus)
        
        logger.info(f"Added {len(products)} products to unified indexes (content_type=product)")
        
        # Save unified indexes
        self._save_indexes()
    
    def _save_product_indexes(self):
        """Save product indexes to disk"""
        try:
            # Save product FAISS index
            faiss.write_index(self.product_faiss_index, str(self.product_faiss_index_path))
            logger.info(f"Saved product FAISS index ({self.product_faiss_index.ntotal} vectors)")
            
            # Save product BM25 index
            if self.product_bm25_index:
                with open(self.product_bm25_index_path, 'wb') as f:
                    pickle.dump(self.product_bm25_index, f)
                logger.info("Saved product BM25 index")
            
            # Save product metadata
            with open(self.product_metadata_path, 'wb') as f:
                pickle.dump(self.product_metadata, f)
            logger.info(f"Saved {len(self.product_metadata)} product metadata entries")
            
            # Save product filters cache
            with open(self.product_filters_cache_path, 'wb') as f:
                pickle.dump(self.filters_cache, f)
            logger.debug("Saved product filters cache")
            
        except Exception as e:
            logger.error(f"Error saving product indexes: {e}")
            raise
    
    def get_filters_cache(self) -> Dict:
        """
        Get filters cache for fast filtering
        
        Returns:
            Dictionary with filterable fields aligned with vector indices
        """
        return self.filters_cache.copy()
    
    def get_product_metadata(self, product_id: str) -> Optional[Dict]:
        """
        Get product metadata by product_id.
        
        Args:
            product_id (str): Product identifier.
            
        Returns:
            Optional[Dict]: Product metadata dictionary or None if not found.
        """
        for chunk in self.metadata:
            if chunk.get('metadata', {}).get('product_id') == product_id:
                return chunk.get('metadata')
        return None

