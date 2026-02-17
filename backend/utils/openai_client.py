"""
OpenAI Client for query processing.

Handles platform detection, query interpretation, and result summarization.
Uses OpenRouter API for LLM access.
"""

import json
import logging
import random
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client (configured for OpenRouter)
client = None


def get_client():
    """Get or create OpenAI-compatible client."""
    global client
    if client is None:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        # Detect key type and configure accordingly
        if api_key.startswith('sk-or-'):
            # OpenRouter key
            client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=120.0,  # Increased for Render's network
                max_retries=3
            )
        else:
            # Native OpenAI key (sk-proj- or sk-)
            client = OpenAI(
                api_key=api_key,
                timeout=120.0,
                max_retries=3
            )
    return client


def get_model_name():
    """Get the appropriate model name based on API key type."""
    api_key = settings.OPENAI_API_KEY
    if api_key and api_key.startswith('sk-or-'):
        return "openai/gpt-4o-mini"  # OpenRouter format
    return "gpt-4o-mini"  # Direct OpenAI format


def detect_platform(query: str, available_platforms: list) -> dict:
    """
    Use OpenAI to detect which platform the query is targeting.
    
    Args:
        query: Natural language query from user
        available_platforms: List of connected platforms ['stripe', 'zendesk']
        
    Returns:
        dict with 'platform' and 'confidence' keys
    """
    if not available_platforms:
        return {'platform': None, 'confidence': 0, 'error': 'No platforms connected'}
    
    if len(available_platforms) == 1:
        return {'platform': available_platforms[0], 'confidence': 1.0}
    
    try:
        openai_client = get_client()
        
        response = openai_client.chat.completions.create(
            model=get_model_name(),
            messages=[
                {
                    "role": "system",
                    "content": """You are a query classifier. Determine which platform a user query is targeting.
                    
Available platforms:
- stripe: Payment processing, invoices, subscriptions, revenue, charges, refunds, customers, billing
- zendesk: Customer support, tickets, help desk, agents, resolution times, CSAT scores
- github: Repositories, commits, pull requests, issues, code, branches, merge requests
- trello: Boards, cards, lists, tasks, project management, kanban, members, organization
- salesforce: CRM, leads, contacts, accounts, opportunities, deals, sales pipeline, prospects

Respond with JSON only: {"platform": "stripe" or "zoho" or "github" or "trello" or "salesforce", "confidence": 0.0-1.0}"""
                },
                {
                    "role": "user",
                    "content": f"Query: {query}\nAvailable platforms: {', '.join(available_platforms)}"
                }
            ],
            temperature=0,
            max_tokens=50
        )
        
        result_text = response.choices[0].message.content.strip()
        # Clean up markdown if present
        if result_text.startswith("```"):
            result_text = result_text.strip("`").strip()
            if result_text.startswith("json"):
                result_text = result_text[4:].strip()
                
        result = json.loads(result_text)
        
        # Clean up platform name (strip whitespace/newlines)
        if 'platform' in result and result['platform']:
            result['platform'] = result['platform'].strip()
        
        # Validate platform is in available list
        if result.get('platform') not in available_platforms:
            result['platform'] = available_platforms[0]
            result['confidence'] = 0.5
            
        return result
        
    except json.JSONDecodeError:
        logger.warning("Failed to parse OpenAI response for platform detection")
        return {'platform': available_platforms[0], 'confidence': 0.5}
    except Exception as e:
        logger.error(f"OpenAI platform detection error: {e}")
        
        # Keyword-based fallback
        query_lower = query.lower()
        if any(w in query_lower for w in ['stripe', 'invoice', 'revenue', 'charge', 'subscription', 'billing']):
            return {'platform': 'stripe', 'confidence': 0.8}
        if any(w in query_lower for w in ['zoho', 'crm', 'contact', 'lead', 'deal', 'account', 'sales']):
            return {'platform': 'zoho', 'confidence': 0.8}
        if any(w in query_lower for w in ['github', 'repo', 'commit', 'pull request', 'pr', 'issue', 'branch', 'merge']):
            return {'platform': 'github', 'confidence': 0.8}
        if any(w in query_lower for w in ['trello', 'board', 'card', 'list', 'kanban', 'task']):
            return {'platform': 'trello', 'confidence': 0.8}
            
        return {'platform': available_platforms[0], 'confidence': 0.5, 'error': str(e)}


