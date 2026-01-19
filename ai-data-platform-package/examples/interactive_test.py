import sys
import os

# Ensure we can import the package locally
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

import django
from django.conf import settings

def run_interactive_test():
    print("🤖 AI Data Platform - Interactive Test Mode")
    print("-------------------------------------------")
    
    # 1. Configure
    print("Configuring Django settings...")
    if not settings.configured:
        settings.configure(
            INSTALLED_APPS=['ai_data_platform'],
            AI_DATA_PLATFORM={
                'OPENAI_API_KEY': 'mock-key', # Replace if you want real calls
                'ENCRYPTION_KEY': 'mock-key'
            }
        )
        django.setup()

    from ai_data_platform.services.stripe_service import StripeService
    
    # 2. Instantiate
    print("\nInitializing Stripe Service...")
    service = StripeService()
    
    # 3. Connect (Mock)
    print("Connecting to platform (Mocking API Key)...")
    service.connect({'api_key': 'sk_test_mock'})
    
    print("\n✅ Service Ready!")
    print("Type a query (or 'quit' to exit).")
    print("Note: Since we are using mock keys, real API calls will fail, but the *logic flow* will execute.")
    
    while True:
        query = input("\nQuery > ")
        if query.lower() in ['quit', 'exit']:
            break
            
        print(f"\nProcessing: '{query}'...")
        
        # We pass a mock API key in user_context
        # In a real app, this comes from the database
        result = service.process_query(query, {'api_key': 'sk_test_mock'})
        
        print("\n--- Result ---")
        if 'error' in result:
             print(f"❌ Error: {result['error']}")
             print("(This is expected if OpenAI key is invalid or Stripe key is mock)")
        else:
             print(f"📄 Summary: {result.get('summary')}")
             print(f"📊 Data count: {len(result.get('data', {}).get('data', []))}")

if __name__ == "__main__":
    run_interactive_test()
