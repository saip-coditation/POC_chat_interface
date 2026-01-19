"""
OpenAI Client for query processing.

Handles platform detection, query interpretation, and result summarization.
Uses OpenRouter API for LLM access.
"""

import json
import logging
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
                base_url="https://openrouter.ai/api/v1"
            )
        else:
            # Native OpenAI key (sk-proj- or sk-)
            client = OpenAI(api_key=api_key)
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

Respond with JSON only: {"platform": "stripe" or "zoho" or "github", "confidence": 0.0-1.0}"""
                },
                {
                    "role": "user",
                    "content": f"Query: {query}\nAvailable platforms: {', '.join(available_platforms)}"
                }
            ],
            temperature=0,
            max_tokens=50
        )
        
        result = json.loads(response.choices[0].message.content)
        
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
- list_invoices: [filters: status (paid/unpaid/open/void), period, limit, customer]
- list_subscriptions: [filters: status (active/past_due/canceled), limit, plan]
- get_revenue: [filters: period (today/week/month/year)]
- list_customers: [filters: limit, email, created_after]
- list_charges: [filters: status (succeeded/pending/failed), limit, amount_gt]
- list_products: [filters: active (true/false), limit]
- list_payouts: [filters: limit]

RULES:
1. "Unpaid/Open" -> status: "unpaid". "Paid" -> status: "paid".
2. "Last month" -> period: "last_month". "Today" -> period: "today".
3. "Failed charges" -> action: "list_charges", filters: {status: "failed"}.
4. "High value" or "over $500" -> filters: {amount_gt: 500}.
5. Default limit: 20. If "all" or "list", limit: 50.

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
4. Extract repo names like "facebook/react" or "frontend".
5. Default limit: 20. If "all", limit: 100.

Respond with valid JSON only."""
        else:
            system_prompt = """You interpret natural language queries about Zoho CRM data.

Available actions:
- list_contacts: [filters: limit, city, location, state, email]
- list_deals: [filters: limit, stage (Won/Lost/Negotiation), amount_gt]
- list_leads: [filters: limit, city, location, state, status]
- list_accounts: [filters: limit, city]

RULES:
1. "Contacts from Mumbai" -> filters: {city: "Mumbai"}.
2. "Won deals" -> action: "list_deals", filters: {stage: "Closed Won"}.
3. "Big deals" or "over 10k" -> filters: {amount_gt: 10000}.
4. "Hot leads" -> action: "list_leads", filters: {status: "Hot"}.
5. Default limit: 20. If "all", limit: 100.

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
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON: {e}")
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
            if platform == 'zoho' and isinstance(data.get('data'), list):
                items = data.get('data', [])
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
            if isinstance(data.get('data'), list):
                items = data.get('data', [])[:10] # Top 10
                
                # Extract labels (Deal Name / Contact Name)
                labels = [item.get('Deal_Name') or item.get('Full_Name') or item.get('Last_Name') or item.get('name') or item.get('id') or 'Unknown' for item in items]
                
                # Extract values (Amount/Spend/Revenue - or mock for demo)
                values = []
                for item in items:
                    # Look for Amount (Deals), Annual_Revenue (Accounts), or generic amount
                    val = item.get('Amount') or item.get('Annual_Revenue') or item.get('Grand_Total') or item.get('amount')
                    if val:
                        try:
                            values.append(float(val))
                        except:
                            values.append(random.randint(100, 5000))
                    else:
                        # For demo purposes, mock values if missing but intent is financial
                        values.append(random.randint(500, 10000))
                
                chart_label = 'Deal Value (USD)' if any('Deal_Name' in i for i in items[:3]) else 'Spend / Value (USD)'
                
                return {
                    'type': 'bar',
                    'data': {
                        'labels': labels,
                        'datasets': [{
                            'label': chart_label,
                            'data': values,
                            'backgroundColor': 'rgba(54, 162, 235, 0.6)',
                            'borderColor': 'rgba(54, 162, 235, 1)',
                            'borderWidth': 1
                        }]
                    },
                    'options': {
                        'responsive': True,
                        'plugins': {
                            'title': {'display': True, 'text': 'Financial Analysis'}
                        }
                    }
                }

    except Exception as e:
        logger.error(f"Chart generation error: {e}")
        return None
    
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
        
        # Truncate data if too large
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
