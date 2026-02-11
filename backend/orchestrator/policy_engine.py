"""
Governance Policy Engine

Enforces policies before action execution based on governance class.
Handles approval requirements, rate limits, and access controls.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

from connectors.base import GovernanceClass

logger = logging.getLogger(__name__)


class PolicyDecision(Enum):
    """Policy evaluation result."""
    ALLOW = "ALLOW"               # Action can proceed
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"  # Needs approval first
    DENY = "DENY"                 # Action not permitted
    RATE_LIMITED = "RATE_LIMITED" # Too many requests


@dataclass
class PolicyResult:
    """Result of policy evaluation."""
    decision: PolicyDecision
    reason: str = ""
    approval_required_from: List[str] = None
    retry_after_seconds: int = 0
    
    def __post_init__(self):
        if self.approval_required_from is None:
            self.approval_required_from = []
    
    def is_allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOW
    
    def to_dict(self) -> Dict:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "approval_required_from": self.approval_required_from,
            "retry_after_seconds": self.retry_after_seconds
        }


class PolicyEngine:
    """
    Evaluates governance policies before action execution.
    
    Default policies by governance class:
    - READ: Auto-approve
    - WRITE: Log, optional approval
    - MONEY_MOVE: Require approval + 2FA
    """
    
    # Default rate limits per governance class (requests per minute)
    DEFAULT_RATE_LIMITS = {
        GovernanceClass.READ: 100,
        GovernanceClass.WRITE: 20,
        GovernanceClass.MONEY_MOVE: 5,
    }
    
    # Default approval requirements
    DEFAULT_APPROVAL_REQUIRED = {
        GovernanceClass.READ: False,
        GovernanceClass.WRITE: False,  # Can be enabled per-org
        GovernanceClass.MONEY_MOVE: True,
    }
    
    def __init__(self, rate_limit_store=None):
        """
        Initialize the policy engine.
        
        Args:
            rate_limit_store: Optional store for rate limit tracking
        """
        self._rate_limit_store = rate_limit_store or {}
        self._custom_policies: Dict[str, Dict] = {}
    
    def evaluate(
        self,
        user,
        action_type: str,
        governance_class: GovernanceClass,
        tool_id: str = None,
        platform: str = None,
        params: Dict = None
    ) -> PolicyResult:
        """
        Evaluate policies for an action.
        
        Args:
            user: The user requesting the action
            action_type: Type of action (QUERY, TOOL_EXEC, etc.)
            governance_class: Governance classification
            tool_id: Optional specific tool being executed
            platform: Optional platform being accessed
            params: Optional action parameters
        
        Returns:
            PolicyResult with decision and details
        """
        # Step 1: Check rate limits
        rate_result = self._check_rate_limit(user, governance_class)
        if not rate_result.is_allowed():
            return rate_result
        
        # Step 2: Check approval requirements
        if self._requires_approval(user, governance_class, tool_id):
            return PolicyResult(
                decision=PolicyDecision.REQUIRE_APPROVAL,
                reason=f"Actions of class '{governance_class.value}' require approval",
                approval_required_from=self._get_approvers(user, governance_class)
            )
        
        # Step 3: Check custom policies
        custom_result = self._check_custom_policies(
            user, governance_class, tool_id, platform, params
        )
        if custom_result:
            return custom_result
        
        # All checks passed
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="Policy checks passed"
        )
    
    def _check_rate_limit(
        self,
        user,
        governance_class: GovernanceClass
    ) -> PolicyResult:
        """Check if user has exceeded rate limits."""
        user_id = str(user.id) if hasattr(user, 'id') else str(user)
        key = f"{user_id}:{governance_class.value}"
        now = datetime.now()
        
        # Get or create rate limit entry
        if key not in self._rate_limit_store:
            self._rate_limit_store[key] = {
                "count": 0,
                "window_start": now
            }
        
        entry = self._rate_limit_store[key]
        
        # Reset window if expired (1 minute)
        if now - entry["window_start"] > timedelta(minutes=1):
            entry["count"] = 0
            entry["window_start"] = now
        
        # Check limit
        limit = self.DEFAULT_RATE_LIMITS.get(governance_class, 100)
        if entry["count"] >= limit:
            retry_after = 60 - int((now - entry["window_start"]).total_seconds())
            return PolicyResult(
                decision=PolicyDecision.RATE_LIMITED,
                reason=f"Rate limit exceeded ({limit}/minute)",
                retry_after_seconds=max(1, retry_after)
            )
        
        # Increment counter
        entry["count"] += 1
        
        return PolicyResult(decision=PolicyDecision.ALLOW)
    
    def _requires_approval(
        self,
        user,
        governance_class: GovernanceClass,
        tool_id: str = None
    ) -> bool:
        """Check if action requires approval."""
        # Check default policy
        default_required = self.DEFAULT_APPROVAL_REQUIRED.get(governance_class, False)
        
        # Check custom policy for tool
        if tool_id and tool_id in self._custom_policies:
            return self._custom_policies[tool_id].get("approval_required", default_required)
        
        return default_required
    
    def _get_approvers(
        self,
        user,
        governance_class: GovernanceClass
    ) -> List[str]:
        """Get list of users who can approve this action."""
        # In a real implementation, this would look up org admins
        # For now, return a placeholder
        return ["admin"]
    
    def _check_custom_policies(
        self,
        user,
        governance_class: GovernanceClass,
        tool_id: str,
        platform: str,
        params: Dict
    ) -> Optional[PolicyResult]:
        """Check any custom policies configured."""
        # This is extensible for org-specific policies
        # Return None if no custom policy applies
        return None
    
    def register_policy(
        self,
        tool_id: str,
        policy: Dict[str, Any]
    ):
        """
        Register a custom policy for a tool.
        
        Args:
            tool_id: The tool to apply policy to
            policy: Policy configuration dict with:
                - approval_required: bool
                - allowed_users: List[str]
                - max_amount: float (for money operations)
        """
        self._custom_policies[tool_id] = policy
        logger.info(f"Registered custom policy for {tool_id}")
    
    def reset_rate_limits(self, user=None):
        """Reset rate limits, optionally for a specific user."""
        if user:
            user_id = str(user.id) if hasattr(user, 'id') else str(user)
            keys_to_remove = [k for k in self._rate_limit_store if k.startswith(f"{user_id}:")]
            for k in keys_to_remove:
                del self._rate_limit_store[k]
        else:
            self._rate_limit_store.clear()


# Singleton instance
_policy_engine = None

def get_policy_engine() -> PolicyEngine:
    """Get the default policy engine instance."""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine
