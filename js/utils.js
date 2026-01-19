/**
 * Utility Functions
 */

const Utils = {
  /**
   * Mask an API key for display (show last 4 characters)
   */
  maskApiKey(key) {
    if (!key || key.length < 8) return '••••••••';
    return '••••••••' + key.slice(-4);
  },

  /**
   * Detect which platform a query is targeting based on keywords
   */
  detectPlatform(query) {
    const lowerQuery = query.toLowerCase();
    
    const stripeKeywords = [
      'invoice', 'payment', 'subscription', 'revenue', 'charge',
      'customer', 'refund', 'payout', 'balance', 'transaction',
      'paid', 'unpaid', 'overdue', 'billing', 'stripe', 'money',
      'amount', 'price', 'mrr', 'arr', 'churn'
    ];
    
    const zendeskKeywords = [
      'ticket', 'support', 'help', 'issue', 'request', 'agent',
      'resolution', 'response', 'open', 'closed', 'pending',
      'escalated', 'zendesk', 'satisfaction', 'csat', 'sla'
    ];
    
    const stripeScore = stripeKeywords.filter(k => lowerQuery.includes(k)).length;
    const zendeskScore = zendeskKeywords.filter(k => lowerQuery.includes(k)).length;
    
    if (stripeScore > zendeskScore) return 'stripe';
    if (zendeskScore > stripeScore) return 'zendesk';
    return null; // Unable to detect
  },

  /**
   * Format currency
   */
  formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  },

  /**
   * Format date
   */
  formatDate(dateStr) {
    const date = new Date(dateStr);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    }).format(date);
  },

  /**
   * Format relative time
   */
  formatRelativeTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return Utils.formatDate(dateStr);
  },

  /**
   * Generate a unique ID
   */
  generateId() {
    return 'id_' + Math.random().toString(36).substr(2, 9);
  },

  /**
   * Debounce function
   */
  debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn(...args), delay);
    };
  },

  /**
   * DOM helper: Query selector
   */
  $(selector) {
    return document.querySelector(selector);
  },

  /**
   * DOM helper: Query all
   */
  $$(selector) {
    return document.querySelectorAll(selector);
  },

  /**
   * Show element
   */
  show(element) {
    if (typeof element === 'string') element = Utils.$(element);
    if (element) element.classList.remove('hidden');
  },

  /**
   * Hide element
   */
  hide(element) {
    if (typeof element === 'string') element = Utils.$(element);
    if (element) element.classList.add('hidden');
  },

  /**
   * Toggle element visibility
   */
  toggle(element, show) {
    if (typeof element === 'string') element = Utils.$(element);
    if (element) element.classList.toggle('hidden', !show);
  },

  /**
   * Add class
   */
  addClass(element, className) {
    if (typeof element === 'string') element = Utils.$(element);
    if (element) element.classList.add(className);
  },

  /**
   * Remove class
   */
  removeClass(element, className) {
    if (typeof element === 'string') element = Utils.$(element);
    if (element) element.classList.remove(className);
  },

  /**
   * Sleep/delay promise
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },

  /**
   * Escape HTML to prevent XSS
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  /**
   * Create element with attributes
   */
  createElement(tag, attrs = {}, children = []) {
    const el = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (key === 'className') el.className = value;
      else if (key === 'innerHTML') el.innerHTML = value;
      else if (key === 'textContent') el.textContent = value;
      else if (key.startsWith('data')) el.setAttribute(key.replace(/([A-Z])/g, '-$1').toLowerCase(), value);
      else el.setAttribute(key, value);
    });
    children.forEach(child => {
      if (typeof child === 'string') el.appendChild(document.createTextNode(child));
      else el.appendChild(child);
    });
    return el;
  }
};

// Make Utils globally available
window.Utils = Utils;
