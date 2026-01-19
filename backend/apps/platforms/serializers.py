"""
Platform Serializers
"""

from rest_framework import serializers
from utils.encryption import mask_api_key
from .models import PlatformConnection


class PlatformConnectionSerializer(serializers.ModelSerializer):
    """Serializer for listing platform connections (masks API key)."""
    
    masked_key = serializers.SerializerMethodField()
    platform_name = serializers.CharField(source='platform_display', read_only=True)
    
    class Meta:
        model = PlatformConnection
        fields = [
            'id', 'platform', 'platform_name', 'masked_key',
            'is_valid', 'connected_at', 'last_verified_at', 'metadata'
        ]
        read_only_fields = ['id', 'connected_at', 'last_verified_at']
    
    def get_masked_key(self, obj):
        """Return masked version of the API key."""
        # We don't expose the actual key, just show last 4 chars
        return "••••••••" + (obj.metadata.get('last_four', '****') if obj.metadata else '****')


class ConnectPlatformSerializer(serializers.Serializer):
    """Serializer for connecting a new platform."""
    
    platform = serializers.ChoiceField(choices=['stripe', 'zendesk', 'zoho', 'github'])
    api_key = serializers.CharField(min_length=10)
    
    def validate_platform(self, value):
        """Check if platform is already connected."""
        user = self.context.get('request').user
        
        if PlatformConnection.objects.filter(user=user, platform=value).exists():
            raise serializers.ValidationError(
                f'{value.title()} is already connected. Disconnect first to reconnect.'
            )
        
        return value


class ReverifySerializer(serializers.Serializer):
    """Serializer for re-verifying platform credentials."""
    
    api_key = serializers.CharField(min_length=10)
