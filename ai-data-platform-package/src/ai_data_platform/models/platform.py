from django.conf import settings
from django.db import models
from ..conf import api_settings

class PlatformConnection(models.Model):
    """Stores user's connected platform credentials."""
    
    # We remove hardcoded choices to allow dynamic platforms
    # Validation will happen in the service layer
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='platform_connections'
    )
    platform = models.CharField(max_length=50) # Increased length for custom platform names
    encrypted_api_key = models.TextField()
    is_valid = models.BooleanField(default=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_verified_at = models.DateTimeField(auto_now=True)
    
    # Platform-specific metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['user', 'platform']
        ordering = ['-connected_at']
        app_label = 'ai_data_platform'
    
    def __str__(self):
        return f"{self.user} - {self.platform}"
