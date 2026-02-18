import sys
from unittest.mock import MagicMock

# Aggressively mock everything before imports
sys.modules["openai"] = MagicMock()
sys.modules["django"] = MagicMock()
sys.modules["django.conf"] = MagicMock()

# Mock settings specifically
mock_settings = MagicMock()
mock_settings.OPENAI_API_KEY = "sk-mock-key"
sys.modules["django.conf"].settings = mock_settings

# Mock logging
logging_mock = MagicMock()
sys.modules["logging"] = logging_mock

import backend.utils.openai_client
# Prevent get_client from doing anything
backend.utils.openai_client.get_client = lambda: MagicMock()
backend.utils.openai_client.get_model_name = lambda: "gpt-mock"

from backend.utils.openai_client import generate_chart_config

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
        'total_amount': 320000,
        'summary': "Found 6 opportunities totaling $320,000.00."
    }
    
    print(f"Testing query: '{query}' for platform: '{platform}'")
    print("Calling generate_chart_config...")
    try:
        chart_config = generate_chart_config(query, data, platform)
        print("generate_chart_config returned.")
        
        if chart_config:
            print("\n✅ Chart Generated Successfully!")
            print(f"Type: {chart_config.get('type')}")
            print(f"Title: {chart_config.get('options', {}).get('plugins', {}).get('title', {}).get('text')}")
            if 'data' in chart_config:
                print(f"Labels: {chart_config['data'].get('labels')}")
                if 'datasets' in chart_config['data'] and len(chart_config['data']['datasets']) > 0:
                    print(f"Data: {chart_config['data']['datasets'][0].get('data')}")
        else:
            print("\n❌ No Chart Generated.")
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_salesforce_chart()
