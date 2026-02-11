"""
Query Orchestrator

Main entry point that ties all components together:
1. Intent Detection
2. Entity Resolution  
3. Policy Evaluation
4. Workflow Execution
5. Audit Logging
"""

import logging
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from connectors.base import GovernanceClass

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorContext:
    """Context for query orchestration."""
    user: Any  # Django user
    session_id: str = ""
    credentials: Dict[str, Dict] = field(default_factory=dict)
    log_callback: Optional[Callable[[str], None]] = None
    
    def log(self, message: str):
        """Log a message through the callback if available."""
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)


@dataclass
class OrchestratorResult:
    """Result of query orchestration."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    intent: Optional[Dict] = None
    entities: List[Dict] = field(default_factory=list)
    workflow_used: Optional[str] = None
    execution_time_ms: int = 0
    requires_approval: bool = False
    approval_id: Optional[str] = None
    summary: str = ""
    chart: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "intent": self.intent,
            "entities": self.entities,
            "workflow_used": self.workflow_used,
            "execution_time_ms": self.execution_time_ms,
            "requires_approval": self.requires_approval,
            "chart": self.chart,
            "approval_id": self.approval_id,
            "summary": self.summary
        }


class QueryOrchestrator:
    """
    Central orchestrator for natural language queries.
    
    Coordinates all layers of the platform:
    1. Intent Detection - What does the user want?
    2. Entity Resolution - What entities are they referencing?
    3. Workflow Selection - What workflow handles this?
    4. Policy Check - Is this action allowed?
    5. Execution - Run the workflow
    6. Audit - Log everything
    """
    
    def __init__(
        self,
        intent_detector=None,
        entity_resolver=None,
        policy_engine=None,
        workflow_executor=None,
        audit_service=None,
        connector_registry=None
    ):
        """Initialize with optional component overrides."""
        self._intent_detector = intent_detector
        self._entity_resolver = entity_resolver
        self._policy_engine = policy_engine
        self._workflow_executor = workflow_executor
        self._audit_service = audit_service
        self._connector_registry = connector_registry
        
        # Workflow registry (workflow_id -> WorkflowDefinition)
        self._workflows: Dict = {}
    
    def _get_intent_detector(self):
        if self._intent_detector is None:
            from orchestrator.intent_detector import get_intent_detector
            self._intent_detector = get_intent_detector()
        return self._intent_detector
    
    def _get_entity_resolver(self):
        if self._entity_resolver is None:
            from orchestrator.entity_resolver import get_entity_resolver
            self._entity_resolver = get_entity_resolver()
        return self._entity_resolver
    
    def _get_policy_engine(self):
        if self._policy_engine is None:
            from orchestrator.policy_engine import get_policy_engine
            self._policy_engine = get_policy_engine()
        return self._policy_engine
    
    def _get_workflow_executor(self):
        if self._workflow_executor is None:
            from orchestrator.workflow_executor import get_workflow_executor
            self._workflow_executor = get_workflow_executor()
        return self._workflow_executor
    
    def _get_audit_service(self):
        if self._audit_service is None:
            from orchestrator.audit_service import get_audit_service
            self._audit_service = get_audit_service()
        return self._audit_service
    
    def _get_connector_registry(self):
        if self._connector_registry is None:
            from connectors.registry import get_registry
            self._connector_registry = get_registry()
        return self._connector_registry
    
    def process_query(
        self,
        query: str,
        context: OrchestratorContext
    ) -> OrchestratorResult:
        """
        Process a natural language query.
        
        Args:
            query: The user's natural language query
            context: Orchestration context with user, credentials, etc.
        
        Returns:
            OrchestratorResult with query results
        """
        start_time = datetime.now()
        audit = self._get_audit_service()
        audit.start_session()
        
        context.log(f"Processing query: {query[:50]}...")
        
        try:
            # Step 1: Detect Intent
            context.log("Detecting intent...")
            intent_detector = self._get_intent_detector()
            intent = intent_detector.detect(query)
            
            
            context.log(f"Intent: {intent.intent_type.value} (confidence: {intent.confidence:.2f}, tool: {intent.tool_id}, platform: {intent.platform})")
            
            # [SAFETY PATCH] Correct known misclassifications
            # Sometimes "list all repos" or "everything about repos" triggers Zoho intent due to "everything" or "list" keywords
            if intent.platform == "zoho" and any(k in query.lower() for k in ["repo", "github", "pr", "pull request", "commit"]):
                context.log(f"[SAFETY] Correcting misclassified intent: {intent.tool_id} -> list_repos (github)")
                intent.tool_id = "list_repos"
                intent.platform = "github"
                intent.confidence = 1.0
            
            # Use corrected query if available (typo correction from IntentDetector)
            corrected_query = intent.matched_query if intent.matched_query else query
            
            # Debug logging for cross-platform queries
            if intent.tool_id == "customer_overview_cross_platform":
                context.log(f"Cross-platform intent detected! Query: {query}")
            
            if not intent.is_confident():
                # Low confidence - ask for clarification
                return OrchestratorResult(
                    success=False,
                    error="Could not understand your request. Please rephrase.",
                    intent=intent.to_dict()
                )
            
            # Step 2: Resolve Entities (if any entity references in query)
            context.log("Resolving entities...")
            entity_resolver = self._get_entity_resolver()
            entities = self._extract_and_resolve_entities(query, entity_resolver, context)
            
            # Step 3: Select Workflow
            workflow = None
            
            # Handle Knowledge Queries
            if intent.intent_type.value == "KNOWLEDGE_QUERY":
                return self._handle_knowledge_query(query, context)
                
            if intent.tool_id == "customer_overview_cross_platform":
                # Handle cross-platform customer overview (Salesforce + Stripe)
                workflow = self._create_cross_platform_customer_workflow(query, context)
            elif intent.tool_id:
                # Direct tool execution
                workflow = self._create_tool_workflow(intent.tool_id, intent.platform)
            else:
                # Look for a matching workflow
                workflow = self._find_workflow(intent, entities)
            
            if not workflow:
                return OrchestratorResult(
                    success=False,
                    error=f"No workflow found for intent: {intent.intent_type.value}",
                    intent=intent.to_dict(),
                    entities=[e.to_dict() for e in entities]
                )
            
            context.log(f"Using workflow: {workflow.workflow_id}")
            
            # Step 4: Policy Check
            context.log("Checking policies...")
            policy_engine = self._get_policy_engine()
            gov_class = GovernanceClass(workflow.governance_class)
            
            policy_result = policy_engine.evaluate(
                user=context.user,
                action_type="WORKFLOW_EXEC",
                governance_class=gov_class,
                tool_id=workflow.workflow_id
            )
            
            if not policy_result.is_allowed():
                if policy_result.decision.value == "REQUIRE_APPROVAL":
                    # Create approval request
                    approval_id = audit.create_approval_request(
                        user=context.user,
                        action_type="WORKFLOW_EXEC",
                        tool_id=workflow.workflow_id,
                        platform=intent.platform or "multi",
                        request_payload={"query": query, "entities": [e.to_dict() for e in entities]}
                    )
                    
                    return OrchestratorResult(
                        success=False,
                        requires_approval=True,
                        approval_id=approval_id,
                        error="This action requires approval",
                        intent=intent.to_dict(),
                        entities=[e.to_dict() for e in entities]
                    )
                else:
                    return OrchestratorResult(
                        success=False,
                        error=policy_result.reason,
                        intent=intent.to_dict()
                    )
            
            # Step 5: Execute Workflow
            context.log("Executing workflow...")
            
            # Build inputs from entities and query (use corrected query for better extraction)
            inputs = self._build_workflow_inputs(workflow, corrected_query, entities, context, platform=intent.platform)
            
            executor = self._get_workflow_executor()
            executor.set_log_callback(context.log)
            
            exec_result = executor.execute(
                workflow=workflow,
                inputs=inputs,
                credentials=context.credentials,
                user=context.user
            )
            
            # Step 5.5: Generate Chart Configuration
            # Skip chart generation for:
            # - Cross-platform queries (they have their own display format)
            # - Simple list queries (contacts, leads, accounts) - these are just data lookups
            skip_chart_workflows = ["customer_overview_cross_platform", "list_contacts", "list_leads", "list_accounts", "list_opportunities", "get_contact", "get_account", "create_contact", "create_record"]
            should_generate_chart = (
                exec_result.success and 
                exec_result.data and 
                workflow.workflow_id not in skip_chart_workflows and
                not any(skip in workflow.workflow_id for skip in ["list_contacts", "list_leads", "list_accounts", "list_opportunities", "get_contact", "get_account"])
            )
            
            chart_config = None
            if should_generate_chart:
                try:
                    from utils.openai_client import generate_chart_config
                    p_name = platform or "stripe" if "get_revenue" in workflow.workflow_id else "unknown"
                    # Debug logging
                    logger.info(f"[CHART DEBUG] Generating chart for query: {query}, platform: {p_name}")
                    logger.info(f"[CHART DEBUG] Data structure: {type(exec_result.data)}, keys: {exec_result.data.keys() if isinstance(exec_result.data, dict) else 'N/A (not dict)'}")
                    chart_config = generate_chart_config(query, exec_result.data, p_name)
                    if chart_config:
                        context.log(f"Chart config generated successfully: {chart_config.get('type')}")
                        logger.info(f"[CHART DEBUG] Chart config created: {chart_config.get('type')}")
                    else:
                        context.log("Chart config generation returned None")
                        logger.info("[CHART DEBUG] Chart config generation returned None")
                except Exception as e:
                    context.log(f"Failed to generate chart config: {e}")
                    import logging
                    logging.getLogger(__name__).exception(f"[CHART DEBUG] Chart generation exception: {e}")
            
            # Step 6: Audit Log
            elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
            
            audit.log_action(
                user=context.user,
                action_type="QUERY",
                governance_class=workflow.governance_class,
                workflow_id=workflow.workflow_id,
                request_payload={"query": query},
                response_summary={"success": exec_result.success},
                status="SUCCESS" if exec_result.success else "FAILED",
                error_message=exec_result.error,
                execution_time_ms=elapsed
            )
            
            intent_data = intent.to_dict()
            if inputs:
                intent_data['params'] = inputs
                
            return OrchestratorResult(
                success=exec_result.success,
                data=exec_result.data,
                error=exec_result.error,
                intent=intent_data,
                entities=[e.to_dict() for e in entities],
                workflow_used=workflow.workflow_id,
                execution_time_ms=elapsed,
                summary=exec_result.summary,
                chart=chart_config
            )
            
        except Exception as e:
            elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.exception("Query orchestration failed")
            
            return OrchestratorResult(
                success=False,
                error=str(e),
                execution_time_ms=elapsed
            )
    
    def execute_tool_direct(
        self,
        platform: str,
        tool_id: str,
        params: Dict[str, Any],
        context: OrchestratorContext
    ) -> OrchestratorResult:
        """
        Execute a tool directly without going through intent detection.
        
        Useful for follow-up actions or known tool invocations.
        
        Args:
            platform: Platform to execute on
            tool_id: Tool identifier
            params: Tool parameters
            context: Orchestration context
        
        Returns:
            OrchestratorResult with execution results
        """
        start_time = datetime.now()
        audit = self._get_audit_service()
        
        try:
            # Get governance class for policy check
            registry = self._get_connector_registry()
            connector = registry.get_connector(platform, context.credentials.get(platform, {}))
            gov_class = connector.get_governance_class(tool_id)
            
            # Policy check
            policy_engine = self._get_policy_engine()
            policy_result = policy_engine.evaluate(
                user=context.user,
                action_type="TOOL_EXEC",
                governance_class=gov_class,
                tool_id=tool_id,
                platform=platform,
                params=params
            )
            
            if not policy_result.is_allowed():
                return OrchestratorResult(
                    success=False,
                    error=policy_result.reason,
                    requires_approval=policy_result.decision.value == "REQUIRE_APPROVAL"
                )
            
            # Execute
            context.log(f"Executing {platform}.{tool_id}...")
            
            result = registry.execute(
                platform=platform,
                tool_id=tool_id,
                params=params,
                credentials=context.credentials.get(platform, {})
            )
            
            elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Audit
            audit.log_action(
                user=context.user,
                action_type="TOOL_EXEC",
                governance_class=gov_class.value,
                tool_id=tool_id,
                platform=platform,
                request_payload=params,
                status="SUCCESS" if result.success else "FAILED",
                error_message=result.error,
                execution_time_ms=elapsed
            )
            
            return OrchestratorResult(
                success=result.success,
                data=result.data,
                error=result.error,
                execution_time_ms=elapsed
            )
            
        except Exception as e:
            elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
            return OrchestratorResult(
                success=False,
                error=str(e),
                execution_time_ms=elapsed
            )
    
    def register_workflow(self, workflow):
        """Register a workflow definition."""
        self._workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered workflow: {workflow.workflow_id}")
    
    def load_workflows_from_directory(self, directory: str) -> int:
        """Load workflow definitions from YAML files."""
        import os
        from orchestrator.workflow_definition import WorkflowParser
        
        count = 0
        for filename in os.listdir(directory):
            if filename.endswith(('.yaml', '.yml')):
                filepath = os.path.join(directory, filename)
                try:
                    workflow = WorkflowParser.parse_file(filepath)
                    self.register_workflow(workflow)
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to load workflow {filepath}: {e}")
        
        return count
    
    def _extract_and_resolve_entities(self, query: str, resolver, context) -> List:
        """Extract entity references from query and resolve them."""
        # Simple extraction - look for quoted strings or capitalized phrases
        import re
        
        entities = []
        
        # Find quoted strings
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', query)
        for match in quoted:
            term = match[0] or match[1]
            resolved = resolver.resolve(term, user=context.user)
            if resolved:
                entities.append(resolved)
        
        return entities
    
    def _create_cross_platform_customer_workflow(self, query: str, context) -> Any:
        """
        Create a workflow for cross-platform customer queries (Salesforce + Stripe).
        Finds contact in Salesforce, then gets payments from Stripe.
        """
        import re
        from .workflow_definition import WorkflowDefinition, WorkflowStep, StepType, WorkflowInput, WorkflowOutput, OutputFormat
        
        context.log(f"Creating cross-platform workflow for query: {query}")
        
        # Extract person name from query - improved patterns
        # Pattern: "show me deatils and payements of Rohan robert from both stripe and salesforce"
        # We want to extract "Rohan robert" which comes after "of" and before "from"
        
        person_name = None
        
        # Pattern 1: Look for "of X from" or "of X in" where X is a capitalized name
        # This is the most reliable pattern for this query structure
        match = re.search(r'(?:of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:from|in|both)', query, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Filter out common words
            if candidate.lower() not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment', 'me', 'show', 'and', 'deatils', 'payements']:
                person_name = candidate
                context.log(f"Extracted person name using 'of X from' pattern: {person_name}")
        
        # Pattern 2: Look for capitalized word pairs that appear before "from both" or "from stripe/salesforce"
        if not person_name:
            match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:from|in)', query)
            if match:
                candidate = match.group(1).strip()
                if candidate.lower() not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment', 'deatils and', 'payements of']:
                    person_name = candidate
                    context.log(f"Extracted person name using 'X from' pattern: {person_name}")
        
        # Pattern 3: Find all capitalized word pairs and pick the one that's not a platform name
        if not person_name:
            # Find all sequences of capitalized words
            matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', query)
            for candidate in matches:
                candidate_lower = candidate.lower()
                # Skip if it's a platform name or common word
                if candidate_lower not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment', 'show me', 'and payments', 'deatils and', 'payements of']:
                    # Check if it appears before "from" or "in"
                    candidate_pos = query.lower().find(candidate_lower)
                    from_pos = query.lower().find('from', candidate_pos)
                    if from_pos > candidate_pos or from_pos == -1:
                        person_name = candidate
                        context.log(f"Extracted person name from capitalized word pair: {person_name}")
                        break
        
        # Pattern 4: Fallback - extract words between "of" and "from"
        if not person_name:
            # Try to extract text between "of" and "from"
            match = re.search(r'(?:of|for)\s+([^from]+?)\s+(?:from|both)', query, re.IGNORECASE)
            if match:
                text_between = match.group(1).strip()
                # Extract capitalized words from this text
                words = text_between.split()
                capitalized_words = [w for w in words if w and w[0].isupper() and len(w) > 2]
                if len(capitalized_words) >= 2:
                    # Take first two capitalized words
                    person_name = f"{capitalized_words[0]} {capitalized_words[1]}"
                    if person_name.lower() not in ['both', 'stripe', 'salesforce']:
                        context.log(f"Extracted person name from text between 'of' and 'from': {person_name}")
        
        # Pattern 5: Last resort - find any two consecutive capitalized words, skipping common ones
        if not person_name:
            words = query.split()
            for i, word in enumerate(words):
                if word and word[0].isupper() and len(word) > 2:
                    if i + 1 < len(words) and words[i+1] and words[i+1][0].isupper() and len(words[i+1]) > 2:
                        candidate = f"{word} {words[i+1]}"
                        candidate_lower = candidate.lower()
                        # Skip common phrases
                        if candidate_lower not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment', 'show me', 'and payments', 'deatils and', 'payements of', 'and payements']:
                            person_name = candidate
                            context.log(f"Extracted person name from consecutive capitalized words: {person_name}")
                            break
        
        context.log(f"Cross-platform query: Final extracted person name: {person_name}")
        
        if not person_name:
            # If we can't extract name, return None to trigger an error
            context.log("Warning: Could not extract person name from query")
            return None  # Will cause workflow creation to fail gracefully
        
        # Create workflow steps
        steps = [
            # Step 1: Find contact in Salesforce
            # The 'name' parameter will be automatically merged from inputs by workflow executor
            WorkflowStep(
                id="find_salesforce_contact",
                step_type=StepType.TOOL,
                tool_id="salesforce.list_contacts",
                params={"limit": 10},  # 'name' will be added from inputs automatically
                depends_on=[]
            ),
            # Step 2: Get Stripe data by email (depends on step 1)
            # Note: We'll handle email extraction in the executor since template interpolation is complex
            WorkflowStep(
                id="get_stripe_data",
                step_type=StepType.TOOL,
                tool_id="stripe.fetch_data_by_email",
                params={"email_from_step": "find_salesforce_contact"},
                depends_on=["find_salesforce_contact"]
            )
        ]
        
        workflow = WorkflowDefinition(
            workflow_id="customer_overview_cross_platform",
            version="1.0.0",
            name="Cross-Platform Customer Overview",
            description=f"Get details and payments for {person_name} from Salesforce and Stripe",
            inputs=[WorkflowInput(name="person_name", type="string", required=True, description=person_name or "Customer name")],
            steps=steps,
            output=WorkflowOutput(format=OutputFormat.TABLE),
            governance_class="READ"
        )
        
        return workflow
    
    def _create_tool_workflow(self, tool_id: str, platform: str):
        """Create a simple single-tool workflow."""
        from orchestrator.workflow_definition import (
            WorkflowDefinition, WorkflowStep, WorkflowOutput, StepType, OutputFormat
        )
        
        return WorkflowDefinition(
            workflow_id=f"auto_{tool_id}",
            name=f"Auto-generated workflow for {tool_id}",
            steps=[
                WorkflowStep(
                    id="main",
                    step_type=StepType.TOOL,
                    tool_id=tool_id if (platform and tool_id.startswith(f"{platform}.")) else (f"{platform}.{tool_id}" if platform else tool_id)
                )
            ],
            output=WorkflowOutput(format=OutputFormat.TABLE),
            governance_class="READ"
        )
    
    def _find_workflow(self, intent, entities) -> Optional[Any]:
        """Find a registered workflow matching the intent."""
        # For now, simple matching by intent type
        # Could be enhanced with semantic matching
        
        intent_type = intent.intent_type.value
        
        for workflow_id, workflow in self._workflows.items():
            # Check if workflow handles this intent type
            if hasattr(workflow, 'intent_types'):
                if intent_type in workflow.intent_types:
                    return workflow
        
        # No registered workflow found - create tool workflow if we have a tool
        if intent.tool_id:
            return self._create_tool_workflow(intent.tool_id, intent.platform)
        
        return None
    
    
    def _build_workflow_inputs(self, workflow, query: str, entities, context, platform: str = None) -> Dict:
        """Build workflow input parameters from query and entities."""
        import re
        
        inputs = {
            "query": query,
            "user_id": str(context.user.id) if hasattr(context.user, 'id') else None
        }
        
        # Special handling for cross-platform customer workflow
        if hasattr(workflow, 'workflow_id') and workflow.workflow_id == "customer_overview_cross_platform":
            # Extract person name from query - improved patterns
            # Pattern: "show me details and payments of Rohan robert from both stripe and salesforce"
            # We want to extract "Rohan robert" which comes after "of" and before "from"
            
            person_name = None
            
            # Pattern 1: Look for "of X from" or "of X in" where X is a capitalized name
            match = re.search(r'(?:of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:from|in|both)', query, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Filter out common words
                if candidate.lower() not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment', 'me', 'show', 'and']:
                    person_name = candidate
                    context.log(f"Extracted person_name using 'of X from' pattern: {person_name}")
            
            # Pattern 2: Look for capitalized word pairs that appear before "from both" or "from stripe/salesforce"
            if not person_name:
                match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:from|in)', query)
                if match:
                    candidate = match.group(1).strip()
                    if candidate.lower() not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment']:
                        person_name = candidate
                        context.log(f"Extracted person_name using 'X from' pattern: {person_name}")
            
            # Pattern 3: Find all capitalized word pairs and pick the one that's not a platform name
            if not person_name:
                # Find all sequences of capitalized words
                matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', query)
                for candidate in matches:
                    candidate_lower = candidate.lower()
                    # Skip if it's a platform name or common word
                    if candidate_lower not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment', 'show me', 'and payments']:
                        # Check if it appears before "from" or "in"
                        candidate_pos = query.lower().find(candidate_lower)
                        from_pos = query.lower().find('from', candidate_pos)
                        if from_pos > candidate_pos or from_pos == -1:
                            person_name = candidate
                            context.log(f"Extracted person_name from capitalized word pair: {person_name}")
                            break
            
            # Pattern 4: Fallback - extract words between "of" and "from" or before "from both"
            if not person_name:
                # Try to extract text between "of" and "from"
                match = re.search(r'(?:of|for)\s+([^from]+?)\s+(?:from|both)', query, re.IGNORECASE)
                if match:
                    text_between = match.group(1).strip()
                    # Extract capitalized words from this text
                    words = text_between.split()
                    capitalized_words = [w for w in words if w and w[0].isupper() and len(w) > 2]
                    if len(capitalized_words) >= 2:
                        # Take first two capitalized words
                        person_name = f"{capitalized_words[0]} {capitalized_words[1]}"
                        if person_name.lower() not in ['both', 'stripe', 'salesforce']:
                            context.log(f"Extracted person_name from text between 'of' and 'from': {person_name}")
            
            # Pattern 5: Last resort - find any two consecutive capitalized words
            if not person_name:
                words = query.split()
                for i, word in enumerate(words):
                    if word and word[0].isupper() and len(word) > 2:
                        if i + 1 < len(words) and words[i+1] and words[i+1][0].isupper() and len(words[i+1]) > 2:
                            candidate = f"{word} {words[i+1]}"
                            candidate_lower = candidate.lower()
                            if candidate_lower not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment', 'show me', 'and payments', 'deatils and', 'payements of']:
                                person_name = candidate
                                context.log(f"Extracted person_name from consecutive capitalized words: {person_name}")
                                break
            
            if person_name:
                inputs["person_name"] = person_name
                # Also add as 'name' for Salesforce tool parameter compatibility
                inputs["name"] = person_name
                context.log(f"Final person_name for workflow: {person_name}")
            else:
                # If we can't extract, use a default or the query itself
                context.log(f"Warning: Could not extract person_name from query: '{query}'")
                # Don't use the whole query - that would be wrong
                # Instead, return an error or try a different approach
                inputs["person_name"] = ""  # Empty string will cause validation error with helpful message
                inputs["name"] = ""
        
        # Add resolved entities as inputs
        for entity in entities:
            # Use entity type as key
            key = f"entity_{entity.entity_type}"
            inputs[key] = {
                "external_id": entity.external_id,
                "name": entity.canonical_name,
                "platform": entity.platform
            }
        
        # Extract platform from workflow/intent to use generate_query_params
        # Priority: explicit param > workflow_id > entities
        if not platform and hasattr(workflow, 'workflow_id'):
            # Try to extract platform from workflow_id (e.g., "stripe.list_invoices" -> "stripe")
            parts = workflow.workflow_id.split('.')
            if len(parts) > 0:
                # Avoid picking 'auto' from 'auto_list_deals'
                if parts[0] == 'auto' and len(parts) > 1:
                     # auto.list_deals? No, typically auto_list_deals
                     pass
                platform = parts[0]
        
        if not platform and entities:
            # Try to get platform from entities
            platform = entities[0].platform if entities else None
        
        # Use generate_query_params to extract filters from natural language query
        # Also add fallback regex extraction for common patterns
        # Fallback: Direct regex extraction for amount filters and period filters (works even if AI fails)
        query_lower = query.lower()
        amount_patterns = [
            r'amount\s*(?:is\s*)?(?:greater\s*than|more\s*than|above|over|>=|>)\s*\$?([0-9,]+)',
            r'(?:greater\s*than|more\s*than|above|over)\s*\$?([0-9,]+)',
            r'\$?([0-9,]+)\s*(?:or\s*more|and\s*above)',
        ]
        
        extracted_amount_gt = None
        for pattern in amount_patterns:
            match = re.search(pattern, query_lower)
            if match:
                amount_str = match.group(1).replace(',', '').strip()
                try:
                    extracted_amount_gt = float(amount_str)
                    logger.info(f"[QUERY PARAMS] Extracted amount_gt via regex: {extracted_amount_gt}")
                    break
                except ValueError:
                    continue
        
        # Extract period filters for "recent" queries
        extracted_period = None
        extracted_limit = None
        extracted_product_name = None
        extracted_customer_name = None
        
        # Extract customer name from various patterns
        customer_name_patterns = [
            # Quoted patterns (highest priority)
            r'(?:create|add|new|make|details?|information|find)\s+(?:contact|person|lead)?\s*[\'"]([^\'"]+)[\'"]',
            
            # Action + Name patterns
            r'(?:details?|information|show|give\s+me|get|find|number|phone|create|add|new|make)\s+(?:for\s+|of\s+|about\s+|a\s+|an\s+)?(?:contact\s+|person\s+|lead\s+)?([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)?)',
            r'(?:for|of)\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)?)',
            r'\b([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)?)\s+(?:in|from|at)',
            r'(?:create|add|new|make)\s+(?:contact|person|lead)?\s*([a-z]+(?:\s+[a-z]+)?)', # lowercase fallback for creation
        ]
        
        # Extract account/company name patterns
        account_patterns = [
            r'(?:at|for|in|company)\s+[\'"]([^\'"]+)[\'"]', # Quoted company
            r'(?:at|company)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', # Unquoted Company
        ]
        
        extracted_account_name = None
        for pattern in account_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                extracted_account_name = match.group(1).strip()
                logger.info(f"[QUERY PARAMS] Extracted account_name via regex: '{extracted_account_name}'")
                break
        
        # Extract job title patterns
        title_patterns = [
            r'(?:with\s+)?(?:title|job|role|position|as)\s+[\'"]([^\'"]+)[\'"]',
            r'(?:with\s+)?(?:title|job|role|position|as)\s+(?:a\s+|an\s+)?([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)?)',
        ]
        
        extracted_title = None
        for pattern in title_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                extracted_title = match.group(1).strip()
                logger.info(f"[QUERY PARAMS] Extracted title via regex: '{extracted_title}'")
                break
        
        stop_words = {'customer', 'details', 'information', 'show', 'give', 'me', 'get', 'for', 'of', 'stripe', 'salesforce', 'zoho', 'everything', 'list', 'all', 'deals', 'invoices', 'revenue', 'leads', 'accounts', 'contacts', 'campaigns', 'contact', 'account', 'deal', 'lead', 'in', 'from', 'and', 'with', 'about'}
        
        for pattern in customer_name_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                clean_words = [w for w in candidate.split() if w.lower() not in stop_words]
                clean_name = " ".join(clean_words).strip()
                if len(clean_name) >= 3 and clean_name.lower() not in stop_words:
                    extracted_customer_name = clean_name
                    logger.info(f"[QUERY PARAMS] Extracted customer_name via regex: '{extracted_customer_name}'")
                    break
        
        # Extract product name from "revenue for X" or "revenue from X" patterns
        product_patterns = [
            r'revenue\s+(?:for|from|of)\s+([a-z]+(?:\s+[a-z]+)?)',
            r'show\s+revenue\s+(?:for|from|of)\s+([a-z]+(?:\s+[a-z]+)?)',
            r'revenue\s+([a-z]+(?:\s+[a-z]+)?)',
        ]
        for pattern in product_patterns:
            match = re.search(pattern, query_lower)
            if match:
                candidate = match.group(1).strip()
                # Filter out common words
                if candidate.lower() not in ['this', 'that', 'the', 'a', 'an', 'all', 'me', 'my', 'week', 'month', 'year', 'today']:
                    extracted_product_name = candidate
                    logger.info(f"[QUERY PARAMS] Extracted product_name via regex: {extracted_product_name}")
                    break
        

        
        if 'recent' in query_lower:
            extracted_period = 'week'  # Recent = last week
            extracted_limit = 20  # Limit to 20 most recent
            logger.info(f"[QUERY PARAMS] Detected 'recent' keyword, setting period: week, limit: 20")
        elif 'this week' in query_lower or 'last week' in query_lower:
            extracted_period = 'week'
            logger.info(f"[QUERY PARAMS] Extracted period via regex: week")
        elif 'this month' in query_lower:
            extracted_period = 'month'
            logger.info(f"[QUERY PARAMS] Extracted period via regex: month")
        elif 'today' in query_lower:
            extracted_period = 'today'
            logger.info(f"[QUERY PARAMS] Extracted period via regex: today")
        
        if platform:
            try:
                from utils.openai_client import generate_query_params
                logger.info(f"[QUERY PARAMS] Calling generate_query_params for query: '{query}', platform: '{platform}'")
                
                query_params = generate_query_params(query, platform)
                logger.info(f"[QUERY PARAMS] Raw response from generate_query_params: {query_params}")
                
                if query_params:
                    # Extract filters - could be in 'filters' key or at root level
                    filters = query_params.get('filters', {})
                    if not filters and isinstance(query_params, dict):
                        # If no 'filters' key, check if params are at root (like amount_gt directly)
                        filter_keys = ['amount_gt', 'stage', 'city', 'location', 'email', 'status', 'limit']
                        filters = {k: v for k, v in query_params.items() if k in filter_keys}
                    
                    # Use regex-extracted value if AI didn't extract it
                    if extracted_amount_gt is not None and 'amount_gt' not in filters:
                        filters['amount_gt'] = extracted_amount_gt
                        logger.info(f"[QUERY PARAMS] Added regex-extracted amount_gt to filters: {extracted_amount_gt}")
                    
                    # Merge regex-extracted period/limit/product_name if AI didn't extract them
                    if extracted_period and 'period' not in filters:
                        filters['period'] = extracted_period
                        logger.info(f"[QUERY PARAMS] Added regex-extracted period: {extracted_period}")
                    if extracted_limit and 'limit' not in filters:
                        filters['limit'] = extracted_limit
                        logger.info(f"[QUERY PARAMS] Added regex-extracted limit: {extracted_limit}")
                    if extracted_product_name and 'product_name' not in filters and 'product' not in filters:
                        filters['product_name'] = extracted_product_name
                        logger.info(f"[QUERY PARAMS] Added regex-extracted product_name: {extracted_product_name}")
                    
                    if extracted_customer_name:
                        filters['name'] = extracted_customer_name
                        logger.info(f"[QUERY PARAMS] Added regex-extracted customer name to filters: '{extracted_customer_name}'")
                    elif filters.get('name') or filters.get('customer_name'):
                        # AI might have extracted it
                        logger.info(f"[QUERY PARAMS] Using AI-extracted customer name: '{filters.get('name') or filters.get('customer_name')}'")
                    
                    if extracted_account_name:
                        filters['account'] = extracted_account_name
                        logger.info(f"[QUERY PARAMS] Added regex-extracted account name to filters: '{extracted_account_name}'")
                    elif filters.get('account') or filters.get('company') or filters.get('account_name'):
                        logger.info(f"[QUERY PARAMS] Using AI-extracted account name: '{filters.get('account') or filters.get('company') or filters.get('account_name')}'")
                    
                    if extracted_title:
                        filters['title'] = extracted_title
                        logger.info(f"[QUERY PARAMS] Added regex-extracted title to filters: '{extracted_title}'")
                    elif filters.get('title') or filters.get('job_title'):
                        logger.info(f"[QUERY PARAMS] Using AI-extracted title: '{filters.get('title') or filters.get('job_title')}'")
                    
                    # Use regex-extracted amount_gt if AI didn't extract it
                    if extracted_amount_gt is not None and 'amount_gt' not in filters:
                        filters['amount_gt'] = extracted_amount_gt
                        logger.info(f"[QUERY PARAMS] Added regex-extracted amount_gt: {extracted_amount_gt}")
                    
                    if filters:
                        # Merge filters into inputs
                        inputs.update(filters)
                        # Also store as 'filters' key for workflow executor
                        inputs['filters'] = filters
                        logger.info(f"[QUERY PARAMS] Extracted and merged filters for {platform}: {filters}")
                        logger.info(f"[QUERY PARAMS] Final inputs: {inputs}")
                    elif extracted_amount_gt is not None or extracted_period is not None or extracted_customer_name:
                        # If AI didn't extract filters but regex did, use regex result
                        filters = {}
                        if extracted_amount_gt is not None:
                            filters['amount_gt'] = extracted_amount_gt
                        if extracted_customer_name:
                            filters['name'] = extracted_customer_name
                            logger.info(f"[QUERY PARAMS] Using regex-extracted customer name in fallback: '{extracted_customer_name}'")
                        if extracted_period is not None:
                            filters['period'] = extracted_period
                        if extracted_limit is not None:
                            filters['limit'] = extracted_limit
                        inputs.update(filters)
                        inputs['filters'] = filters
                        logger.info(f"[QUERY PARAMS] Using regex-extracted filters: {filters}")
                    else:
                        logger.warning(f"[QUERY PARAMS] No filters found in query_params: {query_params}")
            except Exception as e:
                import traceback
                logger.exception(f"[QUERY PARAMS] Failed to generate query params: {e}\n{traceback.format_exc()}")
                # Fallback to regex extraction if AI fails
                filters = {}
                if extracted_amount_gt is not None:
                    filters['amount_gt'] = extracted_amount_gt
                if extracted_period is not None:
                    filters['period'] = extracted_period
                if extracted_limit is not None:
                    filters['limit'] = extracted_limit
                if extracted_product_name is not None:
                    filters['product_name'] = extracted_product_name
                if extracted_customer_name:
                    filters['name'] = extracted_customer_name
                if filters:
                    inputs.update(filters)
                    inputs['filters'] = filters
                    logger.info(f"[QUERY PARAMS] Using regex-extracted filters (AI failed): {filters}")
                    logger.info(f"[QUERY PARAMS] Using regex fallback filters after AI failure: {filters}")
        
        # FINAL FALLBACK: If "filters" is still not populated in inputs (meaning AI returned empty and regex fallback in try/except didn't run or didn't populate),
        # check if we have regex extractions matching our needs.
        if 'filters' not in inputs and (extracted_amount_gt is not None or extracted_customer_name or extracted_account_name or extracted_title or extracted_period):
            filters = {}
            if extracted_amount_gt is not None:
                filters['amount_gt'] = extracted_amount_gt
            if extracted_period:
                filters['period'] = extracted_period
            if extracted_customer_name:
                filters['name'] = extracted_customer_name
            if extracted_account_name:
                filters['account'] = extracted_account_name
            if extracted_title:
                filters['title'] = extracted_title
            if extracted_limit:
                 filters['limit'] = extracted_limit
            
            if filters:
                inputs.update(filters)
                inputs['filters'] = filters
                logger.info(f"[QUERY PARAMS] Final Fallback: Added regex-extracted filters: {filters}")
        
        elif extracted_amount_gt is not None:
            # If platform not detected but we extracted amount, still add it
            filters = {'amount_gt': extracted_amount_gt}
            inputs.update(filters)
            inputs['filters'] = filters
            logger.info(f"[QUERY PARAMS] Platform not detected, using regex-extracted filters: {filters}")
        
        # Extract repo name for GitHub queries (manual extraction as fallback)
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in ['commit', 'issue', 'pr', 'pull request', 'repo']):
            # Pattern 1: "of <repo_name>" or "from <repo_name>" or "in <repo_name>"
            repo_patterns = [
                r'\bof\s+([a-zA-Z0-9_\-\.\/]+)',
                r'\bfrom\s+([a-zA-Z0-9_\-\.\/]+)',
                r'\bin\s+([a-zA-Z0-9_\-\.\/]+)\b',
                r'\bfor\s+([a-zA-Z0-9_\-\.\/]+)',
                r'\brepo\s+([a-zA-Z0-9_\-\.\/]+)',
            ]
            
            for pattern in repo_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    repo_name = match.group(1).strip()
                    # Filter out common words that aren't repo names
                    if repo_name.lower() not in ['the', 'a', 'my', 'all', 'recent', 'latest', 'last']:
                        inputs['repo_name'] = repo_name
                        break
        
        # Extract Trello parameters (board_name, list_name, card name) - Manual extraction fallback
        if any(keyword in query_lower for keyword in ['trello', 'board', 'card']):
            # Extract list name FIRST (before board) to avoid conflicts
            # Extract list name - patterns: "in To Do list", "inside To Do", "To Do card", "inside To Do card"
            # Order matters: more specific patterns first, and extract BEFORE board to avoid conflicts
            trello_list_patterns = [
                r'\b(?:in|inside)\s+(?:the\s+)?([A-Z][a-zA-Z\s]+?)\s+(?:list|card)(?:\s+inside|\s+in|\s+on|$)',  # "in To Do list inside" or "in To Do list"
                r'\b([A-Z][a-zA-Z\s]+?)\s+(?:list|card)(?:\s+inside|\s+in|\s+on|$)',  # "To Do list inside" or "To Do list"
                r'\binside\s+([A-Z][a-zA-Z\s]+?)(?:\s+card|\s+list|$)',  # "inside To Do card"
                r'\b(?:list|card)\s+([A-Z][a-zA-Z\s]+?)(?:\s+in|\s+on|$)',  # "list To Do in"
            ]
            for pattern in trello_list_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    list_candidate = match.group(1).strip()
                    # Filter out common words - be more strict
                    # Don't accept if it contains board-related words
                    if (list_candidate.lower() not in ['trello', 'the', 'a', 'my', 'cards', 'board', 'show', 'me', 'create', 'add', 'new', 'testing', 'inside', 'in', 'on'] and
                        'board' not in list_candidate.lower() and
                        'testing' not in list_candidate.lower()):
                        # Remove "card" or "list" if it's part of the name
                        if list_candidate.lower().endswith(' card'):
                            list_candidate = list_candidate[:-5].strip()
                        if list_candidate.lower().endswith(' list'):
                            list_candidate = list_candidate[:-5].strip()
                        # Remove trailing "card" or "list" words
                        list_candidate = re.sub(r'\s+(card|list)\s*$', '', list_candidate, flags=re.IGNORECASE).strip()
                        
                        if list_candidate:  # Only add if we have a valid name
                            inputs['list_name'] = list_candidate
                            if 'filters' not in inputs: inputs['filters'] = {}
                            inputs['filters']['list_name'] = list_candidate
                            logger.info(f"[QUERY PARAMS] Extracted Trello list_name via regex: {list_candidate}")
                            break
            
            # Extract board name - patterns: "in testing board", "inside testing board", "on testing board"
            # IMPORTANT: Match AFTER list extraction to avoid capturing list names
            # Match the LAST occurrence of "inside X board" to get the board name (not list name)
            # Find all matches and take the last one (which should be the board, not the list)
            all_matches = []
            # Pattern for "inside X board" or "in X board" - but stop before "in trello"
            # Improved pattern that explicitly excludes "in trello" from capture
            for match in re.finditer(r'\b(?:inside|in|on|for)\s+([a-zA-Z0-9_\-\s]+?)\s+board(?:\s+in\s+trello)?\b', query, re.IGNORECASE):
                board_candidate = match.group(1).strip()
                # Filter out "in trello" if it got captured
                if board_candidate.lower().endswith(' in trello'):
                    board_candidate = board_candidate[:-10].strip()
                # Remove "in trello" if it appears anywhere in the candidate
                board_candidate = re.sub(r'\s+in\s+trello\s*', '', board_candidate, flags=re.IGNORECASE).strip()
                # Don't add if it's just "in trello" or similar invalid values
                if (board_candidate.lower() not in ['trello', 'in', 'the', 'a', ''] and 
                    'in trello' not in board_candidate.lower() and
                    len(board_candidate) > 0):
                    all_matches.append((match.start(), board_candidate))
            
            # Also try other patterns
            other_patterns = [
                r'\bboard\s+([a-zA-Z0-9_\-\s]+?)(?:\s+in\s+trello|$)',  # "board testing"
                r'\bfrom\s+(?:the\s+)?(?:board\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+board|\s+in\s+trello|$)',  # "from testing board"
                r'\bfor\s+([a-zA-Z0-9_\-\s]+?)\s+board(?:\s+in\s+trello)?\b',  # "for testing board"
            ]
            for pattern in other_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    board_candidate = match.group(1).strip()
                    # Filter out "in trello" if it got captured
                    if board_candidate.lower().endswith(' in trello'):
                        board_candidate = board_candidate[:-10].strip()
                    # Don't add if it's just "in trello" or similar
                    if board_candidate.lower() not in ['trello', 'in', 'the', 'a']:
                        all_matches.append((match.start(), board_candidate))
            
            # Sort by position and take the last match (rightmost in query)
            if all_matches:
                all_matches.sort(key=lambda x: x[0], reverse=True)
                board_candidate = all_matches[0][1]
                # Filter out common words/artifacts - be more strict
                # Don't accept if it contains list-related words (like "To Do", "list")
                # Also check if we already extracted a list_name - if so, make sure board doesn't contain it
                extracted_list = inputs.get('list_name', '').lower()
                if (board_candidate.lower() not in ['trello', 'the', 'a', 'my', 'cards', 'list', 'show', 'me', 'inside', 'in', 'on'] and
                    'list' not in board_candidate.lower() and
                    'to do' not in board_candidate.lower() and
                    'card' not in board_candidate.lower() and
                    (not extracted_list or extracted_list not in board_candidate.lower())):
                    # Clean up "testing in trello" -> "testing"
                    if board_candidate.lower().endswith(' in trello'):
                        board_candidate = board_candidate[:-10].strip()
                    # Remove trailing "board" word if present
                    board_candidate = re.sub(r'\s+board\s*$', '', board_candidate, flags=re.IGNORECASE).strip()
                    # Remove any trailing list/card words
                    board_candidate = re.sub(r'\s+(list|card)\s*$', '', board_candidate, flags=re.IGNORECASE).strip()
                    
                    if board_candidate:  # Only add if we have a valid name
                        inputs['board_name'] = board_candidate
                        # Also add to filters key
                        if 'filters' not in inputs: inputs['filters'] = {}
                        inputs['filters']['board_name'] = board_candidate
                        logger.info(f"[QUERY PARAMS] Extracted Trello board_name via regex (last match): {board_candidate}")
            
            # Extract list name - patterns: "in To Do list", "inside To Do", "To Do card", "inside To Do card"
            trello_list_patterns = [
                r'\b(?:in|inside)\s+(?:the\s+)?([A-Z][a-zA-Z\s]+?)\s+(?:list|card)',
                r'\b([A-Z][a-zA-Z\s]+?)\s+(?:list|card)',
                r'\b(?:list|card)\s+([A-Z][a-zA-Z\s]+?)(?:\s+in|\s+on|$)',
                r'\binside\s+([A-Z][a-zA-Z\s]+?)(?:\s+card|\s+list|$)',  # "inside To Do card"
            ]
            for pattern in trello_list_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    list_candidate = match.group(1).strip()
                    # Filter out common words - be more strict
                    # Don't accept if it contains board-related words
                    if (list_candidate.lower() not in ['trello', 'the', 'a', 'my', 'cards', 'board', 'show', 'me', 'create', 'add', 'new', 'testing', 'inside', 'in', 'on'] and
                        'board' not in list_candidate.lower() and
                        'testing' not in list_candidate.lower()):
                        # Remove "card" or "list" if it's part of the name
                        if list_candidate.lower().endswith(' card'):
                            list_candidate = list_candidate[:-5].strip()
                        if list_candidate.lower().endswith(' list'):
                            list_candidate = list_candidate[:-5].strip()
                        # Remove trailing "card" or "list" words
                        list_candidate = re.sub(r'\s+(card|list)\s*$', '', list_candidate, flags=re.IGNORECASE).strip()
                        
                        if list_candidate:  # Only add if we have a valid name
                            inputs['list_name'] = list_candidate
                            if 'filters' not in inputs: inputs['filters'] = {}
                            inputs['filters']['list_name'] = list_candidate
                            logger.info(f"[QUERY PARAMS] Extracted Trello list_name via regex: {list_candidate}")
                            break
            
            # Extract card name for write operations (create/delete) - if not specified, will use default
            if any(word in query_lower for word in ['create', 'add', 'new', 'make', 'delete', 'remove']):
                card_name_patterns = [
                    r'card\s+called\s+[\'"]([^\'"]+)[\'"]',  # "card called 'My Task'" - captures quoted name
                    r'card\s+called\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s+in|\s+inside|\s+on|$)',  # "card called My Task in" - captures unquoted name
                    r'(?:create|delete|remove|add|new)\s+(?:a\s+)?card\s+[\'"]([^\'"]+)[\'"]',  # "create a card 'My Task'" - captures quoted name
                    r'(?:create|delete|remove|add|new)\s+(?:a\s+)?card\s+called\s+[\'"]([^\'"]+)[\'"]',  # "create a card called 'My Task'" - captures quoted name
                    r'card\s+[\'"]([^\'"]+)[\'"]\s+(?:in|inside|on)',  # "card 'My Task' in" - captures quoted name
                    r'(?:create|delete|remove|add|new)\s+(?:a\s+)?card\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s+in|\s+inside|\s+on|$)',  # "create card My Task in" - captures unquoted name
                ]
                for pattern in card_name_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        card_candidate = match.group(1).strip()
                        # Filter out common words and make sure we have a real name
                        if (card_candidate.lower() not in ['a', 'the', 'card', 'in', 'inside', 'on', 'called', 'create', 'add', 'new', 'make'] and
                            len(card_candidate) > 1):  # At least 2 characters
                            inputs['name'] = card_candidate
                            if 'filters' not in inputs: inputs['filters'] = {}
                            inputs['filters']['name'] = card_candidate
                            logger.info(f"[QUERY PARAMS] Extracted Trello card name via regex: {card_candidate}")
                            break
        
        return inputs

    def _handle_knowledge_query(self, query: str, context: OrchestratorContext) -> OrchestratorResult:
        """
        Handle a knowledge query by retrieving documents and synthesizing an answer.
        For Trello-specific questions, provides helpful answers about workflows and best practices.
        """
        context.log(f"Handling knowledge query: {query}")
        query_lower = query.lower()
        
        # Check for Trello-specific knowledge questions
        trello_knowledge_base = {
            "move_card_done": {
                "patterns": [r'move.*card.*done', r'when.*move.*done', r'when.*should.*move.*done'],
                "answer": """Move a card to 'Done' when:

