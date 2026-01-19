"""
Stripe API Client

Handles Stripe API interactions for data fetching.
"""

import logging
from datetime import datetime, timedelta
import stripe

logger = logging.getLogger(__name__)


def validate_api_key(api_key: str) -> dict:
    """
    Validate a Stripe API key by making a test request.
    
    Args:
        api_key: Stripe secret key (sk_...)
        
    Returns:
        dict with 'valid' boolean and 'error' message if invalid
    """
    try:
        stripe.api_key = api_key
        # Try to retrieve account info
        account = stripe.Account.retrieve()
        return {
            'valid': True,
            'account_id': account.id,
            'business_name': getattr(account, 'business_profile', {}).get('name', 'Unknown')
        }
    except stripe.error.AuthenticationError:
        return {'valid': False, 'error': 'Invalid API key'}
    except stripe.error.PermissionError:
        return {'valid': False, 'error': 'API key lacks required permissions'}
    except Exception as e:
        logger.error(f"Stripe validation error: {e}")
        return {'valid': False, 'error': str(e)}


def fetch_invoices(api_key: str, filters: dict = None) -> dict:
    """
    Fetch invoices from Stripe with advanced filtering.
    
    Args:
        api_key: Stripe secret key
        filters: Optional filters including:
            - status: 'paid', 'unpaid', 'open', 'void'
            - period: 'today', 'week', 'month', 'year', 'last_month'
            - country: Country name or code (e.g., 'India', 'IN', 'US')
            - state: State/region name (e.g., 'Maharashtra', 'California')
            - limit: Number of results
        
    Returns:
        dict with 'data' list and 'count'
    """
    filters = filters or {}
    
    try:
        stripe.api_key = api_key
        
        params = {
            'limit': min(filters.get('limit', 100), 100),
            'expand': ['data.customer']  # Get customer details including address
        }
        
        # Status filter
        status = filters.get('status')
        if status:
            if status in ['unpaid', 'open']:
                params['status'] = 'open'
            elif status == 'paid':
                params['status'] = 'paid'
            elif status == 'void':
                params['status'] = 'void'
        
        # Date range filter
        period = filters.get('period')
        if period:
            now = datetime.now()
            if period == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'week':
                start_date = now - timedelta(days=7)
            elif period == 'month':
                start_date = now - timedelta(days=30)
            elif period == 'last_month':
                # Get first and last day of previous month
                first_of_current = now.replace(day=1)
                last_of_previous = first_of_current - timedelta(days=1)
                start_date = last_of_previous.replace(day=1)
                params['created'] = {
                    'gte': int(start_date.timestamp()),
                    'lt': int(first_of_current.timestamp())
                }
            elif period == 'year':
                start_date = now - timedelta(days=365)
            
            if period != 'last_month' and period:
                params['created'] = {'gte': int(start_date.timestamp())}
        
        invoices = stripe.Invoice.list(**params)
        
        # Country/State mapping for common variations
        country_map = {
            'india': 'IN', 'in': 'IN',
            'usa': 'US', 'united states': 'US', 'us': 'US', 'america': 'US',
            'uk': 'GB', 'united kingdom': 'GB', 'britain': 'GB', 'gb': 'GB',
            'canada': 'CA', 'ca': 'CA',
            'australia': 'AU', 'au': 'AU',
            'germany': 'DE', 'de': 'DE',
        }
        
        # Get filter values
        country_filter = filters.get('country', '').lower()
        state_filter = filters.get('state', '').lower()
        
        # Normalize country filter
        if country_filter:
            country_filter = country_map.get(country_filter, country_filter.upper())
        
        data = []
        for inv in invoices.data:
            # Get customer address info
            customer = inv.customer if hasattr(inv, 'customer') and inv.customer else None
            customer_address = {}
            
            if customer and hasattr(customer, 'address') and customer.address:
                addr = customer.address
                customer_address = {
                    'city': getattr(addr, 'city', None),
                    'state': getattr(addr, 'state', None),
                    'country': getattr(addr, 'country', None),
                    'postal_code': getattr(addr, 'postal_code', None),
                }
            
            # Apply geographic filters
            if country_filter:
                inv_country = customer_address.get('country', '').upper()
                if inv_country != country_filter:
                    continue
            
            if state_filter:
                inv_state = (customer_address.get('state') or '').lower()
                if state_filter not in inv_state and inv_state not in state_filter:
                    continue
            
            data.append({
                'id': inv.id,
                'number': inv.number,
                'customer_email': inv.customer_email,
                'customer_name': inv.customer_name,
                'amount': inv.amount_due / 100,
                'currency': inv.currency.upper(),
                'status': inv.status,
                'created': datetime.fromtimestamp(inv.created).isoformat(),
                'due_date': datetime.fromtimestamp(inv.due_date).isoformat() if inv.due_date else None,
                'country': customer_address.get('country'),
                'state': customer_address.get('state'),
                'city': customer_address.get('city'),
            })
        
        return {
            'data': data,
            'count': len(data),
            'has_more': invoices.has_more,
            'filters_applied': {
                'country': country_filter or None,
                'state': state_filter or None,
                'period': period or None,
                'status': status or None,
            }
        }
        
    except Exception as e:
        logger.error(f"Stripe fetch invoices error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_subscriptions(api_key: str, filters: dict = None) -> dict:
    """
    Fetch subscriptions from Stripe.
    
    Args:
        api_key: Stripe secret key
        filters: Optional filters (status, limit)
        
    Returns:
        dict with 'data' list and 'count'
    """
    filters = filters or {}
    
    try:
        stripe.api_key = api_key
        
        params = {
            'limit': min(filters.get('limit', 50), 100),
        }
        
        status = filters.get('status')
        if status:
            params['status'] = status
        
        subscriptions = stripe.Subscription.list(**params)
        
        data = []
        for sub in subscriptions.data:
            data.append({
                'id': sub.id,
                'customer': sub.customer,
                'status': sub.status,
                'current_period_start': datetime.fromtimestamp(sub.current_period_start).isoformat(),
                'current_period_end': datetime.fromtimestamp(sub.current_period_end).isoformat(),
                'amount': sub.items.data[0].price.unit_amount / 100 if sub.items.data else 0,
                'interval': sub.items.data[0].price.recurring.interval if sub.items.data else 'month',
            })
        
        return {
            'data': data,
            'count': len(data),
            'has_more': subscriptions.has_more
        }
        
    except Exception as e:
        logger.error(f"Stripe fetch subscriptions error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_revenue(api_key: str, filters: dict = None) -> dict:
    """
    Fetch revenue metrics from Stripe.
    
    Args:
        api_key: Stripe secret key
        filters: Optional filters (period: today/week/month/year)
        
    Returns:
        dict with revenue data
    """
    filters = filters or {}
    period = filters.get('period', 'month')
    
    try:
        stripe.api_key = api_key
        
        # Calculate date range
        now = datetime.now()
        if period == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start = now - timedelta(days=7)
        elif period == 'year':
            start = now - timedelta(days=365)
        else:  # month
            start = now - timedelta(days=30)
        
        # Fetch charges in date range
        charges = stripe.Charge.list(
            created={'gte': int(start.timestamp())},
            limit=100
        )
        
        total_revenue = 0
        successful_charges = 0
        refunded = 0
        
        for charge in charges.auto_paging_iter():
            if charge.status == 'succeeded':
                total_revenue += charge.amount
                successful_charges += 1
            if charge.refunded:
                refunded += charge.amount_refunded
        
        # Get balance
        balance = stripe.Balance.retrieve()
        available_balance = sum(b.amount for b in balance.available) / 100
        
        return {
            'period': period,
            'total_revenue': total_revenue / 100,
            'successful_charges': successful_charges,
            'refunded': refunded / 100,
            'net_revenue': (total_revenue - refunded) / 100,
            'available_balance': available_balance,
            'currency': 'USD'
        }
        
    except Exception as e:
        logger.error(f"Stripe fetch revenue error: {e}")
        return {'error': str(e)}


def fetch_customers(api_key: str, filters: dict = None) -> dict:
    """
    Fetch customers from Stripe.
    
    Args:
        api_key: Stripe secret key
        filters: Optional filters (limit)
        
    Returns:
        dict with 'data' list and 'count'
    """
    filters = filters or {}
    
    try:
        stripe.api_key = api_key
        
        customers = stripe.Customer.list(
            limit=min(filters.get('limit', 50), 100)
        )
        
        data = []
        for cust in customers.data:
            data.append({
                'id': cust.id,
                'email': cust.email,
                'name': cust.name,
                'created': datetime.fromtimestamp(cust.created).isoformat(),
                'balance': cust.balance / 100 if cust.balance else 0,
            })
        
        return {
            'data': data,
            'count': len(data),
            'has_more': customers.has_more
        }
        
    except Exception as e:
        logger.error(f"Stripe fetch customers error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_products(api_key: str, filters: dict = None) -> dict:
    """
    Fetch products from Stripe.
    """
    filters = filters or {}
    try:
        stripe.api_key = api_key
        products = stripe.Product.list(limit=min(filters.get('limit', 50), 100))
        data = []
        for p in products.data:
            data.append({
                'id': p.id,
                'name': p.name,
                'active': p.active,
                'description': p.description,
                'created': datetime.fromtimestamp(p.created).isoformat(),
            })
        return {'data': data, 'count': len(data)}
    except Exception as e:
        logger.error(f"Stripe fetch products error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_payouts(api_key: str, filters: dict = None) -> dict:
    """
    Fetch payouts from Stripe.
    """
    filters = filters or {}
    try:
        stripe.api_key = api_key
        payouts = stripe.Payout.list(limit=min(filters.get('limit', 50), 100))
        data = []
        for p in payouts.data:
            data.append({
                'id': p.id,
                'amount': p.amount / 100,
                'currency': p.currency.upper(),
                'status': p.status,
                'arrival_date': datetime.fromtimestamp(p.arrival_date).isoformat(),
            })
        return {'data': data, 'count': len(data)}
    except Exception as e:
        logger.error(f"Stripe fetch payouts error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}
