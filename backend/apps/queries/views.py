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
from django.db import IntegrityError, models
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platforms.models import PlatformConnection
from utils.encryption import decrypt_api_key
from .models import QueryLog, SavedQuery, Workflow, WorkflowExecution, QuerySuggestion
from .serializers import (
    ProcessQuerySerializer,
    QueryLogSerializer,
    SavedQuerySerializer,
    SavedQueryCreateSerializer,
    WorkflowSerializer,
    WorkflowCreateSerializer,
    WorkflowExecutionSerializer,
    QuerySuggestionSerializer,
)
from .workflow_engine import WorkflowEngine
from .suggestion_service import QuerySuggestionService

# Import new Orchestrator
from orchestrator import get_query_orchestrator, OrchestratorContext

logger = logging.getLogger(__name__)


class QueryHistoryView(generics.ListAPIView):
    """List past queries for the authenticated user."""
    serializer_class = QueryLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return QueryLog.objects.filter(user=self.request.user).order_by('-created_at')


class SavedQueryListCreateView(APIView):
    """List and create saved queries for the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = SavedQuery.objects.filter(user=request.user)
        serializer = SavedQuerySerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SavedQueryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # Check if query with same name already exists for this user
        existing = SavedQuery.objects.filter(
            user=request.user,
            name=data['name']
        ).first()
        
        if existing:
            return Response(
                {'error': 'You already have a saved query with this name.', 'detail': 'A query with this name already exists in your saved queries.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            saved = SavedQuery.objects.create(
                user=request.user,
                name=data['name'],
                query_text=data['query_text'],
                platform=(data.get('platform') or '')[:20] or '',
            )
            return Response(
                SavedQuerySerializer(saved).data,
                status=status.HTTP_201_CREATED,
            )
        except IntegrityError as e:
            # Catch any other integrity errors (shouldn't happen with the check above, but just in case)
            logger.warning(f"IntegrityError saving query: {e}")
            return Response(
                {'error': 'You already have a saved query with this name.', 'detail': 'A query with this name already exists in your saved queries.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class SavedQueryDestroyView(APIView):
    """Delete a saved query (owner only)."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        saved = SavedQuery.objects.filter(user=request.user, pk=pk).first()
        if not saved:
            return Response(status=status.HTTP_404_NOT_FOUND)
        saved.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class QueryAutocompleteView(APIView):
    """Provide query autocomplete suggestions."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get query suggestions based on partial input.
        
        Query params:
        - q: Partial query text (required)
        - limit: Max number of suggestions (default: 15)
        """
        query_text = request.query_params.get('q', '').strip()
        # Increase default limit for better suggestions
        limit = int(request.query_params.get('limit', 15))
        
        # Always return pattern suggestions, even for empty queries on fresh databases
        if not query_text:
            # Return default popular patterns
            return Response({
                'suggestions': self._get_common_patterns('', limit),
                'query': ''
            })
        
        if len(query_text) < 2:
            # Still return common patterns for short queries
            return Response({
                'suggestions': self._get_common_patterns(query_text, limit),
                'query': query_text
            })
        
        suggestions = []
        query_lower = query_text.lower()
        
        # Check if platform-specific query (prioritize patterns)
        is_platform_query = any(p in query_lower for p in ['trello', 'zoho', 'stripe', 'github', 'salesforce'])
        
        # 1. Get matching saved queries (limit to 3 if platform query to make room for patterns)
        saved_limit = 3 if is_platform_query else limit
        saved_queries = SavedQuery.objects.filter(
            user=request.user
        ).filter(
            models.Q(name__icontains=query_text) | 
            models.Q(query_text__icontains=query_text)
        )[:saved_limit]
        
        for sq in saved_queries:
            suggestions.append({
                'text': sq.query_text,
                'type': 'saved',
                'label': sq.name,
                'platform': sq.platform or 'all'
            })
        
        # 2. Get matching query history (limit to 2 if platform query)
        history_limit = 2 if is_platform_query else (limit - len(suggestions))
        if history_limit > 0:
            recent_queries = QueryLog.objects.filter(
                user=request.user,
                query_text__icontains=query_text,
                was_successful=True
            ).order_by('-created_at')[:history_limit]
            
            for ql in recent_queries:
                # Avoid duplicates
                if not any(s['text'] == ql.query_text for s in suggestions):
                    suggestions.append({
                        'text': ql.query_text,
                        'type': 'history',
                        'label': ql.query_text[:60] + ('...' if len(ql.query_text) > 60 else ''),
                        'platform': ql.platform or 'all'
                    })
        
        # 3. Add common query patterns (prioritize when platform is mentioned)
        remaining_limit = limit - len(suggestions)
        if remaining_limit > 0:
            # Use full limit for patterns when platform is mentioned (to ensure we get enough patterns)
            pattern_limit = limit * 2 if is_platform_query else remaining_limit
            common_patterns = self._get_common_patterns(query_lower, pattern_limit)
            for pattern in common_patterns:
                # Check for duplicates by text (case-insensitive)
                is_duplicate = any(s['text'].lower().strip() == pattern['text'].lower().strip() for s in suggestions)
                if not is_duplicate:
                    suggestions.append(pattern)
                    if len(suggestions) >= limit:
                        break
        
        return Response({
            'suggestions': suggestions[:limit],
            'query': query_text
        })
    
    def _get_common_patterns(self, query_lower, limit):
        """Get common query patterns based on keywords."""
        patterns = []
        
        # Default patterns for empty/short queries (popular knowledge questions)
        if not query_lower or len(query_lower) < 2:
            patterns.extend([
                {'text': 'How do I clone a repository?', 'type': 'pattern', 'label': 'How to clone repo', 'platform': 'github'},
                {'text': 'How do I push code to GitHub?', 'type': 'pattern', 'label': 'How to push code to GitHub', 'platform': 'github'},
                {'text': 'Show my boards', 'type': 'pattern', 'label': 'Show my boards', 'platform': 'trello'},
                {'text': 'List all customers', 'type': 'pattern', 'label': 'All customers', 'platform': 'stripe'},
                {'text': 'List all deals', 'type': 'pattern', 'label': 'All deals', 'platform': 'zoho'},
            ])
        
        # Stripe patterns
        if any(word in query_lower for word in ['invoice', 'invoic', 'bill', 'payment']):
            patterns.extend([
                {'text': 'Show unpaid invoices', 'type': 'pattern', 'label': 'Unpaid invoices', 'platform': 'stripe'},
                {'text': 'List all invoices this month', 'type': 'pattern', 'label': 'Invoices this month', 'platform': 'stripe'},
                {'text': 'Show recent payments', 'type': 'pattern', 'label': 'Recent payments', 'platform': 'stripe'},
            ])
        
        if any(word in query_lower for word in ['revenue', 'income', 'money', 'earn']):
            patterns.extend([
                {'text': 'Revenue this month', 'type': 'pattern', 'label': 'Monthly revenue', 'platform': 'stripe'},
                {'text': 'Revenue this week', 'type': 'pattern', 'label': 'Weekly revenue', 'platform': 'stripe'},
                {'text': 'Total revenue', 'type': 'pattern', 'label': 'Total revenue', 'platform': 'stripe'},
            ])
        
        if any(word in query_lower for word in ['customer', 'client', 'user']):
            patterns.extend([
                {'text': 'List all customers', 'type': 'pattern', 'label': 'All customers', 'platform': 'stripe'},
                {'text': 'Show recent customers', 'type': 'pattern', 'label': 'Recent customers', 'platform': 'stripe'},
                {'text': 'Customer growth this month', 'type': 'pattern', 'label': 'Customer growth', 'platform': 'stripe'},
            ])
        
        if any(word in query_lower for word in ['subscription', 'sub', 'plan']):
            patterns.extend([
                {'text': 'List active subscriptions', 'type': 'pattern', 'label': 'Active subscriptions', 'platform': 'stripe'},
                {'text': 'Show subscription revenue', 'type': 'pattern', 'label': 'Subscription revenue', 'platform': 'stripe'},
            ])
        
        # Zoho patterns - Trigger when "zoho" is mentioned
        if 'zoho' in query_lower:
            patterns.extend([
                {'text': 'List all contacts', 'type': 'pattern', 'label': 'All contacts', 'platform': 'zoho'},
                {'text': 'Show recent contacts', 'type': 'pattern', 'label': 'Recent contacts', 'platform': 'zoho'},
                {'text': 'List all deals', 'type': 'pattern', 'label': 'All deals', 'platform': 'zoho'},
                {'text': 'Show deals closing this week', 'type': 'pattern', 'label': 'Deals this week', 'platform': 'zoho'},
                {'text': 'Show won deals', 'type': 'pattern', 'label': 'Won deals', 'platform': 'zoho'},
                {'text': 'Show deals in negotiation', 'type': 'pattern', 'label': 'Deals in negotiation', 'platform': 'zoho'},
                {'text': 'List all leads', 'type': 'pattern', 'label': 'All leads', 'platform': 'zoho'},
                {'text': 'Show hot leads', 'type': 'pattern', 'label': 'Hot leads', 'platform': 'zoho'},
                {'text': 'Create a new lead', 'type': 'pattern', 'label': 'Create lead', 'platform': 'zoho'},
                {'text': 'List all accounts', 'type': 'pattern', 'label': 'All accounts', 'platform': 'zoho'},
                {'text': 'Show big deals over $10000', 'type': 'pattern', 'label': 'Big deals', 'platform': 'zoho'},
                {'text': 'Update deal stage', 'type': 'pattern', 'label': 'Update deal', 'platform': 'zoho'},
            ])
        
        # Zoho patterns
        if any(word in query_lower for word in ['deal', 'opportunity', 'sale']):
            patterns.extend([
                {'text': 'Show deals closing this week', 'type': 'pattern', 'label': 'Deals this week', 'platform': 'zoho'},
                {'text': 'List all deals', 'type': 'pattern', 'label': 'All deals', 'platform': 'zoho'},
                {'text': 'Show recent deals', 'type': 'pattern', 'label': 'Recent deals', 'platform': 'zoho'},
                {'text': 'Show won deals', 'type': 'pattern', 'label': 'Won deals', 'platform': 'zoho'},
                {'text': 'Show deals in negotiation', 'type': 'pattern', 'label': 'Deals in negotiation', 'platform': 'zoho'},
                {'text': 'Show big deals over $10000', 'type': 'pattern', 'label': 'Big deals', 'platform': 'zoho'},
            ])
        
        if any(word in query_lower for word in ['contact', 'person', 'client']):
            patterns.extend([
                {'text': 'List all contacts', 'type': 'pattern', 'label': 'All contacts', 'platform': 'zoho'},
                {'text': 'Show recent contacts', 'type': 'pattern', 'label': 'Recent contacts', 'platform': 'zoho'},
                {'text': 'Show contacts from Mumbai', 'type': 'pattern', 'label': 'Contacts by city', 'platform': 'zoho'},
            ])
        
        if any(word in query_lower for word in ['lead', 'prospect']):
            patterns.extend([
                {'text': 'List all leads', 'type': 'pattern', 'label': 'All leads', 'platform': 'zoho'},
                {'text': 'Show hot leads', 'type': 'pattern', 'label': 'Hot leads', 'platform': 'zoho'},
                {'text': 'Show recent leads', 'type': 'pattern', 'label': 'Recent leads', 'platform': 'zoho'},
                {'text': 'Create a new lead', 'type': 'pattern', 'label': 'Create lead', 'platform': 'zoho'},
            ])
        
        if any(word in query_lower for word in ['account', 'company', 'organization']):
            patterns.extend([
                {'text': 'List all accounts', 'type': 'pattern', 'label': 'All accounts', 'platform': 'zoho'},
                {'text': 'Show recent accounts', 'type': 'pattern', 'label': 'Recent accounts', 'platform': 'zoho'},
            ])
        
        if any(word in query_lower for word in ['create', 'add', 'new']):
            if any(word in query_lower for word in ['lead', 'prospect']):
                patterns.extend([
                    {'text': 'Create a new lead', 'type': 'pattern', 'label': 'Create lead', 'platform': 'zoho'},
                ])
            if any(word in query_lower for word in ['deal', 'opportunity']):
                patterns.extend([
                    {'text': 'Create a new deal', 'type': 'pattern', 'label': 'Create deal', 'platform': 'zoho'},
                ])
        
        if any(word in query_lower for word in ['update', 'change', 'modify', 'edit']):
            if any(word in query_lower for word in ['deal', 'opportunity']):
                patterns.extend([
                    {'text': 'Update deal stage', 'type': 'pattern', 'label': 'Update deal', 'platform': 'zoho'},
                ])
        
        # GitHub patterns
        if any(word in query_lower for word in ['pull', 'pr', 'request', 'merge']):
            patterns.extend([
                {'text': 'Show open pull requests', 'type': 'pattern', 'label': 'Open PRs', 'platform': 'github'},
                {'text': 'List recent pull requests', 'type': 'pattern', 'label': 'Recent PRs', 'platform': 'github'},
            ])
        
        if any(word in query_lower for word in ['issue', 'bug', 'ticket']):
            patterns.extend([
                {'text': 'Show open issues', 'type': 'pattern', 'label': 'Open issues', 'platform': 'github'},
                {'text': 'List recent issues', 'type': 'pattern', 'label': 'Recent issues', 'platform': 'github'},
            ])
        
        if any(word in query_lower for word in ['clone', 'repo', 'repository']):
            patterns.extend([
                {'text': 'How do I clone a repository?', 'type': 'pattern', 'label': 'How to clone repo', 'platform': 'github'},
            ])
        
        # GitHub push/commit patterns
        if any(word in query_lower for word in ['push', 'upload', 'send code', 'deploy code']):
            patterns.extend([
                {'text': 'How do I push code to GitHub?', 'type': 'pattern', 'label': 'How to push code to GitHub', 'platform': 'github'},
                {'text': 'How to push code in github?', 'type': 'pattern', 'label': 'How to push code in GitHub', 'platform': 'github'},
            ])
        
        # General GitHub knowledge questions
        if any(word in query_lower for word in ['how', 'what']) and any(word in query_lower for word in ['github', 'git', 'push', 'clone', 'commit', 'pr', 'pull request']):
            patterns.extend([
                {'text': 'How do I clone a repository?', 'type': 'pattern', 'label': 'How to clone repo', 'platform': 'github'},
                {'text': 'How do I push code to GitHub?', 'type': 'pattern', 'label': 'How to push code to GitHub', 'platform': 'github'},
            ])
        
        # Trello patterns - Trigger when "trello" is mentioned
        if 'trello' in query_lower:
            # Prioritize example queries first - use full text as label
            patterns.extend([
                {'text': 'Add "Fix bug" in Doing Card in your board', 'type': 'pattern', 'label': 'Add "Fix bug" in Doing Card in your board', 'platform': 'trello'},
                {'text': 'Add "Fix bug" in Doing list in your board', 'type': 'pattern', 'label': 'Add "Fix bug" in Doing list in your board', 'platform': 'trello'},
                {'text': 'Add "Review PR" in To Do list in your board', 'type': 'pattern', 'label': 'Add "Review PR" in To Do list in your board', 'platform': 'trello'},
                {'text': 'Add "New task" in To Do Card in your board', 'type': 'pattern', 'label': 'Add "New task" in To Do Card in your board', 'platform': 'trello'},
                {'text': 'Create card "Update docs" in Backlog in your board', 'type': 'pattern', 'label': 'Create card "Update docs" in Backlog in your board', 'platform': 'trello'},
                {'text': 'Add "Test feature" to In Progress list in your board', 'type': 'pattern', 'label': 'Add "Test feature" to In Progress list in your board', 'platform': 'trello'},
                {'text': 'Delete "Fix bug" from Doing list in your board', 'type': 'pattern', 'label': 'Delete "Fix bug" from Doing list in your board', 'platform': 'trello'},
                {'text': 'Delete "Fix bug" from Doing Card in your board', 'type': 'pattern', 'label': 'Delete "Fix bug" from Doing Card in your board', 'platform': 'trello'},
                {'text': 'Remove "Old task" from To Do list in your board', 'type': 'pattern', 'label': 'Remove "Old task" from To Do list in your board', 'platform': 'trello'},
                {'text': 'Remove "Fix bug" from Doing Card in your board', 'type': 'pattern', 'label': 'Remove "Fix bug" from Doing Card in your board', 'platform': 'trello'},
                {'text': 'Delete "Review PR" from To Do list in your board', 'type': 'pattern', 'label': 'Delete "Review PR" from To Do list in your board', 'platform': 'trello'},
                {'text': 'Show my boards', 'type': 'pattern', 'label': 'Show my boards', 'platform': 'trello'},
                {'text': 'List all boards', 'type': 'pattern', 'label': 'List all boards', 'platform': 'trello'},
                {'text': 'Show cards in To Do', 'type': 'pattern', 'label': 'Show cards in To Do', 'platform': 'trello'},
                {'text': 'Show cards in In Progress', 'type': 'pattern', 'label': 'Show cards in In Progress', 'platform': 'trello'},
                {'text': 'Show cards in Done', 'type': 'pattern', 'label': 'Show cards in Done', 'platform': 'trello'},
                {'text': 'Show cards in Backlog', 'type': 'pattern', 'label': 'Show cards in Backlog', 'platform': 'trello'},
                {'text': 'List all cards', 'type': 'pattern', 'label': 'List all cards', 'platform': 'trello'},
                {'text': 'Show cards on board', 'type': 'pattern', 'label': 'Show cards on board', 'platform': 'trello'},
                {'text': 'Show lists in board', 'type': 'pattern', 'label': 'Show lists in board', 'platform': 'trello'},
                {'text': 'Get all lists', 'type': 'pattern', 'label': 'Get all lists', 'platform': 'trello'},
                {'text': 'Get lists from board', 'type': 'pattern', 'label': 'Get lists from board', 'platform': 'trello'},
                {'text': 'Show cards with due date', 'type': 'pattern', 'label': 'Show cards with due date', 'platform': 'trello'},
                {'text': 'Show cards assigned to me', 'type': 'pattern', 'label': 'Show cards assigned to me', 'platform': 'trello'},
                {'text': 'Show overdue cards', 'type': 'pattern', 'label': 'Show overdue cards', 'platform': 'trello'},
            ])
        
        # Trello patterns - Card/task related (only if "trello" not already matched)
        if 'trello' not in query_lower:
            if any(word in query_lower for word in ['card', 'task', 'todo']):
                patterns.extend([
                    {'text': 'Show cards in To Do', 'type': 'pattern', 'label': 'Show cards in To Do', 'platform': 'trello'},
                    {'text': 'List all cards', 'type': 'pattern', 'label': 'List all cards', 'platform': 'trello'},
                    {'text': 'Show cards in In Progress', 'type': 'pattern', 'label': 'Show cards in In Progress', 'platform': 'trello'},
                    {'text': 'Show cards in Done', 'type': 'pattern', 'label': 'Show cards in Done', 'platform': 'trello'},
                ])
            
            if any(word in query_lower for word in ['create', 'add', 'new']):
                if any(word in query_lower for word in ['card', 'task']):
                    patterns.extend([
                        {'text': 'Add "Fix bug" in Doing Card in your board', 'type': 'pattern', 'label': 'Add "Fix bug" in Doing Card in your board', 'platform': 'trello'},
                        {'text': 'Add "Review PR" in To Do list in your board', 'type': 'pattern', 'label': 'Add "Review PR" in To Do list in your board', 'platform': 'trello'},
                        {'text': 'Create card "Update docs" in Backlog in your board', 'type': 'pattern', 'label': 'Create card "Update docs" in Backlog in your board', 'platform': 'trello'},
                    ])
            
            if any(word in query_lower for word in ['delete', 'remove']):
                if any(word in query_lower for word in ['card', 'task']):
                    patterns.extend([
                        {'text': 'Delete "Fix bug" from Doing list in your board', 'type': 'pattern', 'label': 'Delete "Fix bug" from Doing list in your board', 'platform': 'trello'},
                        {'text': 'Delete "Fix bug" from Doing Card in your board', 'type': 'pattern', 'label': 'Delete "Fix bug" from Doing Card in your board', 'platform': 'trello'},
                        {'text': 'Remove "Old task" from To Do list in your board', 'type': 'pattern', 'label': 'Remove "Old task" from To Do list in your board', 'platform': 'trello'},
                        {'text': 'Delete "Review PR" from To Do list in your board', 'type': 'pattern', 'label': 'Delete "Review PR" from To Do list in your board', 'platform': 'trello'},
                    ])
            
            if any(word in query_lower for word in ['board', 'project']):
                patterns.extend([
                    {'text': 'Show my boards', 'type': 'pattern', 'label': 'Show my boards', 'platform': 'trello'},
                    {'text': 'List all boards', 'type': 'pattern', 'label': 'List all boards', 'platform': 'trello'},
                ])
            
            if any(word in query_lower for word in ['list', 'column']):
                patterns.extend([
                    {'text': 'Show lists in board', 'type': 'pattern', 'label': 'Show lists in board', 'platform': 'trello'},
                    {'text': 'Get all lists', 'type': 'pattern', 'label': 'Get all lists', 'platform': 'trello'},
                ])
        
        # Salesforce patterns
        if any(word in query_lower for word in ['lead', 'opportunity', 'account']):
            patterns.extend([
                {'text': 'List all leads', 'type': 'pattern', 'label': 'All leads', 'platform': 'salesforce'},
                {'text': 'Show open opportunities', 'type': 'pattern', 'label': 'Open opportunities', 'platform': 'salesforce'},
            ])
        
        # General patterns
        if any(word in query_lower for word in ['how', 'what', 'when', 'where']):
            patterns.extend([
                {'text': 'How do I handle refunds?', 'type': 'pattern', 'label': 'How to handle refunds', 'platform': 'stripe'},
                {'text': 'How do I set up webhooks?', 'type': 'pattern', 'label': 'How to set up webhooks', 'platform': 'stripe'},
            ])
        
        return patterns[:limit]



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
                platform=(result.intent.get('platform') or 'unknown') if result.intent else 'unknown',
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
        
        # Debug logging for chart
        logger.info(f"[CHART RESPONSE] Checking chart in result - result.chart type: {type(result.chart)}, is None: {result.chart is None}")
        if result.chart:
            logger.info(f"[CHART RESPONSE] Chart included in response: type={result.chart.get('type') if isinstance(result.chart, dict) else 'unknown'}")
            logger.info(f"[CHART RESPONSE] Chart keys: {list(result.chart.keys()) if isinstance(result.chart, dict) else 'N/A'}")
        else:
            logger.warning(f"[CHART RESPONSE] No chart in result! result.chart = {result.chart}")
            logger.warning(f"[CHART RESPONSE] Result object type: {type(result)}, has chart attr: {hasattr(result, 'chart')}")
        
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


