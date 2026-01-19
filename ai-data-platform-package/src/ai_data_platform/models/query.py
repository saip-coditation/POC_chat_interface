from django.conf import settings
from django.db import models

class QueryLog(models.Model):
    """Stores history of user queries."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='query_logs'
    )
    platform = models.CharField(max_length=50)
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
        app_label = 'ai_data_platform'
    
    def __str__(self):
        return f"{self.user} - {self.query_text[:50]}"