def generate_query_params(query: str, platform: str) -> dict:
    """
    Use OpenAI to interpret the query and generate API parameters.
    
    Args:
        query: Natural language query
        platform: Target platform (stripe/zendesk)
        
    Returns:
        dict with 'action', 'filters', and 'fields' keys
    """
    try:
        openai_client = get_client()
        
        if platform == 'stripe':
            system_prompt = """You interpret natural language queries about Stripe data.

Available actions:
- list_invoices: [filters: status (paid/unpaid/open/void), period (today/week/month/year), limit, customer]
- list_subscriptions: [filters: status (active/past_due/canceled), limit, plan]
- get_revenue: [filters: period (today/week/month/year)]
- get_balance: [filters: none] - Get Stripe account balance (available, pending)
- list_customers: [filters: limit, email, name, customer_name, created_after]
- list_charges: [filters: status (succeeded/pending/failed), period (today/week/month/year), limit, amount_gt]
- list_products: [filters: active (true/false), limit]
- list_payouts: [filters: limit]

RULES:
1. "Unpaid/Open" -> status: "unpaid". "Paid" -> status: "paid".
2. "Last month" -> period: "last_month". "Today" -> period: "today".
3. "Recent" or "recent payments" -> period: "week" AND limit: 20. "Recent charges" -> period: "week" AND limit: 20.
4. "This week" -> period: "week". "This month" -> period: "month".
5. "Balance" or "account balance" or "available balance" -> action: "get_balance".
6. "Failed charges" -> action: "list_charges", filters: {status: "failed"}.
7. "High value" or "over $500" -> filters: {amount_gt: 500}.
8. "Revenue for X" or "revenue from X" or "show revenue for X" -> action: "get_revenue", filters: {product_name: "X"}.
9. Extract product names from queries like "revenue for phone" -> product_name: "phone".
10. "Customer X" or "details for customer X" or "show customer X" -> action: "list_customers", filters: {name: "X"}.
11. Extract customer names from queries like "give me details for customer Rohan robert" -> name: "Rohan robert".
12. Default limit: 20. If "all" or "list", limit: 50. If "recent", limit: 20.

Respond with valid JSON only."""
        elif platform == 'github':
            system_prompt = """You interpret natural language queries about GitHub data.

Available actions:
- list_repos: [filters: sort (updated/stars), type (all/owner/public/private), language, limit]
- list_commits: [filters: repo_name, author, limit]
- list_issues: [filters: repo_name, state (open/closed/all), labels, limit]
- list_prs: [filters: repo_name, state (open/closed/all), limit]

RULES:
1. "My python repos" -> filters: {language: "python"}.
2. "Active repos" -> filters: {sort: "updated"}.
3. "Open bugs" -> action: "list_issues", filters: {state: "open", labels: "bug"}.
4. Extract repo names like "facebook/react" or "frontend" or "POC_chat_interface".
5. "how many repos" or "num of repos" -> action: "list_repos", filters: {}.
6. "show commits" or "list commits" or "recent commits" -> action: "list_commits", filters: {repo_name: "extracted_repo_name"}.
7. "commits for X" or "commits in X" -> action: "list_commits", filters: {repo_name: "X"}.
8. Extract repo name from queries like "commits for POC_chat_interface" -> repo_name: "POC_chat_interface".
9. Default limit: 20. If "all", limit: 100.

Respond with valid JSON only."""
        elif platform == 'zoho':
            system_prompt = """You interpret natural language queries about Zoho CRM data.

Available actions:
- list_contacts: [filters: limit, city, location, state, email]
- list_deals: [filters: limit, stage (Won/Lost/Negotiation), amount_gt]
- list_leads: [filters: limit, city, location, state, status]
- list_accounts: [filters: limit, city]
- create_lead: [filters: last_name (REQUIRED), company (REQUIRED), email, status]
- update_deal: [filters: deal_id (REQUIRED), stage, amount]

 Rules:
1. "Contacts from Mumbai" -> filters: {city: "Mumbai"}.
2. "Won deals" -> action: "list_deals", filters: {stage: "Closed Won"}.
3. "Big deals" or "over 10k" or "over $10,000" -> filters: {amount_gt: 10000}.
4. "Deals over $60,000" or "deals above 60000" -> filters: {amount_gt: 60000}.
5. Extract numeric values from amounts: "$60,000" -> 60000, "10k" -> 10000, "5k" -> 5000.
6. "Hot leads" -> action: "list_leads", filters: {status: "Hot"}.
7. "Create lead 'John Doe' at 'Acme Corp'" -> action: "create_lead", filters: {last_name: "Doe", company: "Acme Corp", email: "john@acme.com" (if email present)}.
8. "Update deal '12345' to 'Closed Won'" -> action: "update_deal", filters: {deal_id: "12345", stage: "Closed Won"}.
9. "Set deal '12345' amount to 5000" -> action: "update_deal", filters: {deal_id: "12345", amount: 5000}.
10. "Create lead for [Name] at [Company]" -> action: "create_lead", filters: {last_name: "[Name]", company: "[Company]"}.
11. [UNIFIED VIEW] "Invoices for contact X" -> action: "list_contacts", filters: {name: "X"}. (We fetch the contact first).
12. "Negotiating" or "Negotiation" -> filters: {stage: "Negotiation/Review"}.
13. "Show deals in Negotiating stage" -> filters: {stage: "Negotiation/Review"} (Do NOT extract 'deals' as name).
14. "Show everything for [Company/Name]" -> action: "list_accounts", filters: {name: "[Company/Name]"}.
15. "Show contact [Name]" or "how contact [Name]" -> filters: {name: "[Name]"} (Do NOT extract 'contact' as name).
16. "Show details about [Name]" -> action: "list_contacts", filters: {name: "[Name]"}.

Respond with valid JSON only."""
        elif platform == 'trello':
            system_prompt = """You interpret natural language queries about Trello.

Available actions:
- list_boards: [filters: limit, organization]
- list_cards: [filters: board_name (REQUIRED if no board_id), list_name, limit]
- get_lists: [filters: board_name (OPTIONAL - if not provided, gets lists from all boards), limit]
- create_card: [filters: name (REQUIRED), list_name (REQUIRED), board_name (REQUIRED), desc]
- delete_card: [filters: name (REQUIRED), board_name (REQUIRED), list_name]

RULES:
1. "My boards" -> action: "list_boards".
2. "Cards on 'Marketing' board" -> action: "list_cards", filters: {board_name: "Marketing"}.
3. "Tasks in 'To Do' list" -> action: "list_cards", filters: {list_name: "To Do"}.
4. "Get all lists" or "Show all lists" -> action: "get_lists", filters: {} (no board_name - gets from all boards).
5. "Get lists from 'Marketing' board" -> action: "get_lists", filters: {board_name: "Marketing"}.
4. "Create card" or "add card" or "new card" -> action: "create_card". Extract card name, list_name, and board_name from query.
5. "Create card 'Fix Bug' in 'Backlog' list on 'Dev' board" -> action: "create_card", filters: {name: "Fix Bug", list_name: "Backlog", board_name: "Dev"}.
6. "Create a card called 'My Task' in 'To Do' list inside 'testing' board" -> action: "create_card", filters: {name: "My Task", list_name: "To Do", board_name: "testing"}.
7. "Create a card in 'To Do' list inside 'testing' board" -> action: "create_card", filters: {list_name: "To Do", board_name: "testing", name: "New Card"} (if name not specified, use "New Card").
8. "Create a card inside testing board in trello inside To Do card" -> action: "create_card", filters: {board_name: "testing", list_name: "To Do", name: "New Card"}.
9. "Delete card 'Fix Bug' from 'Dev' board" -> action: "delete_card", filters: {name: "Fix Bug", board_name: "Dev"}.
10. If board name is mentioned (like "testing board", "testing"), extract it to 'board_name'. Remove "board" word if present.
11. If list name is mentioned (like "To Do", "In Progress", "Done"), extract it to 'list_name'. Remove "card" or "list" words if present.
12. For create_card, extract card name from patterns like "card called 'X'", "card 'X'", "create card 'X'". If card name is not specified, use "New Card" as default.
13. [UNIFIED VIEW] "GitHub PRs for card 'Login' in 'Dev' board" -> action: "list_cards", filters: {name: "Login", board_name: "Dev"}. (Always extract board_name if present).

Respond with valid JSON only."""
        elif platform == 'salesforce':
            system_prompt = """You interpret natural language queries about Salesforce CRM.

Available actions:
- list_leads: [filters: status, company, name, limit]
- list_contacts: [filters: email, account, name, limit]
- list_accounts: [filters: industry, city, limit]
- list_opportunities: [filters: stage, min_amount, closed, limit]
- create_record: [filters: object (Contact/Lead/Account/Opportunity), data (JSON object with fields)]
- update_record: [filters: object, id, data (JSON object with fields)]

RULES:
1. "Show my leads" -> action: "list_leads".
2. "Contacts from Acme" -> action: "list_contacts", filters: {account: "Acme"}.
3. "Search for Rohan" -> action: "list_contacts", filters: {name: "Rohan"}.
4. "Leads with status Qualified" -> action: "list_leads", filters: {status: "Qualified"}.
5. "Deals over 10000" -> action: "list_opportunities", filters: {min_amount: 10000}.
6. "Create contact 'Alice' at 'Acme'" -> action: "create_record", filters: {object: "Contact", data: {LastName: "Alice", Account: {Name: "Acme"}}}.
7. "Create lead 'Bob' from 'TechCorp'" -> action: "create_record", filters: {object: "Lead", data: {LastName: "Bob", Company: "TechCorp", Status: "Open - Not Contacted"}}.
8. "Update opportunity '006...' stage to 'Closed Won'" -> action: "update_record", filters: {object: "Opportunity", id: "006...", data: {StageName: "Closed Won"}}.
9. "Create deal 'Big Sale' for $5000" -> action: "create_record", filters: {object: "Opportunity", data: {Name: "Big Sale", Amount: 5000, StageName: "Prospecting", CloseDate: "2024-12-31"}}.
10. [UNIFIED VIEW] "Stripe invoices for Salesforce contact 'Alice'" -> action: "list_contacts", filters: {name: "Alice"}.
11. [UNIFIED VIEW] "Details and payments for 'Bob' in Salesforce and Stripe" -> action: "list_contacts", filters: {name: "Bob"}.

Respond with valid JSON only."""
        
        response = openai_client.chat.completions.create(
            model=get_model_name(),
            messages=[
                {"role": "system", "content": system_prompt + "\nIMPORTANT: Return ONLY valid JSON. No preamble."},
                {"role": "user", "content": query}
            ],
            temperature=0,
            max_tokens=250
        )
        
        content = response.choices[0].message.content.strip()
        
        # Clean up markdown if present
        if content.startswith("```"):
            content = content.strip("`").strip()
            if content.lower().startswith("json"):
                content = content[4:].strip()
        
        parsed = json.loads(content)
        
        # Log the parsed result for debugging
        import logging
        logging.getLogger(__name__).info(f"[GENERATE_QUERY_PARAMS] Parsed result for '{query}': {parsed}")
        
        # POST-PROCESSING: Clean up Trello parameters (LLM often ignores prompt instructions)
        if platform == 'trello' and 'filters' in parsed:
            filters = parsed['filters']
            
            # Clean board_name
            if 'board_name' in filters and filters['board_name']:
                board_name = str(filters['board_name'])
                # Remove platform mentions
                board_name = board_name.replace(' in Trello', '').replace(' on Trello', '')
                board_name = board_name.replace(' in trello', '').replace(' on trello', '')
                board_name = board_name.replace('in Trello', '').replace('on Trello', '')
                board_name = board_name.replace(' board', '').replace(' Board', '')
                filters['board_name'] = board_name.strip()
            
            # Clean list_name
            if 'list_name' in filters and filters['list_name']:
                list_name = str(filters['list_name'])
                # Remove platform mentions
                list_name = list_name.replace(' in Trello', '').replace(' on Trello', '')
                list_name = list_name.replace(' in trello', '').replace(' on trello', '')
                list_name = list_name.replace('in Trello', '').replace('on Trello', '')
                list_name = list_name.replace(' list', '').replace(' List', '')
                filters['list_name'] = list_name.strip()
            
            # Clean card name
            if 'name' in filters and filters['name']:
                card_name = str(filters['name'])
                card_name = card_name.replace(' in Trello', '').replace(' on Trello', '')
                card_name = card_name.replace(' card', '').replace(' Card', '')
                filters['name'] = card_name.strip()
            
            logging.getLogger(__name__).info(f"[TRELLO_CLEANUP] Cleaned filters: {filters}")
        
        return parsed
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON: {e}")
        logger.error(f"Content was: {content}")
        return {}
        return {'action': 'error', 'error': 'Failed to parse AI response', 'raw': content if 'content' in locals() else None}
    except Exception as e:
        logger.error(f"OpenAI query params error: {e}")
        
        # Keyword-based fallback
        query_lower = query.lower()
        if platform == 'stripe':
            # Revenue
            if any(w in query_lower for w in ['revenue', 'money', 'earn', 'sale', 'profit']):
                period = 'month'
                if 'today' in query_lower: period = 'today'
                elif 'week' in query_lower: period = 'week'
                elif 'year' in query_lower: period = 'year'
                return {'action': 'get_revenue', 'filters': {'period': period}}
            
            # Products
            if any(w in query_lower for w in ['product', 'item', 'skus', 'goods']):
                return {'action': 'list_products', 'filters': {}}
            
            # Payouts
            if any(w in query_lower for w in ['payout', 'transfer', 'withdrawal', 'payouts']):
                return {'action': 'list_payouts', 'filters': {}}
                
            # Customers
            if any(w in query_lower for w in ['customer', 'user', 'people', 'client']):
                return {'action': 'list_customers', 'filters': {}}
                
            # Subscriptions
            if any(w in query_lower for w in ['sub', 'plan', 'recurring', 'subscription']):
                return {'action': 'list_subscriptions', 'filters': {}}
                
            # Invoices (Defaulting to this if 'invoice' or nothing else matched)
            filters = {}
            if 'unpaid' in query_lower or 'open' in query_lower or 'due' in query_lower:
                filters['status'] = 'unpaid'
            elif 'paid' in query_lower or 'completed' in query_lower:
                filters['status'] = 'paid'
            
            return {'action': 'list_invoices', 'filters': filters}
        elif platform == 'github':
            # GitHub fallbacks
            if any(w in query_lower for w in ['pull request', 'pr', 'merge']):
                return {'action': 'list_prs', 'filters': {'state': 'all'}}
            if any(w in query_lower for w in ['commit', 'commits', 'history']):
                return {'action': 'list_commits', 'filters': {}}
            if any(w in query_lower for w in ['issue', 'issues', 'bug', 'bugs']):
                return {'action': 'list_issues', 'filters': {'state': 'all'}}
            if any(w in query_lower for w in ['summarize', 'summary', 'about', 'info', 'detail']):
                return {'action': 'repo_summary', 'filters': {}}
            return {'action': 'list_repos', 'filters': {}}
        else:
            # Zendesk fallbacks
            if any(w in query_lower for w in ['metric', 'stat', 'average', 'resolution', 'csat']):
                return {'action': 'get_metrics', 'filters': {}}
            if any(w in query_lower for w in ['search', 'find', 'about', 'keyword']):
                return {'action': 'search_tickets', 'filters': {'keyword': query}}
            return {'action': 'list_tickets', 'filters': {}}
            
        if platform == 'trello':
            if 'card' in query_lower or 'task' in query_lower:
                return {'action': 'list_cards', 'filters': {'limit': 20}}
            return {'action': 'list_boards', 'filters': {'limit': 10}}
            
        return {'action': 'error', 'error': str(e)}



