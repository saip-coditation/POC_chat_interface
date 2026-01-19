from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BasePlatformService(ABC):
    """
    Abstract base class for all platform services.
    Any new platform (e.g. Salesforce, HubSpot) must inherit from this.
    """
    
    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Unique identifier for the platform (e.g. 'stripe', 'zendesk')"""
        pass

    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate credentials and establish a connection.
        Returns True if successful, raises Exception otherwise.
        """
        pass

    @abstractmethod
    def process_query(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a natural language query against this platform.
        Returns a dictionary with result summary and raw data.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the platform connection (e.g. account name)"""
        pass
