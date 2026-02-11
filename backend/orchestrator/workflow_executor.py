"""
Workflow Executor

Executes workflow definitions using the DAG for dependency resolution.
Handles tool execution, data transformation, and aggregation.
"""

import re
import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .workflow_definition import WorkflowDefinition, WorkflowStep, StepType, OutputFormat
from .dag_builder import WorkflowDAG

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms
        }


@dataclass
class WorkflowResult:
    """Result of executing a complete workflow."""
    workflow_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    execution_time_ms: int = 0
    summary: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "workflow_id": self.workflow_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "summary": self.summary,
            "execution_time_ms": self.execution_time_ms,
            "steps": {
                step_id: result.to_dict()
                for step_id, result in self.step_results.items()
            }
        }


class WorkflowExecutor:
    """
    Executes workflow definitions.
    
    Handles:
    - DAG-based dependency resolution
    - Parallel step execution
    - Variable interpolation
    - Data transformation and aggregation
    """
    
    def __init__(self, connector_registry=None, max_workers: int = 4):
        """
        Initialize the executor.
        
        Args:
            connector_registry: ConnectorRegistry for tool execution
            max_workers: Max parallel threads for step execution
        """
        self._registry = connector_registry
        self._max_workers = max_workers
        self._log_callback: Optional[Callable] = None
    
    def _get_registry(self):
        """Lazy load connector registry."""
        if self._registry is None:
            from connectors.registry import get_registry
            self._registry = get_registry()
        return self._registry
    
    def set_log_callback(self, callback: Callable[[str], None]):
        """Set callback for real-time logging."""
        self._log_callback = callback
    
    def _log(self, message: str):
        """Log a message and call the callback if set."""
        logger.info(message)
        if self._log_callback:
            self._log_callback(message)
    
    def execute(
        self,
        workflow: WorkflowDefinition,
        inputs: Dict[str, Any],
        credentials: Dict[str, Dict[str, Any]],
        user=None
    ) -> WorkflowResult:
        """
        Execute a workflow synchronously.
        
        Args:
            workflow: The workflow definition to execute
            inputs: Input parameters for the workflow
            credentials: Dict of platform -> credentials
            user: Optional user for context
        
        Returns:
            WorkflowResult with execution results
        """
        start_time = datetime.now()
        
        # Validate inputs
        errors = workflow.validate_inputs(inputs)
        if errors:
            return WorkflowResult(
                workflow_id=workflow.workflow_id,
                success=False,
                error=f"Input validation failed: {', '.join(errors)}"
            )
        
        # Build DAG
        try:
            dag = WorkflowDAG(workflow)
        except ValueError as e:
            return WorkflowResult(
                workflow_id=workflow.workflow_id,
                success=False,
                error=str(e)
            )
        
        # Get execution order
        execution_layers = dag.get_execution_order()
        
        # Context for variable interpolation
        context = {
            "inputs": inputs,
            "steps": {}  # Will store step results
        }
        
        step_results: Dict[str, StepResult] = {}
        
        # Execute layer by layer
        for layer_idx, layer_step_ids in enumerate(execution_layers):
            self._log(f"Executing layer {layer_idx + 1}/{len(execution_layers)}: {layer_step_ids}")
            
            # Execute steps in this layer (could be parallel)
            if len(layer_step_ids) > 1 and self._max_workers > 1:
                layer_results = self._execute_parallel(
                    [dag.get_step(sid) for sid in layer_step_ids],
                    context,
                    credentials
                )
            else:
                layer_results = [
                    self._execute_step(dag.get_step(sid), context, credentials)
                    for sid in layer_step_ids
                ]
            
            # Store results
            for result in layer_results:
                step_results[result.step_id] = result
                context["steps"][result.step_id] = result.data
                
                if not result.success:
                    # Step failed - abort workflow
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    return WorkflowResult(
                        workflow_id=workflow.workflow_id,
                        success=False,
                        error=f"Step '{result.step_id}' failed: {result.error}",
                        step_results=step_results,
                        execution_time_ms=int(elapsed)
                    )
        
        # Build output
        output_data = self._build_output(workflow, context)
        summary = self._build_summary(workflow, context)
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        
        return WorkflowResult(
            workflow_id=workflow.workflow_id,
            success=True,
            data=output_data,
            step_results=step_results,
            execution_time_ms=int(elapsed),
            summary=summary
        )
    
    def _execute_parallel(
        self,
        steps: List[WorkflowStep],
        context: Dict,
        credentials: Dict
    ) -> List[StepResult]:
        """Execute multiple steps in parallel."""
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [
                executor.submit(self._execute_step, step, context, credentials)
                for step in steps
            ]
            return [f.result() for f in futures]
    
    def _execute_step(
        self,
        step: WorkflowStep,
        context: Dict,
        credentials: Dict
    ) -> StepResult:
        """Execute a single workflow step."""
        start_time = datetime.now()
        
        try:
            if step.step_type == StepType.TOOL:
                result_data = self._execute_tool_step(step, context, credentials)
            elif step.step_type == StepType.TRANSFORM:
                result_data = self._execute_transform_step(step, context)
            elif step.step_type == StepType.AGGREGATE:
                result_data = self._execute_aggregate_step(step, context)
            else:
                raise ValueError(f"Unsupported step type: {step.step_type}")
            
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            
            self._log(f"Step '{step.id}' completed in {int(elapsed)}ms")
            
            return StepResult(
                step_id=step.id,
                success=True,
                data=result_data,
                execution_time_ms=int(elapsed)
            )
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.exception(f"Step '{step.id}' failed")
            
            return StepResult(
                step_id=step.id,
                success=False,
                error=str(e),
                execution_time_ms=int(elapsed)
            )
    
    def _execute_tool_step(
        self,
        step: WorkflowStep,
        context: Dict,
        credentials: Dict
    ) -> Any:
        """Execute a tool/API call step."""
        if not step.tool_id:
            raise ValueError(f"Step '{step.id}' has no tool_id")
        
        # Parse tool_id to get platform
        parts = step.tool_id.split('.')
        if len(parts) < 2:
            raise ValueError(f"Invalid tool_id format: {step.tool_id}")
        
        platform = parts[0]
        tool_name = '.'.join(parts[1:])
        
        # Get credentials for this platform
        platform_creds = credentials.get(platform, {})
        if not platform_creds:
            raise ValueError(f"No credentials for platform: {platform}")
        
        # Interpolate parameters from step definition
        params = self._interpolate_params(step.params, context)
        
        # Handle special case: email_from_step for cross-platform queries
        if 'email_from_step' in params:
            step_id = params.pop('email_from_step')
            steps_context = context.get("steps", {})
            
            if step_id not in steps_context:
                raise ValueError(f"Step {step_id} has not been executed yet or failed")
            
            step_data = steps_context[step_id]
            self._log(f"Looking for email in step {step_id}, data type: {type(step_data)}, length: {len(step_data) if isinstance(step_data, (list, dict)) else 'N/A'}")
            
            # Extract email from Salesforce contact data
            if isinstance(step_data, list):
                if len(step_data) == 0:
                    # Try to get the search name from inputs for better error message
                    search_name = context.get("inputs", {}).get("name") or context.get("inputs", {}).get("person_name") or "the specified name"
                    raise ValueError(f"No contacts found in Salesforce matching '{search_name}'. Please verify the name spelling or check if the contact exists in Salesforce.")
                
                # Try to get email from first contact
                contact = step_data[0]
                self._log(f"First contact data keys: {list(contact.keys()) if isinstance(contact, dict) else 'Not a dict'}")
                self._log(f"First contact data: {contact}")
                
                # Salesforce returns Email (capital E), but check both
                email = None
                if isinstance(contact, dict):
                    # Try multiple possible email field names
                    email = (
                        contact.get('Email') or 
                        contact.get('email') or 
                        contact.get('Email__c') or
                        contact.get('EmailAddress') or
                        contact.get('email_address')
                    )
                
                if email:
                    params['email'] = email
                    self._log(f"Extracted email '{email}' from step {step_id} for Stripe lookup")
                else:
                    # Log available fields for debugging
                    available_fields = list(contact.keys()) if isinstance(contact, dict) else []
                    raise ValueError(f"No email field found in Salesforce contact data. Available fields: {available_fields}. Contact data: {contact}")
            elif isinstance(step_data, dict):
                # Handle case where step returns a dict instead of list
                email = step_data.get('Email') or step_data.get('email') or step_data.get('Email__c')
                if email:
                    params['email'] = email
                    self._log(f"Extracted email {email} from step {step_id} (dict format)")
                else:
                    raise ValueError(f"No email found in Salesforce contact data (dict format). Available keys: {list(step_data.keys())}")
            else:
                raise ValueError(f"Step {step_id} returned unexpected data type: {type(step_data)}. Expected list or dict.")
        
        # Also merge in any relevant inputs from context (for auto-generated workflows)
        # These inputs come from query parsing (e.g., repo_name, board_name)
        if context.get("inputs"):
            inputs = context["inputs"]
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[WORKFLOW EXEC] Inputs received: {inputs}")
            logger.info(f"[WORKFLOW EXEC] Step params before merge: {params}")
            
            # Common parameter names to pass through
            # Include platform-specific filters
            param_keys = [
                'repo_name', 'board_name', 'limit', 'since', 'until', 'status', 'state', 'owner', 'repo',
                # Zoho filters
                'amount_gt', 'stage', 'city', 'location', 'email',
                # Stripe filters
                'period', 'customer', 'plan', 'product_name', 'name', 'customer_name',
                # GitHub filters
                'language', 'sort', 'type', 'labels', 'author',
                # Trello filters
                'list_id', 'board_id', 'board_name', 'list_name', 'desc',
                # Salesforce filters
                'name', 'person_name', 'company', 'account'
            ]
            for key in param_keys:
                if key in inputs and key not in params:
                    params[key] = inputs[key]
                    logger.info(f"[WORKFLOW EXEC] Added param {key} = {inputs[key]}")
            
            # Also pass through any filters dict if present
            if 'filters' in inputs and isinstance(inputs['filters'], dict):
                logger.info(f"[WORKFLOW EXEC] Merging filters dict: {inputs['filters']}")
                params.update(inputs['filters'])
            
            logger.info(f"[WORKFLOW EXEC] Final params for {step.tool_id}: {params}")
        
        # Try connector registry first
        try:
            registry = self._get_registry()
            result = registry.execute(
                platform=platform,
                tool_id=tool_name,
                params=params,
                credentials=platform_creds
            )
            
            if result.success:
                return result.data
            else:
                raise RuntimeError(result.error)
        except Exception as registry_error:
            # Fallback to legacy clients if registry fails
            self._log(f"Registry failed for {platform}.{tool_name}, trying legacy client...")
            return self._execute_legacy_tool(platform, tool_name, params, platform_creds, context, step.id)
    
    def _execute_legacy_tool(
        self,
        platform: str,
        tool_name: str,
        params: Dict,
        credentials: Dict,
        context: Dict = None,
        step_id: str = None
    ) -> Any:
        """Fallback to legacy util clients for platforms without adapters."""
        # Use module-level logger
        import logging
        _logger = logging.getLogger(__name__)
        
        if platform == "stripe":
            from utils import stripe_client
            api_key = credentials.get('api_key', '')
            
            if tool_name == "list_invoices":
                result = stripe_client.fetch_invoices(api_key, filters=params)
            elif tool_name == "list_customers":
                result = stripe_client.fetch_customers(api_key, filters=params)
            elif tool_name == "list_products":
                result = stripe_client.fetch_products(api_key, filters=params)
            elif tool_name == "get_revenue":
                result = stripe_client.fetch_revenue(api_key, filters=params)
            elif tool_name == "get_balance":
                result = stripe_client.fetch_balance(api_key, filters=params)
                # Return balance data in a format that can be displayed
                if result.get('error'):
                    _logger.error(f"[BALANCE] Error from fetch_balance: {result.get('error')}")
                    raise RuntimeError(f"Failed to fetch balance: {result.get('error')}")
                # Ensure result has required fields
                if 'available' not in result or 'pending' not in result:
                    _logger.error(f"[BALANCE] Invalid result structure: {result}")
                    raise RuntimeError("Invalid balance data structure returned")
                # Format as list for table display
                return [result]
            elif tool_name == "list_charges":
                # Charges use fetch_invoices as fallback
                result = stripe_client.fetch_invoices(api_key, filters=params)
            elif tool_name == "list_subscriptions":
                result = stripe_client.fetch_subscriptions(api_key, filters=params)
            elif tool_name == "fetch_data_by_email":
                # Cross-platform: fetch Stripe data by email
                email = params.get('email')
                if not email:
                    raise ValueError("Email parameter required for fetch_data_by_email")
                result = stripe_client.fetch_data_by_email(api_key, email)
                # Return structured data for cross-platform workflow
                # Always return the full result structure so frontend can display it properly
                if result.get('found'):
                    return {
                        'found': True,
                        'customer': result.get('customer', {}),
                        'invoices': result.get('invoices', []),
                        'summary': result.get('summary', {}),
                        'message': f"Found customer: {result.get('customer', {}).get('name', 'Unknown')} ({result.get('customer', {}).get('email', 'No email')})"
                    }
                else:
                    return {
                        'found': False, 
                        'message': result.get('message', 'Customer not found'),
                        'customer': {},
                        'invoices': [],
                        'summary': {}
                    }
            else:
                raise ValueError(f"Unknown Stripe tool: {tool_name}")
            
            # Stripe client returns {'data': [...], 'count': N, 'error': '...'}
            if result.get('error'):
                raise RuntimeError(result.get('error'))
            return result.get('data', [])
        
        elif platform == "zoho":
            from utils import zoho_client
            
            # Get refresh token from credentials
            refresh_token = credentials.get('api_key', '')  # Stored as 'api_key' in platform connection
            
            if tool_name == "list_contacts":
                result = zoho_client.fetch_contacts(refresh_token, filters=params)
            elif tool_name == "list_deals":
                result = zoho_client.fetch_deals(refresh_token, filters=params)
            elif tool_name == "list_leads":
                result = zoho_client.fetch_leads(refresh_token, filters=params)
            elif tool_name == "list_accounts":
                result = zoho_client.fetch_accounts(refresh_token, filters=params)
            else:
                raise ValueError(f"Unknown Zoho tool: {tool_name}")
            
            # Zoho client returns {'data': [...], 'count': N, 'error': '...'} on error
            if result.get('error'):
                raise RuntimeError(result.get('error'))
            return result.get('data', [])
        
        elif platform == "github":
            from utils import github_client
            token = credentials.get('api_key', '')
            
            if tool_name == "list_repos":
                result = github_client.fetch_repos(token, filters=params)
            elif tool_name == "repo_summary":
                # repo_summary needs owner/repo parsed from repo_name
                repo_name = params.get('repo_name', '')
                owner, repo = self._resolve_github_repo(token, repo_name, github_client)
                if owner and repo:
                    result = github_client.fetch_repo_summary(token, owner, repo)
                else:
                    result = github_client.fetch_repos(token, filters=params)
            elif tool_name == "list_prs":
                repo_name = params.get('repo_name', '')
                owner, repo = self._resolve_github_repo(token, repo_name, github_client)
                if owner and repo:
                    result = github_client.fetch_pull_requests(token, owner, repo, filters=params)
                else:
                    # No specific repo - use GitHub search API to find PRs
                    # GitHub search requires a scope (user/repo), so we need to get user first
                    import requests
                    state = params.get('state', 'all')
                    
                    # First, get the authenticated user's username (required for search scope)
                    username = None
                    try:
                        user_response = requests.get(
                            f"{github_client.GITHUB_API_BASE}/user",
                            headers=github_client._get_headers(token),
                            timeout=10
                        )
                        if user_response.status_code == 200:
                            username = user_response.json().get('login', '')
                            logger.info(f"[GITHUB] Authenticated user: {username}")
                    except Exception as e:
                        logger.warning(f"[GITHUB] Could not get user info: {e}")
                    
                    if not username:
                        # Fallback: try to get PRs from user's repos
                        logger.warning("[GITHUB] Could not get username, fetching repos to search PRs")
                        repos_result = github_client.fetch_repos(token, filters={'limit': 10})
                        if repos_result.get('data'):
                            # Aggregate PRs from first few repos
                            all_prs = []
                            for repo in repos_result['data'][:5]:  # Limit to first 5 repos
                                owner, repo_name = repo['full_name'].split('/')
                                pr_result = github_client.fetch_pull_requests(token, owner, repo_name, filters=params)
                                if pr_result.get('data'):
                                    all_prs.extend(pr_result['data'])
                            result = {'data': all_prs[:30], 'count': len(all_prs[:30])}
                        else:
                            result = {'data': [], 'count': 0, 'error': 'Could not fetch user repos'}
                    else:
                        # Build search query with user scope (required by GitHub API)
                        search_query = f"is:pr user:{username}"
                        
                        # Add state filter only if not 'all'
                        if state == 'open':
                            search_query += " is:open"
                        elif state == 'closed':
                            search_query += " is:closed"
                        
                        logger.info(f"[GITHUB] PR search query: {search_query}")
                        result = github_client.search_issues(token, search_query, filters=params)
                        
                        # If search fails or returns no results, try author filter instead
                        if result.get('error') or result.get('count', 0) == 0:
                            logger.info(f"[GITHUB] Trying author filter instead")
                            author_query = f"is:pr author:{username}"
                            if state == 'open':
                                author_query += " is:open"
                            elif state == 'closed':
                                author_query += " is:closed"
                            result = github_client.search_issues(token, author_query, filters=params)
            elif tool_name == "list_issues":
                repo_name = params.get('repo_name', '')
                owner, repo = self._resolve_github_repo(token, repo_name, github_client)
                if owner and repo:
                    result = github_client.fetch_issues(token, owner, repo, filters=params)
                else:
                    result = github_client.fetch_repos(token, filters=params)
            elif tool_name == "list_commits":
                repo_name = params.get('repo_name', '')
                owner, repo = self._resolve_github_repo(token, repo_name, github_client)
                if owner and repo:
                    result = github_client.fetch_commits(token, owner, repo, filters=params)
                else:
                    result = github_client.fetch_repos(token, filters=params)
            else:
                raise ValueError(f"Unknown GitHub tool: {tool_name}")
            
            # GitHub client returns {'data': [...], 'count': N, 'error': '...'}
            if result.get('error'):
                raise RuntimeError(result.get('error'))
            return result.get('data', [])
        
        elif platform == "trello":
            from utils import trello_client
            api_key = credentials.get('api_key', '')
            token = credentials.get('token', '')
            
            # Trello uses execute_query function
            if tool_name == "list_boards":
                result = trello_client.execute_query('list_boards', params, api_key, token)
            elif tool_name == "list_cards":
                result = trello_client.execute_query('list_cards', params, api_key, token)
            elif tool_name == "get_lists":
                result = trello_client.execute_query('get_lists', params, api_key, token)
            elif tool_name == "create_card":
                result = trello_client.execute_query('create_card', params, api_key, token)
            elif tool_name == "delete_card":
                result = trello_client.execute_query('delete_card', params, api_key, token)
            else:
                raise ValueError(f"Unknown Trello tool: {tool_name}")
            
            # Trello client returns {'success': True/False, 'data': [...], 'error': '...', 'summary': '...'}
            if not result.get('success', True):
                raise RuntimeError(result.get('error', 'Trello query failed'))
            
            # Store summary in context for _build_summary to use
            # The context is passed by reference, so we can modify it
            if 'summary' in result and context is not None:
                if 'step_summaries' not in context:
                    context['step_summaries'] = {}
                # Use the step_id parameter or fallback to tool_name
                final_step_id = step_id or tool_name or 'main'
                context['step_summaries'][final_step_id] = result['summary']
                _logger.info(f"[WORKFLOW EXEC] Stored Trello summary for step {final_step_id}: {result['summary']}")
            
            # For write operations, return the result data (which includes the created/deleted item info)
            return result.get('data', [])
        
        elif platform == "salesforce":
            from utils import salesforce_client
            # Use _logger defined at function start
            
            # Salesforce credentials can be stored in two formats:
            # 1. "access_token:instance_url" in api_key (legacy)
            # 2. access_token in api_key, instance_url in metadata (OAuth)
            creds_str = credentials.get('api_key', '')
            # Metadata is merged into credentials dict in queries/views.py
            # So instance_url, refresh_token, client_id, client_secret are at root level of credentials
            
            _logger.info(f"[SALESFORCE] Credentials keys: {list(credentials.keys())}")
            
            if ':' in creds_str:
                # Legacy format: "access_token:instance_url"
                access_token, instance_url = creds_str.split(':', 1)
                _logger.info("[SALESFORCE] Using legacy credential format")
            else:
                # OAuth format: access_token in api_key, instance_url in metadata
                access_token = creds_str
                instance_url = credentials.get('instance_url', '')
                _logger.info(f"[SALESFORCE] Using OAuth format, instance_url: {instance_url[:50] if instance_url else 'NOT FOUND'}")
            
            if not access_token:
                raise ValueError("Salesforce access token not found")
            if not instance_url:
                raise ValueError("Salesforce instance_url not found. Please reconnect Salesforce.")
            
            # Extract refresh credentials (stored at root level after metadata merge)
            refresh_token = credentials.get('refresh_token')
            client_id = credentials.get('client_id')
            client_secret = credentials.get('client_secret')
            
            _logger.info(f"[SALESFORCE] Has refresh_token: {bool(refresh_token)}, client_id: {bool(client_id)}, client_secret: {bool(client_secret)}")
            
            # Map tool names to Salesforce actions
            action_map = {
                'list_contacts': 'list_contacts',
                'list_leads': 'list_leads',
                'list_accounts': 'list_accounts',
                'list_opportunities': 'list_opportunities',
                'list_deals': 'list_opportunities',  # Alias
                'get_contact': 'list_contacts',     # RAG Alias
                'get_account': 'list_accounts',      # RAG Alias
                'create_contact': 'create_contact',
                'create_record': 'create_record'
            }
            
            action = action_map.get(tool_name)
            if not action:
                raise ValueError(f"Unknown Salesforce tool: {tool_name}")
            
            # Salesforce execute_query expects 'filters' parameter, not 'params'
            # Convert params to filters format
            filters = params.copy() if params else {}
            
            # Log parameters being sent to Salesforce
            _logger.info(f"[SALESFORCE] Executing {action} with filters: {filters}")
            
            # Try to execute query
            result = salesforce_client.execute_query(action, filters, access_token, instance_url)
            
            # Log result
            _logger.info(f"[SALESFORCE] Query result - success: {result.get('success')}, data count: {len(result.get('data', []))}")
            if result.get('data'):
                _logger.info(f"[SALESFORCE] First record keys: {list(result['data'][0].keys()) if isinstance(result['data'], list) and len(result['data']) > 0 else 'N/A'}")
            
            # If we get 401, try to refresh the token
            if not result.get('success', True):
                error_msg = result.get('error', '')
                status_code = result.get('status_code')
                
                if status_code == 401 or '401' in str(error_msg) or 'Unauthorized' in error_msg:
                    # Token expired, try to refresh
                    # refresh_token, client_id, client_secret are already extracted above
                    
                    if refresh_token and client_id and client_secret:
                        self._log("Salesforce token expired, attempting refresh...")
                        refresh_result = salesforce_client.refresh_access_token(client_id, client_secret, refresh_token)
                        
                        if refresh_result.get('success'):
                            # Use new token
                            access_token = refresh_result['access_token']
                            # instance_url might change, but usually stays the same
                            if refresh_result.get('instance_url'):
                                instance_url = refresh_result['instance_url']
                            
                            self._log("Salesforce token refreshed successfully, retrying query...")
                            # Retry with new token
                            result = salesforce_client.execute_query(action, params, access_token, instance_url)
                            
                            # TODO: Update stored credentials with new token (requires DB access)
                            # For now, just log that refresh happened
                            import logging
                            logging.getLogger(__name__).info(f"[SALESFORCE] Token refreshed, new token: {access_token[:20]}...")
                        else:
                            self._log(f"Failed to refresh Salesforce token: {refresh_result.get('error')}")
                            raise RuntimeError(f"Salesforce token expired and refresh failed: {refresh_result.get('error', 'Unknown error')}. Please reconnect Salesforce.")
                    else:
                        missing = []
                        if not refresh_token:
                            missing.append('refresh_token')
                        if not client_id:
                            missing.append('client_id')
                        if not client_secret:
                            missing.append('client_secret')
                        raise RuntimeError(f"Salesforce token expired. Missing: {', '.join(missing)}. Please reconnect Salesforce.")
            
            if not result.get('success', True):
                raise RuntimeError(result.get('error', 'Salesforce query failed'))
            
            # Store summary in context for _build_summary to use
            if 'summary' in result and context is not None:
                if 'step_summaries' not in context:
                    context['step_summaries'] = {}
                final_step_id = step_id or tool_name or 'main'
                context['step_summaries'][final_step_id] = result['summary']
                _logger.info(f"[WORKFLOW EXEC] Stored Salesforce summary for step {final_step_id}: {result['summary']}")
            
            # Salesforce returns {'success': True, 'data': [...], ...}
            return result.get('data', [])
        
        else:
            raise ValueError(f"No connector available for platform: {platform}")
    
    def _resolve_github_repo(self, token: str, repo_name: str, github_client) -> tuple:
        """
        Resolve a repo name to owner/repo format.
        
        If repo_name contains '/', assume it's already in owner/repo format.
        Otherwise, search the user's repos for a matching name.
        
        Returns:
            Tuple of (owner, repo) or (None, None) if not found
        """
        if not repo_name:
            return (None, None)
        
        # Already in owner/repo format
        if '/' in repo_name:
            parts = repo_name.split('/', 1)
            return (parts[0], parts[1])
        
        # Search user's repos for matching name
        try:
            repos_result = github_client.fetch_repos(token, filters={'limit': 100})
            if repos_result.get('error'):
                self._log(f"Error fetching repos: {repos_result.get('error')}")
                return (None, None)
            
            repos = repos_result.get('data', [])
            
            # Look for exact match (case-insensitive)
            repo_name_lower = repo_name.lower()
            for repo in repos:
                name = repo.get('name', '')
                full_name = repo.get('full_name', '')  # e.g., "owner/repo"
                
                if name.lower() == repo_name_lower:
                    if '/' in full_name:
                        owner, rname = full_name.split('/', 1)
                        return (owner, rname)
                    # Fallback: try to get owner from repo data
                    owner = repo.get('owner', {})
                    if isinstance(owner, dict):
                        return (owner.get('login', ''), name)
            
            self._log(f"Could not find repo matching '{repo_name}'")
            return (None, None)
            
        except Exception as e:
            self._log(f"Error resolving repo: {e}")
            return (None, None)
    
    def _execute_transform_step(
        self,
        step: WorkflowStep,
        context: Dict
    ) -> Any:
        """Execute a data transformation step."""
        operation = step.operation
        
        # Get input data from dependencies
        input_data = []
        for dep_id in step.depends_on:
            if dep_id in context["steps"]:
                input_data.append(context["steps"][dep_id])
        
        if not input_data:
            return None
        
        data = input_data[0] if len(input_data) == 1 else input_data
        
        if operation == "filter":
            return self._transform_filter(data, step.condition, context)
        elif operation == "map":
            return self._transform_map(data, step.params, context)
        elif operation == "merge":
            return self._transform_merge(input_data)
        elif operation == "flatten":
            return self._transform_flatten(data)
        else:
            logger.warning(f"Unknown transform operation: {operation}")
            return data
    
    def _execute_aggregate_step(
        self,
        step: WorkflowStep,
        context: Dict
    ) -> Any:
        """Execute a data aggregation step."""
        # Get input data
        input_data = []
        for dep_id in step.depends_on:
            if dep_id in context["steps"]:
                input_data.extend(
                    context["steps"][dep_id] 
                    if isinstance(context["steps"][dep_id], list) 
                    else [context["steps"][dep_id]]
                )
        
        if not input_data:
            return {"groups": [], "totals": {}}
        
        # Group by field if specified
        if step.group_by:
            groups = {}
            for item in input_data:
                if isinstance(item, dict):
                    key = item.get(step.group_by, "unknown")
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(item)
            
            # Calculate metrics for each group
            result = []
            for group_key, items in groups.items():
                group_result = {step.group_by: group_key}
                for metric in step.metrics:
                    metric_name = metric.get("name")
                    metric_op = metric.get("operation")
                    metric_field = metric.get("field")
                    
                    values = [
                        item.get(metric_field, 0) 
                        for item in items 
                        if isinstance(item, dict)
                    ]
                    
                    if metric_op == "sum":
                        group_result[metric_name] = sum(values)
                    elif metric_op == "count":
                        group_result[metric_name] = len(values)
                    elif metric_op == "avg":
                        group_result[metric_name] = sum(values) / len(values) if values else 0
                    elif metric_op == "min":
                        group_result[metric_name] = min(values) if values else 0
                    elif metric_op == "max":
                        group_result[metric_name] = max(values) if values else 0
                
                result.append(group_result)
            
            return result
        
        # No grouping - just calculate totals
        totals = {}
        for metric in step.metrics:
            metric_name = metric.get("name")
            metric_op = metric.get("operation")
            metric_field = metric.get("field")
            
            values = [
                item.get(metric_field, 0) 
                for item in input_data 
                if isinstance(item, dict)
            ]
            
            if metric_op == "sum":
                totals[metric_name] = sum(values)
            elif metric_op == "count":
                totals[metric_name] = len(values)
        
        return totals
    
    def _interpolate_params(
        self,
        params: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Interpolate template variables in parameters."""
        result = {}
        
        for key, value in params.items():
            if isinstance(value, str):
                # Replace {{ var }} patterns
                pattern = r'\{\{\s*(\w+(?:\.\w+)*)\s*\}\}'
                
                def replacer(match):
                    path = match.group(1).split('.')
                    current = context
                    for part in path:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            return match.group(0)  # Keep original if not found
                    return str(current) if current is not None else ""
                
                result[key] = re.sub(pattern, replacer, value)
            elif isinstance(value, dict):
                result[key] = self._interpolate_params(value, context)
            else:
                result[key] = value
        
        return result
    
    def _transform_filter(
        self,
        data: Any,
        condition: str,
        context: Dict
    ) -> List:
        """Filter data based on condition."""
        if not isinstance(data, list):
            data = [data]
        
        if not condition:
            return data
        
        # Simple condition parsing (field contains 'value')
        # Format: "field contains 'value'"
        match = re.match(r"(\w+)\s+contains\s+'([^']+)'", condition)
        if match:
            field, value = match.groups()
            return [
                item for item in data
                if isinstance(item, dict) and 
                value.lower() in str(item.get(field, '')).lower()
            ]
        
        return data
    
    def _transform_map(
        self,
        data: Any,
        params: Dict,
        context: Dict
    ) -> List:
        """Map/transform data fields."""
        if not isinstance(data, list):
            data = [data]
        
        fields = params.get("fields", [])
        if not fields:
            return data
        
        return [
            {field: item.get(field) for field in fields if isinstance(item, dict)}
            for item in data
        ]
    
    def _transform_merge(self, datasets: List) -> Dict:
        """Merge multiple datasets into one."""
        merged = {}
        for idx, data in enumerate(datasets):
            merged[f"source_{idx}"] = data
        return merged
    
    def _transform_flatten(self, data: Any) -> List:
        """Flatten nested lists."""
        if not isinstance(data, list):
            return [data]
        
        result = []
        for item in data:
            if isinstance(item, list):
                result.extend(item)
            else:
                result.append(item)
        return result
    
    def _build_output(
        self,
        workflow: WorkflowDefinition,
        context: Dict
    ) -> Any:
        """Build the final output based on workflow output config."""
        # Special handling for cross-platform customer overview
        if workflow.workflow_id == "customer_overview_cross_platform":
            salesforce_data = context["steps"].get("find_salesforce_contact", [])
            stripe_data = context["steps"].get("get_stripe_data", {})
            
            # Combine data into unified format
            combined = {
                'type': 'bulk_response',
                'data': []
            }
            
            # Add Salesforce contact info
            if isinstance(salesforce_data, list) and len(salesforce_data) > 0:
                contact = salesforce_data[0]
                combined['data'].append({
                    'platform': 'salesforce',
                    'success': True,
                    'summary': f"Found contact: {contact.get('Name', 'Unknown')}",
                    'data': salesforce_data
                })
            
            # Add Stripe payment info
            if isinstance(stripe_data, dict):
                if stripe_data.get('found'):
                    invoices = stripe_data.get('invoices', [])
                    customer = stripe_data.get('customer', {})
                    summary_data = stripe_data.get('summary', {})
                    total_spend = summary_data.get('total_spend', 0)
                    currency = summary_data.get('currency', 'USD')
                    
                    # Build summary message
                    if len(invoices) > 0:
                        summary_msg = f"Found {len(invoices)} invoice(s) for {customer.get('email', 'customer')}. Total spend: {currency} ${total_spend:,.2f}"
                    else:
                        summary_msg = f"Found customer: {customer.get('name', 'Unknown')} ({customer.get('email', 'No email')}). No invoices found."
                    
                    combined['data'].append({
                        'platform': 'stripe',
                        'success': True,
                        'summary': summary_msg,
                        'data': invoices if invoices else []  # Always include data array, even if empty
                    })
                else:
                    combined['data'].append({
                        'platform': 'stripe',
                        'success': False,
                        'error': stripe_data.get('message', 'No Stripe customer found'),
                        'data': []
                    })
            
            return combined
        
        if not workflow.output:
            # Return last step's data
            if context["steps"]:
                last_step_id = list(context["steps"].keys())[-1]
                return context["steps"][last_step_id]
            return None
        
        output = workflow.output
        
        if output.format == OutputFormat.UNIFIED_VIEW:
            # Build unified view from sections
            unified = {}
            for section in output.sections:
                name = section.get("name")
                source = section.get("source")
                if source in context["steps"]:
                    unified[name] = context["steps"][source]
            return unified
        
        elif output.format == OutputFormat.TABLE:
            # Extract columns from last step
            last_data = list(context["steps"].values())[-1] if context["steps"] else []
            if isinstance(last_data, list) and output.columns:
                return [
                    {col: item.get(col) for col in output.columns}
                    for item in last_data
                    if isinstance(item, dict)
                ]
            return last_data
        
        else:
            # Default: return all step data
            return context["steps"]
    
    def _build_summary(
        self,
        workflow: WorkflowDefinition,
        context: Dict
    ) -> str:
        """Build summary string from template or generate auto-summary."""
        # Special handling for cross-platform customer overview
        if workflow.workflow_id == "customer_overview_cross_platform":
            salesforce_data = context["steps"].get("find_salesforce_contact", [])
            stripe_data = context["steps"].get("get_stripe_data", {})
            
            parts = []
            if isinstance(salesforce_data, list) and len(salesforce_data) > 0:
                contact = salesforce_data[0]
                parts.append(f"**Salesforce Contact:** {contact.get('Name', 'Unknown')} ({contact.get('Email', 'No email')})")
            
            if isinstance(stripe_data, dict) and stripe_data.get('found'):
                invoices = stripe_data.get('invoices', [])
                total_spend = stripe_data.get('summary', {}).get('total_spend', 0)
                parts.append(f"**Stripe Payments:** {len(invoices)} invoice(s), Total: ${total_spend:,.2f}")
            elif isinstance(stripe_data, dict):
                parts.append(f"**Stripe:** {stripe_data.get('message', 'No customer found')}")
            
            return " | ".join(parts) if parts else "No data found."
        
        # If we have a template, use it
        if workflow.output and workflow.output.summary_template:
            template = workflow.output.summary_template
            return self._interpolate_string(template, context)
        
        # Special handling for cross-platform customer overview
        if workflow.workflow_id == "customer_overview_cross_platform":
            salesforce_data = context["steps"].get("find_salesforce_contact", [])
            stripe_data = context["steps"].get("get_stripe_data", {})
            
            parts = []
            if isinstance(salesforce_data, list) and len(salesforce_data) > 0:
                contact = salesforce_data[0]
                parts.append(f"**Salesforce Contact:** {contact.get('Name', 'Unknown')} ({contact.get('Email', 'No email')})")
            
            if isinstance(stripe_data, dict) and stripe_data.get('found'):
                invoices = stripe_data.get('invoices', [])
                total_spend = stripe_data.get('summary', {}).get('total_spend', 0)
                parts.append(f"**Stripe Payments:** {len(invoices)} invoice(s), Total: ${total_spend:,.2f}")
            elif isinstance(stripe_data, dict):
                parts.append(f"**Stripe:** {stripe_data.get('message', 'No customer found')}")
            
            return " | ".join(parts) if parts else "No data found."
        
        # Check for step summaries first (from Trello write operations)
        if context.get('step_summaries'):
            # Use the summary from the last step if available
            step_ids = list(context.get('steps', {}).keys())
            if step_ids:
                last_step_id = step_ids[-1]
                summary = context['step_summaries'].get(last_step_id)
                if summary:
                    logger.info(f"[WORKFLOW EXEC] Using stored summary for step {last_step_id}: {summary}")
                    return summary
            # If no step_ids match, try to get any summary
            summaries = list(context['step_summaries'].values())
            if summaries:
                logger.info(f"[WORKFLOW EXEC] Using first available summary: {summaries[0]}")
                return summaries[0]
        
        # Auto-generate summary based on results
        if not context.get("steps"):
            return "No data found."
        
        # Get the last step's data
        last_step_data = list(context["steps"].values())[-1] if context["steps"] else None
        
        if last_step_data is None:
            return "Query completed but returned no data."
        
        if isinstance(last_step_data, list):
            count = len(last_step_data)
            if count == 0:
                # Check if this is a write operation that succeeded but returned empty data
                workflow_id = workflow.workflow_id.lower() if hasattr(workflow, 'workflow_id') else ""
                if "create" in workflow_id or "delete" in workflow_id:
                    # For write operations, check if there's a summary message
                    # The summary should be in the result, not the data
                    return "Operation completed successfully."
                return "No records found matching your query."
            # Try to infer the data type from workflow name
            workflow_name = workflow.name.lower() if workflow.name else ""
            workflow_id = workflow.workflow_id.lower() if hasattr(workflow, 'workflow_id') else ""
            
            # Check for write operations first
            if "create_card" in workflow_id:
                if count > 0 and last_step_data[0].get('name'):
                    card_name = last_step_data[0].get('name')
                    return f"Successfully created card '{card_name}'."
                return "Card created successfully."
            elif "delete_card" in workflow_id:
                return "Card deleted successfully."
            elif "deal" in workflow_name:
                return f"Found {count} deal{'s' if count != 1 else ''}."
            elif "contact" in workflow_name:
                return f"Found {count} contact{'s' if count != 1 else ''}."
            elif "lead" in workflow_name:
                return f"Found {count} lead{'s' if count != 1 else ''}."
            elif "invoice" in workflow_name:
                return f"Found {count} invoice{'s' if count != 1 else ''}."
            elif "customer" in workflow_name:
                return f"Found {count} customer{'s' if count != 1 else ''}."
            elif "repo" in workflow_name:
                return f"Found {count} repositor{'ies' if count != 1 else 'y'}."
            elif "board" in workflow_name:
                return f"Found {count} board{'s' if count != 1 else ''}."
            elif "card" in workflow_name:
                return f"Found {count} card{'s' if count != 1 else ''}."
            else:
                return f"Found {count} record{'s' if count != 1 else ''}."
        elif isinstance(last_step_data, dict):
            # Revenue or summary data
            if 'total_revenue' in last_step_data:
                return f"Total revenue: ${last_step_data['total_revenue']:,.2f}"
            return f"Query completed successfully with {len(last_step_data)} field(s)."
        else:
            return "Query completed successfully."
    
    def _interpolate_string(self, template: str, context: Dict) -> str:
        """Interpolate a template string with context values."""
        pattern = r'\{\{\s*(\w+(?:\.\w+)*)\s*\}\}'
        
        def replacer(match):
            path = match.group(1).split('.')
            current = context
            for part in path:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return match.group(0)
            return str(current) if current is not None else ""
        
        return re.sub(pattern, replacer, template)


# Singleton instance
_workflow_executor = None

def get_workflow_executor() -> WorkflowExecutor:
    """Get the default workflow executor instance."""
    global _workflow_executor
    if _workflow_executor is None:
        _workflow_executor = WorkflowExecutor()
    return _workflow_executor
