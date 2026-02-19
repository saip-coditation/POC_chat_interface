from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Dashboard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboards')
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.user.email})"

class Widget(models.Model):
    WIDGET_TYPES = [
        ('chart', 'Chart'),
        ('text', 'Text'),
        ('metric', 'Metric'),
    ]

    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='widgets')
    title = models.CharField(max_length=255)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    data = models.JSONField(default=dict)
    position = models.JSONField(default=dict) # x, y, w, h
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.widget_type}"
