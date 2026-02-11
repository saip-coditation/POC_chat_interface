"""
Audit Service

Provides logging and tracking of all platform actions.
Integrates with the Audit models for persistent storage.
"""

import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps

from connectors.base import GovernanceClass

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for recording audit logs.
    
    All actions executed through the platform are logged here
    for compliance, debugging, and analytics.
    """
    
    def __init__(self):
        """Initialize the audit service."""
        self._session_id = None
    
    def start_session(self) -> str:
        """Start a new audit session."""
        self._session_id = str(uuid.uuid4())
        return self._session_id
    
    def log_action(
        self,
        user,
        action_type: str,
        governance_class: str,
        workflow_id: str = None,
        tool_id: str = None,
        platform: str = None,
        request_payload: Dict = None,
        response_summary: Dict = None,
        status: str = "SUCCESS",
        error_message: str = None,
        execution_time_ms: int = None,
        approval_id: str = None
    ) -> str:
        """
        Log an action to the audit trail.
        
        Args:
            user: Django user who performed the action
            action_type: Type of action (QUERY, TOOL_EXEC, etc.)
            governance_class: READ, WRITE, or MONEY_MOVE
            workflow_id: Optional workflow being executed
            tool_id: Optional tool being called
            platform: Optional platform being accessed
            request_payload: Request data (sanitized)
            response_summary: Summary of response (not full data)
            status: SUCCESS, FAILED, PENDING, etc.
            error_message: Error details if failed
            execution_time_ms: Time taken
            approval_id: Related approval if required
        
        Returns:
            Audit log ID
        """
        from audit.models import AuditLog
        
        try:
            log_entry = AuditLog.objects.create(
                user=user,
                session_id=self._session_id,
                action_type=action_type,
                governance_class=governance_class,
                workflow_id=workflow_id,
                tool_id=tool_id,
                platform=platform,
                request_payload=self._sanitize_payload(request_payload or {}),
                response_summary=response_summary or {},
                status=status,
                error_message=error_message,
                execution_time_ms=execution_time_ms
            )
            
            logger.info(
                f"Audit: {action_type} by user {user.id} - {status} "
                f"[{governance_class}] {tool_id or workflow_id}"
            )
            
            return str(log_entry.id)
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            return None
    
    def log_step(
        self,
        audit_log_id: str,
        step_id: str,
        step_order: int,
        tool_id: str = None,
        input_data: Dict = None,
        output_data: Dict = None,
        status: str = "SUCCESS",
        error_message: str = None,
        started_at: datetime = None,
        completed_at: datetime = None,
        execution_time_ms: int = None
    ) -> str:
        """
        Log an individual workflow step.
        
        Args:
            audit_log_id: Parent audit log ID
            step_id: Step identifier
            step_order: Execution order
            tool_id: Tool being executed
            input_data: Step input
            output_data: Step output
            status: Step status
            error_message: Error if failed
            started_at: Start time
            completed_at: End time
            execution_time_ms: Duration
        
        Returns:
            Execution step ID
        """
        from audit.models import AuditLog, ExecutionStep
        
        try:
            audit_log = AuditLog.objects.get(id=audit_log_id)
            
            step = ExecutionStep.objects.create(
                audit_log=audit_log,
                step_id=step_id,
                step_order=step_order,
                tool_id=tool_id,
                input_data=self._sanitize_payload(input_data or {}),
                output_data=self._summarize_output(output_data),
                status=status,
                error_message=error_message,
                started_at=started_at,
                completed_at=completed_at,
                execution_time_ms=execution_time_ms
            )
            
            return str(step.id)
            
        except Exception as e:
            logger.error(f"Failed to create execution step log: {e}")
            return None
    
    def create_approval_request(
        self,
        user,
        action_type: str,
        tool_id: str,
        platform: str,
        request_payload: Dict,
        justification: str = ""
    ) -> str:
        """
        Create an approval request for a sensitive action.
        
        Args:
            user: User requesting approval
            action_type: Type of action
            tool_id: Tool to be executed
            platform: Platform to access
            request_payload: What will be executed
            justification: Why this is needed
        
        Returns:
            Approval request ID
        """
        from audit.models import ApprovalRequest
        from datetime import timedelta
        
        try:
            request = ApprovalRequest.objects.create(
                requested_by=user,
                action_type=action_type,
                tool_id=tool_id,
                platform=platform,
                request_payload=self._sanitize_payload(request_payload),
                justification=justification,
                expires_at=datetime.now() + timedelta(hours=24)
            )
            
            logger.info(f"Approval request created: {request.id}")
            return str(request.id)
            
        except Exception as e:
            logger.error(f"Failed to create approval request: {e}")
            return None
    
    def process_approval(
        self,
        approval_id: str,
        approver,
        approved: bool,
        reason: str = ""
    ) -> bool:
        """
        Process an approval request.
        
        Args:
            approval_id: The approval request ID
            approver: User approving/rejecting
            approved: True to approve, False to reject
            reason: Reason for decision
        
        Returns:
            True if processed successfully
        """
        from audit.models import ApprovalRequest
        
        try:
            request = ApprovalRequest.objects.get(id=approval_id)
            
            request.approved_by = approver
            request.status = "APPROVED" if approved else "REJECTED"
            request.decision_reason = reason
            request.decided_at = datetime.now()
            request.save()
            
            logger.info(f"Approval {approval_id}: {'APPROVED' if approved else 'REJECTED'}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process approval: {e}")
            return False
    
    def get_user_actions(
        self,
        user,
        limit: int = 100,
        action_type: str = None,
        since: datetime = None
    ) -> list:
        """
        Get recent actions for a user.
        
        Args:
            user: The user
            limit: Max results
            action_type: Optional filter
            since: Optional date filter
        
        Returns:
            List of audit log entries
        """
        from audit.models import AuditLog
        
        queryset = AuditLog.objects.filter(user=user).order_by('-created_at')
        
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        if since:
            queryset = queryset.filter(created_at__gte=since)
        
        return list(queryset[:limit].values())
    
    def _sanitize_payload(self, payload: Dict) -> Dict:
        """Remove sensitive data from payloads before logging."""
        if not payload:
            return {}
        
        sanitized = {}
        sensitive_keys = {'password', 'api_key', 'secret', 'token', 'authorization'}
        
        for key, value in payload.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_payload(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _summarize_output(self, output: Any) -> Dict:
        """Create a summary of output data (not full content)."""
        if output is None:
            return {}
        
        if isinstance(output, dict):
            return {
                "type": "dict",
                "keys": list(output.keys())[:10],
                "key_count": len(output)
            }
        elif isinstance(output, list):
            return {
                "type": "list",
                "count": len(output),
                "sample_keys": list(output[0].keys()) if output and isinstance(output[0], dict) else []
            }
        else:
            return {
                "type": type(output).__name__,
                "preview": str(output)[:100]
            }


def audit_action(action_type: str, governance_class: str = "READ"):
    """
    Decorator to automatically audit function calls.
    
    Usage:
        @audit_action("TOOL_EXEC", "READ")
        def my_function(user, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get('user') or (args[0] if args else None)
            service = get_audit_service()
            
            start_time = datetime.now()
            status = "SUCCESS"
            error = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "FAILED"
                error = str(e)
                raise
            finally:
                elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
                
                if user and hasattr(user, 'id'):
                    service.log_action(
                        user=user,
                        action_type=action_type,
                        governance_class=governance_class,
                        tool_id=func.__name__,
                        status=status,
                        error_message=error,
                        execution_time_ms=elapsed
                    )
        
        return wrapper
    return decorator


# Singleton instance
_audit_service = None

def get_audit_service() -> AuditService:
    """Get the default audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
