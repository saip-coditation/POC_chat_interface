"""
Salesforce API Client
"""

import requests
import logging

logger = logging.getLogger(__name__)

LOGIN_URL = "https://login.salesforce.com/services/oauth2/token"
API_VERSION = "v57.0"


def validate_credentials(client_id, client_secret, username, password):
    """
    Validate Salesforce credentials using Username-Password OAuth flow.
    Returns dict with 'valid' (bool), 'access_token', 'instance_url', and 'error' (optional).
    
    Note: password should be password+security_token concatenated.
    """
    try:
        payload = {
            'grant_type': 'password',
            'client_id': client_id,
            'client_secret': client_secret,
            'username': username,
            'password': password
        }
        
        response = requests.post(LOGIN_URL, data=payload)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'valid': True,
                'access_token': data['access_token'],
                'instance_url': data['instance_url'],
                'user_id': data.get('id', '').split('/')[-1]
            }
        else:
            error_data = response.json()
            error_msg = error_data.get('error_description', response.text)
            return {'valid': False, 'error': error_msg}
            
    except Exception as e:
        logger.error(f"Salesforce validation error: {e}")
        return {'valid': False, 'error': str(e)}


def refresh_access_token(client_id, client_secret, refresh_token):
    """
    Refresh Salesforce access token using refresh token.
    """
    try:
        payload = {
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token
        }
        
        response = requests.post(LOGIN_URL, data=payload)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'access_token': data['access_token'],
                'instance_url': data.get('instance_url')  # Might change or be same
            }
        else:
            return {
                'success': False, 
                'error': response.json().get('error_description', response.text)
            }
    except Exception as e:
        logger.error(f"Salesforce token refresh error: {e}")
        return {'success': False, 'error': str(e)}


