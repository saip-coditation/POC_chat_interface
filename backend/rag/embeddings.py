"""
OpenAI Embeddings Client

Uses OpenAI (or compatible OpenRouter) API to generate text embeddings for semantic search.
Switched from Gemini to leverage existing OPENAI_API_KEY configuration.
"""

import os
import logging
import time
import random
from typing import List, Optional
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


class GeminiEmbeddings:
    """
    Wrapper for OpenAI Embeddings API (Named GeminiEmbeddings to match existing imports).
    
    Usage:
        embeddings = GeminiEmbeddings()
        vector = embeddings.embed("What is the revenue for Product A?")
        vectors = embeddings.embed_batch(["text1", "text2", "text3"])
    """
    
    # Default model for embeddings - standard OpenAI model
    DEFAULT_MODEL = "text-embedding-3-small"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the embeddings client.
        
        Args:
            api_key: OpenAI API key. Falls back to settings.OPENAI_API_KEY.
            model: Embedding model to use. Defaults to text-embedding-3-small.
        """
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', os.getenv("OPENAI_API_KEY"))
        self.model = model or self.DEFAULT_MODEL
        self._client = None
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. Embeddings will fail until configured.")
    
    def _get_client(self):
        """Lazy initialization of the OpenAI client."""
        if self._client is None:
            # Handle OpenRouter config if present
            base_url = None
            if self.api_key and self.api_key.startswith("sk-or-"):
                base_url = "https://openrouter.ai/api/v1"
                
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=base_url
            )
        return self._client
    
    def embed(self, text: str, task_type: str = "retrieval_document") -> List[float]:
        """
        Generate embedding for a single text string.
        (task_type is ignored for OpenAI but kept for signature compatibility)
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return []
        
        return self.embed_batch([text])[0] if text else []
    
    def embed_batch(
        self, 
        texts: List[str], 
        task_type: str = "retrieval_document"
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        """
        if not texts:
            return []
        
        # Filter empty texts
        valid_texts_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        valid_texts = [texts[i] for i in valid_texts_indices]
        
        if not valid_texts:
            return []
            
        max_retries = 5
        base_delay = 2
        
        try:
            client = self._get_client()
            
            for attempt in range(max_retries):
                try:
                    # OpenRouter/OpenAI call
                    response = client.embeddings.create(
                        input=valid_texts,
                        model=self.model
                    )
                    
                    # Extract embeddings ordered by index
                    embeddings_map = {item.index: item.embedding for item in response.data}
                    
                    # Reconstruct list matching input `valid_texts` order
                    # OpenAI guarantees order, but response.data includes index
                    result_vectors = [embeddings_map[i] for i in range(len(valid_texts))]
                    return result_vectors
                    
                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in error_str or "quota" in error_str:
                        if attempt < max_retries - 1:
                            delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                            logger.warning(f"Embedding rate limit. Retrying in {delay:.2f}s")
                            time.sleep(delay)
                            continue
                    
                    logger.error(f"Embedding batch failed ({attempt+1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        raise e
                        
            return []
            
        except Exception as e:
            logger.error(f"Fatal embedding error: {e}")
            return [[] for _ in texts] # Return empty vectors on failure to prevent crashes
    
    def embed_for_query(self, text: str) -> List[float]:
        """Convenience method for query embeddings."""
        return self.embed(text)
    
    def embed_for_storage(self, text: str) -> List[float]:
        """Convenience method for document storage embeddings."""
        return self.embed(text)


# Singleton instance for convenience
_default_embeddings = None

def get_embeddings() -> GeminiEmbeddings:
    """Get the default embeddings instance."""
    global _default_embeddings
    if _default_embeddings is None:
        _default_embeddings = GeminiEmbeddings()
    return _default_embeddings
