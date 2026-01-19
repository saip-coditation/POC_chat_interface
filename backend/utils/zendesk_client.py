"""
Zendesk API Client

Handles Zendesk API interactions for data fetching.
"""

import logging
import os
import requests
import base64
from datetime import datetime

logger = logging.getLogger(__name__)

# Add a file-based logger specifically for Zendesk debugging
def log_debug(msg):
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'zendesk_debug.log')
        with open(log_path, 'a') as f:
            f.write(f"{datetime.now().isoformat()} - {msg}\n")
    except Exception as e:
        print(f"Log Error: {e}")


def parse_credentials(api_key: str) -> dict:
    """
    Parse Zendesk credentials from the API key string.
    """
    try:
        # Split with maxsplit=2 to allow colons in the token if they exist
        parts = api_key.split(':', 2)
        if len(parts) != 3:
            raise ValueError("Invalid format. Expected 3 parts separated by colons (subdomain:email:token)")
        
        return {
            'subdomain': parts[0].strip().lower(),
            'email': parts[1].strip(),
            'token': parts[2].strip()
        }
    except Exception as e:
        logger.error(f"Credential parse error: {e}")
        raise ValueError(f"Failed to parse Zendesk credentials: {e}")


def normalize_credentials(api_key: str) -> dict:
    """
    Parse and normalize Zendesk credentials.
    Handles cases where user includes /token in their email or not.
    """
    creds = parse_credentials(api_key)
    
    subdomain = creds['subdomain'].lower()
    # Aggressive cleaning: remove protocol and everything after the first dot
    subdomain = subdomain.replace('https://', '').replace('http://', '').split('.')[0]
    
    email = creds['email']
    # Clean up email - remove /token if user included it (avoids double /token)
    if email.endswith('/token'):
        email = email[:-6]  # Remove '/token'
    
    # Zendesk API ALWAYS requires /token suffix on the email for token auth
    email = f"{email}/token"
        
    return {
        'subdomain': subdomain,
        'email': email,
        'token': creds['token']
    }


