"""
Zoho CRM API Client

Handles Zoho CRM API interactions using OAuth2 refresh tokens.
"""

import logging
import os
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Zoho OAuth endpoints - configured for India (.in) by default
# Change to .com for US, .eu for EU, etc.
def _get_zoho_config(client_credentials=None):
    """
    Get Zoho configuration from environment or provided credentials.
    
    Args:
        client_credentials (dict, optional): Dict containing 'client_id' and 'client_secret'
    """
    accounts_domain = os.getenv('ZOHO_ACCOUNTS_DOMAIN', 'accounts.zoho.in')
    api_domain = os.getenv('ZOHO_API_DOMAIN', 'www.zohoapis.in')
    
    client_id = os.getenv('ZOHO_CLIENT_ID', '')
    client_secret = os.getenv('ZOHO_CLIENT_SECRET', '')
    
    if client_credentials:
        client_id = client_credentials.get('client_id', client_id)
        client_secret = client_credentials.get('client_secret', client_secret)
        
    return {
        'token_url': f"https://{accounts_domain}/oauth/v2/token",
        'api_base': f"https://{api_domain}/crm/v2",
        'client_id': client_id,
        'client_secret': client_secret
    }


def exchange_code_for_tokens(authorization_code: str, client_credentials=None) -> dict:
    """
    Exchange authorization code for access and refresh tokens.
    """
    config = _get_zoho_config(client_credentials)
    
    if not config['client_id'] or not config['client_secret']:
        return {'success': False, 'error': 'Client ID and Secret are required'}
    
    try:
        response = requests.post(config['token_url'], data={
            'grant_type': 'authorization_code',
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'redirect_uri': 'http://localhost',
            'code': authorization_code
        }, timeout=15)
        
        data = response.json()
        logger.info(f"Zoho token exchange response: {data}")
        
        if 'error' in data:
            return {'success': False, 'error': data.get('error')}
        
        if 'refresh_token' in data:
            return {
                'success': True,
                'refresh_token': data['refresh_token'],
                'access_token': data.get('access_token'),
                'expires_in': data.get('expires_in', 3600)
            }
        else:
            return {'success': False, 'error': 'No refresh token in response. Code may have expired.'}
            
    except Exception as e:
        logger.error(f"Zoho code exchange error: {e}")
        return {'success': False, 'error': str(e)}


def get_access_token(refresh_token: str, client_credentials=None) -> str:
    """
    Exchange refresh token for access token.
    """
    config = _get_zoho_config(client_credentials)
    
    if not config['client_id'] or not config['client_secret']:
        raise ValueError("Client ID and Secret are required")
    
    try:
        response = requests.post(config['token_url'], data={
            'refresh_token': refresh_token,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'grant_type': 'refresh_token'
        }, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"[ZOHO] Token refresh failed: {response.text}")
            error_msg = f"[ZOHO] Failed to refresh token: {response.text}"
            
            if "not valid for any token type" in response.text:
                error_msg += " (Hint: The refresh token may be revoked, expired, or generated for a different Data Center. Current domain: " + config['token_url'] + ")"
            
            if "invalid_client" in response.text:
                 error_msg += " (Hint: Check ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET)"
                 
            raise ValueError(error_msg)
        
        data = response.json()
        if 'error' in data:
            raise ValueError(f"Zoho error: {data.get('error')}")
        return data.get('access_token')
    except Exception as e:
        logger.error(f"Zoho token error: {e}")
        raise


