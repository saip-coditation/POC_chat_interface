"""
Seed Platform-Specific Knowledge Base

Adds knowledge documents for Stripe, Salesforce, GitHub, Zoho, and Trello
to enable RAG functionality for platform-specific questions.
"""

import os
import django
import sys
import logging

# Setup Django environment - use dynamic path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from catalog.services import get_ingestion_service

def seed_platform_knowledge():
    """Seed knowledge base with platform-specific documentation."""
    ingest = get_ingestion_service()
    
    # ===== STRIPE KNOWLEDGE =====
    
    stripe_payment_retry = """
    STRIPE: When to Retry Failed Payments
    
    Retry failed payments in Stripe when:
    
    1. **Card Declined (insufficient_funds)**: Retry after 3-7 days when customer may have funds available.
    2. **Card Expired**: Retry immediately after customer updates payment method.
    3. **Network Error**: Retry within 24 hours as it may be a temporary issue.
    4. **Fraud Review**: Wait for Stripe's review to complete (usually 1-2 days).
    5. **Generic Decline**: Retry once after 24 hours, then contact customer.
    
    Best Practice: Use Stripe's automatic retry logic with exponential backoff. 
    Configure retry schedule: 1 day, 3 days, 7 days, then stop.
    """
    ingest.ingest_document("Stripe Payment Retry Guide", stripe_payment_retry, platform="stripe")
    
    stripe_refunds = """
    STRIPE: How to Handle Refunds
    
    Process refunds in Stripe:
    
    1. **Full Refund**: Use Stripe Dashboard or API to refund entire charge amount.
    2. **Partial Refund**: Specify amount less than original charge.
    3. **Timing**: Refunds typically take 5-10 business days to appear on customer's card.
    4. **Fees**: Stripe fees are not refunded unless you issue a full refund within 60 days.
    5. **Disputes**: If customer disputes, respond within 7 days with evidence.
    
    Best Practice: Issue refunds promptly to maintain customer trust. 
    Document refund reason for accounting purposes.
    """
    ingest.ingest_document("Stripe Refunds Guide", stripe_refunds, platform="stripe")
    
    stripe_subscriptions = """
    STRIPE: Managing Subscriptions
    
    Subscription Management Best Practices:
    
    1. **Failed Payments**: Stripe automatically retries failed subscription payments.
    2. **Cancellations**: Allow customers to cancel anytime, but offer retention discounts.
    3. **Upgrades/Downgrades**: Prorate charges when changing plans mid-cycle.
    4. **Trial Periods**: Set clear trial end dates and send reminders before billing.
    5. **Dunning Management**: Configure email notifications for failed payments.
    
    Best Practice: Monitor subscription health metrics: churn rate, MRR, and failed payment rate.
    """
    ingest.ingest_document("Stripe Subscription Management", stripe_subscriptions, platform="stripe")
    
    # ===== SALESFORCE KNOWLEDGE =====
    
    salesforce_lead_qualification = """
    SALESFORCE: How to Qualify a Lead
    
    Qualify leads in Salesforce using BANT framework:
    
    1. **Budget**: Does the prospect have budget allocated for this solution?
    2. **Authority**: Is the contact the decision maker or influencer?
    3. **Need**: What specific problem are they trying to solve?
    4. **Timeline**: When do they need to implement a solution?
    
    Lead Qualification Score:
    - Score 0-40: Marketing Qualified Lead (MQL) - nurture further
    - Score 41-70: Sales Qualified Lead (SQL) - assign to sales rep
    - Score 71+: Hot Lead - prioritize immediate follow-up
    
    Best Practice: Update lead status and score regularly. Convert to Opportunity when all BANT criteria are met.
    """
    ingest.ingest_document("Salesforce Lead Qualification", salesforce_lead_qualification, platform="salesforce")
    
    salesforce_lead_conversion = """
    SALESFORCE: When to Convert Lead to Opportunity
    
    Convert a lead to opportunity when:
    
    1. **BANT Complete**: Budget, Authority, Need, and Timeline are confirmed.
    2. **Decision Process**: Prospect has shared their evaluation criteria.
    3. **Budget Confirmed**: Specific budget range is discussed.
    4. **Timeline Set**: Implementation date or purchase decision date is known.
    5. **Stakeholders Identified**: All decision makers are known and engaged.
    
    Conversion Process:
    - Create Account (if new company)
    - Create Contact (link to Account)
    - Create Opportunity (link to Account)
    - Set Opportunity Stage: "Qualification" or "Needs Analysis"
    - Set Close Date (based on timeline)
    
    Best Practice: Don't convert too early. Ensure lead is truly qualified to maintain data quality.
    """
    ingest.ingest_document("Salesforce Lead Conversion", salesforce_lead_conversion, platform="salesforce")
    
    salesforce_pipeline = """
    SALESFORCE: Managing Sales Pipeline
    
    Sales Pipeline Best Practices:
    
    1. **Stage Definitions**: Clearly define what qualifies for each stage.
    2. **Regular Updates**: Update opportunity stage weekly or after key activities.
    3. **Forecasting**: Use weighted pipeline value based on probability.
    4. **Activities**: Log all calls, emails, and meetings as activities.
    5. **Follow-ups**: Set reminders for next steps immediately after each interaction.
    
    Pipeline Stages:
    - Qualification: Initial contact, needs assessment
    - Needs Analysis: Understanding requirements
    - Proposal: Solution presented
    - Negotiation: Terms discussed
    - Closed Won/Lost: Final outcome
    
    Best Practice: Keep pipeline moving. Stale opportunities indicate lack of engagement.
    """
    ingest.ingest_document("Salesforce Pipeline Management", salesforce_pipeline, platform="salesforce")
    
    # ===== GITHUB KNOWLEDGE =====
    
    github_pr_best_practices = """
    GITHUB: Creating Good Pull Requests
    
    Best practices for pull requests:
    
    1. **Clear Title**: Use descriptive title explaining what the PR does.
    2. **Description**: Include context, what changed, why, and how to test.
    3. **Small Scope**: Keep PRs focused on single feature or fix.
    4. **Review Checklist**: List what reviewers should check.
    5. **Link Issues**: Reference related issues using #issue-number.
    6. **Self-Review**: Review your own code before requesting reviews.
    
    PR Description Template:
    - What: Brief summary of changes
    - Why: Problem being solved
    - How: Implementation approach
    - Testing: How to verify changes
    - Screenshots: If UI changes
    
    Best Practice: Keep PRs under 400 lines when possible. Large PRs are harder to review.
    """
    ingest.ingest_document("GitHub PR Best Practices", github_pr_best_practices, platform="github")
    
    github_pr_merge = """
    GITHUB: When to Merge a Pull Request
    
    Merge a pull request when:
    
    1. **Approvals**: At least one approval from code owner (or 2 for critical changes).
    2. **CI Passing**: All tests pass, no build errors.
    3. **No Conflicts**: Branch is up to date with base branch.
    4. **Reviewed**: All requested changes addressed or discussed.
    5. **Documentation**: Code comments and docs updated if needed.
    
    Merge Strategies:
    - **Merge**: Preserves full history, creates merge commit
    - **Squash**: Combines all commits into one, cleaner history
    - **Rebase**: Linear history, rewrites commit history
    
    Best Practice: Use squash merge for feature branches, merge for long-lived branches.
    """
    ingest.ingest_document("GitHub PR Merge Guidelines", github_pr_merge, platform="github")
    
    github_commits = """
    GITHUB: Writing Good Commit Messages
    
    Commit message best practices:
    
    1. **Format**: Use imperative mood ("Add feature" not "Added feature").
    2. **Subject Line**: Keep under 50 characters, capitalize first letter.
    3. **Body**: Explain what and why, not how (code shows how).
    4. **Reference**: Link to issues using "Fixes #123" or "Closes #123".
    5. **Atomic Commits**: One logical change per commit.
    
    Commit Message Template:
    ```
    Short summary (50 chars max)
    
    Longer explanation if needed. Explain the problem being solved
    and why this change is necessary. Wrap at 72 characters.
    
    Fixes #123
    ```
    
    Best Practice: Write commits as if explaining to future you. Clear messages save time during debugging.
    """
    ingest.ingest_document("GitHub Commit Messages", github_commits, platform="github")
    
    # ===== ZOHO KNOWLEDGE =====
    
    zoho_deal_management = """
    ZOHO: Managing Deals
    
    Deal management best practices:
    
    1. **Stage Progression**: Move deals through stages based on customer actions, not time.
    2. **Probability**: Set realistic probability percentages for accurate forecasting.
    3. **Next Steps**: Always set next step date and action after each interaction.
    4. **Activities**: Log all calls, emails, and meetings linked to the deal.
    5. **Stakeholders**: Identify all decision makers and their roles.
    
    Deal Stages:
    - Qualification: Initial interest confirmed
    - Needs Analysis: Requirements gathering
    - Proposal: Solution presented
    - Negotiation: Terms discussed
    - Closed Won/Lost: Final outcome
    
    Best Practice: Update deal stage immediately after key milestones. Don't let deals stall.
    """
    ingest.ingest_document("Zoho Deal Management", zoho_deal_management, platform="zoho")
    
    zoho_deal_stages = """
    ZOHO: When to Move Deals to Next Stage
    
    Move deals to next stage when:
    
    1. **Qualification → Needs Analysis**: Budget and authority confirmed.
    2. **Needs Analysis → Proposal**: Requirements fully understood and documented.
    3. **Proposal → Negotiation**: Proposal sent and initial feedback received.
    4. **Negotiation → Closed**: Terms agreed upon and contract ready.
    
    Don't move forward if:
    - Key stakeholders not engaged
    - Budget not confirmed
    - Requirements unclear
    - Timeline uncertain
    
    Best Practice: Use stage gates. Only move forward when all criteria for current stage are met.
    """
    ingest.ingest_document("Zoho Deal Stage Progression", zoho_deal_stages, platform="zoho")
    
    # ===== TRELLO KNOWLEDGE =====
    # (Already has static knowledge base, but adding to RAG for consistency)
    
    trello_card_organization = """
    TRELLO: Organizing Cards
    
    Card organization best practices:
    
    1. **Labels**: Use color-coded labels for categories (bug, feature, urgent).
    2. **Due Dates**: Set realistic deadlines and enable notifications.
    3. **Checklists**: Break large tasks into actionable checklist items.
    4. **Attachments**: Add relevant files, links, and screenshots.
    5. **Comments**: Use comments for discussions, not card description.
    
    Card Structure:
    - Title: Clear, action-oriented (e.g., "Fix login bug" not "Bug")
    - Description: Context, requirements, acceptance criteria
    - Checklist: Subtasks or steps to complete
    - Labels: Category, priority, team
    - Members: Assignees and watchers
    
    Best Practice: Keep cards focused on single deliverable. Split large cards into multiple cards.
    """
    ingest.ingest_document("Trello Card Organization", trello_card_organization, platform="trello")
    
    trello_board_structure = """
    TRELLO: Structuring Boards
    
    Board structure best practices:
    
    1. **List Flow**: To Do → In Progress → Review → Done (or similar workflow).
    2. **WIP Limits**: Limit cards in "In Progress" to focus team.
    3. **Archive Regularly**: Archive completed cards monthly to keep board clean.
    4. **Templates**: Create board templates for recurring project types.
    5. **Power-Ups**: Use automation power-ups for recurring tasks.
    
    List Naming:
    - Use action verbs: "To Do", "In Progress", "Review", "Done"
    - Keep consistent across boards
    - Add context if needed: "Waiting for Client", "Blocked"
    
    Best Practice: Start simple with 3-5 lists. Add more only if workflow requires it.
    """
    ingest.ingest_document("Trello Board Structure", trello_board_structure, platform="trello")
    
    print("\n✅ Platform knowledge base seeded successfully!")
    print("\nAdded knowledge documents for:")
    print("  - Stripe: Payment retry, refunds, subscriptions")
    print("  - Salesforce: Lead qualification, conversion, pipeline")
    print("  - GitHub: PR best practices, merge guidelines, commits")
    print("  - Zoho: Deal management, stage progression")
    print("  - Trello: Card organization, board structure")
    print("\nYou can now test RAG queries for these platforms!")

if __name__ == "__main__":
    seed_platform_knowledge()