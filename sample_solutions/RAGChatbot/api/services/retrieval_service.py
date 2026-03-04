"""
Retrieval service
Handles query processing and retrieval operations
"""

import logging
from langchain_community.vectorstores import FAISS
import config

logger = logging.getLogger(__name__)


def query_documents(query: str, vectorstore: FAISS, api_key: str) -> dict:
    """
    Query the documents using RAG with custom embedding and inference
    
    Simple workflow:
    1. Create embedding for the query
    2. Search for similar documents in the vectorstore
    3. Format the retrieved context
    4. Summarize using Llama inference endpoint
    
    Args:
        query: User's question
        vectorstore: FAISS vectorstore instance
        api_key: API key
        
    Returns:
        Dictionary with answer and query
        
    Raises:
        Exception: If query processing fails
    """
    try:
        logger.info(f"Processing query: {query}")
        
        # Step 1: Create embedding for the query
        logger.info("Creating query embedding...")
        from .api_client import get_api_client
        api_client = get_api_client()
        
        query_embedding = api_client.embed_text(query)
        logger.info(f"Query embedding created (dimension: {len(query_embedding)})")
        
        # Step 2: Search for similar documents (similarity search)
        logger.info("Searching for similar documents...")
        similar_docs = vectorstore.similarity_search_by_vector(query_embedding, k=4)
        logger.info(f"Found {len(similar_docs)} similar documents")
        
        if not similar_docs:
            return {
                "answer": "I couldn't find any relevant documents to answer your question.",
                "query": query
            }
        
        # Step 3: Format the retrieved context
        context_parts = []
        for i, doc in enumerate(similar_docs):
            context_parts.append(f"Document {i+1}:\n{doc.page_content}")
        
        context = "\n\n".join(context_parts)
        logger.info(f"Context length: {len(context)} characters")
        
        # Step 4: Create prompt for summarization using Llama
        prompt = f"""Based on the following documents, provide a comprehensive summary that addresses the question.

Documents:
{context}

Question: {query}

Summary:"""
        
        logger.info(f"Calling Llama inference with prompt length: {len(prompt)}")
        
        # Call Llama inference endpoint for summarization
        answer = api_client.complete(
            prompt=prompt,
            max_tokens=200,
            temperature=0
        )
        
        answer = answer.strip()
        
        if not answer:
            answer = "I couldn't find a relevant answer in the documents."
        
        logger.info("✓ Query completed successfully")
        
        return {
            "answer": answer,
            "query": query
        }
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise

