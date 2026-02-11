"""
Stripe Connector Adapter

Implements the BaseConnector interface for Stripe.
This adapter wraps the existing stripe_client functionality
in the new connector pattern.
"""

import logging
from typing import Any, Dict, List

from ..base import BaseConnector, ConnectorResult, GovernanceClass

logger = logging.getLogger(__name__)


class StripeConnector(BaseConnector):
    """
    Stripe platform connector.
    
    Wraps the Stripe API for use with the connector registry.
    """
    
    PLATFORM_NAME = "stripe"
    PLATFORM_DISPLAY_NAME = "Stripe"
    
    # Tool ID to governance class mapping
    GOVERNANCE_MAP = {
        "list_invoices": GovernanceClass.READ,
        "get_revenue": GovernanceClass.READ,
        "list_customers": GovernanceClass.READ,
        "get_customer": GovernanceClass.READ,
        "create_invoice": GovernanceClass.WRITE,
        "create_refund": GovernanceClass.MONEY_MOVE,
        "create_charge": GovernanceClass.MONEY_MOVE,
    }
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize Stripe connector.
        
        Args:
            credentials: Must contain 'api_key'
        """
        super().__init__(credentials)
        self._api_key = credentials.get('api_key')
    
    def _get_stripe(self):
        """Get configured Stripe client."""
        if self._client is None:
            try:
                import stripe
                stripe.api_key = self._api_key
                self._client = stripe
            except ImportError:
                raise ImportError("stripe package not installed")
        return self._client
    
    def validate_credentials(self) -> bool:
        """Validate Stripe API key by making a test API call."""
        try:
            stripe = self._get_stripe()
            # Try to retrieve account info (minimal API call)
            stripe.Account.retrieve()
            return True
        except Exception as e:
            logger.error(f"Stripe credential validation failed: {e}")
            return False
    
    def get_supported_tools(self) -> List[str]:
        """Return list of supported tool IDs."""
        return [
            "list_invoices",
            "get_revenue",
            "list_customers",
            "get_customer",
            "list_subscriptions",
            "list_products",
        ]
    
    def get_governance_class(self, tool_id: str) -> GovernanceClass:
        """Get governance class for a tool."""
        return self.GOVERNANCE_MAP.get(tool_id, GovernanceClass.READ)
    
    def execute(self, tool_id: str, params: Dict[str, Any]) -> ConnectorResult:
        """
        Execute a Stripe tool action.
        
        Args:
            tool_id: The tool to execute
            params: Tool parameters
        
        Returns:
            ConnectorResult with execution result
        """
        try:
            stripe = self._get_stripe()
            
            if tool_id == "list_invoices":
                return self._list_invoices(stripe, params)
            elif tool_id == "get_revenue":
                return self._get_revenue(stripe, params)
            elif tool_id == "list_customers":
                return self._list_customers(stripe, params)
            elif tool_id == "get_customer":
                return self._get_customer(stripe, params)
            elif tool_id == "list_subscriptions":
                return self._list_subscriptions(stripe, params)
            elif tool_id == "list_products":
                return self._list_products(stripe, params)
            else:
                return ConnectorResult(
                    success=False,
                    error=f"Unknown tool: {tool_id}"
                )
        except Exception as e:
            logger.exception(f"Stripe execution error: {tool_id}")
            return ConnectorResult(
                success=False,
                error=str(e)
            )
    
    def _list_invoices(self, stripe, params: Dict) -> ConnectorResult:
        """List invoices with optional filters."""
        api_params = {"limit": params.get("limit", 50)}
        
        if "customer" in params:
            api_params["customer"] = params["customer"]
        if "status" in params:
            api_params["status"] = params["status"]
        
        invoices = stripe.Invoice.list(**api_params)
        
        data = [self._normalize_invoice(inv) for inv in invoices.data]
        
        return ConnectorResult(
            success=True,
            data=data,
            has_more=invoices.has_more,
            next_cursor=data[-1]["id"] if data and invoices.has_more else None,
            total_count=len(data)
        )
    
    def _get_revenue(self, stripe, params: Dict) -> ConnectorResult:
        """Calculate revenue from paid invoices."""
        # Fetch paid invoices
        invoices = stripe.Invoice.list(status="paid", limit=100)
        
        product_filter = params.get("product_name", "").lower()
        total_revenue = 0
        matched_invoices = []
        
        for invoice in invoices.data:
            invoice_amount = 0
            
            for line_item in invoice.lines.data:
                description = (line_item.description or "").lower()
                
                if not product_filter or product_filter in description:
                    invoice_amount += line_item.amount
            
            if invoice_amount > 0:
                total_revenue += invoice_amount
                matched_invoices.append({
                    "id": invoice.id,
                    "amount": invoice_amount / 100,
                    "customer": invoice.customer
                })
        
        return ConnectorResult(
            success=True,
            data={
                "total_revenue": total_revenue / 100,
                "currency": "usd",
                "invoice_count": len(matched_invoices),
                "invoices": matched_invoices[:10]  # Top 10 for reference
            }
        )
    
    def _list_customers(self, stripe, params: Dict) -> ConnectorResult:
        """List customers."""
        customers = stripe.Customer.list(limit=params.get("limit", 50))
        data = [self._normalize_customer(c) for c in customers.data]
        
        return ConnectorResult(
            success=True,
            data=data,
            has_more=customers.has_more,
            total_count=len(data)
        )
    
    def _get_customer(self, stripe, params: Dict) -> ConnectorResult:
        """Get a single customer."""
        customer_id = params.get("customer_id")
        if not customer_id:
            return ConnectorResult(success=False, error="customer_id required")
        
        customer = stripe.Customer.retrieve(customer_id)
        return ConnectorResult(
            success=True,
            data=self._normalize_customer(customer)
        )
    
    def _list_subscriptions(self, stripe, params: Dict) -> ConnectorResult:
        """List subscriptions."""
        subs = stripe.Subscription.list(limit=params.get("limit", 50))
        data = [{
            "id": s.id,
            "customer": s.customer,
            "status": s.status,
            "current_period_end": s.current_period_end
        } for s in subs.data]
        
        return ConnectorResult(success=True, data=data, total_count=len(data))
    
    def _list_products(self, stripe, params: Dict) -> ConnectorResult:
        """List products."""
        products = stripe.Product.list(active=True, limit=params.get("limit", 50))
        data = [{
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "active": p.active
        } for p in products.data]
        
        return ConnectorResult(success=True, data=data, total_count=len(data))
    
    def _normalize_invoice(self, invoice) -> Dict[str, Any]:
        """Normalize Stripe invoice to standard format."""
        return {
            "id": invoice.id,
            "customer_id": invoice.customer,
            "customer_email": invoice.customer_email,
            "amount": invoice.amount_due / 100,
            "amount_paid": invoice.amount_paid / 100,
            "currency": invoice.currency,
            "status": invoice.status,
            "created_at": invoice.created,
            "description": invoice.description
        }
    
    def _normalize_customer(self, customer) -> Dict[str, Any]:
        """Normalize Stripe customer to standard format."""
        return {
            "id": customer.id,
            "email": customer.email,
            "name": customer.name,
            "created_at": customer.created
        }
