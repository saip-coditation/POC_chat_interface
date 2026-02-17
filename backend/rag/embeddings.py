"""
OpenAI Embeddings Client

Uses OpenAI (or compatible OpenRouter) API to generate text embeddings for semantic search.
Falls back to sentence-transformers (local) when OpenAI API is unreachable (e.g. Render APIConnectionError).
"""

import os
import logging
import time
import random
from typing import List, Optional
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# Connection errors that trigger local fallback
_CONNECTION_ERROR_NAMES = ("APIConnectionError", "ConnectionError", "ConnectError", "Timeout")


def _is_connection_error(exc: Exception) -> bool:
    """True if this exception indicates OpenAI API is unreachable."""
    name = type(exc).__name__
    if name in _CONNECTION_ERROR_NAMES:
        return True
    msg = str(exc).lower()
    return "connection" in msg or "connection error" in msg or "connection refused" in msg


class LocalEmbeddings:
    """
    Local embeddings via sentence-transformers. No API calls.
    Used when OpenAI is unreachable (e.g. Render APIConnectionError).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                logger.info("Local embeddings (sentence-transformers) initialized")
            except ImportError:
                raise ImportError(
                    "sentence-transformers required for local fallback. "
                    "Install: pip install sentence-transformers"
                )
        return self._model

    def embed(self, text: str, task_type: str = "retrieval_document") -> List[float]:
        if not text or not text.strip():
            return []
        vectors = self.embed_batch([text])
        return vectors[0] if vectors else []

    def embed_batch(
        self, texts: List[str], task_type: str = "retrieval_document"
    ) -> List[List[float]]:
        if not texts:
            return []
        valid = [t.strip() for t in texts if t and t.strip()]
        if not valid:
            return []
        model = self._get_model()
        vectors = model.encode(valid, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    def embed_for_query(self, text: str) -> List[float]:
        return self.embed(text)

    def embed_for_storage(self, text: str) -> List[float]:
        return self.embed(text)


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
        
        # Determine if using OpenRouter
        self.is_openrouter = self.api_key and self.api_key.startswith("sk-or-")
        
        # Select appropriate model
        if model:
            self.model = model
        elif self.is_openrouter:
            # OpenRouter uses different embedding models
            self.model = "openai/text-embedding-3-small"
        else:
            self.model = self.DEFAULT_MODEL
            
        self._client = None
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. Embeddings will fail until configured.")
    
    def _get_client(self):
        """Lazy initialization of the OpenAI client."""
        if self._client is None:
            # Handle OpenRouter config if present
            base_url = None
            if self.is_openrouter:
                base_url = "https://openrouter.ai/api/v1"
                
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
                timeout=120.0,  # Increased from default 60s for Render's network
                max_retries=3    # Increased from default 2
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
                    logger.error(f"Embedding batch failed ({attempt+1}/{max_retries}): {type(e).__name__}: {e}")

                    if _is_connection_error(e):
                        logger.warning("OpenAI unreachable (connection error), using local embeddings")
                        raise  # Re-raise so FallbackEmbeddings can catch and use local
                    if "429" in error_str or "quota" in error_str:
                        if attempt < max_retries - 1:
                            delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                            logger.warning(f"Embedding rate limit. Retrying in {delay:.2f}s")
                            time.sleep(delay)
                            continue
                    if attempt == max_retries - 1:
                        raise
            return []
        except Exception as e:
            if _is_connection_error(e):
                raise
            logger.error(f"Fatal embedding error: {e}")
            return [[] for _ in texts]
    
    def embed_for_query(self, text: str) -> List[float]:
        """Convenience method for query embeddings."""
        return self.embed(text)
    
    def embed_for_storage(self, text: str) -> List[float]:
        """Convenience method for document storage embeddings."""
        return self.embed(text)


class FallbackEmbeddings:
    """
    Tries OpenAI first; on APIConnectionError uses local sentence-transformers.
    """
    # Chroma collection for local embeddings (384 dims vs OpenAI 1536)
    LOCAL_COLLECTION = "documents_local"

    def __init__(self):
        self._openai = GeminiEmbeddings()
        self._local: Optional[LocalEmbeddings] = None
        self._use_local = False

    @property
    def collection_name(self) -> str:
        """Use documents_local when on local fallback to avoid dimension mismatch."""
        return self.LOCAL_COLLECTION if self._use_local else "documents"

    def embed(self, text: str, task_type: str = "retrieval_document") -> List[float]:
        return self.embed_batch([text], task_type)[0] if text and text.strip() else []

    def embed_batch(
        self, texts: List[str], task_type: str = "retrieval_document"
    ) -> List[List[float]]:
        if not texts:
            return []
        if self._use_local:
            return self._get_local().embed_batch(texts, task_type)
        try:
            return self._openai.embed_batch(texts, task_type)
        except Exception as e:
            if _is_connection_error(e):
                logger.warning("Switching to local embeddings (OpenAI unreachable)")
                self._use_local = True
                return self._get_local().embed_batch(texts, task_type)
            raise

    def _get_local(self) -> LocalEmbeddings:
        if self._local is None:
            self._local = LocalEmbeddings()
        return self._local

    def embed_for_query(self, text: str) -> List[float]:
        return self.embed(text)

    def embed_for_storage(self, text: str) -> List[float]:
        return self.embed(text)


# Singleton instance for convenience
_default_embeddings = None

def get_embeddings() -> FallbackEmbeddings:
    """Get the default embeddings instance (tries OpenAI, falls back to local on connection error)."""
    global _default_embeddings
    if _default_embeddings is None:
        _default_embeddings = FallbackEmbeddings()
    return _default_embeddings
