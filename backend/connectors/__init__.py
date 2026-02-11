"""
Connectors Package

Platform connector abstractions and implementations.
"""

from .base import BaseConnector, ConnectorResult, GovernanceClass
from .tool_spec import ToolSpec, ToolSpecParser
from .registry import ConnectorRegistry, get_registry

__all__ = [
    'BaseConnector',
    'ConnectorResult',
    'GovernanceClass',
    'ToolSpec',
    'ToolSpecParser',
    'ConnectorRegistry',
    'get_registry',
]
