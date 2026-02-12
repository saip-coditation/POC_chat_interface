# Test Queries for RAG-Based Answers

This file contains test queries to verify that the RAG (Retrieval-Augmented Generation) system correctly retrieves and answers questions based on the seeded knowledge base.

## How to Use

Run these queries in the chat interface and verify that the AI provides accurate answers based on the platform-specific knowledge documents.

---

## Stripe Test Queries

### Payment Retry
- "When should I retry a failed payment in Stripe?"
- "What's the best practice for retrying declined cards?"
- "How do I handle insufficient funds errors in Stripe?"
- "When can I retry a payment after a fraud review?"

### Refunds
- "How do I process a refund in Stripe?"
- "What's the timeline for Stripe refunds to appear on customer cards?"
- "Are Stripe fees refunded when I issue a refund?"
- "How should I handle disputes in Stripe?"

### Subscriptions
- "How do I manage Stripe subscriptions?"
- "What happens when a subscription payment fails?"
- "How do I handle subscription cancellations?"
- "What are best practices for subscription upgrades?"

### Webhooks
- "How do I set up webhooks in Stripe?"
- "What's the process for configuring Stripe webhook endpoints?"
- "How do I verify webhook signatures in Stripe?"
- "What events should I listen to for Stripe webhooks?"

### Chargebacks
- "How do I handle chargebacks in Stripe?"
- "What evidence do I need to respond to a Stripe dispute?"
- "How long do I have to respond to a Stripe chargeback?"
- "What happens if I win a Stripe dispute?"

### Subscription Upgrades
- "How do I upgrade a Stripe subscription?"
- "Does Stripe automatically prorate subscription changes?"
- "How do I handle failed upgrade payments?"
- "What's the best practice for subscription upgrades?"

---

## Salesforce Test Queries

### Lead Qualification
- "How do I qualify a lead in Salesforce?"
- "What is the BANT framework for lead qualification?"
- "What score indicates a hot lead in Salesforce?"
- "When should I convert a lead to an opportunity?"

### Lead Conversion
- "When should I convert a lead to opportunity in Salesforce?"
- "What criteria must be met before converting a lead?"
- "What's the process for converting a lead in Salesforce?"
- "How do I create an opportunity from a lead?"

### Pipeline Management
- "How do I manage my sales pipeline in Salesforce?"
- "What are the stages in a Salesforce sales pipeline?"
- "How often should I update opportunity stages?"
- "What's the best practice for sales forecasting?"

---

## GitHub Test Queries

### Pull Requests
- "What makes a good pull request on GitHub?"
- "How should I write a PR description?"
- "What's the best practice for pull request size?"
- "How do I link issues in a pull request?"

### Merging
- "When should I merge a pull request?"
- "What's the difference between merge and squash merge?"
- "How many approvals do I need before merging?"
- "What should I check before merging a PR?"

### Commits
- "How do I write a good commit message?"
- "What format should commit messages follow?"
- "How do I reference issues in commit messages?"
- "What's the best practice for atomic commits?"

### Repository Management
- "How do I create a new repository on GitHub?"
- "What's the difference between public and private repositories?"
- "How do I initialize a repository with a README?"
- "What files should I include when creating a repo?"

### Pushing Files
- "How do I push files to GitHub?"
- "What's the workflow for pushing changes?"
- "How do I push to a specific branch?"
- "What's the difference between git add and git commit?"

### Cloning
- "How do I clone a GitHub repository?"
- "What's the difference between HTTPS and SSH cloning?"
- "How do I clone a specific branch?"
- "How do I clone a repo into a specific folder?"

---

## Zoho Test Queries

### Deal Management
- "How do I manage deals in Zoho?"
- "What are the stages in a Zoho deal pipeline?"
- "How do I move a deal to the next stage?"
- "What's the best practice for deal probability?"

### Deal Stages
- "When should I move a deal to the next stage?"
- "What criteria must be met before advancing a deal?"
- "What are the deal stages in Zoho?"
- "How do I know if a deal is ready to move forward?"

### Custom Fields
- "How do I create custom fields in Zoho?"
- "What types of fields can I create in Zoho?"
- "How do I add a picklist field in Zoho?"
- "How do I assign custom fields to layouts?"

### Automation
- "How do I automate workflows in Zoho?"
- "What actions can I automate in Zoho?"
- "How do I create a workflow rule?"
- "What triggers can I use for Zoho automation?"

### Reports
- "How do I create reports in Zoho?"
- "What types of reports can I create?"
- "How do I filter data in Zoho reports?"
- "How do I schedule report delivery?"

### Email Templates
- "How do I create email templates in Zoho?"
- "What merge fields can I use in templates?"
- "How do I use email templates in workflows?"
- "What's the difference between HTML and plain text templates?"

### Blueprints
- "How do I use blueprints in Zoho?"
- "What are blueprints used for?"
- "How do I configure blueprint stages?"
- "When should I use blueprints vs workflows?"

---

## Trello Test Queries

### Card Organization
- "How do I organize cards in Trello?"
- "What's the best way to use labels in Trello?"
- "How do I add checklists to Trello cards?"
- "What information should I include in a card description?"

### Board Structure
- "How should I structure my Trello board?"
- "What lists should I have in my Trello board?"
- "How do I set up a workflow in Trello?"
- "What's the best practice for board organization?"

### Creating Cards
- "How do I create a new card in Trello?"
- "What details should I add to a Trello card?"
- "How do I assign members to a card?"
- "What keyboard shortcuts can I use in Trello?"

### Card Best Practices
- "What makes a good Trello card?"
- "How should I write card titles?"
- "When should I create a new card?"
- "How do I link related cards in Trello?"

---

## Cross-Platform Test Queries

### General Knowledge
- "What platforms are supported?"
- "How do I connect my accounts?"
- "What data can I query?"
- "How does the RAG system work?"

### Comparison Queries
- "What's the difference between Stripe and Zoho for payment processing?"
- "How do GitHub and Trello differ for project management?"
- "Which platform is better for CRM: Salesforce or Zoho?"

---

## Expected Behavior

When testing these queries:

1. **Accurate Answers**: The AI should provide answers based on the seeded knowledge documents
2. **Platform Context**: Answers should be specific to the platform mentioned
3. **Best Practices**: Answers should include best practices when relevant
4. **Step-by-Step**: For "how-to" questions, answers should include clear steps
5. **Code Examples**: Technical queries should include code examples when appropriate

---

## Notes

- These queries test the RAG system's ability to retrieve relevant knowledge from ChromaDB
- Answers should be based on the knowledge documents seeded via `seed_platform_knowledge.py`
- If a query doesn't return expected results, check:
  1. Knowledge documents are seeded (run `python manage.py seed_platform_knowledge`)
  2. Embeddings are generated correctly
  3. ChromaDB collection contains the documents
  4. Query intent detection is working properly

---

## Running Tests

To test RAG functionality:

1. Ensure knowledge base is seeded:
   ```bash
   cd backend
   python manage.py seed_platform_knowledge
   ```

2. Start the Django server:
   ```bash
   python manage.py runserver
   ```

3. Open the chat interface and try the queries above

4. Verify answers match the knowledge documents

---

## Adding New Test Queries

When adding new knowledge documents to the RAG system:

1. Add corresponding test queries here
2. Test that queries return accurate answers
3. Update this file with new test cases
4. Document any edge cases or special scenarios
