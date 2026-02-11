"""
Catalog Models

Defines the database models for:
1. Platform Ontology - Canonical entity definitions per platform
2. Tenant Catalog - Tenant-specific entities and metadata
3. Business Glossary - Synonyms and term mappings
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField

User = get_user_model()


class PlatformOntology(models.Model):
    """
    Canonical entity definitions for each platform.
    
    This defines the "shape" of data for each platform (e.g., what fields
    exist on a Stripe Invoice, what a Salesforce Contact looks like).
    
    These are system-wide and not tenant-specific.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Platform identification
    platform = models.CharField(max_length=50, db_index=True)
    entity_type = models.CharField(max_length=100, db_index=True)
    canonical_name = models.CharField(max_length=200)
    
    # Description for semantic search
    description = models.TextField(blank=True)
    
    # Hierarchical relationships
    parent_entity = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='children'
    )
    
    # Schema definition (fields, types, etc.)
    properties = models.JSONField(default=dict, blank=True)
    
    # Versioning
    version = models.PositiveIntegerField(default=1)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'platform_ontology'
        unique_together = [['platform', 'entity_type', 'version']]
        ordering = ['platform', 'entity_type']
        verbose_name_plural = 'Platform Ontologies'
    
    def __str__(self):
        return f"{self.platform}.{self.entity_type} (v{self.version})"


class TenantCatalog(models.Model):
    """
    Tenant-specific entities and metadata.
    
    When a user connects a platform, we introspect their account
    and store their specific entities (products, customers, etc.)
    for entity resolution.
    
    Example: Stripe products like "Pro Plan", "Enterprise License"
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Tenant/User association
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='catalog_items')
    
    # Platform and entity type
    platform = models.CharField(max_length=50, db_index=True)
    entity_type = models.CharField(max_length=100, db_index=True)
    
    # External reference
    external_id = models.CharField(max_length=200, db_index=True)
    
    # Display information
    display_name = models.CharField(max_length=500)
    
    # Synonyms for entity resolution (stored as JSON array for SQLite compatibility)
    synonyms = models.JSONField(default=list, blank=True)
    
    # Additional metadata from the source system
    metadata = models.JSONField(default=dict, blank=True)
    
    # Vector embedding ID for Chroma lookup
    embedding_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Versioning
    version = models.PositiveIntegerField(default=1)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenant_catalog'
        indexes = [
            models.Index(fields=['user', 'platform']),
            models.Index(fields=['platform', 'entity_type']),
            models.Index(fields=['external_id']),
        ]
        ordering = ['platform', 'entity_type', 'display_name']
    
    def __str__(self):
        return f"{self.platform}.{self.entity_type}: {self.display_name}"


class BusinessGlossary(models.Model):
    """
    Business terms and their mappings to entities.
    
    Allows mapping user-friendly terms to canonical entities.
    Example: "earnings" -> "revenue", "clients" -> "customers"
    
    Can be system-wide or tenant-specific.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Optional user association (null = system-wide)
    user = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        related_name='glossary_terms'
    )
    
    # The term as users might say it
    term = models.CharField(max_length=200, db_index=True)
    
    # What it maps to
    canonical_term = models.CharField(max_length=200)
    
    # Optional platform scope
    platform = models.CharField(max_length=50, blank=True, null=True)
    
    # Context/category
    category = models.CharField(max_length=100, blank=True)
    
    # Description for clarity
    description = models.TextField(blank=True)
    
    # Is this an exact match or fuzzy?
    is_exact_match = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'business_glossary'
        unique_together = [['user', 'term', 'platform']]
        ordering = ['term']
        verbose_name_plural = 'Business Glossary'
    
    def __str__(self):
        scope = f"[{self.platform}]" if self.platform else "[global]"
        return f"{scope} {self.term} -> {self.canonical_term}"


class ToolSpecMetadata(models.Model):
    """
    Metadata about loaded ToolSpecs for tracking and versioning.
    
    Stores information about which ToolSpec YAML files have been loaded
    and their versions for diffing/updates.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Tool identification
    tool_id = models.CharField(max_length=200, unique=True)
    platform = models.CharField(max_length=50, db_index=True)
    
    # Version tracking
    version = models.CharField(max_length=20)
    file_hash = models.CharField(max_length=64)  # SHA-256 of YAML file
    
    # Governance classification
    governance_class = models.CharField(
        max_length=20,
        choices=[
            ('READ', 'Read'),
            ('WRITE', 'Write'),
            ('MONEY_MOVE', 'Money Move'),
        ],
        default='READ'
    )
    
    # Semantic description for RAG
    semantic_description = models.TextField(blank=True)
    
    # Vector embedding ID
    embedding_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    loaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tool_spec_metadata'
        ordering = ['platform', 'tool_id']
    
    def __str__(self):
        return f"{self.tool_id} v{self.version}"


class Document(models.Model):
    """
    Unstructured documents (policies, manuals, etc.) for RAG.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Metadata
    title = models.CharField(max_length=500)
    platform = models.CharField(max_length=50, blank=True)
    
    # Ownership
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    
    # Content tracking
    file_hash = models.CharField(max_length=64, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    """
    Chunks of text from a Document, with embeddings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.PositiveIntegerField()
    
    # The actual text content
    content = models.TextField()
    
    # Reference to Chroma embedding
    embedding_id = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['chunk_index']
        unique_together = [['document', 'chunk_index']]
    
    def __str__(self):
        return f"{self.document.title} - Chunk {self.chunk_index}"