✓ Task is fully completed and all acceptance criteria are met
✓ Code is reviewed and merged (if applicable)
✓ Documentation is updated
✓ No pending reviews or follow-up tasks

**Quick tip:** Review checklists and related cards before moving to Done."""
            },
            "default_trello": {
                "answer": """**Trello Best Practices:**

• Move cards to Done when all work is complete and verified
• Use labels, due dates, and checklists to organize tasks
• Keep lists focused (To Do → In Progress → Review → Done)
• Assign team members and use comments for collaboration

Ask me specific questions about Trello workflows!"""
            }
        }
        
        # Check if it's a specific Trello knowledge question
        if any(keyword in query_lower for keyword in ['trello', 'board', 'card', 'list']):
            # Check for specific patterns
            if re.search(r'move.*card.*done|when.*move.*done|when.*should.*move.*done', query_lower):
                answer = trello_knowledge_base["move_card_done"]["answer"]
                return OrchestratorResult(
                    success=True,
                    data=[{"answer": answer, "type": "knowledge", "topic": "Trello Workflow"}],
                    intent={"intent_type": "KNOWLEDGE_QUERY", "tool_id": "trello_knowledge"},
                    summary=answer.split('\n')[0] if answer else "Trello workflow guidance",
                    workflow_used="trello_knowledge"
                )
            else:
                # Try RAG search first, then fallback to default answer
                try:
                    # 1. Embed query
                    from rag.embeddings import get_embeddings
                    embeddings = get_embeddings()
                    query_vec = embeddings.embed_for_query(query)
                    
                    # 2. Search Chroma
                    from rag.chroma_client import get_chroma_client
                    chroma = get_chroma_client()
                    collection = chroma.get_or_create_collection("documents")
                    
                    results = collection.query(
                        query_embeddings=[query_vec],
                        n_results=3,
                        include=["documents", "metadatas", "distances"]
                    )
                    
                    if results['ids'] and results['ids'][0]:
                        # Found relevant documents - synthesize answer
                        context_text = ""
                        sources = set()
                        
                        for i, doc_text in enumerate(results['documents'][0]):
                            meta = results['metadatas'][0][i]
                            source_title = meta.get('title', 'Unknown Source')
                            sources.add(source_title)
                            context_text += f"Source: {source_title}\nContent: {doc_text}\n\n"
                        
                        # Synthesize Answer
                        from utils.openai_client import get_client, get_model_name
                        client = get_client()
                        
                        # Detect platform from query and context
                        query_lower = query.lower()
                        detected_platform = None
                        if any(kw in query_lower for kw in ['payment', 'invoice', 'charge', 'refund', 'stripe', 'billing', 'subscription']):
                            detected_platform = 'Stripe'
                        elif any(kw in query_lower for kw in ['lead', 'opportunity', 'salesforce', 'crm', 'pipeline']):
                            detected_platform = 'Salesforce'
                        elif any(kw in query_lower for kw in ['pr', 'pull request', 'commit', 'github', 'repo', 'merge']):
                            detected_platform = 'GitHub'
                        elif any(kw in query_lower for kw in ['deal', 'zoho', 'contact']):
                            detected_platform = 'Zoho'
                        elif any(kw in query_lower for kw in ['trello', 'board', 'card', 'list']):
                            detected_platform = 'Trello'
                        
                        # Check for platform mismatch
                        context_platforms = set()
                        # Platform name mapping for proper capitalization
                        platform_name_map = {
                            'github': 'GitHub',
                            'stripe': 'Stripe',
                            'trello': 'Trello',
                            'salesforce': 'Salesforce',
                            'zoho': 'Zoho'
                        }
                        for meta in results['metadatas'][0]:
                            platform = meta.get('platform', '').lower()
                            if platform:
                                context_platforms.add(platform_name_map.get(platform, platform.capitalize()))
                        
                        platform_note = ""
                        if detected_platform and context_platforms:
                            if detected_platform not in context_platforms and len(context_platforms) == 1:
                                platform_note = f"\n\nIMPORTANT: The user's question mentions '{detected_platform}', but the knowledge base content is about {', '.join(context_platforms)}. You MUST start your answer by clarifying that this is a {', '.join(context_platforms)} concept, NOT a {detected_platform} concept. Then provide the answer from the context."
                        
                        # Also check if query explicitly mentions wrong platform
                        if 'trello' in query_lower and context_platforms and 'Trello' not in context_platforms:
                            platform_note += f"\n\nCRITICAL: The user asked about Trello, but payment retries are a {', '.join(context_platforms)} concept. Start your answer by stating: 'Payment retries are a {', '.join(context_platforms)} concept, not Trello.'"
                        
                        system_prompt = """You are a helpful assistant. Answer the user's question based on the provided context.

