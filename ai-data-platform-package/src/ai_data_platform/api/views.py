from rest_framework import status, views, viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from ..models import PlatformConnection, QueryLog
from ..core.encryption import decrypt_api_key, encrypt_api_key
from ..services import StripeService, ZohoService, ai_service
from .serializers import (
    LoginSerializer, RegisterSerializer, UserSerializer,
    PlatformConnectionSerializer, ConnectPlatformSerializer,
    ProcessQuerySerializer, QueryLogSerializer
)

# Registry of available services
SERVICES = {
    'stripe': StripeService(),
    'zoho': ZohoService(),
}

class AuthViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        # In a real DRF app, you'd emit JWT here using simplejwt
        # For simplicity in this package demo, we return user info
        return Response({
            'success': True,
            'user': UserSerializer(user).data,
            # 'token': ...
        })

    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            'success': True,
            'user': UserSerializer(user).data
        })

class PlatformViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PlatformConnectionSerializer
    
    def get_queryset(self):
        return PlatformConnection.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def connect(self, request):
        serializer = ConnectPlatformSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        platform_id = serializer.validated_data['platform']
        api_key = serializer.validated_data['api_key']
        
        # Verify credentials using Service
        service = SERVICES.get(platform_id)
        if service:
            try:
                service.connect({'api_key': api_key})
            except Exception as e:
                return Response({'error': str(e)}, status=400)
        
        # Save
        PlatformConnection.objects.create(
            user=request.user,
            platform=platform_id,
            encrypted_api_key=encrypt_api_key(api_key)
        )
        return Response({'success': True})

class QueryView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ProcessQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        query = serializer.validated_data['query']
        platform_id = serializer.validated_data.get('platform') or 'stripe' # Default
        
        # Get connection
        try:
            conn = PlatformConnection.objects.get(user=request.user, platform=platform_id)
        except PlatformConnection.DoesNotExist:
            return Response({'error': 'Platform not connected'}, status=400)
            
        api_key = decrypt_api_key(conn.encrypted_api_key)
        
        # Process via Service
        service = SERVICES.get(platform_id)
        if not service:
            return Response({'error': 'Service not supported'}, status=400)
            
        result = service.process_query(query, {'api_key': api_key})
        
        # Log
        QueryLog.objects.create(
            user=request.user,
            platform=platform_id,
            query_text=query,
            response_summary=result.get('summary', ''),
            was_successful='error' not in result
        )
        
        return Response(result)
