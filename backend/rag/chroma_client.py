"""
Chroma DB Client

Provides a persistent vector database for semantic search.
Uses Chroma in persistent mode - no external server required.
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ChromaClient:
    """
    Wrapper for ChromaDB persistent client.
    
    The database is stored locally in a folder, similar to SQLite.
    No separate server process is required.
    
    Usage:
        client = ChromaClient()
        collection = client.get_or_create_collection("intents")
        collection.add(ids=["1"], embeddings=[[0.1, 0.2, ...]], documents=["text"])
    """
    
    # Default path for the persistent database
    DEFAULT_DB_PATH = "data/chroma_db"
    
    def __init__(self, persist_directory: Optional[str] = None):
        """
        Initialize the Chroma persistent client.
        
        Args:
            persist_directory: Path to store the database. 
                              Defaults to data/chroma_db relative to backend.
        """
        # Resolve path relative to this file's directory (backend/)
        if persist_directory is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            persist_directory = os.path.join(base_dir, self.DEFAULT_DB_PATH)
        
        self.persist_directory = persist_directory
        self._client = None
        
        # Ensure directory exists
        os.makedirs(self.persist_directory, exist_ok=True)
        logger.info(f"Chroma DB initialized at: {self.persist_directory}")
    
    def _get_client(self):
        """Lazy initialization of the Chroma client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
                
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
            except ImportError:
                raise ImportError(
                    "chromadb package not installed. "
                    "Run: pip install chromadb"
                )
        return self._client
    
    def get_or_create_collection(
        self, 
        name: str, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Get or create a collection by name.
        
        Args:
            name: Collection name (e.g., "intents", "entities", "tool_docs")
            metadata: Optional metadata for the collection
        
        Returns:
            Chroma Collection object
        """
        client = self._get_client()
        return client.get_or_create_collection(
            name=name,
            metadata=metadata or {"hnsw:space": "cosine"}
        )
    
    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection by name.
        
        Args:
            name: Collection name to delete
        
        Returns:
            True if deleted, False if not found
        """
        try:
            client = self._get_client()
            client.delete_collection(name=name)
            logger.info(f"Deleted collection: {name}")
            return True
        except Exception as e:
            logger.warning(f"Could not delete collection {name}: {e}")
            return False
    
    def list_collections(self) -> List[str]:
        """List all collection names."""
        client = self._get_client()
        collections = client.list_collections()
        return [c.name for c in collections]
    
    def reset(self):
        """
        Reset the entire database. USE WITH CAUTION.
        This deletes all collections and data.
        """
        client = self._get_client()
        client.reset()
        logger.warning("Chroma database has been reset!")


class ChromaCollection:
    """
    High-level wrapper for a Chroma collection with embedding integration.
    """
    
    def __init__(self, collection, embeddings_client=None):
        """
        Initialize collection wrapper.
        
        Args:
            collection: Raw Chroma collection
            embeddings_client: Optional GeminiEmbeddings instance
        """
        self._collection = collection
        self._embeddings = embeddings_client
    
    def add(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        embeddings: Optional[List[List[float]]] = None
    ):
        """
        Add documents to the collection.
        
        If embeddings are not provided and an embeddings client is configured,
        embeddings will be generated automatically.
        """
        if embeddings is None and self._embeddings is not None:
            embeddings = self._embeddings.embed_batch(documents)
        
        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )
    
    def query(
        self,
        query_text: str = None,
        query_embedding: List[float] = None,
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Query the collection for similar documents.
        
        Args:
            query_text: Text to search for (will be embedded)
            query_embedding: Pre-computed embedding vector
            n_results: Number of results to return
            where: Optional metadata filter
        
        Returns:
            Dictionary with ids, documents, metadatas, distances
        """
        if query_embedding is None:
            if query_text is None:
                raise ValueError("Either query_text or query_embedding must be provided")
            if self._embeddings is None:
                raise ValueError("No embeddings client configured for text queries")
            query_embedding = self._embeddings.embed_for_query(query_text)
        
        return self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )
    
    def count(self) -> int:
        """Return the number of documents in the collection."""
        return self._collection.count()


# Singleton instance
_default_client = None

def get_chroma_client() -> ChromaClient:
    """Get the default Chroma client instance."""
    global _default_client
    if _default_client is None:
        _default_client = ChromaClient()
    return _default_client
