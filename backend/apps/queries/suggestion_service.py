"""
Query Suggestion Service

Generates AI-powered query suggestions based on user history, patterns, and trends.
"""

import logging
from typing import List, Dict, Optional
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, F
from django.utils import timezone
from datetime import timedelta
from apps.queries.models import QueryLog, QuerySuggestion
from utils.openai_client import get_client, get_model_name

logger = logging.getLogger(__name__)
User = get_user_model()


class QuerySuggestionService:
    """Service for generating query suggestions."""
    
    def __init__(self, user: User):
        self.user = user
    
    def get_suggestions(
        self,
        current_query: str = '',
        platform: str = '',
        limit: int = 10
    ) -> List[Dict]:
        """
        Get query suggestions for the user.
        
        Args:
            current_query: Current partial query (for completion)
            platform: Filter by platform
            limit: Maximum number of suggestions
            
        Returns:
            List of suggestion dictionaries
        """
        suggestions = []
        
        # 1. Similar queries (based on current query)
        if current_query:
            similar = self._get_similar_queries(current_query, platform, limit=3)
            suggestions.extend(similar)
        
        # 2. Related queries (users who asked X also asked Y)
        if current_query:
            related = self._get_related_queries(current_query, platform, limit=3)
            suggestions.extend(related)
        
        # 3. Trending queries (popular in last 7 days)
        trending = self._get_trending_queries(platform, limit=3)
        suggestions.extend(trending)
        
        # 4. Popular queries (most successful queries)
        popular = self._get_popular_queries(platform, limit=3)
        suggestions.extend(popular)
        
        # 5. Query completion (AI-powered)
        if current_query and len(current_query) > 3:
            completions = self._get_query_completions(current_query, platform, limit=2)
            suggestions.extend(completions)
        
        # Remove duplicates and sort by confidence
        seen = set()
        unique_suggestions = []
        for sug in suggestions:
            key = (sug['query_text'], sug.get('platform', ''))
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(sug)
        
        # Sort by confidence score
        unique_suggestions.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)
        
        return unique_suggestions[:limit]
    
    def _get_similar_queries(self, query: str, platform: str = '', limit: int = 5) -> List[Dict]:
        """Get queries similar to the current one."""
        # Get user's query history
        user_queries = QueryLog.objects.filter(
            user=self.user,
            was_successful=True
        )
        
        if platform:
            user_queries = user_queries.filter(platform=platform)
        
        # Simple keyword matching for now (can be enhanced with embeddings)
        query_words = set(query.lower().split())
        similar_queries = []
        
        for qlog in user_queries[:100]:  # Check last 100 queries
            qtext = qlog.query_text.lower()
            qwords = set(qtext.split())
            
            # Calculate similarity (Jaccard similarity)
            intersection = len(query_words & qwords)
            union = len(query_words | qwords)
            similarity = intersection / union if union > 0 else 0
            
            if similarity > 0.3:  # Threshold
                similar_queries.append({
                    'query_text': qlog.query_text,
                    'platform': qlog.platform,
                    'suggestion_type': 'similar',
                    'confidence_score': similarity,
                    'source_query_id': qlog.id
                })
        
        # Sort by similarity
        similar_queries.sort(key=lambda x: x['confidence_score'], reverse=True)
        return similar_queries[:limit]
    
    def _get_related_queries(self, query: str, platform: str = '', limit: int = 5) -> List[Dict]:
        """Get queries that users who asked this also asked."""
        # Find queries that appeared in the same session or around the same time
        # as the current query pattern
        
        # Get queries from users who asked similar things
        user_queries = QueryLog.objects.filter(
            user=self.user,
            was_successful=True
        )
        
        if platform:
            user_queries = user_queries.filter(platform=platform)
        
        # Find queries that appeared within 1 hour of queries matching current pattern
        query_words = set(query.lower().split())
        related = []
        
        # Get recent successful queries
        recent_queries = user_queries.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        )[:200]
        
        # Group by time windows and find co-occurring queries
        query_groups = {}
        for qlog in recent_queries:
            time_window = qlog.created_at.replace(minute=0, second=0, microsecond=0)
            if time_window not in query_groups:
                query_groups[time_window] = []
            query_groups[time_window].append(qlog)
        
        # Find queries that co-occurred with similar queries
        for time_window, queries in query_groups.items():
            if len(queries) > 1:
                # Check if any query matches current pattern
                has_match = any(
                    len(set(q.query_text.lower().split()) & query_words) > 0
                    for q in queries
                )
                
                if has_match:
                    # Add other queries from this time window
                    for qlog in queries:
                        qwords = set(qlog.query_text.lower().split())
                        if len(qwords & query_words) == 0:  # Different query
                            related.append({
                                'query_text': qlog.query_text,
                                'platform': qlog.platform,
                                'suggestion_type': 'related',
                                'confidence_score': 0.6,
                                'source_query_id': qlog.id
                            })
        
        return related[:limit]
    
    def _get_trending_queries(self, platform: str = '', limit: int = 5) -> List[Dict]:
        """Get trending queries (popular in last 7 days)."""
        trending_period = timezone.now() - timedelta(days=7)
        
        trending = QueryLog.objects.filter(
            created_at__gte=trending_period,
            was_successful=True
        )
        
        if platform:
            trending = trending.filter(platform=platform)
        
        # Group by query text and count
        query_counts = trending.values('query_text', 'platform').annotate(
            count=Count('id'),
            avg_time=Count('processing_time_ms')
        ).order_by('-count')[:limit]
        
        suggestions = []
        max_count = query_counts[0]['count'] if query_counts else 1
        
        for item in query_counts:
            # Normalize confidence (0.5 to 0.9 based on popularity)
            confidence = 0.5 + (item['count'] / max_count) * 0.4
            
            suggestions.append({
                'query_text': item['query_text'],
                'platform': item['platform'],
                'suggestion_type': 'trending',
                'confidence_score': confidence,
                'usage_count': item['count']
            })
        
        return suggestions
    
    def _get_popular_queries(self, platform: str = '', limit: int = 5) -> List[Dict]:
        """Get most popular successful queries."""
        popular = QueryLog.objects.filter(
            user=self.user,
            was_successful=True
        )
        
        if platform:
            popular = popular.filter(platform=platform)
        
        # Get most frequently used queries
        query_counts = popular.values('query_text', 'platform').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]
        
        suggestions = []
        max_count = query_counts[0]['count'] if query_counts else 1
        
        for item in query_counts:
            # Normalize confidence (0.6 to 1.0)
            confidence = 0.6 + (item['count'] / max_count) * 0.4
            
            suggestions.append({
                'query_text': item['query_text'],
                'platform': item['platform'],
                'suggestion_type': 'popular',
                'confidence_score': confidence,
                'usage_count': item['count']
            })
        
        return suggestions
    
    def _get_query_completions(self, partial_query: str, platform: str = '', limit: int = 3) -> List[Dict]:
        """Get AI-powered query completions."""
        try:
            client = get_client()
            
            # Get user's query history for context
            recent_queries = QueryLog.objects.filter(
                user=self.user,
                was_successful=True
            ).order_by('-created_at')[:10]
            
            context_queries = [q.query_text for q in recent_queries]
            
            prompt = f"""Based on the user's query history and the partial query, suggest 3 complete query completions.

User's recent successful queries:
{chr(10).join(f"- {q}" for q in context_queries[:5])}

Partial query: "{partial_query}"

Suggest 3 natural completions that:
1. Complete the thought naturally
2. Are similar to queries the user has asked before
3. Are actionable and specific
4. Match the user's query style

Return only the completions, one per line, without numbering or bullets."""

            response = client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that suggests query completions based on user history."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            completions_text = response.choices[0].message.content.strip()
            completions = [line.strip() for line in completions_text.split('\n') if line.strip()][:limit]
            
            suggestions = []
            for completion in completions:
                # Remove numbering/bullets if present
                completion = completion.lstrip('1234567890.- ').strip()
                if completion:
                    suggestions.append({
                        'query_text': completion,
                        'platform': platform,
                        'suggestion_type': 'completion',
                        'confidence_score': 0.7
                    })
            
            return suggestions
            
        except Exception as e:
            logger.warning(f"Failed to generate query completions: {e}")
            return []
    
    def track_suggestion_shown(self, suggestion: Dict):
        """Track when a suggestion is shown to the user."""
        try:
            suggestion_obj, created = QuerySuggestion.objects.get_or_create(
                user=self.user,
                query_text=suggestion['query_text'],
                platform=suggestion.get('platform', ''),
                suggestion_type=suggestion.get('suggestion_type', 'similar'),
                defaults={
                    'confidence_score': suggestion.get('confidence_score', 0.5),
                    'source_query_id': suggestion.get('source_query_id')
                }
            )
            
            suggestion_obj.shown_count += 1
            suggestion_obj.last_shown_at = timezone.now()
            suggestion_obj.save()
        except Exception as e:
            logger.warning(f"Failed to track suggestion: {e}")
    
    def track_suggestion_clicked(self, suggestion: Dict):
        """Track when a suggestion is clicked."""
        try:
            suggestion_obj = QuerySuggestion.objects.filter(
                user=self.user,
                query_text=suggestion['query_text']
            ).first()
            
            if suggestion_obj:
                suggestion_obj.clicked_count += 1
                suggestion_obj.save()
        except Exception as e:
            logger.warning(f"Failed to track suggestion click: {e}")
