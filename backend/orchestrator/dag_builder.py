"""
DAG Builder

Builds a directed acyclic graph (DAG) from workflow steps
for dependency resolution and parallel execution.
"""

import logging
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass
from collections import defaultdict

from .workflow_definition import WorkflowDefinition, WorkflowStep

logger = logging.getLogger(__name__)


@dataclass
class DAGNode:
    """A node in the workflow DAG."""
    step: WorkflowStep
    dependencies: Set[str]
    dependents: Set[str]
    
    @property
    def id(self) -> str:
        return self.step.id
    
    def is_ready(self, completed: Set[str]) -> bool:
        """Check if all dependencies are completed."""
        return self.dependencies.issubset(completed)


class WorkflowDAG:
    """
    Directed Acyclic Graph representation of a workflow.
    
    Enables:
    - Dependency resolution
    - Parallel execution of independent steps
    - Topological ordering
    """
    
    def __init__(self, workflow: WorkflowDefinition):
        """
        Build DAG from workflow definition.
        
        Args:
            workflow: The workflow to build DAG from
        """
        self.workflow = workflow
        self.nodes: Dict[str, DAGNode] = {}
        self._build()
    
    def _build(self):
        """Build the DAG from workflow steps."""
        # Create nodes
        for step in self.workflow.steps:
            self.nodes[step.id] = DAGNode(
                step=step,
                dependencies=set(step.depends_on),
                dependents=set()
            )
        
        # Link dependents
        for node_id, node in self.nodes.items():
            for dep_id in node.dependencies:
                if dep_id in self.nodes:
                    self.nodes[dep_id].dependents.add(node_id)
        
        # Validate no cycles
        if not self._validate_acyclic():
            raise ValueError("Workflow contains circular dependencies")
    
    def _validate_acyclic(self) -> bool:
        """Validate that the graph has no cycles using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node_id: WHITE for node_id in self.nodes}
        
        def dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            for dep_id in self.nodes[node_id].dependents:
                if color[dep_id] == GRAY:
                    return False  # Back edge = cycle
                if color[dep_id] == WHITE and not dfs(dep_id):
                    return False
            color[node_id] = BLACK
            return True
        
        for node_id in self.nodes:
            if color[node_id] == WHITE:
                if not dfs(node_id):
                    return False
        return True
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get execution order as layers of parallel steps.
        
        Returns:
            List of lists where each inner list contains step IDs
            that can be executed in parallel.
        """
        layers = []
        completed = set()
        remaining = set(self.nodes.keys())
        
        while remaining:
            # Find all steps that can run now
            ready = [
                node_id for node_id in remaining
                if self.nodes[node_id].is_ready(completed)
            ]
            
            if not ready:
                # Should never happen if graph is acyclic
                raise ValueError("Cannot resolve remaining dependencies")
            
            layers.append(ready)
            completed.update(ready)
            remaining.difference_update(ready)
        
        return layers
    
    def get_entry_steps(self) -> List[str]:
        """Get steps with no dependencies (entry points)."""
        return [
            node_id for node_id, node in self.nodes.items()
            if not node.dependencies
        ]
    
    def get_exit_steps(self) -> List[str]:
        """Get steps with no dependents (exit points)."""
        return [
            node_id for node_id, node in self.nodes.items()
            if not node.dependents
        ]
    
    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get a step by ID."""
        if step_id in self.nodes:
            return self.nodes[step_id].step
        return None
    
    def get_dependencies(self, step_id: str) -> List[str]:
        """Get dependencies of a step."""
        if step_id in self.nodes:
            return list(self.nodes[step_id].dependencies)
        return []
    
    def get_dependents(self, step_id: str) -> List[str]:
        """Get steps that depend on this step."""
        if step_id in self.nodes:
            return list(self.nodes[step_id].dependents)
        return []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DAG to dictionary for visualization."""
        return {
            "workflow_id": self.workflow.workflow_id,
            "nodes": [
                {
                    "id": node_id,
                    "dependencies": list(node.dependencies),
                    "dependents": list(node.dependents),
                    "tool_id": node.step.tool_id
                }
                for node_id, node in self.nodes.items()
            ],
            "execution_order": self.get_execution_order()
        }