def validate_credentials(api_key: str) -> dict:
    """
    Validate Zendesk credentials by making a test request using requests for better error reporting.
    """
    import requests
    import base64
    
    try:
        log_debug(f"Starting validation for key length: {len(api_key)}")
        creds = normalize_credentials(api_key)
        subdomain = creds['subdomain']
        email = creds['email']
        token = creds['token']
        
        # Test auth with tickets endpoint (more definitive than users/me)
        url = f"https://{subdomain}.zendesk.com/api/v2/tickets.json?per_page=1"
        log_debug(f"Validation attempt (tickets endpoint): {url} as {email}")
        
        response = requests.get(
            url,
            auth=(email, token),
            headers={"Accept": "application/json"},
            timeout=10
        )
        
        log_debug(f"Validation Response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json().get('tickets', [])
            log_debug(f"Validation success! (Found {len(data)} tickets)")
            return {
                'valid': True,
                'message': "Credentials successfully validated (can list tickets)"
            }
        
        # If tickets failed, check WHY by looking at the user profile
        url_me = f"https://{subdomain}.zendesk.com/api/v2/users/me.json"
        res_me = requests.get(url_me, auth=(email, token), headers={"Accept": "application/json"}, timeout=10)
        
        if res_me.status_code == 200:
            user_data = res_me.json().get('user', {})
            role = user_data.get('role', 'unknown')
            verified = user_data.get('verified', False)
            
            log_debug(f"User Profile - Role: {role}, Verified: {verified}")
            
            if role == 'end-user':
                return {
                    'valid': False, 
                    'error': "Access Restricted: You are connected as an 'End-User'. Zendesk requires an 'Agent' or 'Admin' role to list all tickets."
                }
            if not verified:
                return {
                    'valid': False,
                    'error': "Account Unverified: Please verify your email address in Zendesk to enable API access to tickets."
                }
            
            return {'valid': False, 'error': f"Zendesk rejected access to tickets (Status: {response.status_code}). Check your Agent permissions."}
            
        else:
            try:
                error_detail = response.json().get('error', response.text)
            except:
                error_detail = response.text
            
            log_debug(f"Auth failed: {error_detail}")
            
            if response.status_code == 401:
                return {'valid': False, 'error': "Zendesk authentication failed. Check your Subdomain, Email, and Token. Ensure 'Token Access' is ENABLED in Zendesk."}
            
            return {'valid': False, 'error': error_detail}
            
    except Exception as e:
        logger.error(f"Zendesk validation logic error: {e}")
        return {'valid': False, 'error': str(e)}


def _extract_error(response_or_err) -> str:
    """Extract a clean error message from a Zendesk response or exception."""
    try:
        # If it's a requests Response object
        if isinstance(response_or_err, requests.Response):
            try:
                data = response_or_err.json()
                if 'error' in data:
                    if isinstance(data['error'], dict):
                        msg = data['error'].get('title', str(data['error']))
                        if 'authenticate' in msg.lower():
                            return "Zendesk authentication failed. Check if your email is verified and if you have 'Agent' permissions."
                        return f"Zendesk error: {msg}"
                    return f"Zendesk error: {data['error']}"
                if 'description' in data:
                    return f"Zendesk error: {data['description']}"
            except:
                return f"Zendesk HTTP {response_or_err.status_code}: {response_or_err.text[:200]}"
        
        # If it's a Zenpy error, it might have a response with JSON info
        e = response_or_err
        if hasattr(e, 'response') and hasattr(e.response, 'json'):
            try:
                data = e.response.json()
                if 'error' in data:
                    return f"Zendesk error: {data['error']}"
            except:
                pass
        
        # Fallback to string representation
        error_str = str(e)
        if 'Couldn\'t authenticate you' in error_str:
            return "Zendesk authentication failed. Please re-verify your credentials."
            
        return error_str
    except Exception as ex:
        return f"Error extracting message: {str(ex)}"


def fetch_tickets(api_key: str, filters: dict = None) -> dict:
    """
    Fetch tickets from Zendesk using requests.
    """
    filters = filters or {}
    try:
        creds = normalize_credentials(api_key)
        subdomain = creds['subdomain']
        email = creds['email']
        token = creds['token']
        
        limit = min(filters.get('limit', 50), 100)
        url = f"https://{subdomain}.zendesk.com/api/v2/tickets.json?limit={limit}&sort_by=created_at&sort_order=desc"
        
        # Add search filtering if needed
        status_filter = filters.get('status')
        if status_filter:
            # Search is better for status filtering
            query = f"type:ticket status:{status_filter}"
            url = f"https://{subdomain}.zendesk.com/api/v2/search.json?query={query}&per_page={limit}"
        
        log_debug(f"Fetching tickets from: {url}")
        response = requests.get(
            url,
            auth=(email, token),
            headers={"Accept": "application/json"},
            timeout=15
        )
        
        if response.status_code != 200:
            error_msg = _extract_error(response)
            log_debug(f"Fetch tickets failed ({response.status_code}): {error_msg}")
            return {'data': [], 'count': 0, 'error': error_msg}
            
        json_data = response.json()
        tickets = json_data.get('tickets') or json_data.get('results', [])
        
        data = []
        for ticket in tickets:
            data.append({
                'id': ticket.get('id'),
                'subject': ticket.get('subject'),
                'description': (ticket.get('description') or '')[:200],
                'status': ticket.get('status'),
                'priority': ticket.get('priority') or 'normal',
                'created_at': ticket.get('created_at'),
                'updated_at': ticket.get('updated_at'),
                'requester_id': ticket.get('requester_id'),
                'assignee_id': ticket.get('assignee_id'),
            })
            
        return {
            'data': data,
            'count': len(data)
        }
        
    except Exception as e:
        error_msg = str(e)
        log_debug(f"Fetch tickets exception: {error_msg}")
        return {'data': [], 'count': 0, 'error': error_msg}


def fetch_metrics(api_key: str, filters: dict = None) -> dict:
    """
    Fetch support metrics from Zendesk using requests.
    """
    try:
        creds = normalize_credentials(api_key)
        subdomain = creds['subdomain']
        email = creds['email']
        token = creds['token']
        
        # Use search to get counts
        def get_count(query):
            res = requests.get(
                f"https://{subdomain}.zendesk.com/api/v2/search.json?query={query}",
                auth=(email, token),
                headers={"Accept": "application/json"},
                timeout=10
            )
            return res.json().get('count', 0) if res.status_code == 200 else 0

        open_tickets = get_count("type:ticket status<solved")
        pending_tickets = get_count("type:ticket status:pending")
        solved_recently = get_count("type:ticket status:solved created>7daysago")
        
        return {
            'open_tickets': open_tickets,
            'pending_tickets': pending_tickets,
            'solved_recently': solved_recently,
            'avg_resolution_hours': 0, # Placeholder for now as it requires complex parsing
            'avg_resolution_time': "Data not available"
        }
        
    except Exception as e:
        error_msg = str(e)
        log_debug(f"Fetch metrics exception: {error_msg}")
        return {'error': error_msg}


def search_tickets(api_key: str, keyword: str, limit: int = 25) -> dict:
    """
    Search tickets by keyword using requests.
    """
    try:
        creds = normalize_credentials(api_key)
        subdomain = creds['subdomain']
        email = creds['email']
        token = creds['token']
        
        url = f"https://{subdomain}.zendesk.com/api/v2/search.json?query=type:ticket {keyword}&per_page={limit}"
        log_debug(f"Searching tickets: {url}")
        
        response = requests.get(
            url,
            auth=(email, token),
            headers={"Accept": "application/json"},
            timeout=15
        )
        
        if response.status_code != 200:
            error_msg = _extract_error(response)
            return {'data': [], 'count': 0, 'error': error_msg}
            
        results = response.json().get('results', [])
        data = []
        for ticket in results:
            data.append({
                'id': ticket.get('id'),
                'subject': ticket.get('subject'),
                'status': ticket.get('status'),
                'priority': ticket.get('priority') or 'normal',
                'created_at': ticket.get('created_at'),
            })
            
        return {
            'data': data,
            'count': len(data),
            'query': keyword
        }
        
    except Exception as e:
        error_msg = str(e)
        log_debug(f"Search tickets exception: {error_msg}")
        return {'data': [], 'count': 0, 'error': error_msg}
