"""
Trello API Client
"""

import requests
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.trello.com/1"

def validate_credentials(api_key, token):
    """
    Validate Trello API Key and Token.
    Returns dict with 'valid' (bool) and 'error' (str, optional)
    """
    try:
        url = f"{BASE_URL}/members/me"
        params = {
            'key': api_key,
            'token': token
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'valid': True, 
                'username': data.get('username'),
                'fullName': data.get('fullName')
            }
        elif response.status_code == 401:
            return {'valid': False, 'error': 'Invalid API Key or Token'}
        else:
            return {'valid': False, 'error': f'Validation failed: {response.text}'}
            
    except Exception as e:
        logger.error(f"Trello validation error: {e}")
        return {'valid': False, 'error': str(e)}

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
            response = requests.get(url, params=params)
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
                boards_resp = requests.get(f"{BASE_URL}/members/me/boards", params=params)
                boards = boards_resp.json()
                # Fuzzy match
                board = next((b for b in boards if board_name.lower() in b['name'].lower()), None)
                if not board:
                    return {'success': False, 'error': f"Could not find board matching '{board_name}'"}
                board_id = board['id']
                
            # Now fetch cards
            url = f"{BASE_URL}/boards/{board_id}/cards"
            response = requests.get(url, params=params)
            response.raise_for_status()
            cards = response.json()
            
            # Filter by list/status if possible (requires fetching lists to map names)
            list_name = filters.get('list_name')
            if list_name:
                lists_resp = requests.get(f"{BASE_URL}/boards/{board_id}/lists", params=params)
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
             # Need board_id or name
            board_name = filters.get('board_name')
            if not board_name:
                return {'success': False, 'error': 'Please specify a board name.'}
                
             # Resolve board
            boards_resp = requests.get(f"{BASE_URL}/members/me/boards", params=params)
            boards = boards_resp.json()
            board = next((b for b in boards if board_name.lower() in b['name'].lower()), None)
            
            if not board:
                return {'success': False, 'error': f"Could not find board matching '{board_name}'"}
                
            url = f"{BASE_URL}/boards/{board['id']}/lists"
            response = requests.get(url, params=params)
            data = response.json()
            
            return {
                'success': True,
                'data': data,
                'summary': f"Found {len(data)} lists on board '{board['name']}'"
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
            boards_resp = requests.get(f"{BASE_URL}/members/me/boards", params=params)
            boards_resp.raise_for_status()
            boards = boards_resp.json()
            board = next((b for b in boards if board_name.lower() in b['name'].lower()), None)
            
            if not board:
                 return {'success': False, 'error': f"Could not find board matching '{board_name}'"}
            
            # 2. Resolve List
            lists_resp = requests.get(f"{BASE_URL}/boards/{board['id']}/lists", params=params)
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
            
            response = requests.post(url, params=post_params)
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
            boards_resp = requests.get(f"{BASE_URL}/members/me/boards", params=params)
            boards_resp.raise_for_status()
            boards = boards_resp.json()
            board = next((b for b in boards if board_name.lower() in b['name'].lower()), None)
            
            if not board:
                 return {'success': False, 'error': f"Could not find board matching '{board_name}'"}
            
            # 2. Find Card (Fetch all cards on board)
            url = f"{BASE_URL}/boards/{board['id']}/cards"
            response = requests.get(url, params=params)
            response.raise_for_status()
            cards = response.json()
            
            # Filter by list if provided
            if list_name:
                lists_resp = requests.get(f"{BASE_URL}/boards/{board['id']}/lists", params=params)
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
            del_resp = requests.delete(del_url, params=params)
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
