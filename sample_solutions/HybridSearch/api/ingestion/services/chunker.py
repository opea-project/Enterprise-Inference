"""
Text Chunker
Splits text into chunks for embedding and retrieval
"""

import logging
from typing import List, Dict
import re

logger = logging.getLogger(__name__)


class TextChunker:
    """Chunk text into smaller pieces for processing"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Initialize chunker.
        
        Args:
            chunk_size (int): Maximum number of tokens per chunk.
            chunk_overlap (int): Number of tokens to overlap between chunks.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        logger.info(f"TextChunker initialized with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    
    @staticmethod
    def simple_tokenize(text: str) -> List[str]:
        """
        Simple tokenization by splitting on whitespace and punctuation marks.
        
        Args:
            text (str): Input text to tokenize.
            
        Returns:
            List[str]: List of token strings.
        """
        # Split on whitespace and punctuation
        tokens = re.findall(r'\w+|[^\w\s]', text)
        return tokens
    
    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Chunk text into overlapping segments based on token count.
        
        Args:
            text (str): Input text to chunk.
            metadata (Dict, optional): Optional metadata to attach to each chunk.
            
        Returns:
            List[Dict]: List of chunk dictionaries with text, token counts, and metadata.
        """
        if not text.strip():
            return []
        
        metadata = metadata or {}
        
        # Tokenize
        tokens = self.simple_tokenize(text)
        logger.info(f"Tokenized text into {len(tokens)} tokens")
        
        if len(tokens) <= self.chunk_size:
            # Text is smaller than chunk size, return as single chunk
            return [{
                "text": text,
                "token_count": len(tokens),
                **metadata
            }]
        
        chunks = []
        start = 0
        
        while start < len(tokens):
            # Get chunk
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            
            # Reconstruct text from tokens
            chunk_text = " ".join(chunk_tokens)
            
            chunks.append({
                "text": chunk_text,
                "token_count": len(chunk_tokens),
                "start_token": start,
                "end_token": end,
                **metadata
            })
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            
            # Prevent infinite loop
            if start >= len(tokens):
                break
        
        logger.debug(f"Created {len(chunks)} chunks from {len(tokens)} tokens")
        return chunks
    
    def chunk_document(
        self,
        pages_or_sections: Dict[int, str],
        document_id: str
    ) -> List[Dict]:
        """
        Chunk an entire document preserving page/section context.
        
        Args:
            pages_or_sections (Dict[int, str]): Dictionary mapping page/section numbers to text.
            document_id (str): Unique document identifier.
            
        Returns:
            List[Dict]: List of chunk dictionaries with added chunk IDs and metadata.
        """
        all_chunks = []
        chunk_id_counter = 0
        
        for page_num, text in pages_or_sections.items():
            # Chunk each page/section
            page_chunks = self.chunk_text(
                text,
                metadata={
                    "page_number": page_num,
                    "document_id": document_id
                }
            )
            
            # Add chunk IDs
            for chunk in page_chunks:
                chunk_id_counter += 1
                chunk["chunk_id"] = f"{document_id}_chunk_{chunk_id_counter}"
                all_chunks.append(chunk)
        
        logger.info(
            f"Document {document_id}: Created {len(all_chunks)} chunks "
            f"from {len(pages_or_sections)} pages/sections"
        )
        
        return all_chunks

