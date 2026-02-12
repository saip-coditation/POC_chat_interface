"""
Query Serializers
"""

from rest_framework import serializers
from .models import QueryLog, SavedQuery


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