FORMATTING RULES (CRITICAL - Always use proper markdown):
1. Use ## for main sections (e.g., ## Steps, ## Best Practices)
2. Use **bold** for key terms and section headers
3. Use bullet points (-) for lists
4. Use numbered lists (1., 2., 3.) for sequential steps
5. Use code blocks (```bash or ```) for commands
6. Use `backticks` for inline code or commands
7. Structure: Brief intro → ## Section → Bullet/Numbered list

CONTENT RULES:
- Be VERY concise (under 150 words)
- Get straight to the point
- Skip unnecessary explanations
- Focus on actionable steps
- If platform mismatch, clarify briefly at start"""
                        
                        response = client.chat.completions.create(
                            model=get_model_name(),
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {query}{platform_note}"}
                            ],
                            temperature=0.2,
                            max_tokens=300
                        )
                        
                        answer = response.choices[0].message.content
                        
                        return OrchestratorResult(
                            success=True,
                            data=[{"answer": answer, "sources": list(sources), "type": "knowledge"}],
                            intent={"intent_type": "KNOWLEDGE_QUERY"},
                            summary=answer.split('\n')[0] if answer else "Trello guidance",
                            workflow_used="knowledge_search"
                        )
                except Exception as e:
                    logger.warning(f"RAG search failed, using default answer: {e}")
                
                # Fallback to default Trello answer
                answer = trello_knowledge_base["default_trello"]["answer"]
                return OrchestratorResult(
                    success=True,
                    data=[{"answer": answer, "type": "knowledge", "topic": "Trello"}],
                    intent={"intent_type": "KNOWLEDGE_QUERY", "tool_id": "trello_knowledge"},
                    summary="Trello workflow guidance",
                    workflow_used="trello_knowledge"
                )
        
        # General knowledge query - use RAG
        try:
            # 1. Embed query
            from rag.embeddings import get_embeddings
            embeddings = get_embeddings()
            query_vec = embeddings.embed_for_query(query)
            
            # 2. Search Chroma
            from rag.chroma_client import get_chroma_client
            chroma = get_chroma_client()
            collection = chroma.get_or_create_collection("documents")
            
            results = collection.query(
                query_embeddings=[query_vec],
                n_results=3,
                include=["documents", "metadatas", "distances"]
            )
            
            if not results['ids'] or not results['ids'][0]:
                # Check if query mentions a platform mismatch
                query_lower = query.lower()
                platform_hint = ""
                if any(kw in query_lower for kw in ['payment', 'invoice', 'charge', 'refund', 'stripe', 'billing']):
                    platform_hint = " Note: Payment-related questions are typically about Stripe, not Trello."
                elif any(kw in query_lower for kw in ['lead', 'opportunity', 'salesforce', 'crm', 'pipeline']):
                    platform_hint = " Note: Lead and sales questions are typically about Salesforce, not Trello."
                elif any(kw in query_lower for kw in ['pr', 'pull request', 'commit', 'github', 'repo']):
                    platform_hint = " Note: Code-related questions are typically about GitHub, not Trello."
                
                error_msg = "I couldn't find any relevant information in the knowledge base."
                if platform_hint:
                    error_msg += platform_hint
                
                return OrchestratorResult(
                    success=False,
                    error=error_msg,
                    intent={"intent_type": "KNOWLEDGE_QUERY"}
                )
            
            # 3. Construct Context
            context_text = ""
            sources = set()
            
            for i, doc_text in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                source_title = meta.get('title', 'Unknown Source')
                sources.add(source_title)
                context_text += f"Source: {source_title}\nContent: {doc_text}\n\n"
            
            # 4. Synthesize Answer
            from utils.openai_client import get_client, get_model_name
            client = get_client()
            
            # Detect platform from query
            query_lower = query.lower()
            detected_platform = None
            if any(kw in query_lower for kw in ['payment', 'invoice', 'charge', 'refund', 'stripe', 'billing', 'subscription']):
                detected_platform = 'Stripe'
            elif any(kw in query_lower for kw in ['lead', 'opportunity', 'salesforce', 'crm', 'pipeline']):
                detected_platform = 'Salesforce'
            elif any(kw in query_lower for kw in ['pr', 'pull request', 'commit', 'github', 'repo', 'merge']):
                detected_platform = 'GitHub'
            elif any(kw in query_lower for kw in ['deal', 'zoho', 'contact']):
                detected_platform = 'Zoho'
            elif any(kw in query_lower for kw in ['trello', 'board', 'card', 'list']):
                detected_platform = 'Trello'
            
            # Check for platform mismatch
            context_platforms = set()
            # Platform name mapping for proper capitalization
            platform_name_map = {
                'github': 'GitHub',
                'stripe': 'Stripe',
                'trello': 'Trello',
                'salesforce': 'Salesforce',
                'zoho': 'Zoho'
            }
            for meta in results['metadatas'][0]:
                platform = meta.get('platform', '').lower()
                if platform:
                    context_platforms.add(platform_name_map.get(platform, platform.capitalize()))
            
            platform_note = ""
            if detected_platform and context_platforms:
                if detected_platform not in context_platforms and len(context_platforms) == 1:
                    platform_note = f"\n\nIMPORTANT: The user's question mentions '{detected_platform}', but the knowledge base content is about {', '.join(context_platforms)}. You MUST clarify this in your answer. Start your answer by stating that this is a {', '.join(context_platforms)} concept, not a {detected_platform} concept. Then provide the answer from the context."
            
            # Also check if query mentions wrong platform in the question itself
            query_platforms_mentioned = []
            if 'trello' in query_lower:
                query_platforms_mentioned.append('Trello')
            if 'stripe' in query_lower:
                query_platforms_mentioned.append('Stripe')
            if 'salesforce' in query_lower:
                query_platforms_mentioned.append('Salesforce')
            if 'github' in query_lower:
                query_platforms_mentioned.append('GitHub')
            if 'zoho' in query_lower:
                query_platforms_mentioned.append('Zoho')
            
            if query_platforms_mentioned and context_platforms:
                for qp in query_platforms_mentioned:
                    if qp not in context_platforms:
                        platform_note += f"\n\nIMPORTANT: The user mentioned '{qp}' in their question, but the answer is about {', '.join(context_platforms)}. Clarify that {qp} is not the correct platform for this question."
            
            system_prompt = """You are a helpful assistant. Answer the user's question based ONLY on the provided context.

