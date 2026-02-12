# Query Autocomplete Examples

This document provides examples of how the query autocomplete feature works.

## How It Works

The autocomplete feature suggests queries as you type (after 2+ characters). Suggestions come from:
1. **Saved Queries** 💾 - Your saved favorite queries
2. **Query History** 🕒 - Your recent successful queries
3. **Common Patterns** 💡 - Predefined query templates based on keywords

## Usage

1. Start typing in the query input field
2. After 2+ characters, suggestions appear above the input
3. Use **Arrow Up/Down** to navigate, **Enter** to select, or **click** to choose
4. Press **Escape** to close the dropdown

---

## Example Scenarios

### Example 1: Typing "invoice"

**Input:** `invoice`

**Possible Suggestions:**
- 💾 **Unpaid invoices** (if you have this saved)
- 🕒 **Show unpaid invoices** (from your query history)
- 💡 **Unpaid invoices** → `Show unpaid invoices` (Stripe pattern)
- 💡 **Invoices this month** → `List all invoices this month` (Stripe pattern)
- 💡 **Recent payments** → `Show recent payments` (Stripe pattern)

**Result:** Select any suggestion to fill the input field with that query.

---

### Example 2: Typing "revenue"

**Input:** `revenue`

**Possible Suggestions:**
- 💾 **Monthly revenue** (if saved)
- 🕒 **Revenue this month** (from history)
- 💡 **Monthly revenue** → `Revenue this month` (Stripe pattern)
- 💡 **Weekly revenue** → `Revenue this week` (Stripe pattern)
- 💡 **Total revenue** → `Total revenue` (Stripe pattern)

---

### Example 3: Typing "pull"

**Input:** `pull`

**Possible Suggestions:**
- 💡 **Open PRs** → `Show open pull requests` (GitHub pattern)
- 💡 **Recent PRs** → `List recent pull requests` (GitHub pattern)
- 🕒 **Show open pull requests** (from history)

---

### Example 4: Typing "deal"

**Input:** `deal`

**Possible Suggestions:**
- 💡 **Deals this week** → `Show deals closing this week` (Zoho pattern)
- 💡 **All deals** → `List all deals` (Zoho pattern)
- 💡 **Recent deals** → `Show recent deals` (Zoho pattern)
- 💾 **Weekly deals report** (if saved)

---

### Example 5: Typing "how"

**Input:** `how`

**Possible Suggestions:**
- 💡 **How to clone repo** → `How do I clone a repository?` (GitHub pattern)
- 💡 **How to handle refunds** → `How do I handle refunds?` (Stripe pattern)
- 💡 **How to set up webhooks** → `How do I set up webhooks?` (Stripe pattern)
- 🕒 **How do I clone a repository?** (from history)

---

### Example 6: Typing "customer"

**Input:** `customer`

**Possible Suggestions:**
- 💡 **All customers** → `List all customers` (Stripe pattern)
- 💡 **Recent customers** → `Show recent customers` (Stripe pattern)
- 💡 **Customer growth** → `Customer growth this month` (Stripe pattern)
- 💾 **Top customers** (if saved)

---

### Example 7: Typing "clone"

**Input:** `clone`

**Possible Suggestions:**
- 💡 **How to clone repo** → `How do I clone a repository?` (GitHub pattern)
- 🕒 **How do I clone a repository?** (from history - RAG answer)

---

### Example 8: Typing "card"

**Input:** `card`

**Possible Suggestions:**
- 💡 **To Do cards** → `Show cards in To Do` (Trello pattern)
- 💡 **All cards** → `List all cards` (Trello pattern)
- 💾 **My cards** (if saved)

---

### Example 9: Typing "subscription"

**Input:** `subscription`

**Possible Suggestions:**
- 💡 **Active subscriptions** → `List active subscriptions` (Stripe pattern)
- 💡 **Subscription revenue** → `Show subscription revenue` (Stripe pattern)
- 🕒 **List active subscriptions** (from history)

---

### Example 10: Typing "issue"

**Input:** `issue`

**Possible Suggestions:**
- 💡 **Open issues** → `Show open issues` (GitHub pattern)
- 💡 **Recent issues** → `List recent issues` (GitHub pattern)
- 🕒 **Show open issues** (from history)

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Arrow Down** | Navigate to next suggestion |
| **Arrow Up** | Navigate to previous suggestion |
| **Enter** | Select highlighted suggestion |
| **Escape** | Close autocomplete dropdown |
| **Click** | Select suggestion with mouse |

---

## Suggestion Types Explained

### 💾 Saved Queries
These are queries you've explicitly saved using the save button. They appear first in suggestions.

**Example:** If you saved "Revenue this month" as "Monthly Revenue", typing "revenue" will show it.

### 🕒 Query History
These are queries from your recent successful query history. They help you quickly repeat past queries.

**Example:** If you previously asked "Show unpaid invoices", typing "invoice" will suggest it.

### 💡 Common Patterns
These are intelligent suggestions based on keywords in your input. The system recognizes platform-specific patterns.

**Example:** Typing "invoice" suggests Stripe-related invoice queries.

---

## Platform-Specific Patterns

### Stripe Patterns
Triggered by: `invoice`, `payment`, `revenue`, `customer`, `subscription`, `refund`
- Unpaid invoices
- Revenue queries (monthly, weekly, total)
- Customer lists
- Subscription management

### GitHub Patterns
Triggered by: `pull`, `pr`, `issue`, `clone`, `repository`
- Pull request queries
- Issue queries
- Repository cloning help

### Zoho Patterns
Triggered by: `deal`, `opportunity`, `contact`, `lead`
- Deal queries
- Contact management
- Opportunity tracking

### Trello Patterns
Triggered by: `card`, `task`, `todo`, `board`
- Card queries
- Board listings

### Salesforce Patterns
Triggered by: `lead`, `opportunity`, `account`
- Lead management
- Opportunity tracking

---

## Tips for Best Results

1. **Save frequently used queries** - They'll appear first in autocomplete
2. **Use specific keywords** - More specific terms yield better suggestions
3. **Type at least 2 characters** - Autocomplete activates after 2+ characters
4. **Use keyboard navigation** - Faster than mouse for power users
5. **Check platform badges** - See which platform each suggestion targets

---

## Example Workflow

1. User types: `rev`
2. Autocomplete shows:
   - 💾 **Monthly Revenue** (saved query)
   - 🕒 **Revenue this month** (from history)
   - 💡 **Monthly revenue** → `Revenue this month`
3. User presses **Arrow Down** twice, then **Enter**
4. Input field fills with: `Revenue this month`
5. User clicks submit or presses Enter to execute

---

## Testing the Feature

Try these queries to see autocomplete in action:

1. Type `inv` → See invoice-related suggestions
2. Type `rev` → See revenue-related suggestions  
3. Type `how` → See "how to" help queries
4. Type `pull` → See GitHub PR suggestions
5. Type `deal` → See Zoho deal suggestions

The more you use the system, the better suggestions become as your query history grows!
