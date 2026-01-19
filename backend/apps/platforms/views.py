"""
Platform Views
"""

import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.encryption import encrypt_api_key, decrypt_api_key
from utils import stripe_client, zoho_client, github_client
from .models import PlatformConnection
from .serializers import (
    PlatformConnectionSerializer,
    ConnectPlatformSerializer,
    ReverifySerializer
)

logger = logging.getLogger(__name__)


class ListPlatformsView(APIView):
    """List all connected platforms for the current user."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        connections = PlatformConnection.objects.filter(user=request.user)
        serializer = PlatformConnectionSerializer(connections, many=True)
        
        return Response({
            'success': True,
            'platforms': serializer.data
        })


class ConnectPlatformView(APIView):
    """Connect a new platform."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ConnectPlatformSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        platform = serializer.validated_data['platform']
        api_key = serializer.validated_data['api_key']
        
        # Validate credentials with the platform
        if platform == 'stripe':
            validation = stripe_client.validate_api_key(api_key)
        elif platform == 'zoho':
            validation = zoho_client.validate_credentials(api_key)
            logger.info(f"Zoho validation result: {validation}")
        elif platform == 'github':
            validation = github_client.validate_token(api_key)
            logger.info(f"GitHub validation result: {validation}")
        else:
            return Response({
                'success': False,
                'error': 'Unsupported platform'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not validation.get('valid'):
            return Response({
                'success': False,
                'error': validation.get('error', 'Invalid credentials')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Encrypt and store credentials
        try:
            encrypted_key = encrypt_api_key(api_key)
            
            connection = PlatformConnection.objects.create(
                user=request.user,
                platform=platform,
                encrypted_api_key=encrypted_key,
                is_valid=True,
                metadata={
                    'last_four': api_key[-4:],
                    **{k: v for k, v in validation.items() if k != 'valid'}
                }
            )
            
            return Response({
                'success': True,
                'message': f'Successfully connected to {platform.title()}',
                'platform': PlatformConnectionSerializer(connection).data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Failed to save platform connection: {e}")
            return Response({
                'success': False,
                'error': 'Failed to save connection'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DisconnectPlatformView(APIView):
    """Disconnect a platform."""
    
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, platform_id):
        try:
            connection = PlatformConnection.objects.get(
                id=platform_id,
                user=request.user
            )
            platform_name = connection.platform
            connection.delete()
            
            return Response({
                'success': True,
                'message': f'{platform_name.title()} disconnected successfully'
            })
            
        except PlatformConnection.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Platform connection not found'
            }, status=status.HTTP_404_NOT_FOUND)


class ReverifyPlatformView(APIView):
    """Re-verify platform credentials."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, platform_id):
        try:
            connection = PlatformConnection.objects.get(
                id=platform_id,
                user=request.user
            )
        except PlatformConnection.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Platform connection not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ReverifySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        api_key = serializer.validated_data['api_key']
        
        # Validate new credentials
        if connection.platform == 'stripe':
            validation = stripe_client.validate_api_key(api_key)
        elif connection.platform == 'zoho':
            validation = zoho_client.validate_credentials(api_key)
        elif connection.platform == 'github':
            validation = github_client.validate_token(api_key)
        else:
            return Response({
                'success': False,
                'error': 'Unsupported platform'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not validation.get('valid'):
            connection.is_valid = False
            connection.save()
            
            return Response({
                'success': False,
                'error': validation.get('error', 'Invalid credentials')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update with new encrypted key
        try:
            connection.encrypted_api_key = encrypt_api_key(api_key)
            connection.is_valid = True
            connection.metadata = {
                'last_four': api_key[-4:],
                **{k: v for k, v in validation.items() if k != 'valid'}
            }
            connection.save()
            
            return Response({
                'success': True,
                'message': 'Credentials verified successfully',
                'platform': PlatformConnectionSerializer(connection).data
            })
            
        except Exception as e:
            logger.error(f"Failed to update platform connection: {e}")
            return Response({
                'success': False,
                'error': 'Failed to update connection'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ZohoCodeExchangeView(APIView):
    """
    Exchange Zoho authorization code for refresh token and connect.
    
    This automates the token generation process:
    1. User generates authorization code from Zoho API Console (Self Client)
    2. User provides the code to this endpoint
    3. We exchange it for a refresh token and save the connection
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        authorization_code = request.data.get('code')
        client_id = request.data.get('client_id')
        client_secret = request.data.get('client_secret')
        
        if not authorization_code:
            return Response({
                'success': False,
                'error': 'Authorization code is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if Zoho is already connected
        if PlatformConnection.objects.filter(user=request.user, platform='zoho').exists():
            return Response({
                'success': False,
                'error': 'Zoho is already connected. Disconnect first to reconnect.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Prepare client credentials if provided
        client_credentials = None
        if client_id and client_secret:
            client_credentials = {
                'client_id': client_id,
                'client_secret': client_secret
            }
        
        # Exchange code for tokens
        result = zoho_client.exchange_code_for_tokens(authorization_code, client_credentials)
        
        if not result.get('success'):
            return Response({
                'success': False,
                'error': result.get('error', 'Failed to exchange code')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        refresh_token = result['refresh_token']
        
        # Validate the token works
        validation = zoho_client.validate_credentials(refresh_token, client_credentials)
        
        if not validation.get('valid'):
            return Response({
                'success': False,
                'error': validation.get('error', 'Token validation failed')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save the connection
        try:
            encrypted_key = encrypt_api_key(refresh_token)
            
            metadata = {
                'last_four': refresh_token[-4:],
                'message': 'Zoho CRM connected successfully'
            }
            
            # Save client credentials in metadata if provided
            if client_credentials:
                metadata['client_id'] = client_id
                metadata['client_secret'] = client_secret
            
            connection = PlatformConnection.objects.create(
                user=request.user,
                platform='zoho',
                encrypted_api_key=encrypted_key,
                is_valid=True,
                metadata=metadata
            )
            
            return Response({
                'success': True,
                'message': 'Zoho CRM connected successfully!',
                'refresh_token': refresh_token,  # Return so user can save if needed
                'platform': PlatformConnectionSerializer(connection).data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Failed to save Zoho connection: {e}")
            return Response({
                'success': False,
                'error': 'Failed to save connection'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