def execute_query(action, filters, access_token, instance_url):
    """
    Execute a Salesforce query based on action and filters.
    """
    try:
        logger.info(f"Salesforce execute_query: action={action}, filters={filters}")
        
        # Remove prefix if present
        if action.startswith('salesforce.'):
            action = action.split('.', 1)[1]
            
        # Alias new RAG intents to existing list actions
        if action == 'get_contact': 
            action = 'list_contacts'
        if action == 'get_account':
            action = 'list_accounts'

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        base_url = f"{instance_url}/services/data/{API_VERSION}"

        if action == 'list_leads':
            # Build SOQL query for Leads
            soql = "SELECT Id, Name, Email, Company, Status, Phone, CreatedDate FROM Lead"
            
            # Apply filters
            conditions = []
            if filters.get('status'):
                conditions.append(f"Status = '{filters['status']}'")
            if filters.get('company'):
                conditions.append(f"Company LIKE '%{filters['company']}%'")
            if filters.get('name'):
                conditions.append(f"Name LIKE '%{filters['name']}%'")
            
            if conditions:
                soql += " WHERE " + " AND ".join(conditions)
            
            soql += " ORDER BY CreatedDate DESC"
            limit = filters.get('limit', 20)
            soql += f" LIMIT {limit}"
            
            url = f"{base_url}/query/"
            response = requests.get(url, headers=headers, params={'q': soql})
            
            if response.status_code == 401:
                return {
                    'success': False,
                    'error': f'401 Unauthorized: {response.text[:200]}',
                    'status_code': 401
                }
            
            response.raise_for_status()
            data = response.json()
            
            
            records = data.get('records', [])
            
            # Clean up records by removing the 'attributes' field
            cleaned_records = [{k: v for k, v in record.items() if k != 'attributes'} for record in records]
            
            return {
                'success': True,
                'data': cleaned_records,
                'summary': f"Found {len(cleaned_records)} lead{'s' if len(cleaned_records) != 1 else ''}."
            }
            
        elif action == 'list_contacts':
            soql = "SELECT Id, Name, Email, Phone, Account.Name, Title, CreatedDate FROM Contact"
            
            conditions = []
            if filters.get('email'):
                conditions.append(f"Email LIKE '%{filters['email']}%'")
            if filters.get('account'):
                conditions.append(f"Account.Name LIKE '%{filters['account']}%'")
            if filters.get('name'):
                conditions.append(f"Name LIKE '%{filters['name']}%'")
            
            if conditions:
                soql += " WHERE " + " AND ".join(conditions)
            
            soql += " ORDER BY CreatedDate DESC"
            limit = filters.get('limit', 20)
            soql += f" LIMIT {limit}"
            
            url = f"{base_url}/query/"
            response = requests.get(url, headers=headers, params={'q': soql})
            
            if response.status_code == 401:
                return {
                    'success': False,
                    'error': f'401 Unauthorized: {response.text[:200]}',
                    'status_code': 401
                }
            
            response.raise_for_status()
            data = response.json()
            
            
            records = data.get('records', [])
            
            # Clean up records by removing the 'attributes' field (contains type and url)
            cleaned_records = []
            for record in records:
                cleaned_record = {k: v for k, v in record.items() if k != 'attributes'}
                cleaned_records.append(cleaned_record)
            
            return {
                'success': True,
                'data': cleaned_records,
                'summary': f"Found {len(cleaned_records)} contact{'s' if len(cleaned_records) != 1 else ''}."
            }
            
        elif action == 'list_accounts':
            soql = "SELECT Id, Name, Industry, Phone, Website, BillingCity, CreatedDate FROM Account"
            
            conditions = []
            if filters.get('industry'):
                conditions.append(f"Industry = '{filters['industry']}'")
            if filters.get('city'):
                conditions.append(f"BillingCity LIKE '%{filters['city']}%'")
            
            if conditions:
                soql += " WHERE " + " AND ".join(conditions)
            
            soql += " ORDER BY CreatedDate DESC"
            limit = filters.get('limit', 20)
            soql += f" LIMIT {limit}"
            
            url = f"{base_url}/query/"
            response = requests.get(url, headers=headers, params={'q': soql})
            
            if response.status_code == 401:
                return {
                    'success': False,
                    'error': f'401 Unauthorized: {response.text[:200]}',
                    'status_code': 401
                }
            
            response.raise_for_status()
            data = response.json()
            
            
            records = data.get('records', [])
            
            # Clean up records by removing the 'attributes' field
            cleaned_records = [{k: v for k, v in record.items() if k != 'attributes'} for record in records]
            
            return {
                'success': True,
                'data': cleaned_records,
                'summary': f"Found {len(cleaned_records)} account{'s' if len(cleaned_records) != 1 else ''}."
            }
            
        elif action in ['list_deals', 'list_opportunities']:
            soql = "SELECT Id, Name, Amount, StageName, CloseDate, Account.Name, Probability, CreatedDate FROM Opportunity"
            
            conditions = []
            if filters.get('stage'):
                conditions.append(f"StageName = '{filters['stage']}'")
            if filters.get('min_amount'):
                conditions.append(f"Amount >= {filters['min_amount']}")
            if filters.get('closed'):
                if filters['closed'].lower() == 'true':
                    conditions.append("IsClosed = true")
                else:
                    conditions.append("IsClosed = false")
            
            if conditions:
                soql += " WHERE " + " AND ".join(conditions)
            
            soql += " ORDER BY CloseDate DESC"
            limit = filters.get('limit', 20)
            soql += f" LIMIT {limit}"
            
            url = f"{base_url}/query/"
            response = requests.get(url, headers=headers, params={'q': soql})
            
            if response.status_code == 401:
                return {
                    'success': False,
                    'error': f'401 Unauthorized: {response.text[:200]}',
                    'status_code': 401
                }
            
            response.raise_for_status()
            data = response.json()
            
            
            records = data.get('records', [])
            
            # Clean up records by removing the 'attributes' field
            cleaned_records = [{k: v for k, v in record.items() if k != 'attributes'} for record in records]
            
            # Calculate stats
            total_amount = sum(r.get('Amount', 0) or 0 for r in cleaned_records)
            
            return {
                'success': True,
                'data': cleaned_records,
                'total_amount': total_amount,
                'summary': f"Found {len(cleaned_records)} opportunit{'ies' if len(cleaned_records) != 1 else 'y'} totaling ${total_amount:,.2f}."
            }
            
        elif action == 'create_contact':
            # Simplified high-level creation tool
            # filters: 'name', 'account' or 'company', 'email', 'title'
            name = filters.get('name', 'New Contact')
            account_name = filters.get('account') or filters.get('company')
            email = filters.get('email')
            title = filters.get('title')
            
            # 1. Parse Name
            name_parts = name.strip().split()
            if len(name_parts) > 1:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])
            else:
                first_name = ""
                last_name = name
                
            # 2. Account Lookup (if provided)
            # ... (lines 304-315)
            account_id = None
            if account_name:
                logger.info(f"Looking up account for contact: {account_name}")
                acc_soql = f"SELECT Id FROM Account WHERE Name LIKE '%{account_name}%' LIMIT 1"
                acc_url = f"{base_url}/query/"
                acc_resp = requests.get(acc_url, headers=headers, params={'q': acc_soql})
                if acc_resp.status_code == 200:
                    acc_data = acc_resp.json()
                    if acc_data.get('records'):
                        account_id = acc_data['records'][0].get('Id')
                        logger.info(f"Found account ID: {account_id}")
            
            # 3. Prepare Data
            record_data = {
                'FirstName': first_name,
                'LastName': last_name
            }
            if account_id:
                record_data['AccountId'] = account_id
            if email:
                record_data['Email'] = email
            if title:
                record_data['Title'] = title
                
            # 4. Create Contact
            url = f"{base_url}/sobjects/Contact/"
            response = requests.post(url, headers=headers, json=record_data)
            
            if response.status_code == 201:
                result = response.json()
                summary = f"Successfully created Contact '{name}'"
                if title:
                    summary += f" ({title})"
                if account_name and account_id:
                    summary += f" at '{account_name}'"
                summary += f" (ID: {result.get('id')})."
                
                return {
                    'success': True,
                    'data': [
                        {
                            'Contact ID': result.get('id'),
                            'Status': 'Successfully Created',
                            'Name': name,
                            'Title': title if title else 'None',
                            'Account': account_name if account_id else 'None'
                        }
                    ],
                    'summary': summary
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to create Contact: {response.text}",
                    'status_code': response.status_code
                }

        elif action == 'create_record':
            # Create a new record
            # filters expected: 'object', 'data'
            object_type = filters.get('object', 'Lead') # Default to Lead
            if object_type.lower() == 'contact': object_type = 'Contact'
            elif object_type.lower() == 'lead': object_type = 'Lead'
            elif object_type.lower() == 'account': object_type = 'Account'
            elif object_type.lower() == 'opportunity' or object_type.lower() == 'deal': object_type = 'Opportunity'
            
            record_data = filters.get('data', {})
            if not record_data:
                return {'success': False, 'error': 'No data provided for creation'}

            url = f"{base_url}/sobjects/{object_type}/"
            response = requests.post(url, headers=headers, json=record_data)
            
            if response.status_code == 201:
                result = response.json()
                return {
                    'success': True,
                    'data': [result],
                    'summary': f"Successfully created {object_type} (ID: {result.get('id')})."
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to create {object_type}: {response.text}",
                    'status_code': response.status_code
                }

        elif action == 'update_record':
            # Update an existing record
            # filters expected: 'object', 'id', 'data'
            object_type = filters.get('object', 'Lead')
            if object_type.lower() == 'contact': object_type = 'Contact'
            elif object_type.lower() == 'lead': object_type = 'Lead'
            elif object_type.lower() == 'account': object_type = 'Account'
            elif object_type.lower() == 'opportunity' or object_type.lower() == 'deal': object_type = 'Opportunity'
            
            record_id = filters.get('id')
            record_data = filters.get('data', {})
            
            if not record_id:
                return {'success': False, 'error': 'Record ID is required for update'}
            if not record_data:
                return {'success': False, 'error': 'No data provided for update'}
                
            url = f"{base_url}/sobjects/{object_type}/{record_id}"
            response = requests.patch(url, headers=headers, json=record_data)
            
            if response.status_code == 204:
                return {
                    'success': True,
                    'data': [],
                    'summary': f"Successfully updated {object_type} (ID: {record_id})."
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to update {object_type}: {response.text}",
                    'status_code': response.status_code
                }

        else:
            return {'success': False, 'error': f"Unknown action: {action}"}
            
    except requests.exceptions.HTTPError as e:
        return {'success': False, 'error': f"Salesforce API Error: {str(e)}"}
    except Exception as e:
        logger.error(f"Salesforce execute_query error: {e}")
        return {'success': False, 'error': f"Internal Error: {str(e)}"}
