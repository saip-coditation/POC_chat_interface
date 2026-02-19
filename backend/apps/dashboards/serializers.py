from rest_framework import serializers
from .models import Dashboard, Widget

class WidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Widget
        fields = ['id', 'dashboard', 'title', 'widget_type', 'data', 'position', 'created_at']
        read_only_fields = ['id', 'created_at']

class DashboardSerializer(serializers.ModelSerializer):
    widgets = WidgetSerializer(many=True, read_only=True)

    class Meta:
        model = Dashboard
        fields = ['id', 'user', 'title', 'widgets', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
