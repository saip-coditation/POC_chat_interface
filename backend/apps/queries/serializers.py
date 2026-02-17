"""
Query Serializers
"""

from rest_framework import serializers
from .models import QueryLog, SavedQuery, Workflow, WorkflowExecution, QuerySuggestion


class ProcessQuerySerializer(serializers.Serializer):
    """Serializer for processing a query."""
    
    query = serializers.CharField(min_length=3, max_length=500)
    platform = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class QueryLogSerializer(serializers.ModelSerializer):
    """Serializer for query history."""
    
    class Meta:
        model = QueryLog
        fields = [
            'id', 'platform', 'query_text', 'response_summary',
            'was_successful', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class QueryResponseSerializer(serializers.Serializer):
    """Serializer for query response."""
    
    platform = serializers.CharField()
    summary = serializers.CharField()
    data = serializers.ListField(required=False, allow_null=True)
    columns = serializers.ListField(child=serializers.CharField(), required=False)
    type = serializers.CharField()


class SavedQuerySerializer(serializers.ModelSerializer):
    """Serializer for saved queries (list/detail)."""

    class Meta:
        model = SavedQuery
        fields = ['id', 'name', 'query_text', 'platform', 'created_at']
        read_only_fields = ['id', 'created_at']


class SavedQueryCreateSerializer(serializers.Serializer):
    """Serializer for creating a saved query."""

    name = serializers.CharField(min_length=1, max_length=120)
    query_text = serializers.CharField(min_length=1, max_length=500)
    platform = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class WorkflowSerializer(serializers.ModelSerializer):
    """Serializer for workflows."""
    
    class Meta:
        model = Workflow
        fields = [
            'id', 'name', 'description', 'status', 'definition',
            'created_at', 'updated_at', 'last_run_at',
            'run_count', 'success_count', 'failure_count'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'last_run_at',
            'run_count', 'success_count', 'failure_count'
        ]


class WorkflowCreateSerializer(serializers.Serializer):
    """Serializer for creating a workflow."""
    
    name = serializers.CharField(min_length=1, max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    definition = serializers.DictField()


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    """Serializer for workflow executions."""
    
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)
    
    class Meta:
        model = WorkflowExecution
        fields = [
            'id', 'workflow', 'workflow_name', 'status',
            'input_data', 'output_data', 'step_results',
            'error_message', 'failed_step',
            'started_at', 'completed_at', 'execution_time_ms'
        ]
        read_only_fields = [
            'id', 'started_at', 'completed_at', 'execution_time_ms'
        ]


class QuerySuggestionSerializer(serializers.Serializer):
    """Serializer for query suggestions."""
    
    query_text = serializers.CharField()
    platform = serializers.CharField(required=False, allow_blank=True)
    suggestion_type = serializers.CharField()
    confidence_score = serializers.FloatField()
    source_query_id = serializers.IntegerField(required=False, allow_null=True)
    usage_count = serializers.IntegerField(required=False)
