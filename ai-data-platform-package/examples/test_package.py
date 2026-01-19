import sys
import os

# Ensure we can import the package locally
# Resolving src directory relative to this file
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

import django
from django.conf import settings

# Configure Django settings needed for the package
if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[
            'ai_data_platform',
        ],
        AI_DATA_PLATFORM={
            'OPENAI_API_KEY': 'mock-key',
            'ENCRYPTION_KEY': 'mock-base64-key'
        }
    )
    django.setup()

from ai_data_platform.services.stripe_service import StripeService
from ai_data_platform.conf import api_settings

def test_package_structure():
    print("✅ Django Package Structure Loaded")
    
    # Test 1: Configuration Loading
    print(f"✅ Configuration Loaded: OPENAI_API_KEY={'found' if api_settings.OPENAI_API_KEY else 'missing'}")
    
    # Test 2: Service Instantiation
    service = StripeService()
    print(f"✅ Service Instantiated: {service.platform_id}")

    # Test 3: Metadata
    meta = service.get_metadata()
    print(f"✅ Metadata: {meta}")
    
    # Test 4: Extensibility check
    from ai_data_platform.core.base import BasePlatformService
    print("✅ Extensibility: BasePlatformService available")

if __name__ == "__main__":
    test_package_structure()