def validate_credentials(refresh_token: str, client_credentials=None) -> dict:
    """
    Validate Zoho credentials by attempting to get an access token and fetch contacts.
    """
    try:
        access_token = get_access_token(refresh_token, client_credentials)
        config = _get_zoho_config(client_credentials)
        
        # Test by fetching first contact (uses ZohoCRM.modules.ALL scope)
        response = requests.get(
            f"{config['api_base']}/Contacts?per_page=1",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            timeout=10
        )
        
        # 200 = success, 204 = no content (valid but empty)
        if response.status_code in [200, 204]:
            return {
                'valid': True,
                'message': 'Zoho CRM connected successfully'
            }
        
        return {'valid': False, 'error': f"Zoho API error: {response.text}"}
    except ValueError as e:
        # Token refresh failed
        return {'valid': False, 'error': str(e)}
    except Exception as e:
        return {'valid': False, 'error': str(e)}


def fetch_contacts(refresh_token: str, filters: dict = None, client_credentials=None) -> dict:
    """
    Fetch contacts from Zoho CRM.
    """
    filters = filters or {}
    try:
        access_token = get_access_token(refresh_token, client_credentials)
        config = _get_zoho_config(client_credentials)
        
        name_filter = filters.get('name')
        
        if name_filter:
            # Use Search API for specific name lookup (bypass pagination limits)
            url = f"{config['api_base']}/Contacts/search?criteria=((First_Name:starts_with:{name_filter})OR(Last_Name:starts_with:{name_filter}))"
        else:
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

        # Get location filter if specified
        # Get location filter if specified
        location_filter = filters.get('city') or filters.get('location') or filters.get('state')
        
        result = []
        for contact in contacts:
            # Safe name formatting
            first = contact.get('First_Name') or ''
            last = contact.get('Last_Name') or ''
            name = f"{first} {last}".strip()
            
            contact_data = {
                'id': contact.get('id'),
                'name': name,
                'email': contact.get('Email'),
                'phone': contact.get('Phone'),
                'company': contact.get('Account_Name', {}).get('name') if contact.get('Account_Name') else None,
                # Capture location fields for filtering
                'city': contact.get('Mailing_City') or contact.get('Other_City') or '',
                'state': contact.get('Mailing_State') or contact.get('Other_State') or '',
                'country': contact.get('Mailing_Country') or contact.get('Other_Country') or '',
                'created': contact.get('Created_Time')
            }
            
            # Apply name filter if specified
            if name_filter and name_filter.lower() not in name.lower():
                continue

            # Apply location filter if specified
            if location_filter:
                loc_lower = location_filter.lower()
                # Check against all address fields
                contact_loc = f"{contact_data['city']} {contact_data['state']} {contact_data['country']}".lower()
                if loc_lower in contact_loc:
                    result.append(contact_data)
            else:
                result.append(contact_data)
        
        return {'data': result, 'count': len(result), 'filter_applied': location_filter}
    except Exception as e:
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_deals(refresh_token: str, filters: dict = None, client_credentials=None) -> dict:
    """
    Fetch deals from Zoho CRM.
    """
    filters = filters or {}
    try:
        access_token = get_access_token(refresh_token, client_credentials)
        config = _get_zoho_config(client_credentials)
        
        limit = min(filters.get('limit', 50), 200)
        page = filters.get('page', 1)
        url = f"{config['api_base']}/Deals?per_page={limit}&page={page}"
        
        response = requests.get(
            url,
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            timeout=15
        )
        
        if response.status_code != 200:
            return {'data': [], 'count': 0, 'error': f"Zoho API error: {response.text}"}
        
        data = response.json()
        deals = data.get('data', [])
        
        # Apply filters
        amount_gt = filters.get('amount_gt')  # Filter deals above this amount
        stage_filter = filters.get('stage')  # Filter by stage
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ZOHO DEALS] Received filters dict: {filters}")
        logger.info(f"[ZOHO DEALS] Total deals fetched from API: {len(deals)}, filters: amount_gt={amount_gt} (type: {type(amount_gt)}), stage={stage_filter}")
        
        result = []
        for deal in deals:
            deal_amount = deal.get('Amount')
            deal_stage = deal.get('Stage')
            
            # Filter by amount if specified
            if amount_gt is not None:
                try:
                    # Parse amount_gt - handle strings like "60000", "60,000", "$60000"
                    amount_threshold = amount_gt
                    if isinstance(amount_threshold, str):
                        # Remove currency symbols, commas, and spaces
                        amount_threshold = amount_threshold.replace('$', '').replace(',', '').replace(' ', '').strip()
                    amount_threshold = float(amount_threshold)
                    
                    # Parse deal amount - handle various formats from Zoho
                    amount_value = 0
                    if deal_amount:
                        if isinstance(deal_amount, (int, float)):
                            amount_value = float(deal_amount)
                        elif isinstance(deal_amount, str):
                            # Remove currency symbols, commas, spaces
                            amount_str = deal_amount.replace('$', '').replace(',', '').replace(' ', '').strip()
                            amount_value = float(amount_str) if amount_str else 0
                        else:
                            amount_value = float(deal_amount)
                    
                    # Filter: only include deals >= threshold
                    logger.info(f"[ZOHO DEALS] Comparing deal '{deal.get('Deal_Name')}': amount_value={amount_value} (from '{deal_amount}') vs threshold={amount_threshold}")
                    if amount_value < amount_threshold:
                        logger.info(f"[ZOHO DEALS] ❌ FILTERED OUT deal '{deal.get('Deal_Name')}' - amount {amount_value} < {amount_threshold}")
                        continue
                    else:
                        logger.info(f"[ZOHO DEALS] ✅ INCLUDING deal '{deal.get('Deal_Name')}' - amount {amount_value} >= {amount_threshold}")
                except (ValueError, TypeError) as e:
                    # If amount can't be parsed, skip this deal
                    logger.warning(f"[ZOHO DEALS] Could not parse deal amount '{deal_amount}' for deal '{deal.get('Deal_Name')}': {e}")
                    continue
            
            # Filter by stage if specified
            if stage_filter and deal_stage:
                # Case-insensitive partial match
                if stage_filter.lower() not in deal_stage.lower():
                    continue
            
            result.append({
                'id': deal.get('id'),
                'name': deal.get('Deal_Name'),
                'amount': deal_amount,
                'stage': deal_stage,
                'closing_date': deal.get('Closing_Date'),
                'account': deal.get('Account_Name', {}).get('name') if deal.get('Account_Name') else None,
                'created': deal.get('Created_Time')
            })
        
        logger.info(f"[ZOHO DEALS] Returning {len(result)} deals after filtering")
        return {'data': result, 'count': len(result)}
    except Exception as e:
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_leads(refresh_token: str, filters: dict = None, client_credentials=None) -> dict:
    """
    Fetch leads from Zoho CRM with optional location filtering.
    """
    filters = filters or {}
    try:
        access_token = get_access_token(refresh_token, client_credentials)
        config = _get_zoho_config(client_credentials)
        
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
        
        # Get location filter if specified
        location_filter = filters.get('city') or filters.get('location') or filters.get('state')
        
        result = []
        for lead in leads:
            lead_data = {
                'id': lead.get('id'),
                'name': f"{lead.get('First_Name', '')} {lead.get('Last_Name', '')}".strip(),
                'email': lead.get('Email'),
                'company': lead.get('Company'),
                'city': lead.get('City', ''),
                'state': lead.get('State', ''),
                'country': lead.get('Country', ''),
                'status': lead.get('Lead_Status'),
                'source': lead.get('Lead_Source'),
                'created': lead.get('Created_Time')
            }
            
            # Apply location filter if specified
            if location_filter:
                location_lower = location_filter.lower()
                lead_location = f"{lead_data['city']} {lead_data['state']} {lead_data['country']}".lower()
                if location_lower in lead_location:
                    result.append(lead_data)
            else:
                result.append(lead_data)
        
        return {'data': result, 'count': len(result), 'filter_applied': location_filter}
    except Exception as e:
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_accounts(refresh_token: str, filters: dict = None, client_credentials=None) -> dict:
    """
    Fetch accounts (companies) from Zoho CRM.
    """
    filters = filters or {}
    try:
        access_token = get_access_token(refresh_token, client_credentials)
        config = _get_zoho_config(client_credentials)
        
        name_filter = filters.get('name')
        
        if name_filter:
            # Use Search API for specific name lookup
            url = f"{config['api_base']}/Accounts/search?criteria=(Account_Name:starts_with:{name_filter})"
        else:
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
        
        # Apply filters
        city_filter = filters.get('city')
        name_filter = filters.get('name')
        
        result = []
        for account in accounts:
            acc_name = account.get('Account_Name', '')
            acc_city = account.get('Billing_City', '')
            
            # Filter by name if specified
            if name_filter and name_filter.lower() not in acc_name.lower():
                continue
                
            # Filter by city if specified
            if city_filter and city_filter.lower() not in acc_city.lower():
                continue

            result.append({
                'id': account.get('id'),
                'name': acc_name,
                'website': account.get('Website'),
                'industry': account.get('Industry'),
                'phone': account.get('Phone'),
                'created': account.get('Created_Time')
            })
        
        return {'data': result, 'count': len(result)}
    except Exception as e:
        return {'data': [], 'count': 0, 'error': str(e)}


