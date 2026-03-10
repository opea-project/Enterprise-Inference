"""
Metadata Store
SQLite database for document metadata and processing status
"""

import logging
import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class MetadataStore:
    """
    SQLite-based metadata storage.
    
    Manages persistence for document and product metadata, processing status,
    and catalog statistics using a local SQLite database.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize metadata store.
        
        Args:
            db_path (str): Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = None
        self._connect()
        self._initialize_schema()
    
    def _connect(self):
        """
        Connect to database.
        
        Establishes connection, enables WAL mode for concurrency, and configures
        synchronous mode for performance.
        
        Raises:
            PermissionError: If database file is read-only.
            sqlite3.Error: For other database connection issues.
        """
        try:
            # Ensure parent directory exists and is writable
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if database file exists and is writable
            if self.db_path.exists():
                if not os.access(self.db_path, os.W_OK):
                    logger.warning(f"Database file {self.db_path} is not writable, attempting to fix permissions")
                    import stat
                    self.db_path.chmod(stat.S_IWRITE | stat.S_IREAD)
            
            # Connect with timeout to handle locked database
            # Use default isolation level (not autocommit) for transaction safety
            self.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=10.0  # 10 second timeout for locked database
            )
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            
            # Enable WAL mode for better concurrency (allows multiple readers + one writer)
            cursor = self.conn.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                result = cursor.fetchone()
                logger.info(f"Database journal mode: {result[0] if result else 'unknown'}")
            except Exception as e:
                logger.warning(f"Could not enable WAL mode: {e}")
            
            try:
                cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
            except Exception as e:
                logger.warning(f"Could not set synchronous mode: {e}")
            
            self.conn.commit()
            
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.OperationalError as e:
            if "readonly" in str(e).lower() or "read-only" in str(e).lower():
                logger.error(f"Database is read-only: {self.db_path}. Check file permissions.")
                raise PermissionError(f"Database file is read-only: {self.db_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to database {self.db_path}: {e}")
            raise
    
    def _initialize_schema(self):
        """
        Initialize database schema.
        
        Creates tables for documents, products, product attributes, and catalog metadata
        if they do not already exist. Also sets up performance indexes.
        """
        cursor = self.conn.cursor()
        
        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER,
                upload_timestamp TEXT NOT NULL,
                processing_status TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                error_message TEXT,
                metadata TEXT
            )
        """)
        
        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                price REAL,
                rating REAL,
                review_count INTEGER,
                image_url TEXT,
                brand TEXT,
                embedding_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Product attributes table (flexible key-value pairs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                attribute_name TEXT NOT NULL,
                attribute_value TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                UNIQUE(product_id, attribute_name)
            )
        """)
        
        # Catalog metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS catalog_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                catalog_name TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                product_count INTEGER DEFAULT 0,
                categories TEXT,
                price_range_min REAL,
                price_range_max REAL
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_rating ON products(rating)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_attributes_product_id 
            ON product_attributes(product_id)
        """)
        
        # Commit explicitly (even though we're in autocommit mode, this ensures it's written)
        self.conn.commit()
        logger.info("Database schema initialized")
    
    def add_document(
        self,
        document_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        metadata: Dict = None
    ):
        """
        Add new document record.
        
        Args:
            document_id (str): Unique document identifier.
            filename (str): Original filename.
            file_type (str): File extension/type.
            file_size (int): File size in bytes.
            metadata (Dict, optional): Additional metadata dictionary.
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO documents 
            (document_id, filename, file_type, file_size, upload_timestamp, 
             processing_status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            filename,
            file_type,
            file_size,
            datetime.utcnow().isoformat(),
            "pending",
            json.dumps(metadata or {})
        ))
        
        self.conn.commit()
        logger.info(f"Added document: {document_id}")
    
    def update_status(
        self,
        document_id: str,
        status: str,
        chunk_count: int = None,
        error_message: str = None
    ):
        """
        Update document processing status.
        
        Args:
            document_id (str): Document identifier.
            status (str): New status ('pending', 'processing', 'completed', 'failed').
            chunk_count (int, optional): Number of chunks created.
            error_message (str, optional): Error message if failed.
        """
        cursor = self.conn.cursor()
        
        query = "UPDATE documents SET processing_status = ?"
        params = [status]
        
        if chunk_count is not None:
            query += ", chunk_count = ?"
            params.append(chunk_count)
        
        if error_message is not None:
            query += ", error_message = ?"
            params.append(error_message)
        
        query += " WHERE document_id = ?"
        params.append(document_id)
        
        cursor.execute(query, params)
        self.conn.commit()
        
        logger.info(f"Updated document {document_id} status to: {status}")
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        """
        Get document by ID
        
        Args:
            document_id: Document identifier
            
        Returns:
            Document dictionary or None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM documents WHERE document_id = ?",
            (document_id,)
        )
        row = cursor.fetchone()
        
        if row:
            doc = dict(row)
            doc['metadata'] = json.loads(doc['metadata'])
            return doc
        return None
    
    def list_documents(
        self,
        status: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        List documents.
        
        Args:
            status (str, optional): Filter by processing status.
            limit (int): Maximum number of documents to return.
            
        Returns:
            List[Dict]: List of document dictionaries.
        """
        cursor = self.conn.cursor()
        
        if status:
            cursor.execute(
                "SELECT * FROM documents WHERE processing_status = ? "
                "ORDER BY upload_timestamp DESC LIMIT ?",
                (status, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM documents ORDER BY upload_timestamp DESC LIMIT ?",
                (limit,)
            )
        
        rows = cursor.fetchall()
        documents = []
        
        for row in rows:
            doc = dict(row)
            doc['metadata'] = json.loads(doc['metadata'])
            documents.append(doc)
        
        return documents
    
    def delete_document(self, document_id: str):
        """
        Delete document record
        
        Args:
            document_id: Document identifier
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM documents WHERE document_id = ?",
            (document_id,)
        )
        self.conn.commit()
        logger.info(f"Deleted document: {document_id}")
    
    def get_stats(self) -> Dict:
        """
        Get database statistics.
        
        Returns:
            Dict: Dictionary with total documents, status breakdowns, and chunk counts.
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM documents")
        total = cursor.fetchone()['total']
        
        cursor.execute(
            "SELECT processing_status, COUNT(*) as count "
            "FROM documents GROUP BY processing_status"
        )
        status_counts = {row['processing_status']: row['count'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT SUM(chunk_count) as total_chunks FROM documents")
        total_chunks = cursor.fetchone()['total_chunks'] or 0
        
        return {
            "total_documents": total,
            "status_counts": status_counts,
            "total_chunks": total_chunks
        }
    
    def clear_all(self):
        """
        Clear all documents from the database
        
        WARNING: This operation cannot be undone!
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM documents")
        self.conn.commit()
        logger.warning("All documents cleared from database")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    # Product-related methods
    def add_product(
        self,
        product_id: str,
        name: str,
        description: str = None,
        category: str = None,
        price: float = None,
        rating: float = None,
        review_count: int = None,
        image_url: str = None,
        brand: str = None,
        embedding_text: str = None
    ):
        """
        Add new product record
        
        Args:
            product_id: Unique product identifier
            name: Product name/title
            description: Product description
            category: Product category
            price: Product price
            rating: Product rating (0-5)
            review_count: Number of reviews
            image_url: Product image URL
            brand: Product brand
            embedding_text: Text used for embedding
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO products 
            (id, name, description, category, price, rating, review_count, 
             image_url, brand, embedding_text, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            product_id,
            name,
            description,
            category,
            price,
            rating,
            review_count,
            image_url,
            brand,
            embedding_text
        ))
        
        self.conn.commit()
        logger.debug(f"Added product: {product_id}")
    
    def add_product_attribute(
        self,
        product_id: str,
        attribute_name: str,
        attribute_value: str
    ):
        """
        Add product attribute
        
        Args:
            product_id: Product identifier
            attribute_name: Attribute name (e.g., "color", "size")
            attribute_value: Attribute value
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO product_attributes 
            (product_id, attribute_name, attribute_value)
            VALUES (?, ?, ?)
        """, (product_id, attribute_name, attribute_value))
        
        self.conn.commit()
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """
        Get product by ID
        
        Args:
            product_id: Product identifier
            
        Returns:
            Product dictionary or None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        )
        row = cursor.fetchone()
        
        if row:
            product = dict(row)
            # Get attributes
            cursor.execute(
                "SELECT attribute_name, attribute_value FROM product_attributes WHERE product_id = ?",
                (product_id,)
            )
            attributes = {row['attribute_name']: row['attribute_value'] for row in cursor.fetchall()}
            product['attributes'] = attributes
            return product
        return None
    
    def list_products(
        self,
        category: str = None,
        price_min: float = None,
        price_max: float = None,
        rating_min: float = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        List products with optional filters
        
        Args:
            category: Filter by category
            price_min: Minimum price
            price_max: Maximum price
            rating_min: Minimum rating
            limit: Maximum number of products to return
            offset: Offset for pagination
            
        Returns:
            List of product dictionaries
        """
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if price_min is not None:
            query += " AND price >= ?"
            params.append(price_min)
        
        if price_max is not None:
            query += " AND price <= ?"
            params.append(price_max)
        
        if rating_min is not None:
            query += " AND rating >= ?"
            params.append(rating_min)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        products = []
        for row in rows:
            product = dict(row)
            # Get attributes for each product
            cursor.execute(
                "SELECT attribute_name, attribute_value FROM product_attributes WHERE product_id = ?",
                (product['id'],)
            )
            attributes = {row['attribute_name']: row['attribute_value'] for row in cursor.fetchall()}
            product['attributes'] = attributes
            products.append(product)
        
        return products
    
    def get_product_stats(self) -> Dict:
        """
        Get product statistics
        
        Returns:
            Dictionary with product statistics
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM products")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(DISTINCT category) as categories FROM products WHERE category IS NOT NULL")
        categories = cursor.fetchone()['categories']
        
        cursor.execute("SELECT MIN(price) as min_price, MAX(price) as max_price, AVG(price) as avg_price FROM products WHERE price IS NOT NULL")
        price_stats = cursor.fetchone()
        
        cursor.execute("SELECT MIN(rating) as min_rating, MAX(rating) as max_rating, AVG(rating) as avg_rating FROM products WHERE rating IS NOT NULL")
        rating_stats = cursor.fetchone()
        
        return {
            "total_products": total,
            "total_categories": categories,
            "price_range": {
                "min": price_stats['min_price'],
                "max": price_stats['max_price'],
                "avg": price_stats['avg_price']
            } if price_stats['min_price'] else None,
            "rating_range": {
                "min": rating_stats['min_rating'],
                "max": rating_stats['max_rating'],
                "avg": rating_stats['avg_rating']
            } if rating_stats['min_rating'] else None
        }
    
    def update_catalog_metadata(
        self,
        catalog_name: str,
        product_count: int,
        categories: List[str] = None,
        price_range_min: float = None,
        price_range_max: float = None
    ):
        """
        Update catalog metadata
        
        Args:
            catalog_name: Name of the catalog
            product_count: Number of products
            categories: List of unique categories
            price_range_min: Minimum price in catalog
            price_range_max: Maximum price in catalog
        """
        cursor = self.conn.cursor()
        
        # Clear existing catalog metadata (single catalog mode)
        cursor.execute("DELETE FROM catalog_metadata")
        
        cursor.execute("""
            INSERT INTO catalog_metadata 
            (catalog_name, product_count, categories, price_range_min, price_range_max)
            VALUES (?, ?, ?, ?, ?)
        """, (
            catalog_name,
            product_count,
            json.dumps(categories) if categories else None,
            price_range_min,
            price_range_max
        ))
        
        self.conn.commit()
        logger.info(f"Updated catalog metadata: {catalog_name} ({product_count} products)")
    
    def get_catalog_metadata(self) -> Optional[Dict]:
        """
        Get current catalog metadata
        
        Returns:
            Catalog metadata dictionary or None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM catalog_metadata ORDER BY upload_date DESC LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            metadata = dict(row)
            if metadata.get('categories'):
                metadata['categories'] = json.loads(metadata['categories'])
            return metadata
        return None
    
    def clear_all_products(self):
        """
        Clear all products from the database
        
        WARNING: This operation cannot be undone!
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM product_attributes")
        cursor.execute("DELETE FROM catalog_metadata")
        self.conn.commit()
        logger.warning("All products cleared from database")