FORMATTING RULES (CRITICAL - Always use proper markdown):
1. Use ## for main sections (e.g., ## Steps, ## Best Practices)
2. Use **bold** for key terms and section headers
3. Use bullet points (-) for lists
4. Use numbered lists (1., 2., 3.) for sequential steps
5. Use code blocks (```bash or ```) for commands
6. Use `backticks` for inline code or commands
7. Structure: Brief intro → ## Section → Bullet/Numbered list

CONTENT RULES:
- Be VERY concise (under 150 words)
- Get straight to the point
- Skip unnecessary explanations
- Focus on actionable steps
- If platform mismatch, clarify briefly at start"""
            
            response = client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {query}{platform_note}"}
                ],
                temperature=0.2,
                max_tokens=300
            )
            
            answer = response.choices[0].message.content
            
            return OrchestratorResult(
                success=True,
                data=[{"answer": answer, "sources": list(sources), "type": "knowledge", "topic": "Knowledge Base"}],
                intent={"intent_type": "KNOWLEDGE_QUERY"},
                summary=answer.split('\n')[0] if answer else "Knowledge base answer",
                workflow_used="knowledge_search"
            )
            
        except Exception as e:
            logger.exception("Knowledge query processing failed")
            return OrchestratorResult(
                success=False,
                error=f"Error processing knowledge query: {str(e)}",
                intent={"intent_type": "KNOWLEDGE_QUERY"}
            )


# Singleton instance
_query_orchestrator = None

def get_query_orchestrator() -> QueryOrchestrator:
    """Get the default query orchestrator instance."""
    global _query_orchestrator
    if _query_orchestrator is None:
        _query_orchestrator = QueryOrchestrator()
    return _query_orchestrator
