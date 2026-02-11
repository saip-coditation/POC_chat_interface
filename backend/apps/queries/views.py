"""
Query Views
"""

import time
import logging
import json
import threading
import queue
from datetime import datetime
from django.http import StreamingHttpResponse
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.platforms.models import PlatformConnection
from utils.encryption import decrypt_api_key
from .models import QueryLog
from .serializers import ProcessQuerySerializer, QueryLogSerializer

# Import new Orchestrator
from orchestrator import get_query_orchestrator, OrchestratorContext

logger = logging.getLogger(__name__)


class QueryHistoryView(generics.ListAPIView):
    """List past queries for the authenticated user."""
    serializer_class = QueryLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return QueryLog.objects.filter(user=self.request.user).order_by('-created_at')



class ProcessQueryView(APIView):
    """Process a natural language query using the AI Data Orchestrator."""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return StreamingHttpResponse(self.stream_processor(request), content_type='application/x-ndjson')

    def stream_processor(self, request):
        """
        Stream logs and results from the QueryOrchestrator.
        Uses a separate thread for the orchestrator to allow real-time log streaming.
        """
        log_queue = queue.Queue()
        result_queue = queue.Queue()
        
        # 1. Parse Request
        serializer = ProcessQuerySerializer(data=request.data)
        if not serializer.is_valid():
            yield json.dumps({"type": "result", "payload": {'success': False, 'errors': serializer.errors}}) + "\n"
            return

        query = serializer.validated_data['query']
        # We ignore 'platform' override for now, letting the orchestrator handle it 
        # (or we could pass it contextually if we extended OrchestratorContext)
        
        # 2. Prepare Context
        # Fetch connections to populate credentials
        connections = PlatformConnection.objects.filter(user=request.user, is_valid=True)
        credentials = {}
        for conn in connections:
            try:
                # Decrypt and store in map: {'stripe': {'api_key': '...'}, ...}
                decrypted_key = decrypt_api_key(conn.encrypted_api_key)
                
                # Adapters usually expect specific key names. 
                # Our BaseConnector implementation might vary, but for now assuming 'api_key' or raw dict
                # The ConnectorRegistry and Adapters handle the cred structure.
                # StripeAdapter expects {'api_key': ...}
                
                creds = {'api_key': decrypted_key}
                
                # Add metadata
                if conn.metadata:
                    creds.update(conn.metadata)
                    
                    # For Salesforce: decrypt refresh_token if stored encrypted
                    if conn.platform.lower() == 'salesforce' and 'refresh_token_encrypted' in conn.metadata:
                        try:
                            creds['refresh_token'] = decrypt_api_key(conn.metadata['refresh_token_encrypted'])
                        except Exception as e:
                            logger.warning(f"Failed to decrypt Salesforce refresh_token: {e}")
                    
                    # Ensure instance_url is accessible for Salesforce
                    # For Trello: The ConnectPlatformView stores TOKEN in encrypted_api_key 
                    # and KEY in metadata['trello_key']. We need to map them correctly.
                    if conn.platform.lower() == 'trello':
                        if 'trello_key' in conn.metadata:
                            # Swap: encrypted_key is token, metadata is key
                            creds['token'] = creds.pop('api_key') # The decrypted key is actually the token
                            creds['api_key'] = conn.metadata['trello_key']
                        elif 'token' in conn.metadata:
                            # Fallback if stored differently (e.g. key in encrypted, token in metadata)
                            creds['token'] = conn.metadata['token']
                    
                credentials[conn.platform.lower()] = creds
                
            except Exception as e:
                logger.error(f"Failed to decrypt key for {conn.platform}: {e}")

        # Callback for orchestrator logs
        def orchestrator_log_callback(msg):
            log_queue.put(msg)

        context = OrchestratorContext(
            user=request.user,
            credentials=credentials,
            log_callback=orchestrator_log_callback
        )

        # 3. Define Execution Function
        def run_orchestrator():
            try:
                orchestrator = get_query_orchestrator()
                result = orchestrator.process_query(query, context)
                result_queue.put(result)
            except Exception as e:
                logger.exception("Orchestrator execution failed")
                result_queue.put(e)
            finally:
                # Signal end of logs
                log_queue.put(None)

        # 4. Start Thread
        worker_thread = threading.Thread(target=run_orchestrator)
        worker_thread.start()

        # 5. Stream Logs
        logs_list = []
        
        while True:
            try:
                # Wait for log messages
                msg = log_queue.get() # Block indefinitely because thread is running
                
                if msg is None: # Sentinel
                    break
                    
                logs_list.append({"message": msg})
                yield json.dumps({"type": "log", "message": msg}) + "\n"
                
            except Exception:
                break
        
        worker_thread.join()
        
        # 6. Handle Result
        final_result = result_queue.get()
        
        if isinstance(final_result, Exception):
            # System error
            error_msg = str(final_result)
            yield json.dumps({
                "type": "result", 
                "payload": {
                    'success': False, 
                    'error': error_msg,
                    'logs': logs_list
                }
            }) + "\n"
        else:
            # Orchestrator Result
            # Convert OrchestratorResult to frontend expected format
            payload = self._format_result_payload(final_result, logs_list, query, request.user)
            yield json.dumps({"type": "result", "payload": payload}) + "\n"

    def _format_result_payload(self, result, logs, query, user):
        """Convert OrchestratorResult to the dictionary expected by frontend."""
        
        # Save Log
        try:
            QueryLog.objects.create(
                user=user,
                platform=result.intent.get('platform') if result.intent else 'unknown',
                query_text=query,
                response_summary=result.summary,
                was_successful=result.success,
                processing_time_ms=result.execution_time_ms,
                error_message=result.error or "",
                response_data=result.intent or {}
            )
        except Exception as e:
            logger.error(f"Failed to save QueryLog: {e}")

        payload = {
            'success': result.success,
            'summary': result.summary,
            'data': result.data,
            'logs': logs,
            'processing_time_ms': result.execution_time_ms,
            'intent': result.intent,
            'requires_approval': result.requires_approval,
            'approval_id': result.approval_id,
            'chart': result.chart
        }
        
        if result.error:
            payload['error'] = result.error
        
        # Extract platform from intent
        platform = result.intent.get('platform') if result.intent else 'unknown'
        payload['platform'] = platform
        
        # Extract type from intent action (e.g., "list_deals" -> "deals")
        data_type = 'general'
        if result.intent and result.intent.get('action'):
            action = result.intent.get('action', '')
            # Parse action like "list_deals", "list_contacts" to "deals", "contacts"
            if action.startswith('list_'):
                data_type = action[5:]  # Remove "list_" prefix
            elif action.startswith('get_'):
                data_type = action[4:]  # Remove "get_" prefix
            else:
                data_type = action
        
        # Handle data formatting
        if result.data:
            if isinstance(result.data, dict):
                payload['type'] = result.data.get('type', data_type)
                payload['columns'] = result.data.get('columns')
                # If wrapped in 'data' key
                if 'data' in result.data:
                    payload['data'] = result.data['data']
            elif isinstance(result.data, list):
                payload['type'] = data_type
                if len(result.data) > 0:
                    payload['columns'] = list(result.data[0].keys())
        else:
            payload['type'] = data_type
        
        return payload