class WorkflowListCreateView(APIView):
    """List and create workflows."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List user's workflows."""
        workflows = Workflow.objects.filter(user=request.user)
        serializer = WorkflowSerializer(workflows, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new workflow."""
        serializer = WorkflowCreateSerializer(data=request.data)
        if serializer.is_valid():
            workflow = Workflow.objects.create(
                user=request.user,
                name=serializer.validated_data['name'],
                description=serializer.validated_data.get('description', ''),
                definition=serializer.validated_data['definition']
            )
            return Response(WorkflowSerializer(workflow).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WorkflowDetailView(APIView):
    """Retrieve, update, or delete a workflow."""
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Workflow.objects.get(pk=pk, user=self.request.user)
        except Workflow.DoesNotExist:
            return None
    
    def get(self, request, pk):
        """Get workflow details."""
        workflow = self.get_object(pk)
        if not workflow:
            return Response({'error': 'Workflow not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = WorkflowSerializer(workflow)
        return Response(serializer.data)
    
    def put(self, request, pk):
        """Update workflow."""
        workflow = self.get_object(pk)
        if not workflow:
            return Response({'error': 'Workflow not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = WorkflowCreateSerializer(data=request.data)
        if serializer.is_valid():
            workflow.name = serializer.validated_data['name']
            workflow.description = serializer.validated_data.get('description', '')
            workflow.definition = serializer.validated_data['definition']
            workflow.save()
            return Response(WorkflowSerializer(workflow).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete workflow."""
        workflow = self.get_object(pk)
        if not workflow:
            return Response({'error': 'Workflow not found'}, status=status.HTTP_404_NOT_FOUND)
        workflow.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkflowExecuteView(APIView):
    """Execute a workflow."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Execute a workflow."""
        try:
            workflow = Workflow.objects.get(pk=pk, user=request.user)
        except Workflow.DoesNotExist:
            return Response({'error': 'Workflow not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get credentials
        connections = PlatformConnection.objects.filter(user=request.user, is_valid=True)
        credentials = {}
        for conn in connections:
            try:
                decrypted_key = decrypt_api_key(conn.encrypted_api_key)
                creds = {'api_key': decrypted_key}
                if conn.metadata:
                    creds.update(conn.metadata)
                credentials[conn.platform.lower()] = creds
            except Exception as e:
                logger.error(f"Failed to decrypt key for {conn.platform}: {e}")
        
        # Execute workflow
        engine = WorkflowEngine(request.user, credentials)
        input_data = request.data.get('input_data', {})
        execution = engine.execute_workflow(workflow, input_data)
        
        serializer = WorkflowExecutionSerializer(execution)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkflowExecutionListView(APIView):
    """List workflow executions."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get executions for a workflow."""
        try:
            workflow = Workflow.objects.get(pk=pk, user=request.user)
        except Workflow.DoesNotExist:
            return Response({'error': 'Workflow not found'}, status=status.HTTP_404_NOT_FOUND)
        
        executions = WorkflowExecution.objects.filter(workflow=workflow).order_by('-started_at')[:50]
        serializer = WorkflowExecutionSerializer(executions, many=True)
        return Response(serializer.data)


class QuerySuggestionsView(APIView):
    """Get AI-powered query suggestions."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get query suggestions."""
        current_query = request.query_params.get('q', '').strip()
        platform = request.query_params.get('platform', '').strip()
        limit = int(request.query_params.get('limit', 10))
        
        service = QuerySuggestionService(request.user)
        suggestions = service.get_suggestions(
            current_query=current_query,
            platform=platform,
            limit=limit
        )
        
        # Track suggestions shown
        for sug in suggestions:
            service.track_suggestion_shown(sug)
        
        serializer = QuerySuggestionSerializer(suggestions, many=True)
        return Response({
            'suggestions': serializer.data,
            'query': current_query
        })
    
    def post(self, request):
        """Track suggestion click."""
        query_text = request.data.get('query_text', '')
        platform = request.data.get('platform', '')
        suggestion_type = request.data.get('suggestion_type', 'similar')
        
        if query_text:
            service = QuerySuggestionService(request.user)
            service.track_suggestion_clicked({
                'query_text': query_text,
                'platform': platform,
                'suggestion_type': suggestion_type
            })
        
        return Response({'status': 'tracked'})
