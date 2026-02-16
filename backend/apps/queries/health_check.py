"""
Health Check Endpoint for Render Debugging
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
import os


class HealthCheckView(APIView):
    """
    Diagnostic endpoint to verify environment configuration on Render.
    """
    permission_classes = []  # Public endpoint for debugging
    
    def get(self, request):
        """Check critical environment variables and services."""
        
        # Check OpenAI API Key
        openai_key = settings.OPENAI_API_KEY
        openai_status = {
            'configured': bool(openai_key),
            'length': len(openai_key) if openai_key else 0,
            'prefix': openai_key[:7] if openai_key and len(openai_key) > 7 else 'N/A',
            'is_openrouter': openai_key.startswith('sk-or-') if openai_key else False
        }
        
        # Check Database
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_status = {'connected': True, 'engine': settings.DATABASES['default']['ENGINE']}
        except Exception as e:
            db_status = {'connected': False, 'error': str(e)}
        
        # Check Encryption Key
        encryption_key = settings.ENCRYPTION_KEY
        encryption_status = {
            'configured': bool(encryption_key),
            'length': len(encryption_key) if encryption_key else 0
        }
        
        # Check Platform Connections
        from apps.platforms.models import PlatformConnection
        try:
            connections_count = PlatformConnection.objects.filter(is_valid=True).count()
            platforms = list(PlatformConnection.objects.filter(is_valid=True).values_list('platform', flat=True))
        except Exception as e:
            connections_count = 0
            platforms = []
        
        return Response({
            'status': 'ok',
            'environment': {
                'debug': settings.DEBUG,
                'allowed_hosts': settings.ALLOWED_HOSTS
            },
            'openai': openai_status,
            'database': db_status,
            'encryption': encryption_status,
            'platforms': {
                'count': connections_count,
                'connected': platforms
            }
        })
