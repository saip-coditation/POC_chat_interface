"""
Workflow Execution Engine

Handles multi-step workflows with conditional logic and query chaining.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from orchestrator.query_orchestrator import QueryOrchestrator, OrchestratorContext
from apps.queries.models import Workflow, WorkflowExecution

logger = logging.getLogger(__name__)
User = get_user_model()


class WorkflowEngine:
    """Executes multi-step workflows with conditional logic."""
    
    def __init__(self, user: User, credentials: Dict[str, Dict] = None):
        self.user = user
        self.credentials = credentials or {}
        self.orchestrator = QueryOrchestrator()
        self.context = OrchestratorContext(
            user=user,
            credentials=self.credentials
        )
    
    def execute_workflow(self, workflow: Workflow, input_data: Dict = None) -> WorkflowExecution:
        """
        Execute a workflow.
        
        Args:
            workflow: Workflow instance to execute
            input_data: Optional input data for the workflow
            
        Returns:
            WorkflowExecution instance with results
        """
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            user=self.user,
            status='running',
            input_data=input_data or {}
        )
        
        start_time = time.time()
        step_results = []
        
        try:
            definition = workflow.definition
            steps = definition.get('steps', [])
            variables = input_data.copy() if input_data else {}
            
            for step_index, step in enumerate(steps):
                step_result = self._execute_step(step, variables, step_index)
                step_results.append(step_result)
                
                # Update variables with step output
                if step_result.get('success') and step_result.get('output'):
                    step_output = step_result['output']
                    # Merge step output into variables
                    if isinstance(step_output, dict):
                        variables.update(step_output)
                    else:
                        variables[f'step_{step_index}_output'] = step_output
                
                # Check conditional logic
                condition = step.get('condition')
                if condition:
                    should_continue = self._evaluate_condition(condition, variables, step_results)
                    if not should_continue:
                        logger.info(f"Workflow {workflow.id} stopped at step {step_index} due to condition")
                        break
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Determine final status
            all_successful = all(s.get('success', False) for s in step_results)
            final_status = 'completed' if all_successful else 'failed'
            
            execution.status = final_status
            execution.completed_at = timezone.now()
            execution.execution_time_ms = execution_time_ms
            execution.step_results = step_results
            execution.output_data = variables
            
            # Update workflow stats
            workflow.run_count += 1
            if final_status == 'completed':
                workflow.success_count += 1
            else:
                workflow.failure_count += 1
            workflow.last_run_at = execution.started_at
            workflow.save()
            
        except Exception as e:
            logger.exception(f"Workflow execution failed: {e}")
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.execution_time_ms = int((time.time() - start_time) * 1000)
            workflow.failure_count += 1
            workflow.save()
        
        execution.save()
        return execution
    
    def _execute_step(self, step: Dict, variables: Dict, step_index: int) -> Dict:
        """Execute a single workflow step."""
        step_type = step.get('type', 'query')
        
        try:
            if step_type == 'query':
                return self._execute_query_step(step, variables)
            elif step_type == 'condition':
                return self._execute_condition_step(step, variables)
            elif step_type == 'transform':
                return self._execute_transform_step(step, variables)
            else:
                return {
                    'success': False,
                    'error': f'Unknown step type: {step_type}'
                }
        except Exception as e:
            logger.exception(f"Step {step_index} execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'step_index': step_index
            }
    
    def _execute_query_step(self, step: Dict, variables: Dict) -> Dict:
        """Execute a query step."""
        query = step.get('query', '')
        query = self._replace_variables(query, variables)
        platform = step.get('platform', '')
        output_var = step.get('output_var', '')
        
        result = self.orchestrator.process_query(query, self.context)
        
        output = {
            'success': result.success,
            'query': query,
            'result': result.to_dict() if hasattr(result, 'to_dict') else {
                'data': result.data,
                'summary': result.summary,
                'error': result.error
            }
        }
        
        if output_var and result.success:
            variables[output_var] = result.data
        
        return output
    
    def _execute_condition_step(self, step: Dict, variables: Dict) -> Dict:
        """Execute a condition step (if/then/else logic)."""
        condition = step.get('condition', {})
        then_steps = step.get('then', [])
        else_steps = step.get('else', [])
        
        condition_result = self._evaluate_condition(condition, variables, [])
        steps_to_execute = then_steps if condition_result else else_steps
        results = []
        
        for sub_step in steps_to_execute:
            result = self._execute_step(sub_step, variables, len(results))
            results.append(result)
            if not result.get('success'):
                break
        
        return {
            'success': all(r.get('success', False) for r in results),
            'condition_result': condition_result,
            'executed_steps': results
        }
    
    def _execute_transform_step(self, step: Dict, variables: Dict) -> Dict:
        """Execute a transform step (data manipulation)."""
        transform_type = step.get('transform_type', 'extract')
        source_var = step.get('source_var', '')
        output_var = step.get('output_var', '')
        
        source_data = variables.get(source_var, [])
        
        if transform_type == 'extract':
            fields = step.get('fields', [])
            if isinstance(source_data, list):
                transformed = [
                    {field: item.get(field) for field in fields if field in item}
                    for item in source_data
                ]
            else:
                transformed = {field: source_data.get(field) for field in fields if field in source_data}
        
        elif transform_type == 'filter':
            filter_condition = step.get('filter_condition', {})
            if isinstance(source_data, list):
                transformed = [
                    item for item in source_data
                    if self._evaluate_condition(filter_condition, item, [])
                ]
            else:
                transformed = source_data if self._evaluate_condition(filter_condition, source_data, []) else None
        
        elif transform_type == 'aggregate':
            operation = step.get('operation', 'count')
            field = step.get('field', '')
            
            if isinstance(source_data, list):
                if operation == 'count':
                    transformed = len(source_data)
                elif operation == 'sum' and field:
                    transformed = sum(item.get(field, 0) for item in source_data if isinstance(item.get(field), (int, float)))
                elif operation == 'avg' and field:
                    values = [item.get(field, 0) for item in source_data if isinstance(item.get(field), (int, float))]
                    transformed = sum(values) / len(values) if values else 0
                else:
                    transformed = source_data
            else:
                transformed = source_data
        
        else:
            transformed = source_data
        
        if output_var:
            variables[output_var] = transformed
        
        return {
            'success': True,
            'output': transformed
        }
    
    def _evaluate_condition(self, condition: Dict, variables: Dict, step_results: List) -> bool:
        """Evaluate a condition."""
        condition_type = condition.get('type', 'equals')
        
        if condition_type == 'and':
            conditions = condition.get('conditions', [])
            return all(self._evaluate_condition(c, variables, step_results) for c in conditions)
        
        elif condition_type == 'or':
            conditions = condition.get('conditions', [])
            return any(self._evaluate_condition(c, variables, step_results) for c in conditions)
        
        elif condition_type == 'equals':
            field_value = self._get_field_value(condition.get('field', ''), variables, step_results)
            expected_value = condition.get('value')
            return field_value == expected_value
        
        elif condition_type == 'greater_than':
            field_value = self._get_field_value(condition.get('field', ''), variables, step_results)
            threshold = condition.get('value', 0)
            return isinstance(field_value, (int, float)) and field_value > threshold
        
        elif condition_type == 'contains':
            field_value = self._get_field_value(condition.get('field', ''), variables, step_results)
            search_value = condition.get('value', '')
            if isinstance(field_value, str):
                return search_value.lower() in field_value.lower()
            elif isinstance(field_value, list):
                return search_value in field_value
            return False
        
        elif condition_type == 'not_empty':
            field_value = self._get_field_value(condition.get('field', ''), variables, step_results)
            if isinstance(field_value, list):
                return len(field_value) > 0
            return bool(field_value)
        
        return False
    
    def _get_field_value(self, field_path: str, variables: Dict, step_results: List) -> Any:
        """Get value from field path."""
        if not field_path:
            return None
        
        if field_path.startswith('step_'):
            parts = field_path.split('.', 1)
            step_ref = parts[0]
            step_index = int(step_ref.split('_')[1])
            
            if step_index < len(step_results):
                step_result = step_results[step_index]
                if len(parts) > 1:
                    return self._navigate_path(parts[1], step_result.get('output', {}))
                return step_result.get('output')
        
        if '.' in field_path:
            return self._navigate_path(field_path, variables)
        
        return variables.get(field_path)
    
    def _navigate_path(self, path: str, data: Any) -> Any:
        """Navigate a dot-separated path in nested data."""
        parts = path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)] if int(part) < len(current) else None
            else:
                return None
            
            if current is None:
                return None
        
        return current
    
    def _replace_variables(self, text: str, variables: Dict) -> str:
        """Replace {{variable_name}} placeholders in text."""
        import re
        pattern = r'\{\{(\w+)\}\}'
        
        def replace_match(match):
            var_name = match.group(1)
            return str(variables.get(var_name, match.group(0)))
        
        return re.sub(pattern, replace_match, text)
