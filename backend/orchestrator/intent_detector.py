"""
Intent Detector

Uses Chroma vector search to classify user queries into actionable intents.
Intent detection is the first step in query processing.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Supported intent types."""
    DATA_QUERY = "DATA_QUERY"           # Read data from one or more sources
    DATA_AGGREGATE = "DATA_AGGREGATE"   # Aggregate/compare across sources
    DATA_WRITE = "DATA_WRITE"           # Create/update records
    MONEY_MOVE = "MONEY_MOVE"           # Financial transactions
    SYSTEM_CONFIG = "SYSTEM_CONFIG"     # Platform configuration
    CLARIFICATION = "CLARIFICATION"     # User needs to provide more context
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY" # RAG/Knowledge base questions
    UNKNOWN = "UNKNOWN"                 # Could not determine intent


@dataclass
class DetectedIntent:
    """Result of intent detection."""
    intent_type: IntentType
    confidence: float
    tool_id: Optional[str] = None
    platform: Optional[str] = None
    matched_query: Optional[str] = None
    alternatives: List[Dict] = None
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []
    
    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if confidence exceeds threshold."""
        return self.confidence >= threshold
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "tool_id": self.tool_id,
            "platform": self.platform,
            "matched_query": self.matched_query,
            "alternatives": self.alternatives
        }


class IntentDetector:
    """
    Detects user intent using semantic search against known intents.
    
    Uses Chroma to store intent examples and find the closest match
    to user queries.
    """
    
    COLLECTION_NAME = "intents"
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7
    
    def __init__(self, chroma_client=None, embeddings_client=None):
        """
        Initialize the intent detector.
        
        Args:
            chroma_client: Optional ChromaClient instance
            embeddings_client: Optional GeminiEmbeddings instance
        """
        self._chroma = chroma_client
        self._embeddings = embeddings_client
        self._collection = None
    
    def _get_chroma(self):
        """Lazy load Chroma client."""
        if self._chroma is None:
            from rag.chroma_client import get_chroma_client
            self._chroma = get_chroma_client()
        return self._chroma
    
    def _get_embeddings(self):
        """Lazy load embeddings client."""
        if self._embeddings is None:
            from rag.embeddings import get_embeddings
            self._embeddings = get_embeddings()
        return self._embeddings
    
    def _get_collection(self):
        """Get or create the intents collection."""
        if self._collection is None:
            chroma = self._get_chroma()
            self._collection = chroma.get_or_create_collection(self.COLLECTION_NAME)
        return self._collection
    
    def detect(
        self, 
        query: str, 
        n_results: int = 5,
        confidence_threshold: float = None
    ) -> DetectedIntent:
        """
        Detect the intent of a user query.
        
        Args:
            query: The user's natural language query
            n_results: Number of candidate intents to consider
            confidence_threshold: Minimum confidence for a valid match
        
        Returns:
            DetectedIntent with classification results
        """
        if confidence_threshold is None:
            confidence_threshold = self.DEFAULT_CONFIDENCE_THRESHOLD
            
        # 0. Robust Overrides with Fuzzy Matching
        import difflib
        
        # known_platforms and keywords for typo correction
        known_terms = [
            'salesforce', 'stripe', 'zoho', 'github', 'trello', 
            'details', 'contact', 'contacts', 'deal', 'deals', 
            'lead', 'leads', 'account', 'accounts',
            'revenue', 'invoice', 'payment', 'payments',
            'repo', 'commits', 'pr', 'pull', 'request'
        ]
        
        words = query.split()
        corrected_query_parts = []
        typo_detected = False
        
        for word in words:
            # Skip short words to avoid false positives
            if len(word) < 4:
                corrected_query_parts.append(word)
                continue
                
            # Check for close match
            matches = difflib.get_close_matches(word.lower(), known_terms, n=1, cutoff=0.8)
            if matches and matches[0] != word.lower():
                logger.info(f"[INTENT] Correcting typo: '{word}' -> '{matches[0]}'")
                corrected_query_parts.append(matches[0])
                typo_detected = True
            else:
                corrected_query_parts.append(word)
        
        corrected_query = " ".join(corrected_query_parts)
        if typo_detected:
            logger.info(f"[INTENT] Original query: '{query}' -> Corrected: '{corrected_query}'")
            query = corrected_query
            
        query_lower = query.lower()
        logger.info(f"IntentDetector: Checking overrides for query: '{query_lower}'")
        
        # Cross-platform check FIRST (before single-platform checks)
        # Pattern: "details and payments of X from both stripe and salesforce"
        import re
        has_salesforce = "salesforce" in query_lower
        has_stripe = "stripe" in query_lower
        has_both = "both" in query_lower
        has_details = "detail" in query_lower  # Match "details" or "deatils" (typo)
        has_payment = "payment" in query_lower  # Match "payments" or "payements" (typo)
        
        is_cross_platform = (
            (has_salesforce and has_stripe) or
            (has_both and (has_salesforce or has_stripe)) or
            (has_details and has_payment and (has_salesforce or has_stripe))
        )
        
        if is_cross_platform:
            logger.info(f"Cross-platform query detected FIRST: salesforce={has_salesforce}, stripe={has_stripe}, both={has_both}")
            
            # Extract person name from query - improved patterns
            name_patterns = [
                r'(?:details?|payments?|information|show|for|me)\s+(?:of\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:from|in|of)',
                r'(?:of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b',  # Direct pattern: "Rohan robert"
            ]
            person_name = None
            for pattern in name_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    person_name = match.group(1).strip()
                    # Filter out common words
                    if person_name.lower() not in ['both', 'stripe', 'salesforce', 'details', 'payments', 'detail', 'payment', 'me', 'show']:
                        logger.info(f"Extracted person name: {person_name}")
                        break
            
            # Always return cross-platform intent if we detected cross-platform indicators
            logger.info(f"Returning cross-platform intent with tool_id=customer_overview_cross_platform, person_name={person_name}")
            return DetectedIntent(
                IntentType.DATA_QUERY,
                confidence=0.9,
                tool_id="customer_overview_cross_platform",
                platform="multi",  # Multi-platform
                matched_query=query
            )
        
        # 0. Knowledge Query Override (Moved up priority)
        # Questions about policies, procedures, or general knowledge
        knowledge_patterns = [
            r'when\s+(?:should)\s+(?:i|we)\s+(.+)', # Added specific pattern for "When should I..."
            r'what\s+(?:is|are|does|do)\s+(?:the\s+)?(.+)',
            r'how\s+(?:do|can|should|to)\s+(?:i|we)?\s*(.+)',  # "how to clone", "how do i clone"
            r'tell\s+me\s+about\s+(.+)',
            r'explain\s+(.+)',
            r'(.+)\s+policy',
            r'(.+)\s+manual',
            r'(.+)\s+guide'
        ]
        
        # Check if it looks like a knowledge question
        # Be careful not to capture things handled by other tools (like "revenue")
        is_knowledge = any(re.search(p, query_lower) for p in knowledge_patterns)
        
        if is_knowledge and "revenue" not in query_lower and "invoice" not in query_lower:
            # Special check: "how to create/push/add/clone" questions are knowledge queries
            # They're asking for instructions/guidance, not to perform the action
            is_how_to_create = re.search(r'how\s+(can\s+i|do\s+i|to)\s+create', query_lower)
            is_how_to_push = re.search(r'how\s+(can\s+i|do\s+i|to)\s+push', query_lower)
            is_how_to_add = re.search(r'how\s+(can\s+i|do\s+i|to)\s+add', query_lower)
            is_how_to_clone = re.search(r'how\s+(can\s+i|do\s+i|to)\s+clone', query_lower) or re.search(r'how\s+to\s+clone|clone\s+(a\s+)?(repo|repository)', query_lower)
            
            # If it's a "how to create/add/push/clone" question, it's a knowledge query
            if is_how_to_create or is_how_to_push or is_how_to_add or is_how_to_clone:
                logger.info("[INTENT] Matched Knowledge Query - 'how to create/add/push' question")
                return DetectedIntent(
                    intent_type=IntentType.KNOWLEDGE_QUERY,
                    confidence=0.95,
                    tool_id="knowledge_search",
                    platform="rag",
                    matched_query=query
                )
            
            # Other action questions might be actual actions (not knowledge queries)
            # e.g. "create a card" without "how" -> actual action
            is_action_question = any(w in query_lower for w in ["create", "add", "delete", "remove", "update"]) and not any(re.search(r'how\s+(can|do|to)', query_lower))
            
            if not is_action_question:
                logger.info("[INTENT] Matched Knowledge Query")
                return DetectedIntent(
                    intent_type=IntentType.KNOWLEDGE_QUERY,
                    confidence=0.95, # High confidence
                    tool_id="knowledge_search",
                    platform="rag",
                    matched_query=query
                )

        # Revenue override
        if "revenue" in query_lower or "money" in query_lower:
            logger.info("IntentDetector: Matched Revenue Override")
            # Check if it's asking for revenue
            return DetectedIntent(
                intent_type=IntentType.DATA_AGGREGATE, 
                confidence=1.0, 
                tool_id="get_revenue", 
                platform="stripe",
                matched_query=query
            )
            
        # Pull Requests override (high priority, before other GitHub checks)
        if "pull request" in query_lower or ("pr" in query_lower and "card" not in query_lower and "create" not in query_lower and "add" not in query_lower):
            # Check if it's a GitHub context query
            if "github" in query_lower or "show" in query_lower or "list" in query_lower or "me" in query_lower:
                logger.info("[INTENT] Matched: Pull Requests Override (GitHub)")
                return DetectedIntent(
                    intent_type=IntentType.DATA_QUERY,
                    confidence=1.0, 
                    tool_id="list_prs", 
                    platform="github",
                    matched_query=query
                )
            
        # Commits override
        if "commit" in query_lower and ("github" in query_lower or "repo" in query_lower or "of" in query_lower):
            return DetectedIntent(
                intent_type=IntentType.DATA_QUERY,
                confidence=1.0, 
                tool_id="list_commits", 
                platform="github",
                matched_query=query
            )
            
        # Salesforce Write Overrides
        if "salesforce" in query_lower:
            if any(word in query_lower for word in ["create", "add", "new", "make"]):
                if "contact" in query_lower or "person" in query_lower or "customer" in query_lower:
                    logger.info("[INTENT] Matched Salesforce Create Contact Override")
                    return DetectedIntent(
                        intent_type=IntentType.DATA_WRITE,
                        confidence=1.0, 
                        tool_id="create_contact", 
                        platform="salesforce",
                        matched_query=query
                    )
                if "lead" in query_lower:
                    logger.info("[INTENT] Matched Salesforce Create Lead Override")
                    return DetectedIntent(
                        intent_type=IntentType.DATA_WRITE,
                        confidence=1.0, 
                        tool_id="create_record", 
                        platform="salesforce",
                        matched_query=query
                    )
        

        
        # 1. Try Vector Search First
        try:
            # Generate query embedding
            embeddings = self._get_embeddings()
            query_embedding = embeddings.embed_for_query(query)
            
            # Search for similar intents
            collection = self._get_collection()
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            if results.get('ids') and results['ids'] and len(results['ids'][0]) > 0:
                # Calculate confidence from distance
                distances = results['distances'][0] if 'distances' in results else []
                best_distance = distances[0] if distances else 1.0
                confidence = 1.0 / (1.0 + best_distance)
                
                if confidence >= confidence_threshold:
                    # Found a good match via Semantic Search
                    best_metadata = results['metadatas'][0][0] if results['metadatas'][0] else {}
                    best_document = results['documents'][0][0] if results['documents'][0] else ""
                    
                    intent_type_str = best_metadata.get('intent_type', 'UNKNOWN')
                    try:
                        intent_type = IntentType(intent_type_str)
                    except ValueError:
                        intent_type = IntentType.UNKNOWN
                        
                    # Collect alternatives
                    alternatives = []
                    for i in range(1, min(len(results['ids'][0]), 3)):
                        alt_metadata = results['metadatas'][0][i] if results['metadatas'][0] else {}
                        alt_distance = distances[i] if len(distances) > i else 1.0
                        alt_confidence = 1.0 / (1.0 + alt_distance)
                        alternatives.append({
                            "tool_id": alt_metadata.get('tool_id'),
                            "intent_type": alt_metadata.get('intent_type'),
                            "confidence": alt_confidence
                        })
                    
                    return DetectedIntent(
                        intent_type=intent_type,
                        confidence=confidence,
                        tool_id=best_metadata.get('tool_id'),
                        platform=best_metadata.get('platform'),
                        matched_query=best_document,
                        alternatives=alternatives
                    )

        except Exception as e:
            logger.warning(f"Vector search failed: {e}. Falling back to keyword matching.")

        # 2. Fallback: Keyword Matching (Deterministic)
        query_lower = query.lower()
        
        # PRIORITY: Check for knowledge questions FIRST (before platform fallbacks)
        # "How to handle/setup/configure/manage/create/clone" questions are always knowledge queries
        knowledge_action_patterns = [
            r'how\s+(to|do\s+i|can\s+i)\s+handle',
            r'how\s+(to|do\s+i|can\s+i)\s+set\s+up',
            r'how\s+(to|do\s+i|can\s+i)\s+setup',
            r'how\s+(to|do\s+i|can\s+i)\s+configure',
            r'how\s+(to|do\s+i|can\s+i)\s+manage',
            r'how\s+(to|do\s+i|can\s+i)\s+create',
            r'how\s+(to|do\s+i|can\s+i)\s+clone',
            r'clone\s+(a\s+)?(repo|repository)',
            r'how\s+to\s+clone',
        ]
        
        for pattern in knowledge_action_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"[INTENT] Knowledge action pattern detected: {pattern}")
                # Detect platform from context
                platform = "rag"
                if any(kw in query_lower for kw in ['chargeback', 'webhook', 'refund', 'payment', 'stripe', 'subscription', 'invoice']):
                    platform = "stripe"
                elif any(kw in query_lower for kw in ['lead', 'salesforce', 'opportunity', 'pipeline']):
                    platform = "salesforce"
                elif any(kw in query_lower for kw in ['deal', 'zoho']):
                    platform = "zoho"
                elif any(kw in query_lower for kw in ['card', 'trello', 'board']):
                    platform = "trello"
                elif any(kw in query_lower for kw in ['repo', 'github', 'pr', 'pull request', 'merge']):
                    platform = "github"
                
                return DetectedIntent(
                    IntentType.KNOWLEDGE_QUERY,
                    0.95,
                    tool_id="knowledge_search",
                    platform=platform,
                    matched_query=query
                )
        
        # Also check for knowledge-related terms that shouldn't trigger data queries
        knowledge_terms = ['chargeback', 'webhook', 'setup', 'set up', 'configure', 'handle']
        has_knowledge_term = any(term in query_lower for term in knowledge_terms)
        
        # 1. Stripe Fallback
        # Check for Stripe-specific keywords even if "stripe" isn't mentioned
        # BUT exclude knowledge-related queries (chargeback, webhook, handle, setup)
        has_stripe_keywords = (
            ("stripe" in query_lower or
            "invoice" in query_lower or
            "charge" in query_lower or
            "payment" in query_lower or
            "subscription" in query_lower or
            "revenue" in query_lower or
            "balance" in query_lower or
            "customer" in query_lower) and not has_knowledge_term
        )
        
        logger.info(f"[INTENT] Checking Stripe keywords for query: '{query_lower}', has_stripe_keywords: {has_stripe_keywords}, has_knowledge_term: {has_knowledge_term}")
        
        if has_stripe_keywords:
            if "invoice" in query_lower:
                logger.info("[INTENT] Matched: list_invoices")
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_invoices", platform="stripe")
            if "customer" in query_lower:
                logger.info("[INTENT] Matched: list_customers")
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_customers", platform="stripe")
            if "product" in query_lower:
                logger.info("[INTENT] Matched: list_products")
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_products", platform="stripe")
            if "balance" in query_lower:
                logger.info("[INTENT] Matched: get_balance")
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="get_balance", platform="stripe")
            if "revenue" in query_lower or "money" in query_lower:
                logger.info("[INTENT] Matched: get_revenue")
                return DetectedIntent(IntentType.DATA_AGGREGATE, 0.8, tool_id="get_revenue", platform="stripe")
            if "charge" in query_lower or "payment" in query_lower:
                logger.info(f"[INTENT] Matched: list_charges (charge={('charge' in query_lower)}, payment={('payment' in query_lower)})")
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_charges", platform="stripe")
            if "subscription" in query_lower:
                logger.info("[INTENT] Matched: list_subscriptions")
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_subscriptions", platform="stripe")
        
        # 2. Zoho Fallback
        # Exclude knowledge-related queries (manage, create, setup, configure, handle)
        zoho_knowledge_terms = ['manage', 'create', 'setup', 'set up', 'configure', 'handle', 'how to', 'how do']
        is_zoho_knowledge = any(term in query_lower for term in zoho_knowledge_terms)
        
        if ("zoho" in query_lower or "crm" in query_lower) and not is_zoho_knowledge:
            if "contact" in query_lower or "details" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_contacts", platform="zoho")
            if "deal" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_deals", platform="zoho")
            if "lead" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_leads", platform="zoho")
            if "account" in query_lower or "company" in query_lower or "everything" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_accounts", platform="zoho")

        # Check for informational/knowledge questions FIRST (before platform-specific detection)
        informational_patterns = [
            r'\b(when|how|what|why|where)\s+(should|do|can|could|would|is|are|does|did|to)',
            r'\b(when|how|what|why|where)\s+to\s+',
            r'\bhow\s+to\s+',
            r'\bwhat\s+is\s+',
            r'\bwhen\s+should\s+i\s+',
            r'\bhow\s+can\s+i\s+',  # "How can I create..."
            r'\bhow\s+do\s+i\s+',   # "How do I handle..."
        ]
        for pattern in informational_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"[INTENT] Detected informational question: {query}")
                
                # "How to create/add/push/clone/handle/manage/setup" questions are always knowledge queries
                if re.search(r'how\s+(can\s+i|do\s+i|to)\s+(create|add|push|clone|handle|set\s+up|setup|configure|manage)', query_lower) or re.search(r'how\s+to\s+clone|clone\s+(a\s+)?(repo|repository)', query_lower):
                    logger.info("[INTENT] 'How to create/add/push/handle/manage/setup' detected - knowledge query")
                    # Detect platform from context
                    platform = "rag"  # Default
                    if any(kw in query_lower for kw in ['repo', 'repository', 'github', 'push', 'commit', 'pr', 'pull request']):
                        platform = "github"
                    elif any(kw in query_lower for kw in ['card', 'trello', 'board', 'list']):
                        platform = "trello"
                    elif any(kw in query_lower for kw in ['payment', 'stripe', 'invoice', 'charge', 'chargeback', 'webhook', 'refund', 'subscription']):
                        platform = "stripe"
                    elif any(kw in query_lower for kw in ['lead', 'salesforce', 'opportunity']):
                        platform = "salesforce"
                    elif any(kw in query_lower for kw in ['deal', 'zoho', 'crm', 'email template', 'blueprint', 'custom field', 'workflow', 'report']):
                        platform = "zoho"
                    
                    return DetectedIntent(
                        IntentType.KNOWLEDGE_QUERY,
                        0.95,
                        tool_id="knowledge_search",
                        platform=platform,
                        matched_query=query
                    )
                
                # Check for platform-specific keywords - prioritize domain-specific terms over generic ones
                # Payment/billing terms indicate Stripe, not Trello (but exclude knowledge terms)
                knowledge_terms_in_query = any(term in query_lower for term in ['chargeback', 'webhook', 'handle', 'setup', 'set up', 'configure', 'how to'])
                if any(keyword in query_lower for keyword in ['payment', 'invoice', 'charge', 'refund', 'stripe', 'billing']) and knowledge_terms_in_query:
                    # Payment-related knowledge questions are Stripe
                    return DetectedIntent(
                        IntentType.KNOWLEDGE_QUERY,
                        0.9,
                        tool_id="knowledge_search",
                        platform="stripe",
                        matched_query=query
                    )
                # Check if it's asking about Trello workflow/process (but not payment-related)
                elif any(keyword in query_lower for keyword in ['trello', 'board', 'card', 'list', 'move', 'done']) and 'payment' not in query_lower:
                    # This is a knowledge question about Trello - should use RAG/knowledge base
                    return DetectedIntent(
                        IntentType.KNOWLEDGE_QUERY,
                        0.9,
                        tool_id="trello_knowledge",
                        platform="trello",
                        matched_query=query
                    )
                break
        
        # 3. Trello Fallback (moved BEFORE GitHub to prioritize card operations)
        # Check for Trello-specific keywords first, especially "card" which is more specific
        if "trello" in query_lower or "board" in query_lower or "card" in query_lower:
            # Check for write operations first (delete/remove prioritized over create/add)
            if any(word in query_lower for word in ["delete", "remove"]) and ("card" in query_lower or ("list" in query_lower and "board" in query_lower)):
                logger.info("[INTENT] Matched: delete_card (Trello)")
                return DetectedIntent(IntentType.DATA_WRITE, 0.9, tool_id="delete_card", platform="trello")
            elif any(word in query_lower for word in ["create", "add", "new", "make"]) and ("card" in query_lower or ("list" in query_lower and "board" in query_lower)):
                logger.info("[INTENT] Matched: create_card (Trello) - card operation detected")
                return DetectedIntent(IntentType.DATA_WRITE, 0.9, tool_id="create_card", platform="trello")
            elif "board" in query_lower and ("list" not in query_lower and "card" not in query_lower):
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_boards", platform="trello")
            elif "card" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_cards", platform="trello")
            elif "list" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="get_lists", platform="trello")
        
        # 4. GitHub Fallback (moved AFTER Trello to avoid false matches)
        # Only match GitHub if "PR" appears WITHOUT "card" context (PR in card name shouldn't trigger GitHub)
        if "github" in query_lower:
            # Explicit GitHub queries - check for specific actions first
            if "pull request" in query_lower or ("pr" in query_lower and "card" not in query_lower):
                logger.info("[INTENT] Matched: list_prs (GitHub) - explicit PR query")
                return DetectedIntent(IntentType.DATA_QUERY, 0.9, tool_id="list_prs", platform="github")
            if "issue" in query_lower and "card" not in query_lower:
                logger.info("[INTENT] Matched: list_issues (GitHub)")
                return DetectedIntent(IntentType.DATA_QUERY, 0.9, tool_id="list_issues", platform="github")
            if "commit" in query_lower and "card" not in query_lower:
                logger.info("[INTENT] Matched: list_commits (GitHub)")
                return DetectedIntent(IntentType.DATA_QUERY, 0.9, tool_id="list_commits", platform="github")
            if "repo" in query_lower and "summary" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="repo_summary", platform="github")
            # Default to repos if just "github" mentioned
            logger.info("[INTENT] Matched: list_repos (GitHub) - default")
            return DetectedIntent(IntentType.DATA_QUERY, 0.7, tool_id="list_repos", platform="github")
        elif ("repo" in query_lower or "pr" in query_lower or "commit" in query_lower or "issue" in query_lower) and "card" not in query_lower:
            # GitHub-related keywords without explicit "github" - be more careful
            if "pull request" in query_lower or ("pr" in query_lower and "card" not in query_lower):
                logger.info("[INTENT] Matched: list_prs (GitHub) - PR keyword")
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_prs", platform="github")
            if "issue" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_issues", platform="github")
            if "commit" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_commits", platform="github")
            if "repo" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.7, tool_id="list_repos", platform="github")
        
        # 5. Salesforce Fallback
        if "salesforce" in query_lower:
            # Read operations
            if "contact" in query_lower or "person" in query_lower or "customer" in query_lower or "details" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_contacts", platform="salesforce")
            if "lead" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_leads", platform="salesforce")
            if "account" in query_lower or "company" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_accounts", platform="salesforce")
            if "deal" in query_lower or "opportunity" in query_lower:
                return DetectedIntent(IntentType.DATA_QUERY, 0.8, tool_id="list_opportunities", platform="salesforce")
        # 6. Cross-platform queries (Salesforce + Stripe) - Already handled in overrides section above
        # This section is kept for reference but should not be reached if cross-platform was detected earlier

        # No match found
        return DetectedIntent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.0
        )
    
    def seed_intents_from_tool_specs(self, tool_specs_dir: str) -> int:
        """
        Seed the intents collection from ToolSpec YAML files.
        
        Args:
            tool_specs_dir: Path to tool_specs directory
        
        Returns:
            Number of intents added
        """
        import os
        from connectors.tool_spec import ToolSpecParser
        
        collection = self._get_collection()
        embeddings = self._get_embeddings()
        count = 0
        
        # Walk through all platform directories
        for platform_dir in os.listdir(tool_specs_dir):
            platform_path = os.path.join(tool_specs_dir, platform_dir)
            if not os.path.isdir(platform_path):
                continue
            
            for filename in os.listdir(platform_path):
                if not filename.endswith(('.yaml', '.yml')):
                    continue
                
                filepath = os.path.join(platform_path, filename)
                try:
                    spec = ToolSpecParser.parse_file(filepath)
                    
                    # Add each example query as an intent
                    for idx, example in enumerate(spec.example_queries):
                        intent_id = f"{spec.tool_id}_example_{idx}"
                        
                        # Generate embedding
                        embedding = embeddings.embed_for_storage(example)
                        
                        # Map category to intent type
                        intent_type = self._category_to_intent_type(spec.category)
                        
                        collection.add(
                            ids=[intent_id],
                            embeddings=[embedding],
                            documents=[example],
                            metadatas=[{
                                "tool_id": spec.tool_id,
                                "platform": spec.platform,
                                "intent_type": intent_type.value,
                                "governance_class": spec.governance_class
                            }]
                        )
                        count += 1
                    
                    # Also add the description as an intent
                    if spec.semantic_description:
                        desc_id = f"{spec.tool_id}_description"
                        embedding = embeddings.embed_for_storage(spec.semantic_description)
                        intent_type = self._category_to_intent_type(spec.category)
                        
                        collection.add(
                            ids=[desc_id],
                            embeddings=[embedding],
                            documents=[spec.semantic_description],
                            metadatas=[{
                                "tool_id": spec.tool_id,
                                "platform": spec.platform,
                                "intent_type": intent_type.value,
                                "governance_class": spec.governance_class
                            }]
                        )
                        count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing {filepath}: {e}")
        
        logger.info(f"Seeded {count} intents from ToolSpecs")
        return count
    
    def _category_to_intent_type(self, category: str) -> IntentType:
        """Map ToolSpec category to IntentType."""
        mapping = {
            "DATA_QUERY": IntentType.DATA_QUERY,
            "DATA_AGGREGATE": IntentType.DATA_AGGREGATE,
            "DATA_WRITE": IntentType.DATA_WRITE,
            "MONEY_MOVE": IntentType.MONEY_MOVE,
            "SYSTEM_CONFIG": IntentType.SYSTEM_CONFIG,
        }
        return mapping.get(category, IntentType.DATA_QUERY)


# Singleton instance
_intent_detector = None

def get_intent_detector() -> IntentDetector:
    """Get the default intent detector instance."""
    global _intent_detector
    if _intent_detector is None:
        _intent_detector = IntentDetector()
    return _intent_detector
