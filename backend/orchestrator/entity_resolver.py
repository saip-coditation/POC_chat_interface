"""
Entity Resolver

Resolves user terms to canonical entities using:
1. Exact match in tenant catalog
2. Fuzzy match (Levenshtein distance)
3. Semantic match via Chroma
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ResolvedEntity:
    """Result of entity resolution."""
    original_term: str
    canonical_name: str
    entity_type: str
    platform: str
    external_id: Optional[str] = None
    confidence: float = 1.0
    match_type: str = "exact"  # exact, fuzzy, semantic
    alternatives: List[Dict] = None
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []
    
    def is_ambiguous(self) -> bool:
        """Check if there are close alternatives."""
        if not self.alternatives:
            return False
        # Ambiguous if any alternative is within 0.1 confidence
        return any(alt.get('confidence', 0) > self.confidence - 0.1 for alt in self.alternatives)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_term": self.original_term,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type,
            "platform": self.platform,
            "external_id": self.external_id,
            "confidence": self.confidence,
            "match_type": self.match_type,
            "alternatives": self.alternatives
        }


class EntityResolver:
    """
    Resolves user terms to canonical entities.
    
    Resolution strategy:
    1. Exact match against tenant catalog (confidence = 1.0)
    2. Fuzzy match with Levenshtein distance <= 2 (confidence = 0.9)
    3. Semantic match via Chroma (confidence = similarity score)
    """
    
    COLLECTION_NAME = "tenant_catalog"
    MIN_SEMANTIC_CONFIDENCE = 0.6
    
    def __init__(self, chroma_client=None, embeddings_client=None):
        """
        Initialize the entity resolver.
        
        Args:
            chroma_client: Optional ChromaClient instance
            embeddings_client: Optional GeminiEmbeddings instance
        """
        self._chroma = chroma_client
        self._embeddings = embeddings_client
    
    def _get_chroma(self):
        """Lazy load Chroma client."""
        if self._chroma is None:
            from rag.chroma_client import get_chroma_client
            self._chroma = get_chroma_client()
        return self._chroma
    
    def _get_embeddings(self):
        """Lazy load embeddings client."""
        if self._embeddings is None:
            from rag.embeddings import get_embeddings
            self._embeddings = get_embeddings()
        return self._embeddings
    
    def resolve(
        self,
        term: str,
        user=None,
        platform: str = None,
        entity_type: str = None
    ) -> Optional[ResolvedEntity]:
        """
        Resolve a user term to a canonical entity.
        
        Args:
            term: The term to resolve (e.g., "Product A", "John's account")
            user: Optional Django user for tenant-specific resolution
            platform: Optional platform to scope the search
            entity_type: Optional entity type filter
        
        Returns:
            ResolvedEntity if found, None otherwise
        """
        term_lower = term.lower().strip()
        
        # Step 1: Exact match in database
        result = self._exact_match(term_lower, user, platform, entity_type)
        if result:
            return result
        
        # Step 2: Fuzzy match in database
        result = self._fuzzy_match(term_lower, user, platform, entity_type)
        if result:
            return result
        
        # Step 3: Semantic match via Chroma
        result = self._semantic_match(term_lower, user, platform, entity_type)
        if result:
            return result
        
        # Step 4: Check glossary for term mappings
        result = self._glossary_lookup(term_lower, user, platform)
        if result:
            return result
        
        return None
    
    def _exact_match(
        self,
        term: str,
        user=None,
        platform: str = None,
        entity_type: str = None
    ) -> Optional[ResolvedEntity]:
        """Look for exact match in tenant catalog."""
        from catalog.models import TenantCatalog
        
        queryset = TenantCatalog.objects.all()
        
        if user:
            queryset = queryset.filter(user=user)
        if platform:
            queryset = queryset.filter(platform=platform)
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        # Match by display name (case-insensitive)
        match = queryset.filter(display_name__iexact=term).first()
        
        if match:
            return ResolvedEntity(
                original_term=term,
                canonical_name=match.display_name,
                entity_type=match.entity_type,
                platform=match.platform,
                external_id=match.external_id,
                confidence=1.0,
                match_type="exact"
            )
        
        # Check synonyms
        for item in queryset:
            if term in [s.lower() for s in item.synonyms]:
                return ResolvedEntity(
                    original_term=term,
                    canonical_name=item.display_name,
                    entity_type=item.entity_type,
                    platform=item.platform,
                    external_id=item.external_id,
                    confidence=1.0,
                    match_type="exact_synonym"
                )
        
        return None
    
    def _fuzzy_match(
        self,
        term: str,
        user=None,
        platform: str = None,
        entity_type: str = None
    ) -> Optional[ResolvedEntity]:
        """Look for fuzzy match using Levenshtein distance."""
        from catalog.models import TenantCatalog
        
        queryset = TenantCatalog.objects.all()
        
        if user:
            queryset = queryset.filter(user=user)
        if platform:
            queryset = queryset.filter(platform=platform)
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        best_match = None
        best_distance = float('inf')
        alternatives = []
        
        for item in queryset[:100]:  # Limit for performance
            distance = self._levenshtein_distance(term, item.display_name.lower())
            
            if distance <= 2:  # Allow up to 2 edits
                if distance < best_distance:
                    if best_match:
                        alternatives.append({
                            "canonical_name": best_match.display_name,
                            "confidence": 0.9 - (best_distance * 0.1)
                        })
                    best_match = item
                    best_distance = distance
                else:
                    alternatives.append({
                        "canonical_name": item.display_name,
                        "confidence": 0.9 - (distance * 0.1)
                    })
        
        if best_match:
            return ResolvedEntity(
                original_term=term,
                canonical_name=best_match.display_name,
                entity_type=best_match.entity_type,
                platform=best_match.platform,
                external_id=best_match.external_id,
                confidence=0.9 - (best_distance * 0.1),
                match_type="fuzzy",
                alternatives=alternatives[:3]
            )
        
        return None
    
    def _semantic_match(
        self,
        term: str,
        user=None,
        platform: str = None,
        entity_type: str = None
    ) -> Optional[ResolvedEntity]:
        """Look for semantic match via Chroma."""
        try:
            chroma = self._get_chroma()
            collection = chroma.get_or_create_collection(self.COLLECTION_NAME)
            embeddings = self._get_embeddings()
            
            # Generate query embedding
            query_embedding = embeddings.embed_for_query(term)
            
            # Build metadata filter
            where_filter = {}
            if user:
                where_filter["user_id"] = str(user.id)
            if platform:
                where_filter["platform"] = platform
            if entity_type:
                where_filter["entity_type"] = entity_type
            
            # Search
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=5,
                where=where_filter if where_filter else None
            )
            
            if not results['ids'][0]:
                return None
            
            # Get best match
            best_metadata = results['metadatas'][0][0]
            distances = results['distances'][0] if 'distances' in results else [1.0]
            
            # Convert distance to confidence
            confidence = 1.0 / (1.0 + distances[0])
            
            if confidence < self.MIN_SEMANTIC_CONFIDENCE:
                return None
            
            # Collect alternatives
            alternatives = []
            for i in range(1, min(len(results['ids'][0]), 3)):
                alt_metadata = results['metadatas'][0][i]
                alt_confidence = 1.0 / (1.0 + distances[i]) if len(distances) > i else 0.5
                alternatives.append({
                    "canonical_name": alt_metadata.get('display_name'),
                    "confidence": alt_confidence
                })
            
            return ResolvedEntity(
                original_term=term,
                canonical_name=best_metadata.get('display_name', term),
                entity_type=best_metadata.get('entity_type', 'unknown'),
                platform=best_metadata.get('platform', 'unknown'),
                external_id=best_metadata.get('external_id'),
                confidence=confidence,
                match_type="semantic",
                alternatives=alternatives
            )
            
        except Exception as e:
            logger.error(f"Semantic match failed: {e}")
            return None
    
    def _glossary_lookup(
        self,
        term: str,
        user=None,
        platform: str = None
    ) -> Optional[ResolvedEntity]:
        """Look up term in business glossary."""
        from catalog.models import BusinessGlossary
        
        queryset = BusinessGlossary.objects.filter(term__iexact=term)
        
        if platform:
            queryset = queryset.filter(platform=platform) | queryset.filter(platform__isnull=True)
        
        if user:
            queryset = queryset.filter(user=user) | queryset.filter(user__isnull=True)
        
        match = queryset.first()
        
        if match:
            return ResolvedEntity(
                original_term=term,
                canonical_name=match.canonical_term,
                entity_type="glossary_term",
                platform=match.platform or "global",
                confidence=1.0 if match.is_exact_match else 0.95,
                match_type="glossary"
            )
        
        return None
    
    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return EntityResolver._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]


# Singleton instance
_entity_resolver = None

def get_entity_resolver() -> EntityResolver:
    """Get the default entity resolver instance."""
    global _entity_resolver
    if _entity_resolver is None:
        _entity_resolver = EntityResolver()
    return _entity_resolver
