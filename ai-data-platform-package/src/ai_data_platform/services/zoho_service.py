"""
Zoho CRM Service for AI Data Platform

Handles Zoho CRM API interactions using OAuth2 refresh tokens.
"""

import os
import logging
import requests
from typing import Dict, Any

from ..core.base import BasePlatformService
from .ai_service import ai_service

logger = logging.getLogger(__name__)


class ZohoService(BasePlatformService):
    """Service for interacting with Zoho CRM."""
    
    @property
    def platform_id(self) -> str:
        return 'zoho'
    
    def _get_zoho_config(self) -> Dict[str, str]:
        """Get Zoho configuration from environment."""
        accounts_domain = os.getenv('ZOHO_ACCOUNTS_DOMAIN', 'accounts.zoho.in')
        api_domain = os.getenv('ZOHO_API_DOMAIN', 'www.zohoapis.in')
        return {
            'token_url': f"https://{accounts_domain}/oauth/v2/token",
            'api_base': f"https://{api_domain}/crm/v2",
            'client_id': os.getenv('ZOHO_CLIENT_ID', ''),
            'client_secret': os.getenv('ZOHO_CLIENT_SECRET', '')
        }
    
    def _get_access_token(self, refresh_token: str) -> str:
        """Exchange refresh token for access token."""
        config = self._get_zoho_config()
        
        if not config['client_id'] or not config['client_secret']:
            raise ValueError("ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET must be set in environment variables")
        
        response = requests.post(config['token_url'], data={
            'refresh_token': refresh_token,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'grant_type': 'refresh_token'
        }, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Zoho token refresh failed: {response.text}")
            raise ValueError(f"Failed to refresh Zoho token: {response.text}")
        
        data = response.json()
        if 'error' in data:
            raise ValueError(f"Zoho error: {data.get('error')}")
        return data.get('access_token')
    
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """Validate Zoho credentials by attempting to get an access token and fetch contacts."""
        refresh_token = credentials.get('api_key') or credentials.get('refresh_token')
        if not refresh_token:
            raise ValueError("Missing refresh_token or api_key")
        
        try:
            access_token = self._get_access_token(refresh_token)
            config = self._get_zoho_config()
            
            # Test by fetching first contact (uses ZohoCRM.modules.ALL scope)
            response = requests.get(
                f"{config['api_base']}/Contacts?per_page=1",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                timeout=10
            )
            
            # 200 = success, 204 = no content (valid but empty)
            if response.status_code in [200, 204]:
                return True
            
            raise ValueError(f"Zoho API error: {response.text}")
        except Exception as e:
            raise ValueError(f"Zoho connection failed: {e}")
    
    def get_metadata(self) -> Dict[str, Any]:
        return {"name": "Zoho CRM", "description": "Customer relationship management"}
    
    def process_query(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a natural language query against Zoho CRM."""
        refresh_token = user_context.get('api_key') or user_context.get('refresh_token')
        
        if not refresh_token:
            return {'error': 'No Zoho refresh token provided'}
        
        # 1. Interpret Query using AI
        system_prompt = """You interpret natural language queries about Zoho CRM data.
Available actions:
- fetch_contacts: Get contacts (Filters: limit)
- fetch_leads: Get leads (Filters: limit)
- fetch_deals: Get deals (Filters: limit)
- fetch_accounts: Get accounts/companies (Filters: limit)
Respond with JSON: {"action": "...", "filters": {...}}"""
        
        params = ai_service.interpret_query(query, 'zoho', system_prompt)
        
        if params.get('action') == 'error':
            return {'error': params.get('error')}
        
        action = params.get('action')
        filters = params.get('filters', {})
        
        # 2. Execute Action
        data = {}
        try:
            if action == 'fetch_contacts':
                data = self._fetch_contacts(refresh_token, filters)
            elif action == 'fetch_leads':
                data = self._fetch_leads(refresh_token, filters)
            elif action == 'fetch_deals':
                data = self._fetch_deals(refresh_token, filters)
            elif action == 'fetch_accounts':
                data = self._fetch_accounts(refresh_token, filters)
            else:
                data = {'error': f"Unknown action: {action}"}
        except Exception as e:
            logger.error(f"Zoho action error: {e}")
            data = {'error': str(e)}
        
        if 'error' in data:
            return data
        
        # 3. Summarize Results
        summary = ai_service.summarize_results(query, data, 'zoho')
        return {
            'summary': summary,
            'data': data
        }
    
    def _fetch_contacts(self, refresh_token: str, filters: Dict) -> Dict:
        """Fetch contacts from Zoho CRM."""
        try:
            access_token = self._get_access_token(refresh_token)
            config = self._get_zoho_config()
            
            limit = min(filters.get('limit', 50), 200)
            url = f"{config['api_base']}/Contacts?per_page={limit}"
            
            response = requests.get(
                url,
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                timeout=15
            )
            
            if response.status_code != 200:
                return {'data': [], 'count': 0, 'error': f"Zoho API error: {response.text}"}
            
            data = response.json()
            contacts = data.get('data', [])
            
            result = []
            for contact in contacts:
                result.append({
                    'id': contact.get('id'),
                    'name': f"{contact.get('First_Name', '')} {contact.get('Last_Name', '')}".strip(),
                    'email': contact.get('Email'),
                    'phone': contact.get('Phone'),
                    'company': contact.get('Account_Name', {}).get('name') if contact.get('Account_Name') else None,
                    'created': contact.get('Created_Time')
                })
            
            return {'data': result, 'count': len(result)}
        except Exception as e:
            return {'data': [], 'count': 0, 'error': str(e)}
    
    def _fetch_leads(self, refresh_token: str, filters: Dict) -> Dict:
        """Fetch leads from Zoho CRM."""
        try:
            access_token = self._get_access_token(refresh_token)
            config = self._get_zoho_config()
            
            limit = min(filters.get('limit', 50), 200)
            url = f"{config['api_base']}/Leads?per_page={limit}"
            
            response = requests.get(
                url,
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                timeout=15
            )
            
            if response.status_code != 200:
                return {'data': [], 'count': 0, 'error': f"Zoho API error: {response.text}"}
            
            data = response.json()
            leads = data.get('data', [])
            
            result = []
            for lead in leads:
                result.append({
                    'id': lead.get('id'),
                    'name': f"{lead.get('First_Name', '')} {lead.get('Last_Name', '')}".strip(),
                    'email': lead.get('Email'),
                    'company': lead.get('Company'),
                    'status': lead.get('Lead_Status'),
                    'source': lead.get('Lead_Source'),
                    'created': lead.get('Created_Time')
                })
            
            return {'data': result, 'count': len(result)}
        except Exception as e:
            return {'data': [], 'count': 0, 'error': str(e)}
    
    def _fetch_deals(self, refresh_token: str, filters: Dict) -> Dict:
        """Fetch deals from Zoho CRM."""
        try:
            access_token = self._get_access_token(refresh_token)
            config = self._get_zoho_config()
            
            limit = min(filters.get('limit', 50), 200)
            url = f"{config['api_base']}/Deals?per_page={limit}"
            
            response = requests.get(
                url,
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                timeout=15
            )
            
            if response.status_code != 200:
                return {'data': [], 'count': 0, 'error': f"Zoho API error: {response.text}"}
            
            data = response.json()
            deals = data.get('data', [])
            
            result = []
            for deal in deals:
                result.append({
                    'id': deal.get('id'),
                    'name': deal.get('Deal_Name'),
                    'amount': deal.get('Amount'),
                    'stage': deal.get('Stage'),
                    'closing_date': deal.get('Closing_Date'),
                    'account': deal.get('Account_Name', {}).get('name') if deal.get('Account_Name') else None,
                    'created': deal.get('Created_Time')
                })
            
            return {'data': result, 'count': len(result)}
        except Exception as e:
            return {'data': [], 'count': 0, 'error': str(e)}
    
    def _fetch_accounts(self, refresh_token: str, filters: Dict) -> Dict:
        """Fetch accounts (companies) from Zoho CRM."""
        try:
            access_token = self._get_access_token(refresh_token)
            config = self._get_zoho_config()
            
            limit = min(filters.get('limit', 50), 200)
            url = f"{config['api_base']}/Accounts?per_page={limit}"
            
            response = requests.get(
                url,
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                timeout=15
            )
            
            if response.status_code != 200:
                return {'data': [], 'count': 0, 'error': f"Zoho API error: {response.text}"}
            
            data = response.json()
            accounts = data.get('data', [])
            
            result = []
            for account in accounts:
                result.append({
                    'id': account.get('id'),
                    'name': account.get('Account_Name'),
                    'website': account.get('Website'),
                    'industry': account.get('Industry'),
                    'phone': account.get('Phone'),
                    'created': account.get('Created_Time')
                })
            
            return {'data': result, 'count': len(result)}
        except Exception as e:
            return {'data': [], 'count': 0, 'error': str(e)}
