import logging
import json
import random

# Mock logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_chart_config(query: str, data: dict, platform: str) -> dict:
    # ... (Copy-paste of generate_chart_config logic from openai_client.py)
    # ...
    # This is a manual copy to test logic in isolation
    
    logger.info(f"[CHART] generate_chart_config called - query: '{query}', platform: '{platform}'")
    logger.info(f"[CHART] data type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
    
    query_lower = query.lower()
    
    trend_keywords = ['trend', 'history', 'over time', 'growth', 'last month', 'last year', 'timeline']
    breakdown_keywords = ['breakdown', 'distribution', 'split', 'by status', 'by type', 'composition', 'stage']
    financial_keywords = ['spend', 'revenue', 'cost', 'sales', 'pay', 'amount', 'value', 'deal', 'deals', 'price', 'worth', 'budget']
    explicit_chart = ['chart', 'graph', 'plot', 'visualize']
    
    is_trend = any(w in query_lower for w in trend_keywords)
    is_breakdown = any(w in query_lower for w in breakdown_keywords)
    is_financial = any(w in query_lower for w in financial_keywords)
    wants_chart = any(w in query_lower for w in explicit_chart)
    
    print(f"DEBUG: is_trend={is_trend}, is_breakdown={is_breakdown}, is_financial={is_financial}, wants_chart={wants_chart}")

    # ... (Simplified logic focusing on breakdown)
    if is_breakdown:
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('data', [])

        if items:
            counts = {}
            sample = items[0] if items else {}
            group_key = None
            
            # UPDATED KEYS
            possible_keys = ['Stage', 'stage', 'Deal_Stage', 'deal_stage', 'Status', 'status', 'City', 'city', 'State', 'state', 'Type', 'type', 'StageName']
            
            for k in possible_keys:
                if k in sample:
                    group_key = k
                    break
            
            if not group_key:
                for k in sample.keys():
                    if 'stage' in k.lower() or 'status' in k.lower():
                        group_key = k
                        break
                        
            target_key = group_key or 'Unknown'
            print(f"DEBUG: Detected group_key={group_key}, target_key={target_key}")

            for item in items:
                key = item.get(target_key, 'Unknown')
                if isinstance(key, dict):
                        key = key.get('name') or key.get('value') or str(key)
                
                if key is None:
                    key = "None"
                    
                counts[key] = counts.get(key, 0) + 1
            
            labels = list(counts.keys())
            values = list(counts.values())
            
            return {
                'type': 'doughnut',
                'data': {'labels': labels, 'datasets': [{'data': values}]}
            }
            
    return None

def test_salesforce_chart():
    query = "Salesforce deals breakdown"
    platform = "salesforce"
    
    data = {
        'success': True,
        'data': [
            {'Name': 'Deal 1', 'Amount': 50000, 'StageName': 'Prospecting', 'Probability': 10},
            {'Name': 'Deal 2', 'Amount': 75000, 'StageName': 'Closed Won', 'Probability': 100},
            {'Name': 'Deal 3', 'Amount': 25000, 'StageName': 'Negotiation', 'Probability': 50},
            {'Name': 'Deal 4', 'Amount': 100000, 'StageName': 'Closed Won', 'Probability': 100},
            {'Name': 'Deal 5', 'Amount': 10000, 'StageName': 'Closed Lost', 'Probability': 0},
            {'Name': 'Deal 6', 'Amount': 60000, 'StageName': 'Prospecting', 'Probability': 10},
        ],
        'total_amount': 320000
    }
    
    print(f"Testing query: '{query}'")
    chart = generate_chart_config(query, data, platform)
    if chart:
        print("✅ Chart Generated!")
        print(chart)
    else:
        print("❌ No Chart")

if __name__ == "__main__":
    test_salesforce_chart()
