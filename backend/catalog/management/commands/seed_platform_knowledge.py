"""
Django Management Command to Seed Platform Knowledge

Run with: python manage.py seed_platform_knowledge
"""

from django.core.management.base import BaseCommand
from catalog.services import get_ingestion_service


class Command(BaseCommand):
    help = 'Seed platform-specific knowledge base for RAG'

    def handle(self, *args, **options):
        """Execute the seeding process."""
        self.stdout.write("🌱 Seeding platform knowledge base...")
        
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
        result = ingest.ingest_document("Stripe Payment Retry Guide", stripe_payment_retry, platform="stripe")
        self.stdout.write(f"  ✓ Added: Stripe Payment Retry Guide ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("Stripe Refunds Guide", stripe_refunds, platform="stripe")
        self.stdout.write(f"  ✓ Added: Stripe Refunds Guide ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("Stripe Subscription Management", stripe_subscriptions, platform="stripe")
        self.stdout.write(f"  ✓ Added: Stripe Subscription Management ({result.get('chunks', 0)} chunks)")
        
        stripe_webhooks = """
        STRIPE: How to Set Up Webhooks
        
        Steps to set up webhooks in Stripe:
        
        1. **Access Webhook Settings:**
           - Go to Stripe Dashboard → Developers → Webhooks
           - Click "Add endpoint"
        
        2. **Configure Endpoint:**
           - Enter your endpoint URL (e.g., https://yourdomain.com/webhooks/stripe)
           - Select events to listen to (e.g., payment_intent.succeeded, charge.failed)
           - Choose API version (recommend latest)
        
        3. **Get Webhook Secret:**
           - After creating endpoint, copy the "Signing secret"
           - Store securely in environment variables
        
        4. **Verify Webhook Signatures:**
           - Use Stripe SDK to verify webhook signatures
           - Compare signature from header with computed signature
           - Reject requests with invalid signatures
        
        5. **Handle Events:**
           - Parse webhook payload
           - Process event type (payment_intent, charge, customer, etc.)
           - Implement idempotency (handle duplicate events)
        
        Best Practice: Always verify webhook signatures. Use idempotency keys to prevent duplicate processing. Test with Stripe CLI before production.
        """
        result = ingest.ingest_document("Stripe Webhooks Setup", stripe_webhooks, platform="stripe")
        self.stdout.write(f"  ✓ Added: Stripe Webhooks Setup ({result.get('chunks', 0)} chunks)")
        
        stripe_chargebacks = """
        STRIPE: How to Handle Chargebacks
        
        Chargeback handling process:
        
        1. **Monitor Notifications:**
           - Stripe sends webhook: charge.dispute.created
           - Review dispute details in Dashboard
        
        2. **Gather Evidence:**
           - Customer receipt/order confirmation
           - Shipping/tracking information
           - Customer communication records
           - Terms of service acceptance proof
        
        3. **Respond Timeline:**
           - You have 7-21 days to respond (varies by card network)
           - Submit evidence via Stripe Dashboard
           - Or use API: stripe.disputes.update()
        
        4. **Evidence Types:**
           - Proof of delivery (tracking, signature)
           - Customer communication (emails, chats)
           - Proof of service/product delivery
           - Terms acceptance records
        
        5. **Outcomes:**
           - Won: Dispute closed in your favor, funds returned
           - Lost: Funds permanently removed, fee charged
           - Warning: No funds lost, but counts against you
        
        Best Practice: Respond quickly with strong evidence. Keep detailed records of all transactions and communications. Consider chargeback protection services.
        """
        result = ingest.ingest_document("Stripe Chargebacks", stripe_chargebacks, platform="stripe")
        self.stdout.write(f"  ✓ Added: Stripe Chargebacks ({result.get('chunks', 0)} chunks)")
        
        stripe_subscription_upgrades = """
        STRIPE: How to Handle Subscription Upgrades
        
        Subscription upgrade process:
        
        1. **Prorate Charges:**
           - Stripe automatically prorates when changing plans
           - Customer pays difference immediately
           - Remaining time on old plan is credited
        
        2. **Update Subscription:**
           ```python
           subscription = stripe.Subscription.modify(
               subscription_id,
               items=[{'id': item_id, 'price': new_price_id}]
           )
           ```
        
        3. **Handle Downgrades:**
           - Credit applied to next invoice
           - No immediate refund
           - Plan changes at period end (optional)
        
        4. **Best Practices:**
           - Notify customer before upgrade
           - Show prorated amount clearly
           - Update customer records immediately
           - Handle failed upgrade payments
        
        Best Practice: Always show customers the prorated amount before confirming upgrade. Handle payment failures gracefully.
        """
        result = ingest.ingest_document("Stripe Subscription Upgrades", stripe_subscription_upgrades, platform="stripe")
        self.stdout.write(f"  ✓ Added: Stripe Subscription Upgrades ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("Salesforce Lead Qualification", salesforce_lead_qualification, platform="salesforce")
        self.stdout.write(f"  ✓ Added: Salesforce Lead Qualification ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("Salesforce Lead Conversion", salesforce_lead_conversion, platform="salesforce")
        self.stdout.write(f"  ✓ Added: Salesforce Lead Conversion ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("Salesforce Pipeline Management", salesforce_pipeline, platform="salesforce")
        self.stdout.write(f"  ✓ Added: Salesforce Pipeline Management ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("GitHub PR Best Practices", github_pr_best_practices, platform="github")
        self.stdout.write(f"  ✓ Added: GitHub PR Best Practices ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("GitHub PR Merge Guidelines", github_pr_merge, platform="github")
        self.stdout.write(f"  ✓ Added: GitHub PR Merge Guidelines ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("GitHub Commit Messages", github_commits, platform="github")
        self.stdout.write(f"  ✓ Added: GitHub Commit Messages ({result.get('chunks', 0)} chunks)")
        
        github_create_repo = """
        GITHUB: How to Create a New Repository
        
        Steps to create a new repository in GitHub:
        
        1. **Via GitHub Website:**
           - Click the "+" icon in top right corner
           - Select "New repository"
           - Enter repository name (use lowercase, hyphens for spaces)
           - Add description (optional but recommended)
           - Choose visibility: Public (anyone can see) or Private (only you/team)
           - Initialize with README (optional, but helpful)
           - Add .gitignore (select template if applicable)
           - Choose license (optional)
           - Click "Create repository"
        
        2. **Via GitHub CLI:**
           ```bash
           gh repo create my-repo --public --description "My new repository"
           ```
        
        3. **Via Git Command Line:**
           ```bash
           # Create local repo
           mkdir my-repo && cd my-repo
           git init
           echo "# My Repo" > README.md
           git add README.md
           git commit -m "Initial commit"
           
           # Create on GitHub and push
           gh repo create my-repo --public --source=. --remote=origin --push
           ```
        
        Best Practice: Always include a README.md with project description, setup instructions, and usage examples.
        """
        result = ingest.ingest_document("GitHub Create Repository", github_create_repo, platform="github")
        self.stdout.write(f"  ✓ Added: GitHub Create Repository ({result.get('chunks', 0)} chunks)")
        
        github_push_files = """
        GITHUB: How to Push Files to GitHub
        
        Steps to push files to a GitHub repository:
        
        1. **Initial Setup (First Time):**
           ```bash
           # Clone existing repo
           git clone https://github.com/username/repo-name.git
           cd repo-name
           
           # OR initialize new local repo
           git init
           git remote add origin https://github.com/username/repo-name.git
           ```
        
        2. **Add and Commit Files:**
           ```bash
           # Stage files (add to staging area)
           git add .                    # Add all files
           git add file1.txt file2.txt  # Add specific files
           git add *.js                  # Add all .js files
           
           # Commit changes
           git commit -m "Add new feature"
           git commit -m "Fix bug in login"
           ```
        
        3. **Push to GitHub:**
           ```bash
           # Push to main/master branch
           git push origin main
           git push origin master
           
           # Push to specific branch
           git push origin feature-branch
           
           # First time push (set upstream)
           git push -u origin main
           ```
        
        4. **Common Workflow:**
           ```bash
           git status                  # Check what files changed
           git add .                   # Stage all changes
           git commit -m "Description" # Commit with message
           git push                    # Push to remote
           ```
        
        Best Practice: Commit frequently with clear messages. Push after completing logical units of work.
        """
        result = ingest.ingest_document("GitHub Push Files", github_push_files, platform="github")
        self.stdout.write(f"  ✓ Added: GitHub Push Files ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("Zoho Deal Management", zoho_deal_management, platform="zoho")
        self.stdout.write(f"  ✓ Added: Zoho Deal Management ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("Zoho Deal Stage Progression", zoho_deal_stages, platform="zoho")
        self.stdout.write(f"  ✓ Added: Zoho Deal Stage Progression ({result.get('chunks', 0)} chunks)")
        
        zoho_custom_fields = """
        ZOHO: How to Create Custom Fields
        
        Steps to create custom fields in Zoho:
        
        1. **Access Setup:**
           - Go to Setup → Customization → Modules
           - Select the module (Deals, Contacts, Accounts, etc.)
        
        2. **Create Field:**
           - Click "Fields" → "Create Field"
           - Choose field type (Text, Number, Date, Picklist, etc.)
           - Enter field label and API name
        
        3. **Configure Field:**
           - Set field properties (required, unique, visible)
           - Add help text if needed
           - Set default value (optional)
        
        4. **For Picklist Fields:**
           - Add values one by one
           - Set default value
           - Enable multi-select if needed
        
        5. **Layout Assignment:**
           - Assign field to layouts
           - Set field position
           - Set visibility rules if needed
        
        Best Practice: Use descriptive field labels. API names are auto-generated but can be customized. Test custom fields before deploying to production.
        """
        result = ingest.ingest_document("Zoho Custom Fields", zoho_custom_fields, platform="zoho")
        self.stdout.write(f"  ✓ Added: Zoho Custom Fields ({result.get('chunks', 0)} chunks)")
        
        zoho_automation = """
        ZOHO: How to Automate Workflows
        
        Zoho workflow automation setup:
        
        1. **Access Workflow Rules:**
           - Go to Setup → Automation → Workflow Rules
           - Click "Create Rule"
        
        2. **Define Trigger:**
           - Select module (Deals, Contacts, etc.)
           - Choose trigger event (Record Created, Updated, etc.)
           - Set conditions (optional)
        
        3. **Configure Actions:**
           - Send Email: Configure template and recipients
           - Update Field: Set field values automatically
           - Create Task: Assign follow-up tasks
           - Send Notification: Alert team members
        
        4. **Test Workflow:**
           - Use "Test" button to verify
           - Check action execution
           - Review email templates
        
        5. **Activate:**
           - Save workflow rule
           - Activate when ready
           - Monitor execution logs
        
        Best Practice: Start with simple workflows. Test thoroughly before activating. Use conditions to prevent loops.
        """
        result = ingest.ingest_document("Zoho Workflow Automation", zoho_automation, platform="zoho")
        self.stdout.write(f"  ✓ Added: Zoho Workflow Automation ({result.get('chunks', 0)} chunks)")
        
        zoho_reports = """
        ZOHO: How to Create Reports
        
        Creating reports in Zoho:
        
        1. **Access Reports:**
           - Go to Reports → Create Report
           - Select module (Deals, Contacts, etc.)
        
        2. **Choose Report Type:**
           - Summary Report: Aggregated data
           - Tabular Report: Detailed list
           - Matrix Report: Cross-tab analysis
        
        3. **Configure Columns:**
           - Add fields to display
           - Group by fields (for summary)
           - Set sort order
        
        4. **Add Filters:**
           - Set date ranges
           - Filter by status, owner, etc.
           - Use advanced filters for complex criteria
        
        5. **Format & Share:**
           - Format columns (currency, date, etc.)
           - Add charts/graphs
           - Schedule email delivery
        
        Best Practice: Use filters to focus on relevant data. Save reports for reuse. Schedule reports for regular updates.
        """
        result = ingest.ingest_document("Zoho Reports", zoho_reports, platform="zoho")
        self.stdout.write(f"  ✓ Added: Zoho Reports ({result.get('chunks', 0)} chunks)")
        
        zoho_email_templates = """
        ZOHO: How to Set Up Email Templates
        
        Creating email templates in Zoho:
        
        1. **Access Templates:**
           - Go to Setup → Automation → Email Templates
           - Click "Create Template"
        
        2. **Choose Template Type:**
           - Standard Email: General purpose
           - HTML Email: Rich formatting
           - Plain Text: Simple text only
        
        3. **Design Template:**
           - Enter subject line
           - Write email body
           - Use merge fields: {{Deal.Name}}, {{Contact.First_Name}}, etc.
           - Add attachments (optional)
        
        4. **Merge Fields:**
           - {{Deal.Name}} - Deal name
           - {{Contact.First_Name}} - Contact first name
           - {{Account.Name}} - Account name
           - {{User.Name}} - Current user name
        
        5. **Assign & Use:**
           - Assign to modules (Deals, Contacts, etc.)
           - Use in workflows or send manually
           - Preview before sending
        
        Best Practice: Use merge fields for personalization. Test templates before using in workflows. Keep templates concise and professional.
        """
        result = ingest.ingest_document("Zoho Email Templates", zoho_email_templates, platform="zoho")
        self.stdout.write(f"  ✓ Added: Zoho Email Templates ({result.get('chunks', 0)} chunks)")
        
        zoho_blueprints = """
        ZOHO: How to Use Blueprints
        
        Zoho Blueprints setup:
        
        1. **Access Blueprints:**
           - Go to Setup → Automation → Blueprints
           - Click "Create Blueprint"
        
        2. **Define Process:**
           - Select module (Deals, Contacts, etc.)
           - Define stages/steps
           - Set entry criteria
        
        3. **Configure Stages:**
           - Add stage conditions
           - Set required fields per stage
           - Define stage transitions
        
        4. **Set Actions:**
           - Auto-assign records
           - Send notifications
           - Update fields automatically
           - Create related records
        
        5. **Activate:**
           - Test blueprint flow
           - Activate when ready
           - Monitor execution
        
        Best Practice: Use blueprints for complex multi-stage processes. Define clear entry/exit criteria. Test thoroughly before activation.
        """
        result = ingest.ingest_document("Zoho Blueprints", zoho_blueprints, platform="zoho")
        self.stdout.write(f"  ✓ Added: Zoho Blueprints ({result.get('chunks', 0)} chunks)")
        
        # ===== TRELLO KNOWLEDGE =====
        
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
        result = ingest.ingest_document("Trello Card Organization", trello_card_organization, platform="trello")
        self.stdout.write(f"  ✓ Added: Trello Card Organization ({result.get('chunks', 0)} chunks)")
        
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
        result = ingest.ingest_document("Trello Board Structure", trello_board_structure, platform="trello")
        self.stdout.write(f"  ✓ Added: Trello Board Structure ({result.get('chunks', 0)} chunks)")
        
        trello_create_card = """
        TRELLO: How to Create a New Card
        
        Steps to create a new card in Trello:
        
        1. **Via Trello Web/App:**
           - Open the board where you want to create the card
           - Click "Add a card" at the bottom of the list
           - OR click the "+" button in the list header
           - Enter card title (required)
           - Press Enter or click "Add Card"
           - Click the card to add details
        
        2. **Card Details You Can Add:**
           - **Description**: What needs to be done
           - **Members**: Assign team members
           - **Labels**: Color-coded categories (bug, feature, urgent)
           - **Checklist**: Break down into subtasks
           - **Due Date**: Set deadline
           - **Attachments**: Files, images, links
           - **Comments**: Discussion and updates
        
        3. **Quick Card Creation:**
           - Type card title and press Enter (fastest way)
           - Add details later by clicking the card
        
        4. **Best Practices:**
           - Use clear, action-oriented titles: "Fix login bug" not "Bug"
           - Add acceptance criteria in description
           - Assign to appropriate team member
           - Set realistic due dates
           - Use labels for quick filtering
        
        5. **Keyboard Shortcuts:**
           - Press 'N' to create new card (when board is open)
           - Press 'C' to add comment to selected card
        
        Best Practice: Create cards immediately when tasks are identified. Don't wait - capture ideas while fresh.
        """
        result = ingest.ingest_document("Trello Create Card", trello_create_card, platform="trello")
        self.stdout.write(f"  ✓ Added: Trello Create Card ({result.get('chunks', 0)} chunks)")
        
        trello_card_best_practices = """
        TRELLO: Card Creation Best Practices
        
        Best practices for creating effective Trello cards:
        
        1. **Card Title:**
           - Be specific: "Implement user authentication" not "Auth"
           - Use action verbs: "Fix", "Create", "Update", "Review"
           - Keep it concise but descriptive
        
        2. **Card Description:**
           - What: What needs to be done
           - Why: Why it's important
           - Acceptance Criteria: How to know it's done
           - Links: Reference related docs, issues, or PRs
        
        3. **Organization:**
           - One task per card (don't combine multiple tasks)
           - Break large tasks into smaller cards
           - Link related cards using card numbers (#123)
        
        4. **Metadata:**
           - Assign to right person (not everyone)
           - Use labels consistently across board
           - Set realistic due dates
           - Add checklists for multi-step tasks
        
        5. **When to Create Cards:**
           - New feature requests
           - Bugs found
           - Tasks from meetings
           - Ideas that need discussion
           - Follow-up actions
        
        Best Practice: Review and refine cards weekly. Archive completed cards. Update cards as work progresses.
        """
        result = ingest.ingest_document("Trello Card Best Practices", trello_card_best_practices, platform="trello")
        self.stdout.write(f"  ✓ Added: Trello Card Best Practices ({result.get('chunks', 0)} chunks)")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Platform knowledge base seeded successfully!"))
        self.stdout.write("\nAdded knowledge documents for:")
        self.stdout.write("  - Stripe: Payment retry, refunds, subscriptions, webhooks, chargebacks, upgrades")
        self.stdout.write("  - Salesforce: Lead qualification, conversion, pipeline")
        self.stdout.write("  - GitHub: PR best practices, merge guidelines, commits, create repo, push files")
        self.stdout.write("  - Zoho: Deal management, stage progression, custom fields, automation, reports, email templates, blueprints")
        self.stdout.write("  - Trello: Card organization, board structure, create card, card best practices")
        self.stdout.write("\nYou can now test RAG queries for these platforms!")
