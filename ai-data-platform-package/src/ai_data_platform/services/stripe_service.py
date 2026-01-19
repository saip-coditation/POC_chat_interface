from datetime import datetime, timedelta
import stripe
from typing import Dict, Any

from ..core.base import BasePlatformService
from .ai_service import ai_service

class StripeService(BasePlatformService):
    @property
    def platform_id(self) -> str:
        return 'stripe'

    def connect(self, credentials: Dict[str, Any]) -> bool:
        api_key = credentials.get('api_key')
        if not api_key:
            raise ValueError("Missing api_key")
        
        try:
            stripe.api_key = api_key
            stripe.Account.retrieve()
            return True
        except Exception as e:
            raise ValueError(f"Stripe connection failed: {e}")

    def get_metadata(self) -> Dict[str, Any]:
        return {"name": "Stripe", "description": "Payment processing"}

    def process_query(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        api_key = user_context.get('api_key')
        stripe.api_key = api_key
        
        # 1. Interpret Query
        system_prompt = """You interpret natural language queries about Stripe data.
Available actions:
- list_invoices: Get invoices (Filters: status, limit)
- list_customers: Get customers (Filters: limit, email)
Respond with JSON: {"action": "...", "filters": {...}}"""
        
        # Simplified prompt for brevity in this package example
        params = ai_service.interpret_query(query, 'stripe', system_prompt)
        
        if params.get('action') == 'error':
            return {'error': params.get('error')}
            
        action = params.get('action')
        filters = params.get('filters', {})
        
        # 2. Execute Action
        data = {}
        try:
            if action == 'list_invoices':
                data = self._list_invoices(filters)
            elif action == 'list_customers':
                data = self._list_customers(filters)
            else:
                data = {'error': f"Unknown action: {action}"}
        except Exception as e:
            data = {'error': str(e)}

        # 3. Summarize
        summary = ai_service.summarize_results(query, data, 'stripe')
        return {
            'summary': summary,
            'data': data
        }

    def _list_invoices(self, filters: Dict) -> Dict:
        limit = min(filters.get('limit', 10), 50)
        invoices = stripe.Invoice.list(limit=limit)
        return {
            'data': [{'id': i.id, 'amount': i.amount_due} for i in invoices.data],
            'count': len(invoices.data)
        }

    def _list_customers(self, filters: Dict) -> Dict:
        limit = min(filters.get('limit', 10), 50)
        customers = stripe.Customer.list(limit=limit)
        return {
            'data': [{'id': c.id, 'email': c.email} for c in customers.data],
            'count': len(customers.data)
        }
