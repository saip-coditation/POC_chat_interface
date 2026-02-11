"""
Workflow Definition Models

Defines the structure of config-driven workflows.
Workflows are loaded from YAML files and executed by the WorkflowExecutor.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Types of workflow steps."""
    TOOL = "tool"           # Execute a tool/API call
    TRANSFORM = "transform" # Transform/filter data
    AGGREGATE = "aggregate" # Aggregate data from multiple sources
    CONDITION = "condition" # Conditional branching
    PARALLEL = "parallel"   # Execute steps in parallel


class OutputFormat(Enum):
    """Supported output formats."""
    TABLE = "table"
    LIST = "list"
    SINGLE = "single"
    UNIFIED_VIEW = "unified_view"
    CHART = "chart"


@dataclass
class WorkflowInput:
    """Definition of a workflow input parameter."""
    name: str
    type: str  # string, integer, date, date_range, entity:<type>
    required: bool = False
    default: Any = None
    description: str = ""


@dataclass
class WorkflowStep:
    """Definition of a single workflow step."""
    id: str
    step_type: StepType = StepType.TOOL
    tool_id: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    
    # Transform-specific
    operation: Optional[str] = None  # filter, map, merge, join
    condition: Optional[str] = None
    
    # Aggregate-specific
    group_by: Optional[str] = None
    metrics: List[Dict] = field(default_factory=list)
    
    def can_run_parallel(self) -> bool:
        """Check if this step can run in parallel with others."""
        return len(self.depends_on) == 0


@dataclass
class WorkflowOutput:
    """Definition of workflow output."""
    format: OutputFormat = OutputFormat.TABLE
    columns: List[str] = field(default_factory=list)
    summary_template: str = ""
    sections: List[Dict] = field(default_factory=list)


@dataclass
class WorkflowDefinition:
    """
    Complete workflow definition.
    
    Loaded from YAML and executed by WorkflowExecutor.
    """
    workflow_id: str
    version: str = "1.0.0"
    name: str = ""
    description: str = ""
    
    inputs: List[WorkflowInput] = field(default_factory=list)
    steps: List[WorkflowStep] = field(default_factory=list)
    output: WorkflowOutput = None
    
    # Governance
    governance_class: str = "READ"
    approval_required: bool = False
    
    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_required_inputs(self) -> List[WorkflowInput]:
        """Get required input parameters."""
        return [i for i in self.inputs if i.required]
    
    def validate_inputs(self, provided: Dict[str, Any]) -> List[str]:
        """Validate provided inputs against required."""
        errors = []
        for input_def in self.get_required_inputs():
            if input_def.name not in provided:
                errors.append(f"Missing required input: {input_def.name}")
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "governance_class": self.governance_class
        }


class WorkflowParser:
    """
    Parser for YAML workflow definitions.
    """
    
    @staticmethod
    def parse_file(filepath: str) -> WorkflowDefinition:
        """Parse a YAML file into a WorkflowDefinition."""
        import yaml
        
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        
        return WorkflowParser.parse_dict(data)
    
    @staticmethod
    def parse_dict(data: Dict[str, Any]) -> WorkflowDefinition:
        """Parse a dictionary into a WorkflowDefinition."""
        
        # Parse inputs
        inputs = []
        for inp in data.get('inputs', []):
            inputs.append(WorkflowInput(
                name=inp.get('name'),
                type=inp.get('type', 'string'),
                required=inp.get('required', False),
                default=inp.get('default'),
                description=inp.get('description', '')
            ))
        
        # Parse steps
        steps = []
        for step in data.get('steps', []):
            step_type = StepType(step.get('type', 'tool'))
            
            steps.append(WorkflowStep(
                id=step.get('id'),
                step_type=step_type,
                tool_id=step.get('tool'),
                params=step.get('params', {}),
                depends_on=step.get('depends_on', []),
                operation=step.get('operation'),
                condition=step.get('condition'),
                group_by=step.get('group_by'),
                metrics=step.get('metrics', [])
            ))
        
        # Parse output
        output_data = data.get('output', {})
        output = WorkflowOutput(
            format=OutputFormat(output_data.get('format', 'table')),
            columns=output_data.get('columns', []),
            summary_template=output_data.get('summary_template', ''),
            sections=output_data.get('sections', [])
        )
        
        # Parse governance
        gov_data = data.get('governance', {})
        
        return WorkflowDefinition(
            workflow_id=data.get('workflow_id'),
            version=data.get('version', '1.0.0'),
            name=data.get('name', data.get('workflow_id', '')),
            description=data.get('description', ''),
            inputs=inputs,
            steps=steps,
            output=output,
            governance_class=gov_data.get('class', 'READ'),
            approval_required=gov_data.get('approval_required', False)
        )
