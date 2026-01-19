# AI Data Platform Package

A reusable Django backend for querying third-party platforms with AI.

## Supported Platforms

- **Stripe** - Payment processing
- **Zoho CRM** - Customer relationship management

## Installation

```bash
pip install ai-data-platform
```

## Setup

1. Add to `INSTALLED_APPS`:
   ```python
   INSTALLED_APPS = [
       ...
       'ai_data_platform',
   ]
   ```

2. Configure settings:
   ```python
   AI_DATA_PLATFORM = {
       'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
       'ENCRYPTION_KEY': os.getenv('ENCRYPTION_KEY'),
   }
   ```

3. For Zoho CRM, set additional environment variables:
   ```bash
   ZOHO_CLIENT_ID=your_client_id
   ZOHO_CLIENT_SECRET=your_client_secret
   ZOHO_ACCOUNTS_DOMAIN=accounts.zoho.in  # or .com, .eu, etc.
   ZOHO_API_DOMAIN=www.zohoapis.in  # or .com, .eu, etc.
   ```

## Usage

### Stripe
```python
from ai_data_platform.services import StripeService

service = StripeService()
service.connect({'api_key': 'sk_test_...'})
result = service.process_query("Show me unpaid invoices", {'api_key': 'sk_test_...'})
print(result['summary'])
```

### Zoho CRM
```python
from ai_data_platform.services import ZohoService

service = ZohoService()
service.connect({'api_key': 'your_refresh_token'})
result = service.process_query("Show me all contacts", {'api_key': 'your_refresh_token'})
print(result['summary'])
```

## Available Zoho Actions

- `fetch_contacts` - Get contacts from Zoho CRM
- `fetch_leads` - Get leads from Zoho CRM
- `fetch_deals` - Get deals from Zoho CRM
- `fetch_accounts` - Get accounts (companies) from Zoho CRM

