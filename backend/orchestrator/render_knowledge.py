"""
Render-only knowledge: answers from seed_platform_knowledge content.
Used when RENDER=1 to answer knowledge questions without RAG/embeddings.
"""
from typing import Optional

# List of {keywords, answer}. First match wins.
RENDER_KNOWLEDGE = [
    {
        "keywords": ["clone", "cloning", "clone a repo", "clone repository", "how do i clone", "how to clone", "push code", "push to github", "how to push", "push in github", "push code in github"],
        "answer": """**How to Clone a Repository (Git/GitHub)**

1. **Basic command:** `git clone <repository-url>`

2. **Clone via HTTPS:**
   ```bash
   git clone https://github.com/username/repository-name.git
   ```
   Most common; requires GitHub username and password/token.

3. **Clone via SSH:**
   ```bash
   git clone git@github.com:username/repository-name.git
   ```
   Requires SSH key setup; no password needed.

4. **Clone into a specific folder:**
   ```bash
   git clone https://github.com/username/repo.git my-folder-name
   ```

5. **Clone a specific branch:**
   ```bash
   git clone -b branch-name https://github.com/username/repo.git
   ```

**Push code to GitHub:** After cloning, make changes, then:
```bash
git add .
git commit -m "Your message"
git push origin main
```
Get the repo URL from GitHub (click "Code"). Use HTTPS or SSH; ensure you're logged in (token or SSH key)."""
    },
    {
        "keywords": ["retry", "payment", "stripe", "failed payment", "declined"],
        "answer": """**STRIPE: When to Retry Failed Payments**

1. **Card Declined (insufficient_funds)**: Retry after 3-7 days.
2. **Card Expired**: Retry after customer updates payment method.
3. **Network Error**: Retry within 24 hours.
4. **Fraud Review**: Wait for Stripe's review (1-2 days).
5. **Generic Decline**: Retry once after 24 hours, then contact customer.

Best Practice: Use Stripe's automatic retry with exponential backoff (e.g. 1 day, 3 days, 7 days)."""
    },
    {
        "keywords": ["refund", "refunds", "stripe refund"],
        "answer": """**STRIPE: How to Handle Refunds**

1. **Full Refund**: Refund entire charge (Dashboard or API).
2. **Partial Refund**: Specify amount less than original charge.
3. **Timing**: 5-10 business days to appear on customer's card.
4. **Fees**: Stripe fees not refunded unless full refund within 60 days.
5. **Disputes**: Respond within 7 days with evidence.

Best Practice: Issue refunds promptly; document reason for accounting."""
    },
    {
        "keywords": ["subscription", "subscriptions", "stripe subscription", "cancel subscription"],
        "answer": """**STRIPE: Managing Subscriptions**

1. **Failed Payments**: Stripe automatically retries.
2. **Cancellations**: Allow cancel anytime; offer retention discounts.
3. **Upgrades/Downgrades**: Prorate when changing plans mid-cycle.
4. **Trial Periods**: Set clear trial end dates and send reminders.
5. **Dunning**: Configure email notifications for failed payments.

Best Practice: Monitor churn rate, MRR, and failed payment rate."""
    },
    {
        "keywords": ["qualify", "lead", "salesforce", "bant", "mql", "sql"],
        "answer": """**SALESFORCE: How to Qualify a Lead**

Use BANT: **B**udget, **A**uthority, **N**eed, **T**imeline.

- Score 0-40: MQL – nurture further
- Score 41-70: SQL – assign to sales rep
- Score 71+: Hot Lead – prioritize follow-up

Best Practice: Convert to Opportunity when all BANT criteria are met."""
    },
    {
        "keywords": ["convert lead", "lead to opportunity", "salesforce convert"],
        "answer": """**SALESFORCE: When to Convert Lead to Opportunity**

Convert when: BANT complete, decision process shared, budget confirmed, timeline set, stakeholders identified.

Process: Create Account → Contact → Opportunity; set stage (e.g. Qualification) and Close Date.

Best Practice: Don't convert too early; ensure lead is truly qualified."""
    },
    {
        "keywords": ["pipeline", "salesforce pipeline", "opportunity stage"],
        "answer": """**SALESFORCE: Managing Sales Pipeline**

1. Define stage criteria; update opportunity stage weekly.
2. Use weighted pipeline value for forecasting.
3. Log calls, emails, meetings as activities.
4. Set reminders for next steps.

Stages: Qualification → Needs Analysis → Proposal → Negotiation → Closed Won/Lost.

Best Practice: Keep pipeline moving; stale opportunities need engagement."""
    },
    {
        "keywords": ["pull request", "pr", "merge", "github pr", "code review"],
        "answer": """**GITHUB: Pull Requests**

**Creating good PRs:** Clear title, description (what/why/how to test), small scope, link issues (#123), self-review first.

**When to merge:** Approvals, CI passing, no conflicts, changes addressed. Strategies: Merge (full history), Squash (one commit), Rebase (linear history).

Best Practice: Keep PRs under ~400 lines when possible."""
    },
    {
        "keywords": ["commit", "commit message", "git commit", "github commit"],
        "answer": """**GITHUB: Writing Good Commit Messages**

- Use imperative mood ("Add feature" not "Added").
- Subject under 50 chars; body explains what and why.
- Reference issues: "Fixes #123".
- One logical change per commit.

Best Practice: Write as if explaining to future you."""
    },
    {
        "keywords": ["deal", "zoho", "deals", "deal stage", "crm"],
        "answer": """**ZOHO: Managing Deals**

- Move deals by customer actions, not time. Set probability and next steps.
- Log calls, emails, meetings. Identify decision makers.
- Stages: Qualification → Needs Analysis → Proposal → Negotiation → Closed.

**When to move stage:** Only when criteria for current stage are met (e.g. budget confirmed before Proposal)."""
    },
    {
        "keywords": ["trello", "board", "card", "list", "kanban", "organizing cards"],
        "answer": """**TRELLO: Boards and Cards**

**Board structure:** To Do → In Progress → Review → Done. Use WIP limits; archive regularly; use templates.

**Card organization:** Labels, due dates, checklists, attachments, comments. Keep title clear; description for context; one deliverable per card.

Best Practice: 3-5 lists to start; keep cards focused."""
    },
]


def get_render_answer(query: str) -> Optional[str]:
    """Return the first matching knowledge answer for the query, or None."""
    q = query.lower().strip()
    for entry in RENDER_KNOWLEDGE:
        if any(kw in q for kw in entry["keywords"]):
            return entry["answer"]
    return None
