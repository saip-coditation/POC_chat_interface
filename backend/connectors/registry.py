"""
Connector Registry

Central registry for discovering and loading platform connectors.
Provides a single entry point for the Execution Engine.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Type

from .base import BaseConnector, ConnectorResult
from .tool_spec import ToolSpec, ToolSpecParser

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """
    Central registry for all platform connectors.
    
    The registry:
    1. Discovers and loads connector classes
    2. Loads ToolSpecs from YAML files
    3. Provides a unified interface for tool execution
    
    Usage:
        registry = ConnectorRegistry()
        registry.register_connector("stripe", StripeConnector)
        registry.load_tool_specs("tool_specs/stripe")
        
        result = registry.execute(
            platform="stripe",
            tool_id="list_invoices",
            params={"status": "paid"},
            credentials={"api_key": "sk_..."}
        )
    """
    
    def __init__(self):
        """Initialize the registry."""
        self._connectors: Dict[str, Type[BaseConnector]] = {}
        self._tool_specs: Dict[str, Dict[str, ToolSpec]] = {}  # platform -> {tool_id -> spec}
        self._instances: Dict[str, BaseConnector] = {}  # Cache for instantiated connectors
    
    def register_connector(
        self, 
        platform: str, 
        connector_class: Type[BaseConnector]
    ):
        """
        Register a connector class for a platform.
        
        Args:
            platform: Platform identifier (e.g., "stripe", "salesforce")
            connector_class: The connector class (not instance)
        """
        self._connectors[platform.lower()] = connector_class
        logger.info(f"Registered connector: {platform}")
    
    def load_tool_specs(self, directory: str, platform: str = None):
        """
        Load ToolSpecs from a directory.
        
        Args:
            directory: Path to ToolSpec YAML files
            platform: Optional platform name (inferred from specs if not provided)
        """
        specs = ToolSpecParser.load_directory(directory)
        
        for tool_id, spec in specs.items():
            plat = platform or spec.platform
            if plat not in self._tool_specs:
                self._tool_specs[plat] = {}
            self._tool_specs[plat][tool_id] = spec
        
        logger.info(f"Loaded {len(specs)} ToolSpecs from {directory}")
    
    def get_connector(
        self, 
        platform: str, 
        credentials: Dict[str, Any]
    ) -> Optional[BaseConnector]:
        """
        Get or create a connector instance for a platform.
        
        Args:
            platform: Platform identifier
            credentials: Platform credentials
        
        Returns:
            Connector instance or None if not registered
        """
        platform = platform.lower()
        
        if platform not in self._connectors:
            logger.error(f"No connector registered for platform: {platform}")
            return None
        
        # Create cache key from platform + credentials hash
        creds_hash = hash(frozenset(credentials.items()))
        cache_key = f"{platform}:{creds_hash}"
        
        if cache_key not in self._instances:
            connector_class = self._connectors[platform]
            self._instances[cache_key] = connector_class(credentials)
        
        return self._instances[cache_key]
    
    def get_tool_spec(self, platform: str, tool_id: str) -> Optional[ToolSpec]:
        """
        Get a ToolSpec by platform and tool ID.
        
        Args:
            platform: Platform identifier
            tool_id: Tool identifier
        
        Returns:
            ToolSpec or None if not found
        """
        platform = platform.lower()
        
        if platform not in self._tool_specs:
            return None
        
        return self._tool_specs[platform].get(tool_id)
    
    def execute(
        self,
        platform: str,
        tool_id: str,
        params: Dict[str, Any],
        credentials: Dict[str, Any]
    ) -> ConnectorResult:
        """
        Execute a tool action.
        
        Args:
            platform: Platform identifier
            tool_id: Tool identifier
            params: Tool parameters
            credentials: Platform credentials
        
        Returns:
            ConnectorResult with execution result
        """
        # Get the ToolSpec
        spec = self.get_tool_spec(platform, tool_id)
        if spec:
            # Validate parameters against spec
            errors = spec.validate_params(params)
            if errors:
                return ConnectorResult(
                    success=False,
                    error=f"Parameter validation failed: {', '.join(errors)}"
                )
        
        # Get the connector
        connector = self.get_connector(platform, credentials)
        if not connector:
            return ConnectorResult(
                success=False,
                error=f"No connector available for platform: {platform}"
            )
        
        # Execute
        try:
            return connector.execute(tool_id, params)
        except Exception as e:
            logger.exception(f"Execution failed for {platform}.{tool_id}")
            return ConnectorResult(
                success=False,
                error=str(e)
            )
    
    def list_platforms(self) -> List[str]:
        """Return list of registered platforms."""
        return list(self._connectors.keys())
    
    def list_tools(self, platform: str) -> List[str]:
        """Return list of tools for a platform."""
        platform = platform.lower()
        if platform not in self._tool_specs:
            return []
        return list(self._tool_specs[platform].keys())
    
    def get_all_tool_specs(self) -> Dict[str, Dict[str, ToolSpec]]:
        """Return all loaded ToolSpecs."""
        return self._tool_specs


# Global registry instance
_registry = None

def get_registry() -> ConnectorRegistry:
    """Get the global connector registry."""
    global _registry
    if _registry is None:
        _registry = ConnectorRegistry()
    return _registry