def create_record(refresh_token: str, module: str, data: dict, client_credentials=None) -> dict:
    """
    Create a new record in Zoho CRM.
    """
    try:
        access_token = get_access_token(refresh_token, client_credentials)
        config = _get_zoho_config(client_credentials)
        
        # Normalize module name
        module_map = {
            'contact': 'Contacts',
            'lead': 'Leads',
            'deal': 'Deals',
            'account': 'Accounts',
            'contacts': 'Contacts',
            'leads': 'Leads',
            'deals': 'Deals',
            'accounts': 'Accounts'
        }
        target_module = module_map.get(module.lower(), module)
        
        url = f"{config['api_base']}/{target_module}"
        
        # Zoho expects data wrapped in 'data' list
        payload = {'data': [data]}
        
        response = requests.post(
            url,
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            json=payload,
            timeout=15
        )
        
        result = response.json()
        
        if response.status_code in [200, 201] and result.get('data') and result['data'][0].get('status') == 'success':
            return {
                'success': True,
                'data': result.get('data'),
                'summary': f"Successfully created {module} (ID: {result['data'][0].get('details', {}).get('id')})."
            }
        else:
            return {
                'success': False,
                'error': f"Failed to create {module}: {result}",
                'status_code': response.status_code
            }
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def update_record(refresh_token: str, module: str, record_id: str, data: dict, client_credentials=None) -> dict:
    """
    Update an existing record in Zoho CRM.
    """
    try:
        access_token = get_access_token(refresh_token, client_credentials)
        config = _get_zoho_config(client_credentials)
        
        # Normalize module name
        module_map = {
            'contact': 'Contacts',
            'lead': 'Leads',
            'deal': 'Deals',
            'account': 'Accounts',
            'contacts': 'Contacts',
            'leads': 'Leads',
            'deals': 'Deals',
            'accounts': 'Accounts'
        }
        target_module = module_map.get(module.lower(), module)
        
        url = f"{config['api_base']}/{target_module}/{record_id}"
        
        # Zoho expects data wrapped in 'data' list
        payload = {'data': [data]}
        
        response = requests.put(
            url,
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            json=payload,
            timeout=15
        )
        
        result = response.json()
        
        if response.status_code in [200, 201] and result.get('data') and result['data'][0].get('status') == 'success':
            return {
                'success': True,
                'data': result.get('data'),
                'summary': f"Successfully updated {module} (ID: {record_id})."
            }
        else:
            return {
                'success': False,
                'error': f"Failed to update {module}: {result}",
                'status_code': response.status_code
            }
            
    except Exception as e:
        return {'success': False, 'error': str(e)}
