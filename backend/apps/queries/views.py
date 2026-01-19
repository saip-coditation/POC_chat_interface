"""
Query Views
"""

import time
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platforms.models import PlatformConnection
from utils.encryption import decrypt_api_key
from utils import openai_client, stripe_client, zoho_client, github_client
from .models import QueryLog
from .serializers import ProcessQuerySerializer, QueryLogSerializer

logger = logging.getLogger(__name__)


class ProcessQueryView(APIView):
    """Process a natural language query against connected platforms."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        logs = []
        try:
            start_time = time.time()
            
            # --- Agent: Request Handler ---
            serializer = ProcessQuerySerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
            query = serializer.validated_data['query']
            requested_platform = serializer.validated_data.get('platform', '')
            logs.append({"agent": "Request Handler", "message": f"Received query: '{query}'"})

            # Get user's connected platforms
            connections = PlatformConnection.objects.filter(user=request.user, is_valid=True)
            if not connections.exists():
                return Response({'success': False, 'error': 'No platforms connected.'}, status=status.HTTP_400_BAD_REQUEST)
            
            available_platforms = [c.platform for c in connections]
            logs.append({"agent": "Request Handler", "message": f"Active connections: {', '.join(available_platforms)}"})

            # --- Agent 1: Classifier ---
            if requested_platform and requested_platform in available_platforms:
                platform = requested_platform
                logs.append({"agent": "Classifier", "message": f"Using user specified platform: {platform}"})
            else:
                detection = openai_client.detect_platform(query, available_platforms)
                platform = detection.get('platform', available_platforms[0])
                confidence = detection.get('confidence', 0.5)
                logs.append({"agent": "Classifier", "message": f"Detected target platform: {platform} (Confidence: {confidence:.2f})"})
            
            # Get connection and decrypt key
            connection = connections.get(platform=platform)
            try:
                api_key = decrypt_api_key(connection.encrypted_api_key)
            except Exception:
                return Response({'success': False, 'error': 'Credential error'}, status=500)

            # --- Agent 2: Planner ---
            query_params = openai_client.generate_query_params(query, platform)
            action = query_params.get('action', '')
            filters = query_params.get('filters', {})
            logs.append({"agent": "Planner", "message": f"Determined action: '{action}' with filters: {filters}"})

            # --- Agent 3: Fetcher ---
            logs.append({"agent": "Fetcher", "message": f"Executing '{action}' against {platform} API..."})
            try:
                if platform == 'stripe':
                    data = self._fetch_stripe_data(api_key, action, filters)
                elif platform == 'zoho':
                    # Support for Multi-Page Fetching (User Request: "Multiple API Calls")
                    is_paged_fetch = 'deals' in action or 'contacts' in action
                    
                    if is_paged_fetch:
                         all_items = []
                         # Fetch Page 1
                         logs.append({"agent": "Fetcher", "message": "Requesting Page 1 (Records 1-50)..."})
                         p1 = self._fetch_zoho_data(api_key, action, {**filters, 'page': 1, 'limit': 50}, connection.metadata)
                         if isinstance(p1, dict) and 'data' in p1:
                             all_items.extend(p1['data'])
                         
                         # Fetch Page 2
                         logs.append({"agent": "Fetcher", "message": "Requesting Page 2 (Records 51-100)..."})
                         p2 = self._fetch_zoho_data(api_key, action, {**filters, 'page': 2, 'limit': 50}, connection.metadata)
                         if isinstance(p2, dict) and 'data' in p2 and p2['data']:
                             all_items.extend(p2['data'])
                             logs.append({"agent": "Fetcher", "message": f"Retrieved {len(p2['data'])} additional records from Page 2."})
                         else:
                             logs.append({"agent": "Fetcher", "message": "No more records on Page 2."})

                         data = {'data': all_items, 'count': len(all_items)}
                    else:
                         data = self._fetch_zoho_data(api_key, action, filters, connection.metadata)
                elif platform == 'github':
                    data = self._fetch_github_data(api_key, action, filters, query, connection.metadata)
                else:
                    data = {'error': 'Unsupported platform'}
                
                # Check for errors in data
                if 'error' in data and not data.get('data'):
                     raise Exception(data['error'])
                     
                item_count = data.get('count', len(data.get('data', []))) if isinstance(data, dict) else 0
                logs.append({"agent": "Fetcher", "message": f"Successfully retrieved {item_count} items."})
                
            except Exception as e:
                logs.append({"agent": "Fetcher", "message": f"Error: {str(e)}", "status": "error"})
                # Log failure
                QueryLog.objects.create(user=request.user, platform=platform, query_text=query, was_successful=False, error_message=str(e))
                return Response({'success': False, 'error': str(e), 'logs': logs}, status=500)

            # --- Agent 4: Analyst (Charts) ---
            chart_config = openai_client.generate_chart_config(query, data, platform)
            if chart_config:
                logs.append({"agent": "Analyst", "message": f"Generated {chart_config['type']} chart visualization."})
            else:
                logs.append({"agent": "Analyst", "message": "No suitable chart visualization found."})

            # --- Agent 5: Summarizer ---
            summary = openai_client.summarize_results(query, data, platform)
            logs.append({"agent": "Summarizer", "message": "Generated natural language summary."})

            # Format Response
            response_data = self._format_response(data, platform, action)
            processing_time = int((time.time() - start_time) * 1000)

            # Log success
            QueryLog.objects.create(
                user=request.user, platform=platform, query_text=query,
                response_summary=summary, response_data=response_data,
                was_successful=True, processing_time_ms=processing_time
            )

            return Response({
                'success': True,
                'platform': platform,
                'platform_name': platform.title(),
                'summary': summary,
                'data': response_data.get('data'),
                'columns': response_data.get('columns'),
                'type': response_data.get('type', 'general'),
                'chart': chart_config,
                'logs': logs,
                'processing_time_ms': processing_time
            })

        except Exception as e:
            logger.exception("Global query processing error")
            logs.append({"agent": "System", "message": f"Critical Error: {str(e)}", "status": "error"})
            return Response({'success': False, 'error': f"Internal Server Error: {str(e)}", 'logs': logs}, status=500)
    
    def _fetch_stripe_data(self, api_key, action, filters):
        """Fetch data from Stripe based on action."""
        stripe_client.stripe.api_key = api_key
        
        if action == 'list_invoices':
            return stripe_client.fetch_invoices(api_key, filters)
        elif action == 'list_subscriptions':
            return stripe_client.fetch_subscriptions(api_key, filters)
        elif action == 'get_revenue':
            return stripe_client.fetch_revenue(api_key, filters)
        elif action == 'list_customers':
            return stripe_client.fetch_customers(api_key, filters)
        elif action == 'list_products':
            return stripe_client.fetch_products(api_key, filters)
        elif action == 'list_payouts':
            return stripe_client.fetch_payouts(api_key, filters)
        elif action == 'list_charges':
            # Add charge fetching
            try:
                charges = stripe_client.stripe.Charge.list(limit=filters.get('limit', 50))
                return {
                    'data': [
                        {
                            'id': c.id,
                            'amount': c.amount / 100,
                            'status': c.status,
                            'created': datetime.fromtimestamp(c.created).isoformat()
                        } for c in charges.data
                    ],
                    'count': len(charges.data)
                }
            except Exception as e:
                return {'error': str(e)}
        elif action == 'get_account':
            return stripe_client.validate_api_key(api_key)
        else:
            # If no action matched, try to be smart or default to invoices
            logger.warning(f"Unknown Stripe action: {action}")
            return stripe_client.fetch_invoices(api_key, filters)
    
    def _fetch_zoho_data(self, api_key, action, filters, metadata=None):
        """Fetch data from Zoho CRM based on action."""
        client_credentials = None
        if metadata:
            client_credentials = {
                'client_id': metadata.get('client_id'),
                'client_secret': metadata.get('client_secret')
            }

        if action == 'list_contacts':
            return zoho_client.fetch_contacts(api_key, filters, client_credentials)
        elif action == 'list_deals':
            return zoho_client.fetch_deals(api_key, filters, client_credentials)
        elif action == 'list_leads':
            return zoho_client.fetch_leads(api_key, filters, client_credentials)
        elif action == 'list_accounts':
            return zoho_client.fetch_accounts(api_key, filters, client_credentials)
        else:
            # Default to contacts
            return zoho_client.fetch_contacts(api_key, filters, client_credentials)
    
    def _fetch_github_data(self, api_key, action, filters, query='', metadata=None):
        """Fetch data from GitHub based on action."""
        import re
        
        # Get the connected GitHub username from metadata (saved during connection)
        github_username = ''
        if metadata:
            github_username = metadata.get('username', '')
        
        # Extract repo name from filters or from query text
        def get_owner_repo():
            owner = filters.get('owner', '')
            repo = filters.get('repo', '')
            repo_name = filters.get('repo_name', '')
            
            # If we have owner/repo format in repo_name, parse it
            if '/' in repo_name:
                parts = repo_name.split('/', 1)
                owner_part = parts[0]
                repo = parts[1]
                
                # If owner is the placeholder "owner", use the connected username
                if owner_part.lower() == 'owner':
                    owner = github_username
                else:
                    owner = owner_part
            elif repo_name and not owner:
                # repo_name is just the repo, use github_username as owner
                repo = repo_name
                if repo_name.lower() == 'owner':
                    owner = github_username
                else:
                    owner = github_username
            
            # If still no repo, try to extract from query text
            if not repo and query:
                # Look for patterns like "Cobol_to_Java_Converter" or repo names in the query
                query_lower = query.lower()
                
                # Try to find a repo name that looks like a project name
                # Match words with underscores, hyphens, or CamelCase patterns
                matches = re.findall(r'[A-Za-z][A-Za-z0-9_-]{3,}', query)
                
                # Filter out common words
                common_words = {'show', 'list', 'pull', 'requests', 'commits', 'issues', 
                               'number', 'how', 'many', 'the', 'for', 'repository', 
                               'repo', 'from', 'about', 'tell', 'more', 'only', 'github'}
                
                for match in matches:
                    if match.lower() not in common_words and len(match) > 4:
                        repo = match
                        break
            
            # Default to github_username as owner if we have a repo but no owner
            if repo and not owner:
                owner = github_username
                
            return owner, repo
        
        if action == 'list_repos':
            return github_client.fetch_repos(api_key, filters)
        
        elif action == 'repo_summary':
            owner, repo = get_owner_repo()
            if owner and repo:
                return github_client.fetch_repo_summary(api_key, owner, repo)
            return {'error': 'Please specify a repository name (e.g., "summarize owner/repo")'}
        
        elif action == 'list_commits':
            owner, repo = get_owner_repo()
            if owner and repo:
                return github_client.fetch_commits(api_key, owner, repo, filters)
            return {'error': 'Please specify a repository'}
        
        elif action in ['list_prs', 'list_pull_requests']:
            owner, repo = get_owner_repo()
            if owner and repo:
                return github_client.fetch_pull_requests(api_key, owner, repo, filters)
            return {'error': 'Please specify a repository'}
        
        elif action == 'list_issues':
            owner, repo = get_owner_repo()
            if owner and repo:
                return github_client.fetch_issues(api_key, owner, repo, filters)
            return {'error': 'Please specify a repository'}
        
        else:
            # Default to listing repos
            return github_client.fetch_repos(api_key, filters)
    
    def _format_response(self, data, platform, action):
        """Format the response with appropriate columns."""
        if platform == 'stripe':
            if action == 'list_invoices':
                return {
                    'type': 'invoices',
                    'data': data.get('data', []),
                    'columns': ['ID', 'Customer', 'Amount', 'Status', 'Created']
                }
            elif action == 'list_subscriptions':
                return {
                    'type': 'subscriptions',
                    'data': data.get('data', []),
                    'columns': ['ID', 'Customer', 'Status', 'Amount', 'Interval']
                }
            elif action == 'get_revenue':
                return {
                    'type': 'metrics',
                    'data': None,
                    'metrics': data
                }
            elif action == 'list_customers':
                return {
                    'type': 'customers',
                    'data': data.get('data', []),
                    'columns': ['ID', 'Name', 'Email', 'Created']
                }
            elif action == 'list_products':
                return {
                    'type': 'products',
                    'data': data.get('data', []),
                    'columns': ['ID', 'Name', 'Active', 'Description', 'Created']
                }
            elif action == 'list_payouts':
                return {
                    'type': 'payouts',
                    'data': data.get('data', []),
                    'columns': ['ID', 'Amount', 'Currency', 'Status', 'Arrival Date']
                }
            elif action == 'list_charges':
                return {
                    'type': 'charges',
                    'data': data.get('data', []),
                    'columns': ['ID', 'Amount', 'Status', 'Created']
                }
            elif action == 'get_account':
                return {
                    'type': 'account',
                    'data': [data] if 'valid' in data else [],
                    'columns': ['business_name', 'account_id']
                }
        
        elif platform == 'zendesk':
            if action in ['list_tickets', 'search_tickets']:
                return {
                    'type': 'tickets',
                    'data': data.get('data', []),
                    'columns': ['ID', 'Subject', 'Status', 'Priority', 'Created']
                }
            elif action == 'get_metrics':
                return {
                    'type': 'metrics',
                    'data': None,
                    'metrics': data
                }
        
        elif platform == 'github':
            if action == 'list_repos':
                return {
                    'type': 'repositories',
                    'data': data.get('data', []),
                    'columns': ['Name', 'Description', 'Language', 'Stars', 'Updated']
                }
            elif action == 'repo_summary':
                return {
                    'type': 'repo_summary',
                    'data': data,
                    'columns': None
                }
            elif action == 'list_commits':
                return {
                    'type': 'commits',
                    'data': data.get('data', []),
                    'columns': ['SHA', 'Message', 'Author', 'Date']
                }
            elif action in ['list_prs', 'list_pull_requests']:
                return {
                    'type': 'pull_requests',
                    'data': data.get('data', []),
                    'columns': ['#', 'Title', 'State', 'Author', 'Created'],
                    'stats': {
                        'open': data.get('open', 0),
                        'merged': data.get('merged', 0),
                        'closed': data.get('closed', 0)
                    }
                }
            elif action == 'list_issues':
                return {
                    'type': 'issues',
                    'data': data.get('data', []),
                    'columns': ['#', 'Title', 'State', 'Author', 'Created'],
                    'stats': {
                        'open': data.get('open', 0),
                        'closed': data.get('closed', 0)
                    }
                }
        
        # Default
        return {
            'type': 'general',
            'data': data.get('data') if isinstance(data, dict) else data
        }


class QueryHistoryView(APIView):
    """Get query history for the current user."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        queries = QueryLog.objects.filter(user=request.user)[:50]
        serializer = QueryLogSerializer(queries, many=True)
        
        return Response({
            'success': True,
            'queries': serializer.data
        })
