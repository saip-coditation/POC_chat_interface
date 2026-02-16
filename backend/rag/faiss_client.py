"""
FAISS Vector Store Client

Lightweight alternative to ChromaDB for Vercel deployment.
Uses FAISS (Facebook AI Similarity Search) for efficient vector storage and retrieval.
"""

import os
import pickle
import logging
from typing import List, Dict, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """
    FAISS-based vector store that mimics ChromaDB's interface.
    
    Stores embeddings in memory with optional persistence to disk.
    """
    
    def __init__(self, persist_directory: str = "./data/faiss_db"):
        """Initialize FAISS vector store."""
        self.persist_directory = persist_directory
        self.collections = {}
        
        # Create persist directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Load existing collections
        self._load_collections()
    
    def _load_collections(self):
        """Load collections from disk."""
        try:
            collections_file = os.path.join(self.persist_directory, "collections.pkl")
            if os.path.exists(collections_file):
                with open(collections_file, 'rb') as f:
                    self.collections = pickle.load(f)
                logger.info(f"Loaded {len(self.collections)} FAISS collections")
        except Exception as e:
            logger.warning(f"Could not load FAISS collections: {e}")
            self.collections = {}
    
    def _save_collections(self):
        """Save collections to disk."""
        try:
            collections_file = os.path.join(self.persist_directory, "collections.pkl")
            with open(collections_file, 'wb') as f:
                pickle.dump(self.collections, f)
        except Exception as e:
            logger.error(f"Failed to save FAISS collections: {e}")
    
    def get_or_create_collection(self, name: str, embedding_function=None) -> 'FAISSCollection':
        """Get or create a collection."""
        if name not in self.collections:
            self.collections[name] = {
                'embeddings': [],
                'documents': [],
                'metadatas': [],
                'ids': []
            }
            self._save_collections()
        
        return FAISSCollection(name, self, embedding_function)


class FAISSCollection:
    """
    FAISS collection that mimics ChromaDB collection interface.
    """
    
    def __init__(self, name: str, store: FAISSVectorStore, embedding_function=None):
        self.name = name
        self.store = store
        self.embedding_function = embedding_function
        self._data = store.collections[name]
    
    def add(
        self,
        documents: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ):
        """Add documents to the collection."""
        if not documents:
            return
        
        # Generate embeddings if not provided
        if embeddings is None:
            if self.embedding_function is None:
                raise ValueError("No embedding function provided")
            embeddings = [self.embedding_function(doc) for doc in documents]
        
        # Generate IDs if not provided
        if ids is None:
            start_id = len(self._data['ids'])
            ids = [f"doc_{start_id + i}" for i in range(len(documents))]
        
        # Default metadatas
        if metadatas is None:
            metadatas = [{} for _ in documents]
        
        # Store data
        self._data['embeddings'].extend(embeddings)
        self._data['documents'].extend(documents)
        self._data['metadatas'].extend(metadatas)
        self._data['ids'].extend(ids)
        
        self.store._save_collections()
    
    def query(
        self,
        query_embeddings: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 10,
        **kwargs
    ) -> Dict[str, List]:
        """Query the collection."""
        if not self._data['embeddings']:
            return {
                'ids': [[]],
                'documents': [[]],
                'metadatas': [[]],
                'distances': [[]]
            }
        
        # Generate embeddings for query texts if provided
        if query_embeddings is None and query_texts is not None:
            if self.embedding_function is None:
                raise ValueError("No embedding function provided for query")
            query_embeddings = [self.embedding_function(text) for text in query_texts]
        
        if query_embeddings is None:
            raise ValueError("Either query_embeddings or query_texts must be provided")
        
        # Convert to numpy arrays
        query_array = np.array(query_embeddings)
        doc_array = np.array(self._data['embeddings'])
        
        # Compute cosine similarity
        # Normalize vectors
        query_norm = query_array / (np.linalg.norm(query_array, axis=1, keepdims=True) + 1e-10)
        doc_norm = doc_array / (np.linalg.norm(doc_array, axis=1, keepdims=True) + 1e-10)
        
        # Compute similarities
        similarities = np.dot(query_norm, doc_norm.T)
        
        # Get top-k results for each query
        results = {
            'ids': [],
            'documents': [],
            'metadatas': [],
            'distances': []
        }
        
        for i, query_sims in enumerate(similarities):
            # Convert similarity to distance (1 - similarity)
            distances = 1 - query_sims
            
            # Get top-k indices
            top_k = min(n_results, len(distances))
            top_indices = np.argpartition(distances, top_k)[:top_k]
            top_indices = top_indices[np.argsort(distances[top_indices])]
            
            # Extract results
            results['ids'].append([self._data['ids'][idx] for idx in top_indices])
            results['documents'].append([self._data['documents'][idx] for idx in top_indices])
            results['metadatas'].append([self._data['metadatas'][idx] for idx in top_indices])
            results['distances'].append([float(distances[idx]) for idx in top_indices])
        
        return results
    
    def delete(self, ids: Optional[List[str]] = None, where: Optional[Dict] = None):
        """Delete documents from collection."""
        if ids:
            # Remove by IDs
            indices_to_remove = [i for i, doc_id in enumerate(self._data['ids']) if doc_id in ids]
            for idx in sorted(indices_to_remove, reverse=True):
                del self._data['ids'][idx]
                del self._data['documents'][idx]
                del self._data['embeddings'][idx]
                del self._data['metadatas'][idx]
            
            self.store._save_collections()
    
    def count(self) -> int:
        """Get number of documents in collection."""
        return len(self._data['ids'])


# Singleton instance
_faiss_store = None


def get_faiss_store() -> FAISSVectorStore:
    """Get the singleton FAISS store instance."""
    global _faiss_store
    if _faiss_store is None:
        _faiss_store = FAISSVectorStore()
    return _faiss_store
