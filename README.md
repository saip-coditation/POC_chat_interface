# DataBridge AI - AI-Driven Data Access Platform

A modern SaaS web application that allows users to connect their Stripe and Zendesk accounts and query their business data using natural language, powered by OpenAI.

## Features

- **Multi-Platform Support**: Connect Stripe and Zendesk accounts
- **Natural Language Queries**: Ask questions about your data in plain English
- **AI-Powered Insights**: OpenAI-powered query understanding and summarization
- **Secure Credential Storage**: AES-256 encrypted API keys
- **Modern UI**: Clean, responsive SaaS-style interface

## Architecture

```
Chat_Interface/
├── index.html              # Frontend SPA
├── css/                    # Modular CSS
│   ├── variables.css       # Design tokens
│   ├── base.css           # Reset & utilities
│   ├── components.css     # UI components
│   ├── pages.css          # Page layouts
│   └── animations.css     # Animations
├── js/                     # Frontend JavaScript
│   ├── utils.js           # Utility functions
│   ├── state.js           # State management
│   ├── api.js             # API client
│   └── app.js             # Main controller
└── backend/                # Django REST API
    ├── manage.py
    ├── requirements.txt
    ├── config/             # Django settings
    ├── apps/
    │   ├── authentication/ # JWT auth
    │   ├── platforms/      # Platform connections
    │   └── queries/        # Query processing
    └── utils/              # Utilities
        ├── encryption.py   # API key encryption
        ├── openai_client.py
        ├── stripe_client.py
        └── zendesk_client.py
```

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your keys:
# - SECRET_KEY (generate a new one)
# - OPENAI_API_KEY (your OpenAI key)
# - ENCRYPTION_KEY (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Run server
python manage.py runserver
```

### 2. Frontend Setup

The frontend is static HTML/CSS/JS. You can serve it with any static file server:

```bash
# Option 1: Python simple server
cd Chat_Interface
python -m http.server 5500

# Option 2: VS Code Live Server extension
# Option 3: Any static file server
```

### 3. Access the Application

- Frontend: http://localhost:5500 (or wherever you serve it)
- Backend API: http://localhost:8000/api/

## API Endpoints

### Authentication
- `POST /api/auth/login/` - Login with email/password
- `POST /api/auth/register/` - Register new user
- `POST /api/auth/logout/` - Logout (blacklist token)
- `POST /api/auth/refresh/` - Refresh access token
- `GET /api/auth/me/` - Get current user

### Platforms
- `GET /api/platforms/` - List connected platforms
- `POST /api/platforms/connect/` - Connect new platform
- `DELETE /api/platforms/{id}/` - Disconnect platform
- `POST /api/platforms/{id}/reverify/` - Re-verify credentials

### Queries
- `POST /api/queries/process/` - Process natural language query
- `GET /api/queries/history/` - Get query history

## Connecting Platforms

### Stripe
1. Get your API key from https://dashboard.stripe.com/apikeys
2. Use your **Secret Key** (starts with `sk_`)
3. For testing, use a test mode key (starts with `sk_test_`)

### Zendesk
1. Format: `subdomain:email:api_token`
2. Get your API token from Admin > Channels > API
3. Example: `mycompany:admin@company.com:abcd1234token`

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `DEBUG` | Debug mode (True/False) | No |
| `OPENAI_API_KEY` | Your OpenAI API key | Yes |
| `ENCRYPTION_KEY` | Fernet key for API encryption | Yes |
| `CORS_ALLOWED_ORIGINS` | Allowed frontend origins | No |
| `ALLOWED_HOSTS` | Allowed hosts | No |

## Security Features

- **JWT Authentication**: Short-lived access tokens (60 min)
- **API Key Encryption**: Fernet symmetric encryption at rest
- **CORS Protection**: Configured for specific origins only
- **Rate Limiting**: Prevents abuse
- **Input Validation**: All inputs validated and sanitized

## Example Queries

### Stripe
- "Show unpaid invoices"
- "Revenue this month"
- "List active subscriptions"
- "Customer growth last week"

### Zendesk
- "List open tickets"
- "Average resolution time"
- "High priority tickets"
- "Search for billing issues"

## Development

### Running Tests
```bash
cd backend
python manage.py test
```

### CORS Configuration
Update `CORS_ALLOWED_ORIGINS` in `.env` to include your frontend URL.

## License

MIT


Instructions for the creating python pip module
You are a senior Python architect and Django package author.

Your task is to design a reusable, pip-installable Django REST Framework backend
called `ai-data-platform`.

This package must allow anyone to install it via pip and instantly get a
fully working AI-driven backend for querying third-party platforms
(Stripe, GitHub, Zendesk).

### REQUIREMENTS

1. The package must be installable via:
   pip install ai-data-platform

2. It must expose a Django app that can be added to INSTALLED_APPS.

3. The package must include:
   - Django models
   - DRF serializers
   - API views
   - URL routing
   - Migrations
   - Service layers for Stripe, GitHub, Zendesk
   - AI layer using OpenAI + optional LangGraph

4. Database:
   - Use Django ORM
   - Provide migrations
   - Support SQLite by default
   - No hardcoded data

5. APIs to expose:
   - POST /api/login
   - POST /api/connect-platform
   - POST /api/query

6. Security:
   - Encrypt stored credentials
   - Never send credentials to OpenAI
   - Token-based authentication

7. Configuration:
   - Provide default settings via settings_defaults.py
   - Allow override from project settings
   - Read API keys from environment variables

8. Provide management commands:
   - init_platform (initial setup)
   - create_demo_data (optional)

9. The package must be modular:
   - Platforms can be enabled/disabled
   - AI provider can be swapped

10. Output required:
    - Folder structure
    - Key files
    - Example settings.py integration
    - Example usage instructions

##################################################################
Quick Test Queries (Copy & Paste)

GitHub
How can I create a new repo in GitHub?
How to push files in GitHub?
How do I create a good pull request?
When should I merge a pull request?
How do I write good commit messages?
How to create a branch in GitHub?
How to merge branches in GitHub?
How do I resolve merge conflicts?

Trello
How can I create a new card in Trello?
When should I move a card to Done?
How do I organize cards in Trello?
What are best practices for Trello cards?
How to use Trello labels effectively?
How do I add members to a Trello board?
How to archive cards in Trello?
How do I use Trello checklists?

Stripe
When should I retry a failed payment?
How do I process refunds in Stripe?
How do I manage subscriptions in Stripe?
How to handle failed payments in Stripe?
How do I handle subscription upgrades?
How to process partial refunds?
How do I set up webhooks in Stripe?
How to handle chargebacks?

Salesforce
How do I qualify a lead in Salesforce?
When should I convert a lead to an opportunity?
How do I manage my sales pipeline?
What is the BANT framework?
How to build reports in Salesforce?
How do I automate workflows?
How to use Salesforce dashboards?
How do I track activities?

Zoho
How do I manage deals in Zoho?
When should I move a deal to the next stage?
How to track deals in Zoho?
How do I create custom fields in Zoho?
How to automate Zoho workflows?
How to create reports in Zoho?
How do I manage Zoho pipelines?
How to set up Zoho blueprints?

Platform Mismatch Tests
When should I retry a failed payment? in trello
How do I create a card? in stripe
How to push files? in salesforce
How do I qualify a lead? in github

One-Liner Quick Tests
How to create a repo?
How to push code?
How to create a card?
How to retry payments?
How to qualify leads?
How to manage deals?
