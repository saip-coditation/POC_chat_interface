"""
Trello API Client
"""

import requests
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.trello.com/1"

# Timeout to avoid hanging when Render/proxy blocks api.trello.com or Trello is slow
REQUEST_TIMEOUT = 25  # seconds - under Render's ~30s limit

def validate_credentials(api_key, token):
    """
    Validate Trello API Key and Token.
    Returns dict with 'valid' (bool) and 'error' (str, optional)
    """
    try:
        # Clean and validate inputs
        api_key = api_key.strip() if api_key else ''
        token = token.strip() if token else ''
        
        if not api_key:
            return {'valid': False, 'error': 'API Key is required'}
        if not token:
            return {'valid': False, 'error': 'Token is required'}
        
        # Log validation attempt (without exposing full credentials)
        logger.info(f"[TRELLO] Validating credentials - API Key length: {len(api_key)}, Token length: {len(token)}")
        logger.info(f"[TRELLO] API Key starts with: {api_key[:8]}..., Token starts with: {token[:8]}...")
        
        url = f"{BASE_URL}/members/me"
        params = {
            'key': api_key,
            'token': token
        }
        
        logger.info(f"[TRELLO] Making request to: {url}")
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        
        logger.info(f"[TRELLO] Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"[TRELLO] Validation successful - Username: {data.get('username')}, Name: {data.get('fullName')}")
            return {
                'valid': True, 
                'username': data.get('username'),
                'fullName': data.get('fullName')
            }
        elif response.status_code == 401:
            error_text = response.text[:200] if response.text else 'No error message'
            logger.error(f"[TRELLO] Authentication failed (401) - {error_text}")
            return {
                'valid': False, 
                'error': 'Invalid API Key or Token. Please check that both are correct and not expired.'
            }
        elif response.status_code == 403:
            error_text = response.text[:200] if response.text else 'No error message'
            logger.error(f"[TRELLO] Forbidden (403) - {error_text}")
            return {
                'valid': False,
                'error': 'Access forbidden. Please check that your token has the required permissions.'
            }
        else:
            error_text = response.text[:500] if response.text else 'No error message'
            logger.error(f"[TRELLO] Validation failed with status {response.status_code} - {error_text}")
            return {
                'valid': False, 
                'error': f'Validation failed (Status {response.status_code}): {error_text[:100]}'
            }
            
    except requests.exceptions.Timeout:
        logger.error("[TRELLO] Validation timeout - Trello API did not respond in time")
        return {
            'valid': False, 
            'error': 'Connection timeout. Trello API is not responding. Please try again.'
        }
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[TRELLO] Connection error: {e}")
        return {
            'valid': False,
            'error': 'Cannot connect to Trello API. Please check your internet connection.'
        }
    except Exception as e:
        logger.error(f"[TRELLO] Validation error: {e}", exc_info=True)
        return {
            'valid': False, 
            'error': f'Validation error: {str(e)}'
        }

def execute_query(action, filters, api_key, token):
    """
    Execute a Trello query based on action and filters.
    """
    try:
        params = {
            'key': api_key,
            'token': token
        }
        
        if action == 'list_boards':
            # Get user's boards
            url = f"{BASE_URL}/members/me/boards"
            # Apply filters if possible (Trello API filters are limited on this endpoint)
            # Default fetch
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            # Post-processing filters
            limit = filters.get('limit', 10)
            if 'organization' in filters:
                data = [b for b in data if b.get('idOrganization') == filters['organization']]
                
            return {
                'success': True,
                'data': data[:limit],
                'summary': f"Found {len(data)} boards."
            }

        elif action == 'list_cards':
            # This is tricky because we need a board_id.
            # If board_name is provided, we first find the board.
            board_name = filters.get('board_name')
            if not board_name and not filters.get('board_id'):
                return {'success': False, 'error': 'Please specify a board name.'}
            
            board_id = filters.get('board_id')
            
            # Resolve board name to ID if needed
            if not board_id:
                boards_resp = requests.get(f"{BASE_URL}/members/me/boards", params=params, timeout=REQUEST_TIMEOUT)
                boards = boards_resp.json()
                # Fuzzy match
                board = next((b for b in boards if board_name.lower() in b['name'].lower()), None)
                if not board:
                    return {'success': False, 'error': f"Could not find board matching '{board_name}'"}
                board_id = board['id']
                
            # Now fetch cards
            url = f"{BASE_URL}/boards/{board_id}/cards"
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            cards = response.json()
            
            # Filter by list/status if possible (requires fetching lists to map names)
            list_name = filters.get('list_name')
            if list_name:
                lists_resp = requests.get(f"{BASE_URL}/boards/{board_id}/lists", params=params, timeout=REQUEST_TIMEOUT)
                lists = lists_resp.json()
                target_list = next((l for l in lists if list_name.lower() in l['name'].lower()), None)
                if target_list:
                    cards = [c for c in cards if c['idList'] == target_list['id']]
            
            limit = filters.get('limit', 20)
            return {
                'success': True,
                'data': cards[:limit],
                'summary': f"Found {len(cards)} cards on board."
            }
            
        elif action == 'get_lists':
            # board_name is optional - if not provided, get lists from all boards
            board_name = filters.get('board_name')
            board_id = filters.get('board_id')
            
            # Get all boards first
            boards_resp = requests.get(f"{BASE_URL}/members/me/boards", params=params, timeout=REQUEST_TIMEOUT)
            boards_resp.raise_for_status()
            boards = boards_resp.json()
            
            if board_id:
                # Use specific board ID
                target_board = next((b for b in boards if b['id'] == board_id), None)
                if not target_board:
                    return {'success': False, 'error': f"Could not find board with ID '{board_id}'"}
                boards = [target_board]
            elif board_name:
                # Find board by name (fuzzy match)
                board = next((b for b in boards if board_name.lower() in b['name'].lower()), None)
                if not board:
                    return {'success': False, 'error': f"Could not find board matching '{board_name}'. Available boards: {', '.join([b['name'] for b in boards[:5]])}"}
                boards = [board]
            # If no board_name or board_id, get lists from all boards
            
            # Collect lists from all target boards
            all_lists = []
            board_summaries = []
            limit = filters.get('limit', 50)
            
            for board in boards[:10]:  # Limit to first 10 boards to avoid timeout
                try:
                    url = f"{BASE_URL}/boards/{board['id']}/lists"
                    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
                    response.raise_for_status()
                    lists_data = response.json()
                    all_lists.extend(lists_data)
                    board_summaries.append(f"{len(lists_data)} lists from '{board['name']}'")
                except Exception as e:
                    logger.warning(f"Failed to get lists from board '{board['name']}': {e}")
                    continue
            
            if not all_lists:
                if board_name:
                    return {'success': False, 'error': f"Could not find any lists on board '{board_name}'"}
                else:
                    return {'success': False, 'error': 'No lists found in your boards.'}
            
            # Limit results
            all_lists = all_lists[:limit]
            
            summary = f"Found {len(all_lists)} lists"
            if len(boards) == 1:
                summary += f" on board '{boards[0]['name']}'"
            else:
                summary += f" across {len(boards)} boards: {', '.join(board_summaries)}"
            
            return {
                'success': True,
                'data': all_lists,
                'summary': summary
            }

        elif action == 'create_card':
            # Needs board_name and list_name to resolve IDs
            board_name = filters.get('board_name')
            list_name = filters.get('list_name')
            card_name = filters.get('name') or filters.get('card_name') or 'New Card'
            desc = filters.get('desc', '')
            
            logger.info(f"[TRELLO] create_card called with board_name='{board_name}', list_name='{list_name}', card_name='{card_name}'")
            
            if not board_name or not list_name:
                return {'success': False, 'error': 'Creating a card requires board_name and list_name.'}
                
            # 1. Resolve Board
            boards_resp = requests.get(f"{BASE_URL}/members/me/boards", params=params, timeout=REQUEST_TIMEOUT)
            boards_resp.raise_for_status()
            boards = boards_resp.json()
            board = next((b for b in boards if board_name.lower() in b['name'].lower()), None)
            
            if not board:
                 return {'success': False, 'error': f"Could not find board matching '{board_name}'"}
            
            # 2. Resolve List
            lists_resp = requests.get(f"{BASE_URL}/boards/{board['id']}/lists", params=params, timeout=REQUEST_TIMEOUT)
            lists_resp.raise_for_status()
            lists = lists_resp.json()
            
            # Try exact match first (case-insensitive), then substring match
            list_name_lower = list_name.lower().strip()
            target_list = None
            for l in lists:
                l_name_lower = l['name'].lower().strip()
                # Exact match (case-insensitive)
                if l_name_lower == list_name_lower:
                    target_list = l
                    logger.info(f"[TRELLO] Found exact list match: '{l['name']}'")
                    break
                # Substring match (list name contains the search term)
                elif list_name_lower in l_name_lower:
                    target_list = l
                    logger.info(f"[TRELLO] Found substring list match: '{l['name']}' (searching for '{list_name}')")
                    break
            
            if not target_list:
                available_lists = [l['name'] for l in lists]
                logger.warning(f"[TRELLO] Could not find list '{list_name}' on board '{board['name']}'. Available lists: {available_lists}")
                return {'success': False, 'error': f"Could not find list '{list_name}' on board '{board['name']}'. Available lists: {', '.join(available_lists)}"}
                
            # 3. Create Card
            url = f"{BASE_URL}/cards"
            post_params = params.copy()
            post_params.update({
                'idList': target_list['id'],
                'name': card_name,
                'desc': desc
            })
            
            response = requests.post(url, params=post_params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'data': [data], # Return as list for table rendering consistency
                'summary': f"Successfully created card '{card_name}' in list '{target_list['name']}' on board '{board['name']}'."
            }

        elif action == 'delete_card':
            # Needs board_name and card_name
            board_name = filters.get('board_name')
            card_name = filters.get('name')
            list_name = filters.get('list_name') # Optional, helps narrow down
            
            if not board_name or not card_name:
                return {'success': False, 'error': 'Deleting a card requires board_name and name.'}
                
            # 1. Resolve Board
            boards_resp = requests.get(f"{BASE_URL}/members/me/boards", params=params, timeout=REQUEST_TIMEOUT)
            boards_resp.raise_for_status()
            boards = boards_resp.json()
            board = next((b for b in boards if board_name.lower() in b['name'].lower()), None)
            
            if not board:
                 return {'success': False, 'error': f"Could not find board matching '{board_name}'"}
            
            # 2. Find Card (Fetch all cards on board)
            url = f"{BASE_URL}/boards/{board['id']}/cards"
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            cards = response.json()
            
            # Filter by list if provided
            if list_name:
                lists_resp = requests.get(f"{BASE_URL}/boards/{board['id']}/lists", params=params, timeout=REQUEST_TIMEOUT)
                lists = lists_resp.json()
                target_list = next((l for l in lists if list_name.lower() in l['name'].lower()), None)
                if target_list:
                    cards = [c for c in cards if c['idList'] == target_list['id']]
                else:
                    return {'success': False, 'error': f"Could not find list '{list_name}' on board '{board['name']}'"}
            
            # Find specific card by name (case-insensitive)
            # We look for EXACT match first, then substring? Let's do case-insensitive exact match to be safe
            target_card = next((c for c in cards if card_name.lower() == c['name'].lower()), None)
            
            if not target_card:
                return {'success': False, 'error': f"Could not find card '{card_name}' on board '{board['name']}'"}
            
            # 3. Delete Card
            del_url = f"{BASE_URL}/cards/{target_card['id']}"
            del_resp = requests.delete(del_url, params=params, timeout=REQUEST_TIMEOUT)
            del_resp.raise_for_status()
            
            return {
                'success': True,
                'data': [],
                'summary': f"Successfully deleted card '{target_card['name']}' from board '{board['name']}'."
            }
        else:
            return {'success': False, 'error': f"Unknown action: {action}"}

    except requests.exceptions.HTTPError as e:
        return {'success': False, 'error': f"Trello API Error: {str(e)}"}
    except Exception as e:
        return {'success': False, 'error': f"Internal Error: {str(e)}"}
