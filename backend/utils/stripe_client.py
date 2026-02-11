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
        
        # Default limit: 20 for "recent" queries, 100 otherwise
        default_limit = filters.get('limit') if filters.get('limit') else (20 if filters.get('period') == 'week' else 100)
        params = {
            'limit': min(default_limit, 100),
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
        
        product_name = filters.get('product_name') or filters.get('product')
        product_query = product_name.lower() if product_name else None
        
        # If filtering by product, use invoices instead of charges for better product matching
        if product_query:
            logger.info(f"[REVENUE] Filtering by product: {product_name}")
            # Fetch invoices instead - they have better product information
            # Use simpler expand to avoid Stripe's 4-level limit
            invoices = stripe.Invoice.list(
                created={'gte': int(start.timestamp())},
                status='paid',
                limit=100,
                expand=['data.lines']  # Only expand lines, not nested product
            )
            
            for invoice in invoices.auto_paging_iter():
                # Check invoice line items for product name
                matched = False
                for line in invoice.lines.data:
                    # Check line description first (most reliable)
                    try:
                        line_desc = (getattr(line, 'description', None) or '').lower()
                        if product_query in line_desc:
                            matched = True
                            break
                    except Exception as e:
                        logger.debug(f"Error accessing line description: {e}")
                    
                    # Try to get product ID and fetch product separately if needed
                    # But first check if price exists and has product_id
                    try:
                        line_price = getattr(line, 'price', None)
                        if line_price:
                            line_product = getattr(line_price, 'product', None)
                            if line_product:
                                # If product is a string ID, fetch it
                                if isinstance(line_product, str):
                                    try:
                                        product = stripe.Product.retrieve(line_product)
                                        product_name_lower = (getattr(product, 'name', '') or '').lower()
                                        product_desc_lower = (getattr(product, 'description', '') or '').lower()
                                        if product_query in product_name_lower or product_query in product_desc_lower:
                                            matched = True
                                            break
                                    except Exception as e:
                                        logger.debug(f"Could not fetch product {line_product}: {e}")
                                # If product is already an object (from expand)
                                elif hasattr(line_product, 'name'):
                                    product_name_lower = (getattr(line_product, 'name', '') or '').lower()
                                    product_desc_lower = (getattr(line_product, 'description', '') or '').lower()
                                    if product_query in product_name_lower or product_query in product_desc_lower:
                                        matched = True
                                        break
                    except Exception as e:
                        logger.debug(f"Error accessing line price/product: {e}")
                
                if matched:
                    if invoice.status == 'paid':
                        total_revenue += invoice.amount_paid
                        successful_charges += 1
                    if invoice.amount_refunded:
                        refunded += invoice.amount_refunded
        else:
            # No product filter - use charges as before
            for charge in charges.auto_paging_iter():
                if charge.status == 'succeeded':
                    total_revenue += charge.amount
                    successful_charges += 1
                if charge.refunded:
                    refunded += charge.amount_refunded
        
        # Get balance
        balance = stripe.Balance.retrieve()
        available_balance = sum(b.amount for b in balance.available) / 100
        
        # Format return value consistently
        return {
            'period': period,
            'total_revenue': total_revenue / 100,
            'successful_charges': successful_charges,
            'refunded': refunded / 100,
            'net_revenue': (total_revenue - refunded) / 100,
            'available_balance': available_balance,
            'currency': 'USD',
            'product_name': product_name  # Include product filter for reference
        }
        
    except Exception as e:
        logger.error(f"Stripe fetch revenue error: {e}")
        return {'error': str(e)}


def fetch_balance(api_key: str, filters: dict = None) -> dict:
    """
    Fetch Stripe account balance information.
    
    Args:
        api_key: Stripe secret key
        filters: Optional filters (not currently used)
        
    Returns:
        dict with balance data including available, pending, and currency breakdown
    """
    try:
        stripe.api_key = api_key
        
        logger.info("[BALANCE] Fetching Stripe account balance")
        
        # Get balance
        balance = stripe.Balance.retrieve()
        
        # Calculate totals
        available_total = sum(b.amount for b in balance.available) / 100 if balance.available else 0
        pending_total = sum(b.amount for b in balance.pending) / 100 if balance.pending else 0
        
        # Get currency breakdown
        available_by_currency = {}
        if balance.available:
            for b in balance.available:
                currency = b.currency.upper()
                amount = b.amount / 100
                available_by_currency[currency] = available_by_currency.get(currency, 0) + amount
        
        pending_by_currency = {}
        if balance.pending:
            for b in balance.pending:
                currency = b.currency.upper()
                amount = b.amount / 100
                pending_by_currency[currency] = pending_by_currency.get(currency, 0) + amount
        
        # Format currency breakdown as readable string for display
        available_currency_str = ', '.join([f"{curr}: ${amt:,.2f}" for curr, amt in available_by_currency.items()]) if available_by_currency else "N/A"
        pending_currency_str = ', '.join([f"{curr}: ${amt:,.2f}" for curr, amt in pending_by_currency.items()]) if pending_by_currency else "N/A"
        
        result = {
            'available': available_total,
            'pending': pending_total,
            'total': available_total + pending_total,
            'available_by_currency': available_currency_str,  # Convert dict to readable string
            'pending_by_currency': pending_currency_str,  # Convert dict to readable string
            'currency': list(available_by_currency.keys())[0] if available_by_currency else 'USD'
        }
        
        logger.info(f"[BALANCE] Successfully fetched balance: available=${available_total}, pending=${pending_total}")
        return result
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error fetching balance: {e}")
        return {'error': f"Stripe API error: {str(e)}", 'success': False}
    except Exception as e:
        logger.error(f"Stripe fetch balance error: {e}")
        import traceback
        logger.error(f"Balance error traceback: {traceback.format_exc()}")
        return {'error': str(e), 'success': False}


def fetch_customers(api_key: str, filters: dict = None) -> dict:
    """
    Fetch customers from Stripe.
    
    Args:
        api_key: Stripe secret key
        filters: Optional filters (limit, name, email)
        
    Returns:
        dict with 'data' list and 'count'
    """
    filters = filters or {}
    
    logger.info(f"[CUSTOMERS] fetch_customers called with filters: {filters}")
    
    try:
        stripe.api_key = api_key
        
        # Check if we need to filter by name or email
        name_filter = filters.get('name') or filters.get('customer_name')
        email_filter = filters.get('email')
        
        logger.info(f"[CUSTOMERS] Extracted filters - name_filter: '{name_filter}', email_filter: '{email_filter}'")
        
        # Normalize name filter - remove extra whitespace
        if name_filter:
            name_filter = ' '.join(name_filter.split())
            logger.info(f"[CUSTOMERS] Name filter (normalized): '{name_filter}'")
        
        # If name filter is provided, use search API
        customers = None
        used_search_api = False
        
        # Ensure customers is initialized
        if name_filter:
            logger.info(f"[CUSTOMERS] Searching for customer with name: {name_filter}")
            try:
                # Try search API with exact match query
                # Use exact match with quotes for precise matching
                search_query = f"name:'{name_filter}'"
                logger.info(f"[CUSTOMERS] Trying Search API with query: {search_query}")
                try:
                    search_results = stripe.Customer.search(
                        query=search_query,
                        limit=100
                    )
                    if search_results and search_results.data:
                        logger.info(f"[CUSTOMERS] Search API returned {len(search_results.data)} results")
                        # Even with search API, we should verify exact match since search might be fuzzy
                        # Filter results to ensure exact match
                        exact_matches = []
                        filter_name_lower = name_filter.strip().lower()
                        for cust in search_results.data:
                            cust_name_lower = (cust.name or '').strip().lower()
                            logger.debug(f"[CUSTOMERS] Search result: '{cust.name}' -> '{cust_name_lower}' vs filter '{filter_name_lower}'")
                            if cust_name_lower == filter_name_lower:
                                exact_matches.append(cust)
                                logger.info(f"[CUSTOMERS] ✓ Exact match in search results: {cust.name}")
                        
                        if exact_matches:
                            # Create a mock object with exact matches
                            class ExactMatchResults:
                                def __init__(self, data_list):
                                    self.data = data_list
                                    self.has_more = False
                            customers = ExactMatchResults(exact_matches)
                            used_search_api = True
                            logger.info(f"[CUSTOMERS] ✓ Search API found {len(exact_matches)} exact matches for '{name_filter}'")
                        else:
                            logger.info(f"[CUSTOMERS] Search API found {len(search_results.data)} results but no exact match for '{name_filter}'")
                            logger.info(f"[CUSTOMERS] Sample names from search: {[c.name for c in search_results.data[:5]]}")
                            # Will fall back to list API for manual filtering
                    else:
                        logger.info(f"[CUSTOMERS] Search API returned no results")
                except Exception as e1:
                    logger.warning(f"[CUSTOMERS] Exact search failed: {e1}")
                    import traceback
                    logger.debug(f"[CUSTOMERS] Search traceback: {traceback.format_exc()}")
                
                # If search API didn't find anything, fallback to list API
                if not customers:
                    # Fallback to list API - fetch more customers for manual filtering
                    logger.info(f"[CUSTOMERS] Search API found no exact results, using list API with manual filtering")
                    try:
                        customers = stripe.Customer.list(limit=100)  # Get more customers for filtering
                        used_search_api = False
                        if customers and hasattr(customers, 'data'):
                            logger.info(f"[CUSTOMERS] Fetched {len(customers.data)} customers for manual filtering")
                            # Log sample names for debugging
                            sample_names = [c.name for c in customers.data[:5] if c.name]
                            logger.info(f"[CUSTOMERS] Sample customer names: {sample_names}")
                        else:
                            logger.warning(f"[CUSTOMERS] Failed to fetch customers from list API")
                    except Exception as e2:
                        logger.error(f"[CUSTOMERS] Failed to fetch customers from list API: {e2}")
                        return {'data': [], 'count': 0, 'error': str(e2)}
            except stripe.error.InvalidRequestError as e:
                # Fallback to list API and filter manually
                logger.info(f"[CUSTOMERS] Search API failed ({e}), using list API with manual filtering")
                try:
                    customers = stripe.Customer.list(limit=100)
                    used_search_api = False
                except Exception as e2:
                    logger.error(f"[CUSTOMERS] Failed to fetch customers: {e2}")
                    return {'data': [], 'count': 0, 'error': str(e2)}
        elif email_filter:
            # Filter by email
            try:
                customers = stripe.Customer.list(email=email_filter, limit=100)
            except Exception as e:
                logger.error(f"[CUSTOMERS] Failed to fetch customers by email: {e}")
                return {'data': [], 'count': 0, 'error': str(e)}
        else:
            # No filter, get all customers
            limit = filters.get('limit', 50)
            try:
                customers = stripe.Customer.list(
                    limit=min(limit, 100)
                )
                if customers and hasattr(customers, 'data'):
                    logger.info(f"[CUSTOMERS] Fetched {len(customers.data)} customers (no filter)")
            except Exception as e:
                logger.error(f"[CUSTOMERS] Failed to fetch customers: {e}")
                return {'data': [], 'count': 0, 'error': str(e)}
        
        # Ensure customers object exists and has data attribute
        if not customers:
            logger.error("[CUSTOMERS] customers object is None")
            return {'data': [], 'count': 0, 'error': 'Failed to fetch customers'}
        
        if not hasattr(customers, 'data'):
            logger.error(f"[CUSTOMERS] customers object has no 'data' attribute. Type: {type(customers)}")
            return {'data': [], 'count': 0, 'error': 'Invalid customers object returned'}
        
        data = []
        for cust in customers.data:
            # Apply name filter if using list API (search API already filtered)
            if name_filter and not used_search_api:
                try:
                    # Manual name filtering - require exact match or all words match
                    cust_name_raw = cust.name or ''
                    cust_name = cust_name_raw.strip().lower()
                    filter_name = name_filter.strip().lower()
                    
                    logger.info(f"[CUSTOMERS] Comparing: filter='{filter_name}' vs customer='{cust_name}' (raw: '{cust_name_raw}')")
                    
                    # Normalize whitespace - replace multiple spaces with single space
                    filter_name_normalized = ' '.join(filter_name.split())
                    cust_name_normalized = ' '.join(cust_name.split())
                    
                    # Exact match (case-insensitive, normalized)
                    if filter_name_normalized == cust_name_normalized:
                        logger.info(f"[CUSTOMERS] ✓ Exact match found: {cust.name}")
                    # Require ALL words from filter to match words in customer name (strict matching)
                    else:
                        # Word-by-word matching
                        filter_words = [w.strip() for w in filter_name_normalized.split() if len(w.strip()) > 0]
                        cust_words = [w.strip() for w in cust_name_normalized.split() if len(w.strip()) > 0]
                        
                        logger.info(f"[CUSTOMERS] Filter words: {filter_words}, Customer words: {cust_words}")
                        
                        if filter_words and cust_words:
                            # Check if ALL filter words appear in customer name (exact word match)
                            # This ensures "Rohan robert" matches "Rohan robert" but not just "Rohan"
                            all_words_match = all(
                                any(fw == cw for cw in cust_words) 
                                for fw in filter_words
                            )
                            
                            if all_words_match:
                                logger.info(f"[CUSTOMERS] ✓ All words match found: {cust.name}")
                            else:
                                logger.info(f"[CUSTOMERS] ✗ Not all words match, skipping: {cust.name}")
                                logger.info(f"[CUSTOMERS]   Details: filter_words={filter_words}, cust_words={cust_words}")
                                continue
                        else:
                            # If no words to match or customer has no name, skip
                            logger.info(f"[CUSTOMERS] ✗ Cannot match (no words), skipping: {cust.name}")
                            continue
                except Exception as e:
                    logger.warning(f"[CUSTOMERS] Error filtering customer {cust.id}: {e}")
                    import traceback
                    logger.warning(f"[CUSTOMERS] Traceback: {traceback.format_exc()}")
                    continue
            
            # Log customer being processed
            logger.debug(f"[CUSTOMERS] Processing customer: {cust.name} ({cust.email})")
            
            # Customer balance represents account balance (credits/debits), not total spend
            # Most customers will have balance=0 unless you've adjusted their balance
            raw_balance = getattr(cust, 'balance', None)
            balance_value = raw_balance / 100 if raw_balance is not None else 0
            
            # Calculate total spend from invoices (lifetime value)
            # This is more useful than account balance for most use cases
            total_spend = 0
            try:
                # Fetch paid invoices for this customer to calculate total spend
                invoices = stripe.Invoice.list(customer=cust.id, status='paid', limit=100)
                total_spend = sum(inv.amount_paid for inv in invoices.data) / 100
                logger.debug(f"[CUSTOMERS] Customer {cust.id}: balance={balance_value}, total_spend={total_spend}")
            except Exception as e:
                logger.debug(f"[CUSTOMERS] Could not calculate total spend for {cust.id}: {e}")
            
            data.append({
                'id': cust.id,
                'email': cust.email,
                'name': cust.name,
                'created': datetime.fromtimestamp(cust.created).isoformat(),
                'balance': balance_value,  # Account balance (credits/debits)
                'total_spend': total_spend,  # Total amount spent (lifetime value)
                'currency': getattr(cust, 'currency', 'USD') or 'USD'
            })
        
        logger.info(f"[CUSTOMERS] Returning {len(data)} customers after filtering")
        if name_filter and len(data) == 0:
            logger.warning(f"[CUSTOMERS] ⚠ No customers found matching name filter: '{name_filter}'")
            # Log all customer names for debugging
            try:
                all_customers = stripe.Customer.list(limit=100)
                sample_names = [c.name for c in all_customers.data if c.name]
                logger.info(f"[CUSTOMERS] Available customer names in Stripe (first 20): {sample_names[:20]}")
                logger.info(f"[CUSTOMERS] Looking for exact match of: '{name_filter}' (lowercase: '{name_filter.lower()}')")
                
                # Check if there's a close match
                filter_lower = name_filter.lower()
                close_matches = [name for name in sample_names if name and filter_lower in name.lower() or name.lower() in filter_lower]
                if close_matches:
                    logger.info(f"[CUSTOMERS] Found close matches: {close_matches}")
            except Exception as e:
                logger.warning(f"[CUSTOMERS] Could not fetch sample names: {e}")
        
        return {
            'data': data,
            'count': len(data),
            'has_more': customers.has_more if hasattr(customers, 'has_more') else False
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


def fetch_data_by_email(api_key: str, email: str) -> dict:
    """
    Fetch customer details and invoices by email address.
    Used for cross-platform integration (Salesforce -> Stripe).
    """
    try:
        stripe.api_key = api_key
        
        logger.info(f"[STRIPE] Searching for customer with email: {email}")
        
        # 1. Search for customer by email using Search API (more reliable for exact matches)
        # First try Search API for exact email match
        try:
            search_results = stripe.Customer.search(
                query=f"email:'{email}'",
                limit=1
            )
            
            if search_results.data:
                customer = search_results.data[0]
                logger.info(f"[STRIPE] Found customer via Search API: {customer.id} ({customer.email})")
            else:
                # Fallback to list API with email filter
                logger.info(f"[STRIPE] Search API found no results, trying list API...")
                customers = stripe.Customer.list(email=email, limit=10)
                
                # Filter for exact email match (case-insensitive)
                email_lower = email.lower()
                customer = None
                for c in customers.data:
                    if c.email and c.email.lower() == email_lower:
                        customer = c
                        logger.info(f"[STRIPE] Found customer via list API: {customer.id} ({customer.email})")
                        break
                
                if not customer:
                    # Try partial match as last resort
                    logger.info(f"[STRIPE] No exact match, trying partial match...")
                    for c in customers.data:
                        if c.email and email_lower in c.email.lower():
                            customer = c
                            logger.info(f"[STRIPE] Found customer via partial match: {customer.id} ({customer.email})")
                            break
        except stripe.error.InvalidRequestError as e:
            # Search API might not be available, fallback to list
            logger.warning(f"[STRIPE] Search API failed: {e}, falling back to list API")
            customers = stripe.Customer.list(limit=100)  # Get more results to search through
            email_lower = email.lower()
            customer = None
            for c in customers.data:
                if c.email and c.email.lower() == email_lower:
                    customer = c
                    logger.info(f"[STRIPE] Found customer via list API (fallback): {customer.id} ({customer.email})")
                    break
        
        if not customer:
            logger.warning(f"[STRIPE] No customer found with email: {email}")
            return {
                'found': False, 
                'message': f"No Stripe customer found with email: {email}"
            }
        
        # 2. Fetch invoices for this customer
        invoices = stripe.Invoice.list(customer=customer.id, limit=20)
        
        invoice_data = []
        for inv in invoices.data:
            invoice_data.append({
                'id': inv.id,
                'number': inv.number,
                'amount': inv.amount_due / 100,
                'currency': inv.currency.upper(),
                'status': inv.status,
                'date': datetime.fromtimestamp(inv.created).isoformat(),
            })
            
        # 3. Calculate lifetime value (LTV) roughly
        total_spend = sum(inv['amount'] for inv in invoice_data if inv['status'] == 'paid')
        
        return {
            'found': True,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'balance': customer.balance / 100 if customer.balance else 0,
                'created': datetime.fromtimestamp(customer.created).isoformat()
            },
            'invoices': invoice_data,
            'summary': {
                'total_invoices': len(invoice_data),
                'total_spend': total_spend,
                'currency': invoice_data[0]['currency'] if invoice_data else 'USD'
            }
        }
        
    except Exception as e:
        logger.error(f"Stripe fetch by email error: {e}")
        return {'found': False, 'error': str(e)}


def fetch_revenue(api_key: str, filters: dict = None) -> dict:
    """
    Fetch revenue data, optionally filtered by product name.
    
    Args:
        api_key: Stripe secret key
        filters: Dict containing 'product_name', 'period', etc.
    """
    filters = filters or {}
    product_name = filters.get('product_name')
    
    try:
        stripe.api_key = api_key
        
        # Base params - fetch paid invoices
        # Use simpler expand to avoid Stripe's 4-level limit
        params = {
            'limit': 100,
            'status': 'paid',
            'expand': ['data.lines']  # Only expand lines, fetch products separately if needed
        }
        
        # Apply date filters if present
        period = filters.get('period', 'month')  # Default to month if not specified
        now = datetime.now()
        start_date = None
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        
        if start_date:
            params['created'] = {'gte': int(start_date.timestamp())}

        logger.info(f"[REVENUE] Fetching revenue with filters: period={period}, product_name={product_name}")
        invoices = stripe.Invoice.list(**params)
        
        total_revenue_cents = 0.0
        relevant_invoices = []
        currency = 'USD'
        successful_charges = 0
        
        for inv in invoices.data:
            match_amount = 0.0
            is_match = False
            
            if product_name:
                product_query = product_name.lower()
                # Filter by product name in line items
                for line in inv.lines.data:
                    matched_line = False
                    
                    # Check line description first (most reliable and always available)
                    try:
                        desc = (getattr(line, 'description', None) or '').lower()
                        if product_query in desc:
                            line_amount = getattr(line, 'amount', 0) or 0
                            match_amount += line_amount
                            matched_line = True
                            is_match = True
                            continue  # Found match, skip product check
                    except Exception as e:
                        logger.debug(f"Error accessing line description: {e}")
                    
                    # Try to check product if description doesn't match
                    # Since we're not expanding products, product will be a string ID
                    if not matched_line:
                        try:
                            # Safely check for price attribute - handle AttributeError
                            line_price = None
                            try:
                                # Use getattr with default None to safely access price
                                line_price = getattr(line, 'price', None)
                                # Double-check it's not None and is accessible
                                if line_price is not None:
                                    # Try to access it to ensure it's not a lazy-loaded property that fails
                                    _ = str(line_price)  # Force evaluation if it's a lazy property
                            except (AttributeError, TypeError, ValueError) as e:
                                logger.debug(f"Error accessing line.price: {e}")
                                line_price = None
                            
                            if line_price is not None:
                                line_product = None
                                try:
                                    # Use getattr with default None
                                    line_product = getattr(line_price, 'product', None)
                                    if line_product is not None:
                                        _ = str(line_product)  # Force evaluation
                                except (AttributeError, TypeError, ValueError) as e:
                                    logger.debug(f"Error accessing line_price.product: {e}")
                                    line_product = None
                                
                                if line_product is not None:
                                    # Product is a string ID, not an object (since we're not expanding)
                                    if isinstance(line_product, str):
                                        try:
                                            product = stripe.Product.retrieve(line_product)
                                            product_name_lower = (getattr(product, 'name', '') or '').lower()
                                            product_desc_lower = (getattr(product, 'description', '') or '').lower()
                                            if product_query in product_name_lower or product_query in product_desc_lower:
                                                line_amount = getattr(line, 'amount', 0) or 0
                                                match_amount += line_amount
                                                matched_line = True
                                                is_match = True
                                        except Exception as e:
                                            logger.debug(f"Could not fetch product {line_product}: {e}")
                                    # If product is already an object (shouldn't happen, but just in case)
                                    elif hasattr(line_product, 'name'):
                                        product_name_lower = (getattr(line_product, 'name', '') or '').lower()
                                        product_desc_lower = (getattr(line_product, 'description', '') or '').lower()
                                        if product_query in product_name_lower or product_query in product_desc_lower:
                                            line_amount = getattr(line, 'amount', 0) or 0
                                            match_amount += line_amount
                                            matched_line = True
                                            is_match = True
                        except Exception as e:
                            logger.warning(f"Error processing line item for product filter: {e}")
                            import traceback
                            logger.debug(f"Traceback: {traceback.format_exc()}")
                            # Continue to next line if there's an error
            else:
                # No filter, include full amount
                match_amount = inv.amount_paid
                is_match = True
            
            if is_match and match_amount > 0:
                total_revenue_cents += match_amount
                currency = inv.currency.upper()
                successful_charges += 1
                relevant_invoices.append({
                    'id': inv.id,
                    'number': inv.number,
                    'amount': match_amount / 100, # Only the relevant amount
                    'date': datetime.fromtimestamp(inv.created).isoformat(),
                    'status': inv.status,
                    'description': f"Contains: {product_name}" if product_name else "Invoice"
                })
        
        # Sort by date desc
        relevant_invoices.sort(key=lambda x: x['date'], reverse=True)
        
        total_revenue = total_revenue_cents / 100
        
        # Get balance
        balance = stripe.Balance.retrieve()
        available_balance = sum(b.amount for b in balance.available) / 100
        
        summary_text = f"Total Revenue: ${total_revenue:,.2f}"
        if product_name:
            summary_text = f"Total Revenue from '{product_name}': ${total_revenue:,.2f} ({successful_charges} invoice(s))"
        
        logger.info(f"[REVENUE] Calculated revenue: ${total_revenue:,.2f}, invoices: {successful_charges}, product: {product_name}")
            
        return {
            'success': True,
            'data': relevant_invoices,
            'count': len(relevant_invoices),
            'total_revenue': total_revenue,
            'currency': currency,
            'summary': summary_text
        }

    except Exception as e:
        logger.error(f"Stripe fetch_revenue error: {e}")
        return {'success': False, 'error': str(e)}
