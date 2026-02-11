"""
Catalog Package

Models and services for platform metadata management.
"""

from .services import CatalogIngestionService, get_ingestion_service

__all__ = [
    'CatalogIngestionService',
    'get_ingestion_service',
]
