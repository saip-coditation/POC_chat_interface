"""
Platform Connection Models
"""

from django.conf import settings
from django.db import models


class PlatformConnection(models.Model):
    """Stores user's connected platform credentials."""
    
    PLATFORM_CHOICES = [
        ('stripe', 'Stripe'),
        ('zoho', 'Zoho CRM'),
        ('github', 'GitHub'),
        ('trello', 'Trello'),
        ('salesforce', 'Salesforce'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='platform_connections'
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    encrypted_api_key = models.TextField()
    is_valid = models.BooleanField(default=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_verified_at = models.DateTimeField(auto_now=True)
    
    # Platform-specific metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['user', 'platform']
        ordering = ['-connected_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.platform}"
    
    @property
    def platform_display(self):
        return dict(self.PLATFORM_CHOICES).get(self.platform, self.platform)
