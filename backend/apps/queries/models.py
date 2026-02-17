"""
Query Models
"""

from django.conf import settings
from django.db import models
import uuid


class QueryLog(models.Model):
    """Stores history of user queries."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='query_logs'
    )
    platform = models.CharField(max_length=20)
    query_text = models.TextField()
    response_summary = models.TextField(blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    
    # Processing metadata
    processing_time_ms = models.IntegerField(null=True, blank=True)
    was_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['platform', '-created_at']),
            models.Index(fields=['was_successful', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.query_text[:50]}"


class SavedQuery(models.Model):
    """User's saved favorite queries for one-click run."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_queries'
    )
    name = models.CharField(max_length=120)
    query_text = models.TextField()
    platform = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [['user', 'name']]

    def __str__(self):
        return f"{self.user.email} - {self.name}"


class Workflow(models.Model):
    """Multi-step workflow that chains queries together with conditional logic."""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('archived', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workflows'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Workflow definition (JSON structure)
    definition = models.JSONField(default=dict)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.name}"


class WorkflowExecution(models.Model):
    """Execution log for workflows."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(
        Workflow,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workflow_executions'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Execution results
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    step_results = models.JSONField(default=list, blank=True)  # Results from each step
    
    # Error tracking
    error_message = models.TextField(blank=True)
    failed_step = models.IntegerField(null=True, blank=True)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_time_ms = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['workflow', '-started_at']),
            models.Index(fields=['user', '-started_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.workflow.name} - {self.status} - {self.started_at}"


class QuerySuggestion(models.Model):
    """AI-powered query suggestions based on user history and patterns."""
    
    SUGGESTION_TYPES = [
        ('similar', 'Similar Query'),
        ('trending', 'Trending Query'),
        ('related', 'Related Query'),
        ('popular', 'Popular Query'),
        ('completion', 'Query Completion'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='query_suggestions',
        null=True,
        blank=True
    )
    
    # Suggestion details
    suggestion_type = models.CharField(max_length=20, choices=SUGGESTION_TYPES)
    query_text = models.TextField()
    platform = models.CharField(max_length=20, blank=True)
    
    # Context and metadata
    source_query = models.ForeignKey(
        QueryLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suggestions'
    )
    confidence_score = models.FloatField(default=0.0)  # 0.0 to 1.0
    
    # Usage tracking
    shown_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_shown_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-confidence_score', '-created_at']
        indexes = [
            models.Index(fields=['user', '-confidence_score']),
            models.Index(fields=['suggestion_type', '-confidence_score']),
            models.Index(fields=['platform', '-confidence_score']),
        ]
    
    def __str__(self):
        return f"{self.suggestion_type} - {self.query_text[:50]}"
