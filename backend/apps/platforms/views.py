"""
Platform Views
"""

import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.encryption import encrypt_api_key, decrypt_api_key
from utils import stripe_client, zoho_client, github_client, trello_client, salesforce_client
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
        metadata_update = {}
        
        # Validate credentials with the platform
        if platform == 'stripe':
            validation = stripe_client.validate_api_key(api_key)
        elif platform == 'zoho':
            validation = zoho_client.validate_credentials(api_key)
            logger.info(f"Zoho validation result: {validation}")
        elif platform == 'github':
            validation = github_client.validate_token(api_key)
            logger.info(f"GitHub validation result: {validation}")
        elif platform == 'trello':
            # Trello requires Key + Token. We expect "KEY:TOKEN"
            try:
                if ':' not in api_key:
                    return Response({
                        'success': False,
                        'error': 'Invalid format. Please enter "API_KEY:TOKEN"'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                t_key, t_token = api_key.split(':', 1)
                validation = trello_client.validate_credentials(t_key.strip(), t_token.strip())
                
                # If valid, we store the TOKEN as the secret, and KEY in metadata
                if validation.get('valid'):
                    # OVERWRITE api_key with just the token for storage
                    api_key = t_token.strip() 
                    metadata_update['trello_key'] = t_key.strip()
                    
            except Exception as e:
                logger.error(f"Trello parsing error: {e}")
                validation = {'valid': False, 'error': 'Failed to parse Trello credentials'}
        elif platform == 'salesforce':
            # Salesforce: Accept ACCESS_TOKEN:INSTANCE_URL (from Authorization Code flow)
            try:
                if ':' not in api_key:
                    return Response({
                        'success': False,
                        'error': 'Invalid format. Please enter "ACCESS_TOKEN:INSTANCE_URL"'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Split only on first colon (access_token may contain special chars)
                parts = api_key.split(':', 1)
                if len(parts) != 2:
                    return Response({
                        'success': False,
                        'error': 'Invalid format. Please enter "ACCESS_TOKEN:INSTANCE_URL"'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                access_token = parts[0].strip()
                instance_url = parts[1].strip()
                
                # Validate by making a test API call
                import requests
                test_url = f"{instance_url}/services/data/v57.0/sobjects/"
                headers = {'Authorization': f'Bearer {access_token}'}
                test_resp = requests.get(test_url, headers=headers, timeout=10)
                
                if test_resp.status_code == 200:
                    validation = {'valid': True}
                    api_key = access_token
                    metadata_update['instance_url'] = instance_url
                else:
                    validation = {'valid': False, 'error': f'API test failed: {test_resp.text[:100]}'}
                    
            except Exception as e:
                logger.error(f"Salesforce parsing error: {e}")
                validation = {'valid': False, 'error': f'Failed to validate Salesforce credentials: {str(e)}'}
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
                    **metadata_update, 
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
        metadata_update = {}
        
        # Validate new credentials
        if connection.platform == 'stripe':
            validation = stripe_client.validate_api_key(api_key)
        elif connection.platform == 'zoho':
            validation = zoho_client.validate_credentials(api_key)
        elif connection.platform == 'github':
            validation = github_client.validate_token(api_key)
        elif connection.platform == 'trello':
            # Trello requires Key + Token. "KEY:TOKEN"
            try:
                if ':' not in api_key:
                    return Response({
                        'success': False,
                        'error': 'Invalid format. Please enter "API_KEY:TOKEN"'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                t_key, t_token = api_key.split(':', 1)
                validation = trello_client.validate_credentials(t_key.strip(), t_token.strip())
                
                if validation.get('valid'):
                    api_key = t_token.strip()
                    metadata_update['trello_key'] = t_key.strip()
            except Exception as e:
                validation = {'valid': False, 'error': f'Failed to parse Trello credentials {e}'}
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
                **metadata_update,
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


class SalesforceCodeExchangeView(APIView):
    """Exchange Salesforce authorization code for access token."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        import requests
        
        authorization_code = request.data.get('code')
        code_verifier = request.data.get('code_verifier')
        client_id = request.data.get('client_id')
        client_secret = request.data.get('client_secret')
        redirect_uri = request.data.get('redirect_uri', 'https://login.salesforce.com/services/oauth2/success')
        
        if not authorization_code:
            return Response({
                'success': False,
                'error': 'Authorization code is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not code_verifier:
            return Response({
                'success': False,
                'error': 'Code verifier is required for PKCE flow'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if Salesforce is already connected
        if PlatformConnection.objects.filter(user=request.user, platform='salesforce').exists():
            return Response({
                'success': False,
                'error': 'Salesforce is already connected. Disconnect first to reconnect.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Exchange authorization code for tokens
        token_url = 'https://login.salesforce.com/services/oauth2/token'
        payload = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'code': authorization_code,
            'code_verifier': code_verifier
        }
        
        try:
            token_resp = requests.post(token_url, data=payload, timeout=30)
            token_data = token_resp.json()
            
            if token_resp.status_code != 200:
                logger.error(f"Salesforce token exchange failed: {token_data}")
                return Response({
                    'success': False,
                    'error': token_data.get('error_description', 'Token exchange failed')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            access_token = token_data.get('access_token')
            refresh_token = token_data.get('refresh_token')
            instance_url = token_data.get('instance_url')
            
            if not access_token or not instance_url:
                return Response({
                    'success': False,
                    'error': 'Invalid token response from Salesforce'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate the token by making a test API call
            test_url = f"{instance_url}/services/data/v57.0/sobjects/"
            headers = {'Authorization': f'Bearer {access_token}'}
            test_resp = requests.get(test_url, headers=headers, timeout=10)
            
            if test_resp.status_code != 200:
                return Response({
                    'success': False,
                    'error': 'Token validation failed'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Save the connection
            encrypted_key = encrypt_api_key(access_token)
            
            metadata = {
                'instance_url': instance_url,
                'last_four': access_token[-4:],
                'message': 'Salesforce connected successfully',
                # Store credentials for refresh
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            # Store refresh token if available
            if refresh_token:
                metadata['refresh_token_encrypted'] = encrypt_api_key(refresh_token)
            
            connection = PlatformConnection.objects.create(
                user=request.user,
                platform='salesforce',
                encrypted_api_key=encrypted_key,
                is_valid=True,
                metadata=metadata
            )
            
            return Response({
                'success': True,
                'message': 'Salesforce connected successfully!',
                'platform': PlatformConnectionSerializer(connection).data
            }, status=status.HTTP_201_CREATED)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Salesforce connection error: {e}")
            return Response({
                'success': False,
                'error': f'Connection error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Failed to save Salesforce connection: {e}")
            return Response({
                'success': False,
                'error': 'Failed to save connection'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