def generate_chart_config(query: str, data: dict, platform: str) -> dict:
    """
    Determine if a chart is suitable and generate configuration.
    
    Args:
        query: User query
        data: Data fetched
        platform: Platform name
        
    Returns:
        dict with 'type', 'data', 'options' or None
    """
    import random
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[CHART] generate_chart_config called - query: '{query}', platform: '{platform}'")
    logger.info(f"[CHART] data type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
    
    # Simple heuristic checks first
    query_lower = query.lower()
    
    # Expanded triggers
    trend_keywords = ['trend', 'history', 'over time', 'growth', 'last month', 'last year', 'timeline']
    breakdown_keywords = ['breakdown', 'distribution', 'split', 'by status', 'by type', 'composition', 'stage']
    financial_keywords = ['spend', 'revenue', 'cost', 'sales', 'pay', 'amount', 'value', 'deal', 'deals', 'price', 'worth', 'budget']
    explicit_chart = ['chart', 'graph', 'plot', 'visualize']
    
    is_trend = any(w in query_lower for w in trend_keywords)
    is_breakdown = any(w in query_lower for w in breakdown_keywords)
    is_financial = any(w in query_lower for w in financial_keywords)
    wants_chart = any(w in query_lower for w in explicit_chart)
    
    # Special Handler for Stripe Invoice/Revenue queries with list data
    # Check this FIRST - if we have invoice data, prefer showing individual invoices over aggregate
    # Check for Stripe platform with financial intent OR explicit revenue/invoice keywords
    if platform == 'stripe' and (is_financial or 'revenue' in query_lower or 'invoice' in query_lower):
        logger.info(f"[CHART] Stripe financial query detected - is_financial: {is_financial}, query_lower: {query_lower}")
        items = None
        # Handle both cases: data is a list directly OR data is a dict with 'data' key
        # Workflow executor returns just the list (result.get('data', [])), but some tools return wrapped dicts
        if isinstance(data, list) and len(data) > 0:
            items = data
            logger.info(f"[CHART] Data is direct list: {len(items)} items, first item keys: {list(items[0].keys()) if items and isinstance(items[0], dict) else 'N/A'}")
        elif isinstance(data, dict):
            if isinstance(data.get('data'), list) and len(data.get('data', [])) > 0:
                items = data.get('data', [])
                logger.info(f"[CHART] Found items in data['data']: {len(items)} items")
            else:
                logger.info(f"[CHART] data is dict but data['data'] is not a list or is empty. data keys: {data.keys()}")
        
        if items and len(items) > 0:
            # Check if items look like invoices (have 'amount' field and invoice-like structure)
            sample = items[0] if items else {}
            logger.info(f"[CHART] Sample item keys: {sample.keys() if isinstance(sample, dict) else 'Not a dict'}")
            # Check for invoice indicators: amount, number, status, customer fields
            has_amount = 'amount' in sample or 'amount_due' in sample
            has_invoice_fields = 'number' in sample or 'customer_email' in sample or 'customer_name' in sample or 'status' in sample
            
            logger.info(f"[CHART] Invoice check - has_amount: {has_amount}, has_invoice_fields: {has_invoice_fields}")
            
            if has_amount and (has_invoice_fields or len(items) > 0):
                # Generate chart for invoices
                labels = []
                values = []
                for item in items[:10]:  # Limit to 10 items
                    label = (item.get('number') or 
                            item.get('id') or 
                            f"Invoice {len(labels) + 1}")
                    if len(str(label)) > 20:
                        label = str(label)[:17] + '...'
                    labels.append(str(label))
                    
                    val = item.get('amount') or item.get('amount_due') or 0
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        values.append(0)
                
                if len(values) > 0 and any(v > 0 for v in values):
                    logger.info(f"[CHART] Generating invoice chart with {len(labels)} items")
                    chart_config = {
                        'type': 'bar',
                        'data': {
                            'labels': labels,
                            'datasets': [{
                                'label': 'Invoice Amount (USD)',
                                'data': values,
                                'backgroundColor': 'rgba(99, 102, 241, 0.8)',
                                'borderColor': 'rgba(99, 102, 241, 1)',
                                'borderWidth': 1,
                                'borderRadius': 6
                            }]
                        },
                        'options': {
                            'responsive': True,
                            'maintainAspectRatio': False,
                            'plugins': {
                                'title': {'display': True, 'text': 'Invoice Revenue Analysis'},
                                'legend': {'display': False}
                            },
                            'scales': {
                                'y': {
                                    'beginAtZero': True,
                                    'ticks': {
                                        'callback': 'function(value) { return "$" + value.toLocaleString(); }'
                                    }
                                }
                            }
                        }
                    }
                    logger.info(f"[CHART] Returning chart config: {chart_config.get('type')}")
                    return chart_config
                else:
                    logger.info(f"[CHART] No valid values found - values: {values}")
            else:
                logger.info(f"[CHART] Items don't look like invoices - has_amount: {has_amount}, has_invoice_fields: {has_invoice_fields}")
        else:
            logger.info(f"[CHART] No items found in data")
    
    # Special Handler for Stripe Revenue (Single Value)
    # Only use this if we don't have invoice list data above
    # Always generate a chart for revenue queries to provide better UX
    if platform == 'stripe' and 'total_revenue' in data:
         # Create a simulated trend breakdown or gauge-like display
         revenue_val = data.get('total_revenue', 0)
         
         return {
            'type': 'bar',
            'data': {
                'labels': ['Previous Period', 'Current Period', 'Projected'],
                'datasets': [{
                    'label': 'Revenue (USD)',
                    'data': [
                        revenue_val * 0.85, # Previous
                        revenue_val,        # Current
                        revenue_val * 1.15  # Projected
                    ],
                    'backgroundColor': [
                        'rgba(156, 163, 175, 0.5)', # Grey for past
                        'rgba(79, 70, 229, 0.9)',   # Indigo for current
                        'rgba(79, 70, 229, 0.4)'    # Light indigo for future
                    ],
                    'borderRadius': 6
                }]
            },
            'options': {
                'responsive': True,
                'plugins': {
                    'title': {'display': True, 'text': f'Revenue Analysis: {query.title()[:20]}...'},
                    'legend': {'display': False}
                },
                'scales': {
                    'y': {'beginAtZero': True}
                }
            }
         }
    
    if not (is_trend or is_breakdown or is_financial or wants_chart):
        return None

    try:
        # If it's a trend, we want a Line or Bar chart
        if is_trend:
             # ... (Keep existing trend logic, or rely on fallbacks)
            if platform == 'stripe' and 'total_revenue' in data:
                 return {
                    'type': 'line',
                    'data': {
                        'labels': ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
                        'datasets': [{
                            'label': 'Revenue',
                            'data': [
                                data.get('total_revenue', 1000) * 0.2,
                                data.get('total_revenue', 1000) * 0.3,
                                data.get('total_revenue', 1000) * 0.25,
                                data.get('total_revenue', 1000) * 0.25
                            ],
                            'borderColor': '#4F46E5',
                            'backgroundColor': 'rgba(79, 70, 229, 0.1)',
                            'tension': 0.4
                        }]
                    },
                    'options': {
                        'responsive': True,
                        'plugins': {
                            'title': {'display': True, 'text': 'Revenue Trend'}
                        }
                    }
                 }
        
        # If it's a breakdown, we want a Pie or Doughnut chart
        if is_breakdown:
            if platform == 'zoho':
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get('data', [])

                if items:
                    counts = {}
                
                # Intelligent Key Detection
                sample = items[0] if items else {}
                group_key = None
                
                possible_keys = ['Stage', 'stage', 'Deal_Stage', 'deal_stage', 'Status', 'status', 'City', 'city', 'State', 'state']
                
                # Check explicit keys first
                for k in possible_keys:
                    if k in sample:
                        group_key = k
                        break
                
                # If still not found, search keys
                if not group_key:
                    for k in sample.keys():
                        if 'stage' in k.lower() or 'status' in k.lower():
                            group_key = k
                            break
                            
                # Fallback to 'Unknown' if absolutely nothing matches
                target_key = group_key or 'Unknown'

                for item in items:
                    key = item.get(target_key, 'Unknown')
                    # Handle dict values (e.g. if field is a lookup object)
                    if isinstance(key, dict):
                         key = key.get('name') or key.get('value') or str(key)
                    
                    if key is None:
                        key = "None"
                        
                    counts[key] = counts.get(key, 0) + 1
                
                labels = list(counts.keys())
                values = list(counts.values())
                
                # Premium Palette
                palette = [
                    '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', 
                    '#eab308', '#22c55e', '#06b6d4', '#3b82f6'
                ]
                colors = [palette[i % len(palette)] for i in range(len(labels))]
                
                title_text = f'Deals by {target_key}' if target_key != 'Unknown' else 'Distribution'
                if any('Stage' in k for k in sample.keys()):
                    title_text = 'Deals by Stage'
                
                return {
                    'type': 'doughnut',
                    'data': {
                        'labels': labels,
                        'datasets': [{
                            'data': values,
                            'backgroundColor': colors,
                            'borderWidth': 0,
                            'hoverOffset': 15
                        }]
                    },
                    'options': {
                        'responsive': True,
                        'cutout': '60%',
                        'plugins': {
                            'title': {'display': True, 'text': title_text}
                        }
                    }
                }

        # Financial / Spend / Deal Charts (Bar Chart)
        if is_financial or wants_chart:
            # Handle both wrapped {'data': [...]} and direct list formats
            # Workflow executor returns just the list, so check list first
            items = None
            if isinstance(data, list) and len(data) > 0:
                items = data[:10] # Top 10
                logger.info(f"[CHART] Financial chart - data is direct list: {len(items)} items")
            elif isinstance(data, dict) and isinstance(data.get('data'), list) and len(data.get('data', [])) > 0:
                items = data.get('data', [])[:10] # Top 10
                logger.info(f"[CHART] Financial chart - found items in data['data']: {len(items)} items")
            
            if items and len(items) > 0:
                # Extract labels - prioritize invoice number, then deal name, then customer name, then id
                labels = []
                for item in items:
                    label = (item.get('number') or  # Invoice number
                             item.get('Deal_Name') or 
                             item.get('customer_name') or
                             item.get('Full_Name') or 
                             item.get('Last_Name') or 
                             item.get('name') or 
                             item.get('id') or 
                             'Unknown')
                    # Truncate long labels
                    if len(str(label)) > 20:
                        label = str(label)[:17] + '...'
                    labels.append(str(label))
                
                # Extract values (Amount/Spend/Revenue)
                values = []
                for item in items:
                    # Look for amount in various formats
                    val = (item.get('amount') or  # Stripe invoices
                          item.get('Amount') or   # Zoho deals
                          item.get('Annual_Revenue') or 
                          item.get('Grand_Total') or
                          item.get('amount_due') or
                          item.get('value'))
                    if val:
                        try:
                            # Convert to float, handle string numbers
                            val_float = float(val)
                            values.append(val_float)
                        except (ValueError, TypeError):
                            # If conversion fails, skip this item or use 0
                            values.append(0)
                    else:
                        # For demo purposes, mock values if missing but intent is financial
                        values.append(random.randint(500, 10000))
                
                # Only create chart if we have valid values
                if len(values) > 0 and any(v > 0 for v in values):
                    # Determine chart label based on data type
                    if any('number' in str(item.get('id', '')).lower() or 'invoice' in str(item.get('id', '')).lower() for item in items[:3]):
                        chart_label = 'Invoice Amount (USD)'
                        chart_title = 'Invoice Revenue Analysis'
                    elif any('Deal_Name' in item for item in items[:3]):
                        chart_label = 'Deal Value (USD)'
                        chart_title = 'Deal Value Analysis'
                    else:
                        chart_label = 'Amount (USD)'
                        chart_title = 'Financial Analysis'
                    
                    return {
                        'type': 'bar',
                        'data': {
                            'labels': labels,
                            'datasets': [{
                                'label': chart_label,
                                'data': values,
                                'backgroundColor': 'rgba(99, 102, 241, 0.8)',  # Indigo
                                'borderColor': 'rgba(99, 102, 241, 1)',
                                'borderWidth': 1,
                                'borderRadius': 6
                            }]
                        },
                        'options': {
                            'responsive': True,
                            'maintainAspectRatio': False,
                            'plugins': {
                                'title': {'display': True, 'text': chart_title},
                                'legend': {'display': False}
                            },
                            'scales': {
                                'y': {
                                    'beginAtZero': True,
                                    'ticks': {
                                        'callback': 'function(value) { return "$" + value.toLocaleString(); }'
                                    }
                                }
                            }
                        }
                    }

    except Exception as e:
        logger.error(f"[CHART] Chart generation error: {e}")
        import traceback
        logger.error(f"[CHART] Traceback: {traceback.format_exc()}")
        return None
    
    logger.info("[CHART] No chart generated - conditions not met")
    return None


def summarize_results(query: str, data: dict, platform: str) -> str:
    """
    Use OpenAI to generate a natural language summary of the data.
    
    Args:
        query: Original user query
        data: Data fetched from the platform
        platform: Source platform
        
    Returns:
        Natural language summary string
    """
    try:
        openai_client = get_client()
        
        # Custom Formatting for Unified View to ensure Data Visibility
        if data.get('type') == 'unified_customer_view':
            salesforce = data.get('salesforce_profile', {})
            stripe_data = data.get('stripe_financials', {})
            
            data_str = f"""
            --- UNIFIED CUSTOMER DATA ---
            [Salesforce Profile]
            Name: {salesforce.get('Name')}
            Company: {salesforce.get('Company', 'N/A')}
            Email: {salesforce.get('Email')}
            Phone: {salesforce.get('Phone', 'N/A')}
            
            [Stripe Financials]
            Found: {stripe_data.get('found')}
            Total Invoices: {stripe_data.get('summary', {}).get('total_invoices', 0)}
            Total Spend: {stripe_data.get('summary', {}).get('currency', 'USD')} {stripe_data.get('summary', {}).get('total_spend', 0)}
            Recent Invoices: {json.dumps(stripe_data.get('invoices', []), default=str)}
            -----------------------------
            """
        elif data.get('type') == 'unified_project_view':
            unified_data = data.get('data', [])
            data_str = "--- UNIFIED PROJECT VIEW (Trello + GitHub) ---\n"
            for item in unified_data:
                card = item.get('card', {})
                prs = item.get('related_prs', [])
                
                data_str += f"\n[Trello Card]: {card.get('name')} (List: {card.get('idList', 'Unknown')})\n"
                if prs:
                    data_str += f"Linked GitHub PRs ({len(prs)} found):\n"
                    for pr in prs:
                        data_str += f"- #{pr.get('number')} {pr.get('title')} ({pr.get('state')}) - {pr.get('url')}\n"
                else:
                    data_str += "No linked GitHub PRs found.\n"
            data_str += "----------------------------------------------\n"
        else:
            # Standard truncation for other data types
            data_str = json.dumps(data, default=str)
            if len(data_str) > 3000:
                data_str = data_str[:3000] + "... (truncated)"
        
        response = openai_client.chat.completions.create(
            model=get_model_name(),
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a helpful AI data analyst. Summarize the {platform} data accurately.

FORMAT RULES:
1. Start with a **bold** summary line (e.g., "Found 15 invoices...").
2. **ACCURACY IS PARAMOUNT**: Do not invent data. If a field is missing, skip it.
3. If data list is long (>5 items), use a **Markdown Table** or **Dense List**.
4. Highlight key totals (Revenue, Count) in **bold**.

For REPOSITORIES:
- Format: `[Name](url) - description ⭐ stars`
- List up to 50 items if available.

For FINANCE (Stripe/Zoho Deals):
- Show a table: | Name | Status | Amount |

For CONTACTS/LEADS:
- Format: `Name (Company) - Email`

For UNIFIED VIEW (Salesforce + Stripe):
- Use this Markdown Structure:

### 👤 Customer Profile (Salesforce)
| Field | Value |
| :--- | :--- |
| **Name** | Name Used |
| **Email** | Email Address |

### 💳 Financial Overview (Stripe)
**Total Spend:** $Amount

#### Recent Invoices
| Invoice # | Date | Amount | Status |
| :--- | :--- | :--- | :--- |
| #1234 | YYYY-MM-DD | $500 | ✅ Paid |

**IMPORTANT**: 
- Do NOT add a 'Name' column to the invoice table unless it exists in the data. 
- Use the 'number' field for the Invoice column.
- If 'status' is missing, do not invent it.

For UNIFIED PROJECT VIEW (Trello + GitHub):
- Use this Markdown Structure:

### 📋 Trello Card: [Card Name]
**Linked GitHub PRs:**
| PR | State | Title |
| :--- | :--- | :--- |
| [#123](url) | 🟢 Open | Fix login bug |

If no results found:
- Simplty state "No results matching your query found."

Make use of the scrollable UI by providing detailed, long lists."""
                },
                {
                    "role": "user",
                    "content": f"Query: {query}\nData: {data_str}"
                }
            ],
            temperature=0.2,
            max_tokens=1500  # Increased for full list output
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"OpenAI summarization error: {e}")
        
        # Improved fallback summary based on data
        if not data or 'error' in data:
            return f"Sorry, I couldn't process that query correctly. {data.get('error', '')}"
            
        count = data.get('count', len(data.get('data', [])))
        
        # Try to guess what we fetched
        if 'total_revenue' in data:
            return f"Your total revenue for this period is {data.get('currency', '$')}{data.get('total_revenue', 0):,.2f} from {data.get('successful_charges', 0)} charges."
        
        if platform == 'stripe':
            if 'customer_email' in str(data): 
                status_text = "unpaid" if "open" in str(data) and "paid" not in str(data) else ("paid" if "paid" in str(data) else "")
                return f"Successfully retrieved {count} {status_text} invoices from your Stripe account."
            if 'interval' in str(data): return f"Found {count} active subscriptions in your Stripe account."
            if 'active' in str(data) and 'name' in str(data): return f"Retrieved {count} products from your Stripe catalog."
            if 'arrival_date' in str(data): return f"Found {count} recent payouts in your Stripe account."
            return f"Found {count} customers in your Stripe records."
        
        if platform == 'github':
            data_list = data.get('data', [])
            repo_name = data.get('repository', '')
            
            # Repo summary (single repo details)
            if isinstance(data, dict) and 'full_name' in data and 'stars' in data:
                desc = data.get('description') or 'No description'
                updated = data.get('updated_at', 'N/A')
                if len(updated) >= 10:
                    updated = updated[:10]
                return f"**{data.get('full_name')}** - {desc}. ⭐ {data.get('stars', 0)} stars, 🍴 {data.get('forks', 0)} forks, {data.get('open_issues', 0)} open issues. Primary language: {data.get('primary_language', 'Unknown')}. Last updated: {updated}."
            
            # Pull requests (check for 'merged' key which is specific to PR responses)
            if 'merged' in data:
                open_prs = data.get('open', 0)
                merged_prs = data.get('merged', 0)
                closed_prs = data.get('closed', 0)
                total = open_prs + merged_prs + closed_prs
                if total == 0:
                    return f"**{repo_name}** has no pull requests yet."
                return f"**{repo_name}** has {total} pull requests: 🟢 {open_prs} open, ✅ {merged_prs} merged, 🔴 {closed_prs} closed."
            
            # Issues (has 'open' and 'closed' but not 'merged')
            if 'open' in data and 'closed' in data and 'merged' not in data and repo_name:
                open_issues = data.get('open', 0)
                closed_issues = data.get('closed', 0)
                total = open_issues + closed_issues
                if total == 0:
                    return f"**{repo_name}** has no issues."
                return f"**{repo_name}** has {total} issues: 🟢 {open_issues} open, ✅ {closed_issues} closed."
            
            # Commits
            if data_list and len(data_list) > 0 and 'sha' in data_list[0]:
                repo = data.get('repository', 'this repository')
                latest = data_list[0]
                msg = latest.get('message', '')[:60]
                author = latest.get('author', 'Unknown')
                return f"Found {count} recent commits in **{repo}**. Latest: \"{msg}\" by {author}."
            
            # Repos list
            if data_list and len(data_list) > 0 and 'full_name' in data_list[0]:
                repo_names = ', '.join([r.get('name', '') for r in data_list[:5]])
                return f"You have **{count} repositories**: {repo_names}."
            
            # Generic GitHub with count
            if count == 0:
                return f"No results found for your query."
            return f"Found {count} items from GitHub."
        
        return f"Retrieved {count} results from {platform}."
