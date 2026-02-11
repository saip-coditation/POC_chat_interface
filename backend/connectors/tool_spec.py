"""
ToolSpec Parser

Parses YAML-based tool specifications into executable objects.
ToolSpecs define how to call external APIs in a platform-agnostic way.
"""

import os
import yaml
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ParameterType(Enum):
    """Supported parameter types for ToolSpec parameters."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    DATE = "date"
    DATETIME = "datetime"
    ARRAY = "array"
    OBJECT = "object"


class PaginationStrategy(Enum):
    """Supported pagination strategies."""
    NONE = "none"
    CURSOR = "cursor"
    OFFSET = "offset"
    PAGE = "page"


@dataclass
class ToolParameter:
    """Definition of a single tool parameter."""
    name: str
    type: ParameterType
    required: bool = False
    default: Any = None
    description: str = ""
    enum_values: List[str] = field(default_factory=list)
    entity_type: Optional[str] = None  # For entity resolution


@dataclass
class ToolEndpoint:
    """HTTP endpoint definition."""
    method: str  # GET, POST, PUT, DELETE, PATCH
    path: str
    content_type: str = "application/json"


@dataclass
class ToolPagination:
    """Pagination configuration."""
    strategy: PaginationStrategy = PaginationStrategy.NONE
    cursor_param: str = ""
    limit_param: str = "limit"
    offset_param: str = "offset"
    max_limit: int = 100
    default_limit: int = 50


@dataclass
class ToolResponse:
    """Response parsing configuration."""
    data_path: str = "data"  # Path to data in response JSON
    entity_mapping: Dict[str, str] = field(default_factory=dict)


@dataclass
class ToolSpec:
    """
    Complete specification for a single tool/action.
    
    ToolSpecs are loaded from YAML files and define:
    - How to call the API (endpoint, parameters)
    - How to parse the response
    - Governance classification
    - Entity mappings for resolution
    """
    tool_id: str
    version: str
    platform: str
    category: str  # DATA_QUERY, DATA_WRITE, MONEY_MOVE
    governance_class: str  # READ, WRITE, MONEY_MOVE
    description: str = ""
    
    endpoint: ToolEndpoint = None
    parameters: List[ToolParameter] = field(default_factory=list)
    pagination: ToolPagination = None
    response: ToolResponse = None
    
    # For semantic search
    semantic_description: str = ""
    example_queries: List[str] = field(default_factory=list)
    
    def get_required_params(self) -> List[ToolParameter]:
        """Return list of required parameters."""
        return [p for p in self.parameters if p.required]
    
    def get_optional_params(self) -> List[ToolParameter]:
        """Return list of optional parameters."""
        return [p for p in self.parameters if not p.required]
    
    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """
        Validate provided parameters against the spec.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check required params
        for param in self.get_required_params():
            if param.name not in params:
                errors.append(f"Missing required parameter: {param.name}")
        
        # Validate enum values
        for param in self.parameters:
            if param.name in params and param.type == ParameterType.ENUM:
                if params[param.name] not in param.enum_values:
                    errors.append(
                        f"Invalid value for {param.name}. "
                        f"Must be one of: {param.enum_values}"
                    )
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_id": self.tool_id,
            "version": self.version,
            "platform": self.platform,
            "category": self.category,
            "governance_class": self.governance_class,
            "description": self.description,
            "parameters": [
                {"name": p.name, "type": p.type.value, "required": p.required}
                for p in self.parameters
            ]
        }


class ToolSpecParser:
    """
    Parser for YAML ToolSpec files.
    """
    
    @staticmethod
    def parse_file(filepath: str) -> ToolSpec:
        """
        Parse a single YAML file into a ToolSpec.
        
        Args:
            filepath: Path to the YAML file
        
        Returns:
            ToolSpec object
        """
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        
        return ToolSpecParser.parse_dict(data)
    
    @staticmethod
    def parse_dict(data: Dict[str, Any]) -> ToolSpec:
        """
        Parse a dictionary into a ToolSpec.
        
        Args:
            data: Dictionary from parsed YAML
        
        Returns:
            ToolSpec object
        """
        # Parse endpoint
        endpoint = None
        if 'endpoint' in data:
            ep = data['endpoint']
            endpoint = ToolEndpoint(
                method=ep.get('method', 'GET'),
                path=ep.get('path', ''),
                content_type=ep.get('content_type', 'application/json')
            )
        
        # Parse parameters
        parameters = []
        for param_data in data.get('parameters', []):
            param = ToolParameter(
                name=param_data.get('name'),
                type=ParameterType(param_data.get('type', 'string')),
                required=param_data.get('required', False),
                default=param_data.get('default'),
                description=param_data.get('description', ''),
                enum_values=param_data.get('values', []),
                entity_type=param_data.get('entity_type')
            )
            parameters.append(param)
        
        # Parse pagination
        pagination = None
        if 'pagination' in data:
            pag = data['pagination']
            pagination = ToolPagination(
                strategy=PaginationStrategy(pag.get('strategy', 'none')),
                cursor_param=pag.get('cursor_param', ''),
                limit_param=pag.get('limit_param', 'limit'),
                offset_param=pag.get('offset_param', 'offset'),
                max_limit=pag.get('max_limit', 100),
                default_limit=pag.get('default_limit', 50)
            )
        
        # Parse response config
        response = None
        if 'response' in data:
            resp = data['response']
            response = ToolResponse(
                data_path=resp.get('data_path', 'data'),
                entity_mapping=resp.get('entity_mapping', {})
            )
        
        return ToolSpec(
            tool_id=data.get('tool_id'),
            version=data.get('version', '1.0.0'),
            platform=data.get('platform'),
            category=data.get('category', 'DATA_QUERY'),
            governance_class=data.get('governance_class', 'READ'),
            description=data.get('description', ''),
            endpoint=endpoint,
            parameters=parameters,
            pagination=pagination,
            response=response,
            semantic_description=data.get('semantic_description', ''),
            example_queries=data.get('example_queries', [])
        )
    
        return specs
    
    @staticmethod
    def load_directory(directory: str) -> Dict[str, ToolSpec]:
        """
        Load all ToolSpecs from a directory.
        
        Args:
            directory: Path to directory containing YAML files
        
        Returns:
            Dictionary mapping tool_id to ToolSpec
        """
        specs = {}
        
        if not os.path.exists(directory):
            logger.warning(f"ToolSpec directory not found: {directory}")
            return specs
        
        for filename in os.listdir(directory):
            if filename.endswith(('.yaml', '.yml')):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = yaml.safe_load(f)
                    
                    if isinstance(data, list):
                        # Handle list of specs
                        for item in data:
                            spec = ToolSpecParser.parse_dict(item)
                            specs[spec.tool_id] = spec
                            logger.info(f"Loaded ToolSpec: {spec.tool_id}")
                    elif isinstance(data, dict):
                        # Handle single spec
                        spec = ToolSpecParser.parse_dict(data)
                        specs[spec.tool_id] = spec
                        logger.info(f"Loaded ToolSpec: {spec.tool_id}")
                    else:
                        logger.warning(f"Skipping {filename}: Invalid YAML structure (must be dict or list)")
                        
                except Exception as e:
                    logger.error(f"Failed to parse {filepath}: {e}")
        
        return specs
