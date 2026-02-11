"""
Base Connector

Abstract base class that all platform connectors must inherit from.
Provides a consistent interface for the Execution Engine.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GovernanceClass(Enum):
    """Classification of actions for governance purposes."""
    READ = "READ"           # Data retrieval - auto-approve
    WRITE = "WRITE"         # Create/Update - requires logging
    MONEY_MOVE = "MONEY_MOVE"  # Financial transactions - requires approval


@dataclass
class ConnectorResult:
    """
    Standard result object returned by all connectors.
    """
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Pagination info
    has_more: bool = False
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "data": self.data,
        }
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        if self.has_more:
            result["has_more"] = self.has_more
            result["next_cursor"] = self.next_cursor
        if self.total_count is not None:
            result["total_count"] = self.total_count
        return result


class BaseConnector(ABC):
    """
    Abstract base class for all platform connectors.
    
    Each connector wraps a single external platform (Stripe, Salesforce, etc.)
    and provides a standardized interface for execution.
    """
    
    # Override in subclasses
    PLATFORM_NAME: str = "base"
    PLATFORM_DISPLAY_NAME: str = "Base Platform"
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize the connector with credentials.
        
        Args:
            credentials: Platform-specific credentials (API keys, tokens, etc.)
        """
        self.credentials = credentials
        self._client = None
    
    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Validate that the provided credentials are valid.
        
        Returns:
            True if credentials are valid, False otherwise.
        """
        pass
    
    @abstractmethod
    def execute(
        self, 
        tool_id: str, 
        params: Dict[str, Any]
    ) -> ConnectorResult:
        """
        Execute a tool action.
        
        Args:
            tool_id: The tool identifier (e.g., "list_invoices", "get_customer")
            params: Parameters for the tool
        
        Returns:
            ConnectorResult with the execution result
        """
        pass
    
    @abstractmethod
    def get_supported_tools(self) -> List[str]:
        """
        Return list of tool IDs this connector supports.
        
        Returns:
            List of tool identifiers
        """
        pass
    
    def get_governance_class(self, tool_id: str) -> GovernanceClass:
        """
        Get the governance class for a specific tool.
        
        Override in subclasses for more specific classification.
        Default implementation returns READ for all tools.
        
        Args:
            tool_id: The tool identifier
        
        Returns:
            GovernanceClass enum value
        """
        return GovernanceClass.READ
    
    def normalize_response(self, data: Any) -> Any:
        """
        Normalize platform-specific response to a standard format.
        
        Override in subclasses to transform platform data.
        
        Args:
            data: Raw response from the platform
        
        Returns:
            Normalized data structure
        """
        return data
    
    def handle_pagination(
        self, 
        tool_id: str, 
        params: Dict[str, Any],
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle pagination for list operations.
        
        Override in subclasses to implement platform-specific pagination.
        
        Args:
            tool_id: The tool identifier
            params: Original parameters
            cursor: Pagination cursor from previous response
        
        Returns:
            Updated params with pagination info
        """
        if cursor:
            params['cursor'] = cursor
        return params
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.PLATFORM_NAME})>"
