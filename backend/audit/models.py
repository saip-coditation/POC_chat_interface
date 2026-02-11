"""
Audit Models

Models for tracking all actions, approvals, and execution logs.
Provides an immutable audit trail for compliance and debugging.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AuditLog(models.Model):
    """
    Immutable log of all actions executed through the platform.
    
    Every query, tool execution, and data access is logged here
    for compliance, debugging, and analytics.
    """
    
    ACTION_TYPES = [
        ('QUERY', 'Natural Language Query'),
        ('TOOL_EXEC', 'Tool Execution'),
        ('DATA_READ', 'Data Read'),
        ('DATA_WRITE', 'Data Write'),
        ('MONEY_MOVE', 'Money Movement'),
        ('AUTH', 'Authentication'),
        ('CONFIG', 'Configuration Change'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXECUTING', 'Executing'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    GOVERNANCE_CLASSES = [
        ('READ', 'Read'),
        ('WRITE', 'Write'),
        ('MONEY_MOVE', 'Money Move'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User context
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    session_id = models.UUIDField(null=True, blank=True, db_index=True)
    
    # Action details
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, db_index=True)
    governance_class = models.CharField(max_length=20, choices=GOVERNANCE_CLASSES, db_index=True)
    
    # Workflow/tool references
    workflow_id = models.CharField(max_length=100, blank=True, null=True)
    tool_id = models.CharField(max_length=200, blank=True, null=True)
    platform = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    
    # Request/response data
    request_payload = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    
    # Execution status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Performance metrics
    execution_time_ms = models.PositiveIntegerField(null=True, blank=True)
    
    # Approval tracking
    approval = models.ForeignKey(
        'ApprovalRequest',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs'
    )
    
    # Immutable timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action_type', 'status']),
            models.Index(fields=['platform', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.action_type} by {self.user} - {self.status}"


class ApprovalRequest(models.Model):
    """
    Approval requests for sensitive actions.
    
    Required for WRITE and MONEY_MOVE governance classes
    based on policy configuration.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Requester
    requested_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='approval_requests'
    )
    
    # Approver (null until approved/rejected)
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approvals_given'
    )
    
    # Action details
    action_type = models.CharField(max_length=50)
    tool_id = models.CharField(max_length=200)
    platform = models.CharField(max_length=50)
    
    # Request details
    request_payload = models.JSONField(default=dict)
    justification = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    decision_reason = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'approval_request'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Approval for {self.tool_id} by {self.requested_by} - {self.status}"


class ExecutionStep(models.Model):
    """
    Individual steps within a workflow execution.
    
    Tracks the progress of multi-step workflows with
    timing and output for each step.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Parent audit log
    audit_log = models.ForeignKey(
        AuditLog,
        on_delete=models.CASCADE,
        related_name='execution_steps'
    )
    
    # Step details
    step_id = models.CharField(max_length=100)
    step_order = models.PositiveIntegerField()
    tool_id = models.CharField(max_length=200, blank=True, null=True)
    
    # Input/output
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    
    # Status
    status = models.CharField(max_length=20, default='PENDING')
    error_message = models.TextField(blank=True, null=True)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_time_ms = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'execution_step'
        ordering = ['audit_log', 'step_order']
        unique_together = [['audit_log', 'step_id']]
    
    def __str__(self):
        return f"Step {self.step_order}: {self.step_id} - {self.status}"
