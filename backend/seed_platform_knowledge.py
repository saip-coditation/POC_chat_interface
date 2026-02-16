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
    print("\n" + "="*60)
    print("STARTING KNOWLEDGE BASE SEEDING")
    print("="*60)
    
    try:
        ingest = get_ingestion_service()
        print("✅ Ingestion service initialized")
    except Exception as e:
        print(f"❌ FATAL: Failed to initialize ingestion service: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Track success/failure
    total = 0
    succeeded = 0
    failed = 0
    
    # ===== STRIPE KNOWLEDGE =====
    
    documents = [
        ("Stripe Payment Retry Guide", stripe_payment_retry, "stripe"),
        ("Stripe Refunds Guide", stripe_refunds, "stripe"),
        ("Stripe Subscription Management", stripe_subscriptions, "stripe"),
        ("Salesforce Lead Qualification", salesforce_lead_qualification, "salesforce"),
        ("Salesforce Lead Conversion", salesforce_lead_conversion, "salesforce"),
        ("Salesforce Pipeline Management", salesforce_pipeline, "salesforce"),
        ("GitHub PR Best Practices", github_pr_best_practices, "github"),
        ("GitHub PR Merge Guidelines", github_pr_merge, "github"),
        ("GitHub Commit Messages", github_commits, "github"),
        ("Zoho Deal Management", zoho_deal_management, "zoho"),
        ("Zoho Deal Stage Progression", zoho_deal_stages, "zoho"),
        ("Trello Card Organization", trello_card_organization, "trello"),
        ("Trello Board Structure", trello_board_structure, "trello"),
    ]
    
    for title, content, platform in documents:
        total += 1
        try:
            ingest.ingest_document(title, content, platform=platform)
            succeeded += 1
            print(f"✅ {title}")
        except Exception as e:
            failed += 1
            print(f"❌ {title}: {str(e)[:100]}")
    
    print("\n" + "="*60)
    print("KNOWLEDGE BASE SEEDING COMPLETE")
    print("="*60)
    print(f"Total documents: {total}")
    print(f"✅ Succeeded: {succeeded}")
    print(f"❌ Failed: {failed}")
    
    if failed > 0:
        print(f"\n⚠️  WARNING: {failed} documents failed to ingest")
        print("This is likely due to embedding generation failures.")
        print("Check OPENAI_API_KEY and network connectivity.")
    else:
        print("\n🎉 All knowledge documents seeded successfully!")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    seed_platform_knowledge()