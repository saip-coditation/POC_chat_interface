"""
Catalog Ingestion Service

Provides functionality to ingest and embed catalog data:
1. ToolSpec ingestion - Load YAML files into DB and Chroma
2. Platform introspection - Fetch tenant-specific entities
3. Glossary management - Business term mappings
"""

import os
import hashlib
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class CatalogIngestionService:
    """
    Service for ingesting metadata into the catalog and vector store.
    """
    
    def __init__(self, chroma_client=None, embeddings_client=None):
        """
        Initialize the ingestion service.
        
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
    
    def ingest_tool_specs(self, directory: str) -> Dict[str, Any]:
        """
        Ingest all ToolSpec YAML files from a directory.
        
        1. Parse YAML files
        2. Store metadata in database
        3. Generate embeddings
        4. Store in Chroma for semantic search
        
        Args:
            directory: Path to ToolSpec YAML files
        
        Returns:
            Summary of ingestion results
        """
        from connectors.tool_spec import ToolSpecParser
        from catalog.models import ToolSpecMetadata
        
        results = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "errors": []
        }
        
        if not os.path.exists(directory):
            logger.warning(f"ToolSpec directory not found: {directory}")
            return results
        
        # Get Chroma collection for tools
        chroma = self._get_chroma()
        collection = chroma.get_or_create_collection("tool_specs")
        embeddings = self._get_embeddings()
        
        # Process each YAML file
        for filename in os.listdir(directory):
            if not filename.endswith(('.yaml', '.yml')):
                continue
            
            filepath = os.path.join(directory, filename)
            
            try:
                # Calculate file hash for change detection
                with open(filepath, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                
                # Parse the spec
                spec = ToolSpecParser.parse_file(filepath)
                
                # Check if already exists
                existing = ToolSpecMetadata.objects.filter(tool_id=spec.tool_id).first()
                
                if existing and existing.file_hash == file_hash:
                    # No changes
                    results["processed"] += 1
                    continue
                
                # Create semantic description for embedding
                semantic_desc = f"""
                Platform: {spec.platform}
                Tool: {spec.tool_id}
                Category: {spec.category}
                Description: {spec.description}
                Example queries: {', '.join(spec.example_queries)}
                Parameters: {', '.join([p.name for p in spec.parameters])}
                """
                
                # Generate embedding
                embedding = embeddings.embed_for_storage(semantic_desc)
                
                # Store in Chroma
                embedding_id = f"tool_{spec.tool_id}"
                collection.add(
                    ids=[embedding_id],
                    embeddings=[embedding],
                    documents=[semantic_desc],
                    metadatas=[{
                        "tool_id": spec.tool_id,
                        "platform": spec.platform,
                        "category": spec.category,
                        "governance_class": spec.governance_class
                    }]
                )
                
                # Store/update in database
                if existing:
                    existing.version = spec.version
                    existing.file_hash = file_hash
                    existing.governance_class = spec.governance_class
                    existing.semantic_description = semantic_desc
                    existing.embedding_id = embedding_id
                    existing.save()
                    results["updated"] += 1
                else:
                    ToolSpecMetadata.objects.create(
                        tool_id=spec.tool_id,
                        platform=spec.platform,
                        version=spec.version,
                        file_hash=file_hash,
                        governance_class=spec.governance_class,
                        semantic_description=semantic_desc,
                        embedding_id=embedding_id
                    )
                    results["created"] += 1
                
                results["processed"] += 1
                logger.info(f"Ingested ToolSpec: {spec.tool_id}")
                
            except Exception as e:
                logger.error(f"Error ingesting {filepath}: {e}")
                results["errors"].append({"file": filename, "error": str(e)})
        
        return results
    
    def ingest_tenant_entities(
        self, 
        user, 
        platform: str, 
        entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ingest tenant-specific entities from a connected platform.
        
        Args:
            user: Django user instance
            platform: Platform identifier
            entities: List of entity dicts with at least:
                - entity_type: Type of entity (e.g., "product", "customer")
                - external_id: ID in the source system
                - display_name: Human-readable name
                - metadata: Additional metadata (optional)
        
        Returns:
            Summary of ingestion results
        """
        from catalog.models import TenantCatalog
        
        results = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "errors": []
        }
        
        chroma = self._get_chroma()
        collection = chroma.get_or_create_collection("tenant_catalog")
        embeddings = self._get_embeddings()
        
        for entity in entities:
            try:
                entity_type = entity.get("entity_type")
                external_id = entity.get("external_id")
                display_name = entity.get("display_name")
                
                if not all([entity_type, external_id, display_name]):
                    results["errors"].append({
                        "entity": entity,
                        "error": "Missing required fields"
                    })
                    continue
                
                # Check for existing entry
                existing = TenantCatalog.objects.filter(
                    user=user,
                    platform=platform,
                    external_id=external_id
                ).first()
                
                # Create semantic description for embedding
                synonyms = entity.get("synonyms", [])
                metadata = entity.get("metadata", {})
                
                semantic_desc = f"""
                {platform} {entity_type}: {display_name}
                Synonyms: {', '.join(synonyms) if synonyms else 'none'}
                """
                
                # Generate embedding
                embedding = embeddings.embed_for_storage(semantic_desc)
                
                # Create embedding ID
                embedding_id = f"tenant_{user.id}_{platform}_{external_id}"
                
                # Store in Chroma
                collection.add(
                    ids=[embedding_id],
                    embeddings=[embedding],
                    documents=[semantic_desc],
                    metadatas=[{
                        "user_id": str(user.id),
                        "platform": platform,
                        "entity_type": entity_type,
                        "external_id": external_id,
                        "display_name": display_name
                    }]
                )
                
                # Store/update in database
                if existing:
                    existing.display_name = display_name
                    existing.synonyms = synonyms
                    existing.metadata = metadata
                    existing.embedding_id = embedding_id
                    existing.version += 1
                    existing.save()
                    results["updated"] += 1
                else:
                    TenantCatalog.objects.create(
                        user=user,
                        platform=platform,
                        entity_type=entity_type,
                        external_id=external_id,
                        display_name=display_name,
                        synonyms=synonyms,
                        metadata=metadata,
                        embedding_id=embedding_id
                    )
                    results["created"] += 1
                
                results["processed"] += 1
                
            except Exception as e:
                logger.error(f"Error ingesting entity: {e}")
                results["errors"].append({"entity": entity, "error": str(e)})
        
        return results
    
    def add_glossary_term(
        self,
        term: str,
        canonical_term: str,
        user=None,
        platform: str = None,
        category: str = "",
        description: str = ""
    ) -> bool:
        """
        Add a term to the business glossary.
        
        Args:
            term: The user-facing term (e.g., "earnings")
            canonical_term: What it maps to (e.g., "revenue")
            user: Optional user for tenant-specific terms
            platform: Optional platform scope
            category: Optional category
            description: Optional description
        
        Returns:
            True if created/updated successfully
        """
        from catalog.models import BusinessGlossary
        
        try:
            obj, created = BusinessGlossary.objects.update_or_create(
                user=user,
                term=term.lower(),
                platform=platform,
                defaults={
                    "canonical_term": canonical_term,
                    "category": category,
                    "description": description
                }
            )
            
            # Also embed in Chroma for semantic matching
            chroma = self._get_chroma()
            collection = chroma.get_or_create_collection("glossary")
            embeddings = self._get_embeddings()
            
            semantic_desc = f"{term} means {canonical_term}. {description}"
            embedding = embeddings.embed_for_storage(semantic_desc)
            
            embedding_id = f"glossary_{obj.id}"
            collection.add(
                ids=[embedding_id],
                embeddings=[embedding],
                documents=[semantic_desc],
                metadatas=[{
                    "term": term,
                    "canonical_term": canonical_term,
                    "platform": platform or ""
                }]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding glossary term: {e}")
            return False
    
    def seed_default_glossary(self) -> int:
        """
        Seed the glossary with common business term mappings.
        
        Returns:
            Number of terms added
        """
        default_terms = [
            # Revenue/Money
            ("earnings", "revenue", "finance", "Total income from sales"),
            ("income", "revenue", "finance", "Total income from sales"),
            ("sales", "revenue", "finance", "Total income from sales"),
            ("cash", "revenue", "finance", "Money received"),
            
            # Customers
            ("clients", "customers", "crm", "People who buy from you"),
            ("users", "customers", "crm", "People using your product"),
            ("accounts", "customers", "crm", "Customer accounts"),
            ("contacts", "customers", "crm", "Customer contacts"),
            
            # Products
            ("services", "products", "catalog", "Things you sell"),
            ("offerings", "products", "catalog", "Things you sell"),
            ("plans", "subscriptions", "billing", "Recurring product plans"),
            ("subscriptions", "subscriptions", "billing", "Recurring charges"),
            
            # Support
            ("issues", "tickets", "support", "Support requests"),
            ("cases", "tickets", "support", "Support requests"),
            ("requests", "tickets", "support", "Support requests"),
            
            # Time
            ("today", "last_1_day", "time", "Current day"),
            ("yesterday", "last_2_days", "time", "Previous day"),
            ("this week", "last_7_days", "time", "Current week"),
            ("this month", "last_30_days", "time", "Current month"),
            ("this year", "last_365_days", "time", "Current year"),
        ]
        
        count = 0
        for term, canonical, category, description in default_terms:
            if self.add_glossary_term(term, canonical, category=category, description=description):
                count += 1
        
        logger.info(f"Seeded {count} glossary terms")
        return count

    def ingest_document(
        self,
        title: str,
        content: str,
        platform: str = "",
        user=None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> Dict[str, Any]:
        """
        Ingest an unstructured document for RAG.
        
        1. Create Document record
        2. Split content into overlapping chunks
        3. Generate embeddings
        4. Store in Chroma and DB
        """
        from catalog.models import Document, DocumentChunk
        
        results = {
            "title": title,
            "chunks": 0,
            "status": "success",
            "error": None
        }
        
        try:
            # Create/Update Document
            # We use title + user as unique key effectively
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            
            doc_qs = Document.objects.filter(title=title)
            if user:
                doc_qs = doc_qs.filter(user=user)
            else:
                doc_qs = doc_qs.filter(user__isnull=True)
                
            doc = doc_qs.first()
            
            if doc:
                if doc.file_hash == file_hash:
                    logger.info(f"Document '{title}' unchanged. Skipping.")
                    return results
                
                # Update existing
                doc.file_hash = file_hash
                doc.platform = platform
                doc.save()
                # Clear old chunks
                doc.chunks.all().delete()
            else:
                # Create new
                doc = Document.objects.create(
                    title=title,
                    user=user,
                    platform=platform,
                    file_hash=file_hash
                )
            
            # Simple chunking logic
            chunks = []
            start = 0
            if not content:
                return results

            while start < len(content):
                end = min(start + chunk_size, len(content))
                chunk_text = content[start:end]
                chunks.append(chunk_text)
                if end == len(content):
                    break
                start += (chunk_size - chunk_overlap)
            
            # Prepare for Chroma
            chroma = self._get_chroma()
            collection = chroma.get_or_create_collection("documents")
            embeddings = self._get_embeddings()
            
            # Generate embeddings batch
            vectors = embeddings.embed_batch(chunks)
            
            # Store chunks
            ids = []
            metadatas = []
            
            for i, chunk_text in enumerate(chunks):
                chunk_obj = DocumentChunk.objects.create(
                    document=doc,
                    chunk_index=i,
                    content=chunk_text,
                    embedding_id=f"doc_{doc.id}_chunk_{i}"
                )
                
                ids.append(chunk_obj.embedding_id)
                metadatas.append({
                    "document_id": str(doc.id),
                    "title": title,
                    "platform": platform,
                    "chunk_index": i,
                    "user_id": str(user.id) if user else ""
                })
            
            # Add to Chroma
            if ids:
                collection.add(
                    ids=ids,
                    embeddings=vectors,
                    documents=chunks,
                    metadatas=metadatas
                )
                
            results["chunks"] = len(chunks)
            logger.info(f"Ingested document '{title}' with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error ingesting document: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            
        return results


# Singleton instance
_ingestion_service = None

def get_ingestion_service() -> CatalogIngestionService:
    """Get the default ingestion service instance."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = CatalogIngestionService()
    return _ingestion_service
